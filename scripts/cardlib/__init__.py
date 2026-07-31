"""Card and deck data access, split by concern.

    api.py     -> Scryfall HTTP only.     Knows nothing about storage.
    db.py      -> SQLite storage only.    Knows nothing about the network.
    query.py   -> orchestration.          The only module aware of both.
    edhrec.py  -> EDHREC HTTP only.       A sibling of api.py, not a layer above.
    images.py  -> image CDN HTTP only.    Another sibling; different host, bytes not JSON.

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

Card pictures are a third question again — "what does it look like" — and the
site builder is the only caller, so they get their own orchestrator too:

    from cardlib import ImageQuery
    img = ImageQuery(db_path)
    body = img.get(card["image_uris"]["thumb"])               # bytes, or None

All three orchestrators share one SQLite file but separate tables and lifetimes:
card objects live for 30 days, fetched pages for 24 hours, and image bytes never
expire because their URLs are content-addressed. See PageStore and ImageStore.
"""
from .api import ScryfallAPI, ScryfallError
from .db import CardStore, ImageStore, PageStore
from .edhrec import EdhrecAPI, EdhrecError
from .images import ImageAPI, ImageError, local_name
from .query import DEFAULT_DB, CardQuery, EdhrecQuery, ImageQuery, SymbolQuery

__all__ = ["CardQuery", "EdhrecQuery", "ImageQuery", "SymbolQuery",
           "CardStore", "PageStore", "ImageStore",
           "ScryfallAPI", "ScryfallError", "EdhrecAPI", "EdhrecError",
           "ImageAPI", "ImageError", "local_name", "DEFAULT_DB"]
