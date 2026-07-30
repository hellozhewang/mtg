"""Card and deck data access, split by concern.

    api.py     -> Scryfall HTTP only.     Knows nothing about storage.
    db.py      -> SQLite storage only.    Knows nothing about the network.
    query.py   -> orchestration.          The only module aware of both.
    edhrec.py  -> EDHREC HTTP only.       A sibling of api.py, not a layer above.

For card data, business logic imports CardQuery and nothing else:

    from cardlib import CardQuery
    q = CardQuery()
    cards, missing = q.cards(["Sol Ring", "Rhystic Study"])
    hits, total, banked = q.search("t:enchantment mv<=3 id<=wub")

EDHREC answers a different question — "what do other people play with this
commander" — so it gets its own orchestrator rather than living behind CardQuery:

    from cardlib import EdhrecQuery
    e = EdhrecQuery(db_path)
    name, cards = e.average_deck("Sythis, Harvest's Hand")   # starting point
    rows = e.commander_cards("Sythis, Harvest's Hand")       # inclusion + synergy

Both orchestrators share one SQLite file but separate tables and TTLs: card
objects live for 30 days, fetched pages for 24 hours. See PageStore for why.
"""
from .api import ScryfallAPI, ScryfallError
from .db import CardStore, PageStore
from .edhrec import EdhrecAPI, EdhrecError
from .query import DEFAULT_DB, CardQuery, EdhrecQuery

__all__ = ["CardQuery", "EdhrecQuery", "CardStore", "PageStore",
           "ScryfallAPI", "ScryfallError", "EdhrecAPI", "EdhrecError", "DEFAULT_DB"]
