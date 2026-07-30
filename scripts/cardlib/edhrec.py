"""Layer 1 — EDHREC HTTP client.

A sibling of `api.py`, not a layer above it: pure network, knows nothing about
caching, SQLite, Scryfall, decks or brackets. Where `api.py` answers "what is
this card", this answers "what do other people play with this commander".

This module never touches storage. It is split into three kinds of method so the
layer above can insert a cache without this one knowing:

    url_*     build the URL for a resource
    get       fetch and decode one URL
    parse_*   turn a payload into useful shapes

`EdhrecQuery` in query.py composes those with a PageStore. The convenience
methods here (`average_deck`, `commander_cards`, ...) are the uncached path, kept
for one-off use.

EDHREC quirks contained here so no layer above has to care:

  * Two different hosts. Aggregate pages live on `json.edhrec.com/pages/...`;
    individual decklists live on `edhrec.com/api/deckpreview/<hash>`. Asking
    json.edhrec.com for a deckpreview returns an S3 **403 AccessDenied**, not a
    404, which reads like an auth failure but is just the wrong host.
  * The average deck **omits basic lands entirely**, so it comes back at 79-99
    cards depending on the commander. Callers must pad to 100 themselves.
  * `deck.cards` is a dict of type section -> list of `[name, count]` pairs, and
    `deck.commander` is a *list* even for a single commander.
  * Slugs strip apostrophes, commas and periods before hyphenating, so
    "Sythis, Harvest's Hand" -> `sythis-harvests-hand`. Getting this wrong is a
    404 that looks like "no data for this commander".
  * No API key and no registration. A plain User-Agent is accepted.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

PAGES = "https://json.edhrec.com/pages"
API = "https://edhrec.com/api"
HEADERS = {"User-Agent": "MtgDeckTuner/1.0", "Accept": "application/json"}
POLITE_DELAY = 0.12

# Aggregate flavours. "expensive" matters for this repo: these decks are for
# power over budget (README rule 3), and the default
# average is dragged down by what people can actually afford. The expensive cut
# is where Chrome Mox, Lotus Petal, the fetch suite and Aura Shards live.
FLAVOURS = ("average", "expensive", "budget", "cheap")


class EdhrecError(RuntimeError):
    pass


def slug(name: str) -> str:
    """Commander name -> EDHREC URL slug. Front face only for DFCs."""
    n = name.split(" // ")[0].lower()
    n = n.replace("'", "").replace(",", "").replace(".", "")
    return re.sub(r"[^a-z0-9]+", "-", n).strip("-")


class EdhrecAPI:
    """Thin wrapper. `calls` counts HTTP requests made."""

    def __init__(self, delay: float = POLITE_DELAY):
        self.delay = delay
        self.calls = 0

    # ---------- transport ----------

    def get(self, url: str) -> dict:
        req = urllib.request.Request(url, headers=HEADERS)
        self.calls += 1
        try:
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                raise EdhrecError(
                    f"HTTP {e.code} for {url} — commander slug wrong, or no EDHREC "
                    f"data for it yet") from e
            raise EdhrecError(f"HTTP {e.code}: {url}") from e
        finally:
            time.sleep(self.delay)

    # ---------- URLs ----------

    @staticmethod
    def url_average_deck(commander: str, flavour: str = "expensive") -> str:
        if flavour not in FLAVOURS:
            raise ValueError(f"flavour must be one of {FLAVOURS}, got {flavour!r}")
        tail = "" if flavour == "average" else f"/{flavour}"
        return f"{PAGES}/average-decks/{slug(commander)}{tail}.json"

    @staticmethod
    def url_commander(commander: str) -> str:
        return f"{PAGES}/commanders/{slug(commander)}.json"

    @staticmethod
    def url_deck_index(commander: str) -> str:
        return f"{PAGES}/decks/{slug(commander)}.json"

    @staticmethod
    def url_deck(urlhash: str) -> str:
        # Different host on purpose: json.edhrec.com 403s on deckpreview.
        return f"{API}/deckpreview/{urlhash}"

    # ---------- parsers ----------

    @staticmethod
    def parse_average_deck(payload: dict) -> tuple[str, dict[str, int]]:
        """Returns (commander name, {card: count}).

        Short of 100 — EDHREC excludes basic lands from its averages. Pad before
        writing a decklist.
        """
        d = payload["deck"]
        name = d["commander"][0] if isinstance(d["commander"], list) else d["commander"]
        cards: dict[str, int] = {}
        for section in d["cards"].values():
            for card, count in section:
                cards[card] = cards.get(card, 0) + count
        return name, cards

    @staticmethod
    def parse_commander_cards(payload: dict) -> list[dict]:
        """Every card EDHREC associates with a commander, with its stats.

        Each row: name, section, num_decks, potential_decks, inclusion, synergy,
        trend. `inclusion` is the fraction of that commander's decks running the
        card. `synergy` is inclusion minus the card's rate across every deck that
        could legally play it — so it measures how *characteristic* the card is of
        this commander, NOT how strong it is. Sol Ring scores ~0 everywhere.
        """
        rows: list[dict] = []
        seen: set[str] = set()
        for cardlist in payload["container"]["json_dict"]["cardlists"]:
            for c in cardlist["cardviews"]:
                if c["name"].lower() in seen:
                    continue                    # a card can appear in several sections
                seen.add(c["name"].lower())
                nd = c.get("num_decks") or 0
                pd = c.get("potential_decks") or 0
                rows.append({
                    "name": c["name"],
                    "section": cardlist["header"],
                    "num_decks": nd,
                    "potential_decks": pd,
                    "inclusion": (nd / pd) if pd else 0.0,
                    "synergy": c.get("synergy") or 0.0,
                    "trend": c.get("trend_zscore") or 0.0,
                })
        return rows

    @staticmethod
    def parse_deck_index(payload: dict) -> list[dict]:
        """Every uploaded deck for a commander: bracket, price, salt, urlhash.

        `cards` is empty here — the index is metadata only. Fetch a urlhash via
        `url_deck` for the actual list.
        """
        return payload["table"]

    # ---------- uncached convenience ----------

    def average_deck(self, commander: str,
                     flavour: str = "expensive") -> tuple[str, dict[str, int]]:
        return self.parse_average_deck(
            self.get(self.url_average_deck(commander, flavour)))

    def commander_cards(self, commander: str) -> list[dict]:
        return self.parse_commander_cards(self.get(self.url_commander(commander)))

    def deck_index(self, commander: str) -> list[dict]:
        return self.parse_deck_index(self.get(self.url_deck_index(commander)))

    def deck(self, urlhash: str) -> dict:
        return self.get(self.url_deck(urlhash))
