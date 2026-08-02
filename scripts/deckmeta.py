"""Persistent metadata about deck files.

Unlike `.cache/cards.db`, this database is trusted provenance written by the bot
parent outside the Codex sandbox. It is intentionally small and separate: card
objects and images are disposable caches, while the Discord user who created a
deck must survive cache clears and must not be editable by the model whose work
is being attributed.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS deck_authors (
    deck               TEXT PRIMARY KEY,
    author             TEXT NOT NULL,
    attributed_at      REAL NOT NULL,
    file_created_at_ns INTEGER
);
"""


def created_paths(before: dict[str, int | None],
                  after: dict[str, int | None]) -> list[str]:
    """Paths newly present, including same-path files with a new birth time."""
    return sorted(
        deck for deck, timestamp in after.items()
        if deck not in before
        or (timestamp is not None and before[deck] is not None
            and timestamp != before[deck])
    )


class DeckAuthorStore:
    """SQLite-backed mapping of workspace-relative deck path to Discord user."""

    def __init__(self, path: Path, timeout: float = 10.0):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, timeout=timeout)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout = 10000")
        self.conn.executescript(SCHEMA)
        # Existing installations predate file birth timestamps. SQLite's
        # CREATE TABLE IF NOT EXISTS does not add columns, so migrate in place.
        columns = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(deck_authors)")
        }
        if "file_created_at_ns" not in columns:
            self.conn.execute(
                "ALTER TABLE deck_authors ADD COLUMN file_created_at_ns INTEGER"
            )
            self.conn.commit()

    def set(self, deck: str, author: str,
            file_created_at_ns: int | None = None) -> None:
        """Attribute `deck` to `author`, replacing stale data for that path."""
        deck = deck.strip()
        author = author.strip()
        if not deck:
            raise ValueError("deck path cannot be empty")
        if not author:
            raise ValueError("deck author cannot be empty")
        self.conn.execute(
            "INSERT INTO deck_authors"
            "(deck,author,attributed_at,file_created_at_ns) VALUES(?,?,?,?) "
            "ON CONFLICT(deck) DO UPDATE SET author=excluded.author, "
            "attributed_at=excluded.attributed_at, "
            "file_created_at_ns=excluded.file_created_at_ns",
            (deck, author, time.time(), file_created_at_ns),
        )
        self.conn.commit()

    def get(self, deck: str) -> str | None:
        row = self.conn.execute(
            "SELECT author FROM deck_authors WHERE deck = ?", (deck,)
        ).fetchone()
        return row["author"] if row else None

    def all(self) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT deck, author FROM deck_authors ORDER BY deck"
        ).fetchall()
        return {row["deck"]: row["author"] for row in rows}

    def timestamps(self) -> dict[str, int | None]:
        rows = self.conn.execute(
            "SELECT deck, file_created_at_ns FROM deck_authors ORDER BY deck"
        ).fetchall()
        return {row["deck"]: row["file_created_at_ns"] for row in rows}

    def sync(self, existing: dict[str, int | None], created: list[str],
             author: str) -> list[str]:
        """Apply one turn's creations and deletions in one transaction.

        Returns the removed paths in stable order for trusted-parent logging.
        The database models the live catalog, not deletion history: if a path is
        recreated later, the creation turn records its new author from scratch.

        `existing` maps every post-turn path to its filesystem birth timestamp.
        Timestamps are filled in for pre-migration rows without changing their
        authors, and are replaced alongside the author for newly created files.
        """
        author = author.strip()
        if not author:
            raise ValueError("deck author cannot be empty")
        if unknown := set(created) - set(existing):
            raise ValueError(f"created paths absent from filesystem: {sorted(unknown)}")

        missing = sorted(set(self.all()) - set(existing))
        now = time.time()
        with self.conn:
            if missing:
                self.conn.executemany(
                    "DELETE FROM deck_authors WHERE deck = ?",
                    ((deck,) for deck in missing),
                )
            for deck in created:
                self.conn.execute(
                    "INSERT INTO deck_authors"
                    "(deck,author,attributed_at,file_created_at_ns) VALUES(?,?,?,?) "
                    "ON CONFLICT(deck) DO UPDATE SET author=excluded.author, "
                    "attributed_at=excluded.attributed_at, "
                    "file_created_at_ns=excluded.file_created_at_ns",
                    (deck, author, now, existing[deck]),
                )
            # Populate timestamps on rows created before this column existed,
            # without changing their original author or attribution time.
            self.conn.executemany(
                "UPDATE deck_authors SET file_created_at_ns = ? "
                "WHERE deck = ? AND file_created_at_ns IS NULL",
                ((stamp, deck) for deck, stamp in existing.items()
                 if stamp is not None),
            )
        return missing

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> DeckAuthorStore:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
