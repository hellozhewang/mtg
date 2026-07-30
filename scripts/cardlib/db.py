"""Layer 2 — SQLite persistence.

Pure storage. Never makes a network call; if something isn't cached it simply
says so and lets the layer above decide what to do.

Schema notes:
  * Cards are keyed by `oracle_id`, not name -- one card has many printings.
  * The name you *query* is not always the name Scryfall *returns*: ask for
    "Agadeem's Awakening" and you get "Agadeem's Awakening // Agadeem, the
    Undercrypt". The `aliases` table maps every known spelling -> oracle_id,
    including the front face, because decklists always use the front face.
    Getting this wrong silently drops every modal DFC from lookups.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

DEFAULT_TTL_DAYS = 30          # oracle text / legalities drift slowly
PAGE_TTL_HOURS = 24            # deck aggregates move over days, not minutes

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    oracle_id  TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    data       TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS aliases (
    query      TEXT PRIMARY KEY,
    oracle_id  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pages (
    url        TEXT PRIMARY KEY,
    body       TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS images (
    url        TEXT PRIMARY KEY,
    body       BLOB NOT NULL,
    fetched_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);
"""


def aliases_for(query: str, card: dict) -> set[str]:
    """Every spelling this card should be findable by, lowercased."""
    name = card["name"]
    return {query.lower(), name.lower(), name.split(" // ")[0].lower()}


class CardStore:
    def __init__(self, path: Path, ttl_days: int = DEFAULT_TTL_DAYS):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.ttl = ttl_days * 86400
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def get_many(self, names: list[str]) -> tuple[dict[str, dict], list[str]]:
        """Split `names` into cached-and-fresh vs needs-fetching."""
        hits: dict[str, dict] = {}
        misses: list[str] = []
        cutoff = time.time() - self.ttl
        for n in names:
            row = self.conn.execute(
                "SELECT c.data, c.fetched_at FROM aliases a "
                "JOIN cards c ON c.oracle_id = a.oracle_id WHERE a.query = ?",
                (n.lower(),),
            ).fetchone()
            if row and row["fetched_at"] >= cutoff:
                hits[n] = json.loads(row["data"])
            else:
                misses.append(n)
        return hits, misses

    def put(self, card: dict, query: str | None = None) -> None:
        oid = card.get("oracle_id") or card["id"]
        self.conn.execute(
            "INSERT INTO cards(oracle_id,name,data,fetched_at) VALUES(?,?,?,?) "
            "ON CONFLICT(oracle_id) DO UPDATE SET data=excluded.data, "
            "name=excluded.name, fetched_at=excluded.fetched_at",
            (oid, card["name"], json.dumps(card), time.time()),
        )
        for alias in aliases_for(query or card["name"], card):
            self.conn.execute(
                "INSERT OR REPLACE INTO aliases(query,oracle_id) VALUES(?,?)",
                (alias, oid),
            )

    def put_many(self, cards: list[dict]) -> int:
        n = 0
        for c in cards:
            if c.get("name"):
                self.put(c)
                n += 1
        self.conn.commit()
        return n

    def commit(self) -> None:
        self.conn.commit()

    def stats(self) -> dict:
        q = lambda sql: self.conn.execute(sql).fetchone()[0]
        oldest = q("SELECT MIN(fetched_at) FROM cards")
        return {
            "cards": q("SELECT COUNT(*) FROM cards"),
            "aliases": q("SELECT COUNT(*) FROM aliases"),
            "game_changers_cached":
                q("SELECT COUNT(*) FROM cards "
                  "WHERE json_extract(data,'$.game_changer')=1"),
            "oldest_days": round((time.time() - oldest) / 86400, 1) if oldest else None,
            "size_kb": round(self.path.stat().st_size / 1024, 1)
                       if self.path.exists() else 0,
        }

    def clear(self) -> None:
        """Cards and aliases only. The `pages` table belongs to PageStore — wiping
        it from here would throw away ~1000 cached cards to refresh one EDHREC
        page, which costs ~14 Scryfall round trips to rebuild."""
        self.conn.executescript("DELETE FROM cards; DELETE FROM aliases;")
        self.conn.commit()


class PageStore:
    """Raw JSON payload cache, keyed by URL. Same file, separate concern.

    Deliberately not folded into CardStore: a card object is keyed by oracle_id
    and stays valid for a month, whereas a fetched page is keyed by URL and goes
    stale in a day. Sharing one class would mean one TTL for both.

    This exists because EDHREC payloads are large — a commander page is ~90 KB
    and a full deck index is ~3.5 MB — while the numbers inside them move over
    days. Re-downloading megabytes for every question during one tuning session
    is both slow and rude to a free service.
    """

    def __init__(self, path: Path, ttl_hours: int = PAGE_TTL_HOURS):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.ttl = ttl_hours * 3600
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.hits = self.misses = 0

    def get(self, url: str) -> dict | None:
        row = self.conn.execute(
            "SELECT body, fetched_at FROM pages WHERE url = ?", (url,)).fetchone()
        if row is None or (time.time() - row["fetched_at"]) > self.ttl:
            self.misses += 1
            return None
        self.hits += 1
        return json.loads(row["body"])

    def put(self, url: str, payload: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO pages (url, body, fetched_at) VALUES (?,?,?)",
            (url, json.dumps(payload), time.time()))
        self.conn.commit()

    def stats(self) -> dict:
        q = lambda sql: self.conn.execute(sql).fetchone()[0]
        newest = q("SELECT MAX(fetched_at) FROM pages")
        return {
            "pages": q("SELECT COUNT(*) FROM pages"),
            "pages_kb": round((q("SELECT COALESCE(SUM(LENGTH(body)),0) FROM pages")
                               or 0) / 1024, 1),
            "pages_age_hours":
                round((time.time() - newest) / 3600, 1) if newest else None,
        }

    def clear(self) -> None:
        self.conn.executescript("DELETE FROM pages;")
        self.conn.commit()


class ImageStore:
    """Card image bytes, keyed by URL. The third concern in the same file.

    **No TTL, deliberately.** Every other cache here expires because the thing it
    holds drifts: oracle text gets errata'd, inclusion rates move. Image URLs do
    not drift — they are content-addressed, ending in a printing UUID plus a
    `?<version>` stamp that Scryfall changes when it replaces a scan. So a hit is
    correct forever, and a replaced scan arrives as a *different* URL via the
    refreshed card object rather than as stale bytes under the old one.

    Bytes, not paths: the cache has to survive `docs/` being deleted and rebuilt,
    which is the whole point of it. A rebuild from an empty output directory
    should cost zero downloads, and it does.
    """

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.hits = self.misses = 0

    def get(self, url: str) -> bytes | None:
        row = self.conn.execute(
            "SELECT body FROM images WHERE url = ?", (url,)).fetchone()
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        return bytes(row["body"])

    def put(self, url: str, body: bytes) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO images (url, body, fetched_at) VALUES (?,?,?)",
            (url, sqlite3.Binary(body), time.time()))

    def commit(self) -> None:
        self.conn.commit()

    def stats(self) -> dict:
        q = lambda sql: self.conn.execute(sql).fetchone()[0]
        return {
            "images": q("SELECT COUNT(*) FROM images"),
            "images_mb": round((q("SELECT COALESCE(SUM(LENGTH(body)),0) FROM images")
                                or 0) / 1048576, 1),
        }

    def clear(self) -> None:
        self.conn.executescript("DELETE FROM images;")
        self.conn.commit()
        self.conn.execute("VACUUM")          # image blobs are the bulk of the file
