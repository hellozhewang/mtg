"""Layer 3 — orchestration.

The ONLY module that knows about both the cache and the network. Business logic
(find_cards, validate_deck) talks to this and nothing else, so it never has to
think about HTTP status codes, chunk limits, TTLs or alias tables.

Policy decisions live here, not in the layers below:

  * Card lookups are cache-first. Misses are fetched in bulk and written back.
  * Searches always go live. Card *data* is stable, but which cards *match* a
    query changes with every set release -- and the deck rules say favour new
    printings, so a cached search would hide exactly what you are looking for.
    Search results are still banked, because they are complete card objects.
"""
from __future__ import annotations

import os
from pathlib import Path

from .api import ScryfallAPI, ScryfallError          # noqa: F401  (re-exported)
from .db import DEFAULT_TTL_DAYS, PAGE_TTL_HOURS, CardStore, PageStore
from .edhrec import EdhrecAPI, EdhrecError           # noqa: F401  (re-exported)

# Fallback only. Business logic passes an explicit path from workspace.cache_db(),
# because scripts/ lives outside the workspace and must not infer it from __file__.
DEFAULT_DB = Path(
    os.environ.get("MTG_CACHE") or Path.home() / ".cache" / "mtg-cards" / "cards.db"
).expanduser()


class CardQuery:
    """Cache-aware card access. The single entry point for business logic."""

    def __init__(self, db_path: Path = DEFAULT_DB,
                 ttl_days: int = DEFAULT_TTL_DAYS,
                 store: CardStore | None = None,
                 api: ScryfallAPI | None = None):
        self.store = store or CardStore(db_path, ttl_days)
        self.api = api or ScryfallAPI()
        self.hits = self.misses = 0

    # ---------- reads ----------

    def cards(self, names: list[str]) -> tuple[dict[str, dict], list[str]]:
        """Resolve names to cards. Returns ({queried_name: card}, unresolved)."""
        found, todo = self.store.get_many(names)
        self.hits += len(found)
        self.misses += len(todo)
        if not todo:
            return found, []

        fetched, _ = self.api.collection(todo)
        # Scryfall echoes canonical names, which differ from the front-face names
        # decklists use, so match on both rather than assuming positional order.
        by_name: dict[str, dict] = {}
        for c in fetched:
            by_name[c["name"].lower()] = c
            by_name.setdefault(c["name"].split(" // ")[0].lower(), c)

        for n in todo:
            card = by_name.get(n.lower())
            if card:
                found[n] = card
                self.store.put(card, query=n)
        self.store.commit()
        return found, [n for n in todo if n not in found]

    def card(self, name: str) -> dict | None:
        found, _ = self.cards([name])
        return found.get(name)

    def search(self, query: str, order: str = "edhrec",
               limit: int | None = None) -> tuple[list[dict], int, int]:
        """Live search. Returns (cards, total_matches, cards_banked)."""
        cards, total = self.api.search(query, order=order, limit=limit)
        banked = self.store.put_many(cards)
        return cards, total, banked

    # ---------- admin passthroughs ----------

    def stats(self) -> dict:
        return self.store.stats()

    def clear(self) -> None:
        self.store.clear()

    @property
    def api_calls(self) -> int:
        return self.api.calls

    def counters(self) -> str:
        return (f"cache {self.hits} hit / {self.misses} miss, "
                f"{self.api_calls} API calls")


class EdhrecQuery:
    """Cache-aware EDHREC access. The other module that knows about both sides.

    Unlike Scryfall *searches*, which are always live, EDHREC aggregates ARE
    cached — with a much shorter TTL. The reasoning differs because the payloads
    do:

      * A commander page is ~90 KB and a deck index ~3.5 MB, versus a few KB for
        a card. Re-fetching per question during one tuning session is expensive
        for us and rude to a free service with no API key.
      * Inclusion rates move as decks get uploaded, i.e. over days. A 24-hour TTL
        cannot hide a trend that takes weeks to appear, so nothing is lost.

    That is why this is a PageStore with hours, not the CardStore with days.
    """

    def __init__(self, db_path: Path = DEFAULT_DB,
                 ttl_hours: int = PAGE_TTL_HOURS,
                 store: PageStore | None = None,
                 api: EdhrecAPI | None = None):
        self.store = store or PageStore(db_path, ttl_hours)
        self.api = api or EdhrecAPI()

    def _page(self, url: str) -> dict:
        payload = self.store.get(url)
        if payload is None:
            payload = self.api.get(url)
            self.store.put(url, payload)
        return payload

    def average_deck(self, commander: str,
                     flavour: str = "expensive") -> tuple[str, dict[str, int]]:
        """A starting-point decklist. Short of 100 — pad basics before writing."""
        return self.api.parse_average_deck(
            self._page(self.api.url_average_deck(commander, flavour)))

    def commander_cards(self, commander: str) -> list[dict]:
        """Cards EDHREC associates with a commander, with inclusion and synergy."""
        return self.api.parse_commander_cards(
            self._page(self.api.url_commander(commander)))

    def deck_index(self, commander: str) -> list[dict]:
        """Metadata for every uploaded deck: bracket, price, salt, urlhash."""
        return self.api.parse_deck_index(
            self._page(self.api.url_deck_index(commander)))

    def deck(self, urlhash: str) -> dict:
        """One real uploaded deck, as ready "1 Card Name" lines."""
        return self._page(self.api.url_deck(urlhash))

    def counters(self) -> str:
        return (f"pages {self.store.hits} hit / {self.store.misses} miss, "
                f"{self.api.calls} EDHREC calls")
