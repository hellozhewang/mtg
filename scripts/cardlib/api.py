"""Layer 1 — Scryfall HTTP client.

Pure network. Knows nothing about caching, SQLite, decks or brackets. Every
Scryfall quirk is contained here so no layer above has to care:

  * BOTH `User-Agent` and `Accept` headers are required or Scryfall returns 400.
  * `/cards/collection` accepts at most 75 identifiers per POST.
  * Paged endpoints return `has_more` + `next_page`; follow the URL verbatim.
  * A search with no matches is a 404, not an empty result set.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.scryfall.com"
HEADERS = {"User-Agent": "MtgDeckTuner/1.0", "Accept": "application/json"}
COLLECTION_LIMIT = 75          # hard cap imposed by Scryfall
POLITE_DELAY = 0.12            # seconds between requests


class ScryfallError(RuntimeError):
    pass


class ScryfallAPI:
    """Thin, stateless-ish wrapper. `calls` counts HTTP requests made."""

    def __init__(self, delay: float = POLITE_DELAY):
        self.delay = delay
        self.calls = 0

    # ---------- transport ----------

    def _request(self, url: str, data: bytes | None = None) -> dict:
        headers = dict(HEADERS)
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            url, data=data, headers=headers, method="POST" if data else "GET")
        self.calls += 1
        try:
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:                      # "no cards matched"
                return {"data": [], "total_cards": 0, "has_more": False}
            raise ScryfallError(f"HTTP {e.code}: {e.read().decode()[:300]}") from e
        finally:
            time.sleep(self.delay)

    def _get(self, path: str, params: dict) -> dict:
        return self._request(f"{BASE}{path}?{urllib.parse.urlencode(params)}")

    def _post(self, path: str, payload: dict) -> dict:
        return self._request(f"{BASE}{path}", json.dumps(payload).encode())

    # ---------- endpoints ----------

    def named(self, exact: str) -> dict | None:
        card = self._get("/cards/named", {"exact": exact})
        return card if card.get("name") else None

    def collection(self, names: list[str]) -> tuple[list[dict], list[str]]:
        """Resolve many names at once. Returns (cards, unresolved_names)."""
        found: list[dict] = []
        missing: list[str] = []
        for i in range(0, len(names), COLLECTION_LIMIT):
            chunk = names[i:i + COLLECTION_LIMIT]
            payload = {"identifiers": [{"name": n} for n in chunk]}
            r = self._post("/cards/collection", payload)
            found.extend(r.get("data", []))
            missing.extend(x.get("name", "?") for x in r.get("not_found", []))
        return found, missing

    def search(self, query: str, order: str = "edhrec",
               unique: str = "cards", limit: int | None = None) -> tuple[list[dict], int]:
        """Run a Scryfall query, following pagination up to `limit` results."""
        page = self._get("/cards/search",
                         {"q": query, "unique": unique, "order": order})
        total = page.get("total_cards", 0)
        out = list(page.get("data", []))
        while page.get("has_more") and (limit is None or len(out) < limit):
            page = self._request(page["next_page"])
            out.extend(page.get("data", []))
        return (out[:limit] if limit is not None else out), total
