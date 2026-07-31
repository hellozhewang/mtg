#!/usr/bin/env python3
"""Cache administration — an inspection window, not the cache itself.

    ./cache.py                       # stats for every cache
    ./cache.py --warm ../Bracket3    # pre-fetch every card in those decks
    ./cache.py --clear pages         # drop EDHREC pages, KEEP the cards
    ./cache.py --clear               # wipe everything

Administration only. To look a card up, use `find_cards.py --names "Sol Ring"` —
inspecting a card is a card question, not a cache one.

**The caching itself lives in `cardlib/db.py` and happens automatically.** Every
call through `find_cards.py`, `validate_deck.py`, `new_deck.py` and
`find_inspiration.py` already reads and writes it. Nothing here is required for
that to work; this file only exists to look at the result and to force a refetch.

Three caches share one SQLite file because their lifetimes differ:

    cards   CardStore    keyed by oracle_id, 30-day TTL   (Scryfall)
    pages   PageStore    keyed by URL, 24-hour TTL        (EDHREC payloads)
    images  ImageStore   keyed by URL, NEVER expires      (Scryfall image CDN)
    toolcalls ToolLogStore  append-only, never expires    (our own tools)

To read the tool log rather than clear it, use `toollog.py` — it has the query
and flush commands, and this file is for administration only.

Which is why `--clear` takes a target. Clearing everything to refresh one EDHREC
page throws away ~1000 cards that cost ~14 Scryfall round trips to rebuild — and
now also ~830 card images, which are most of the file and the slowest to refill.

Thin CLI over cardlib; holds no card logic of its own.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deckfile
import toollog
import workspace
from cardlib import CardQuery, ImageStore, PageStore, ToolLogStore


def main() -> int:
    toollog.record()
    ap = argparse.ArgumentParser(
        description="Inspect and clear the card, EDHREC page and image caches.")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--clear", nargs="?", const="all",
                    choices=["all", "cards", "pages", "images", "tools"],
                    metavar="WHAT",
                    help="wipe all|cards|pages|images|tools (default: all)")
    ap.add_argument("--warm", nargs="+", metavar="PATH", help="pre-fetch deck cards")
    args = ap.parse_args()

    db = workspace.cache_db()
    q = CardQuery(db_path=db)
    pages = PageStore(db)
    images = ImageStore(db)
    tools = ToolLogStore(db)

    if args.clear:
        if args.clear in ("all", "cards"):
            q.clear()
            print("cleared: cards + aliases")
        if args.clear in ("all", "pages"):
            pages.clear()
            print("cleared: EDHREC pages")
        if args.clear in ("all", "images"):
            images.clear()
            print("cleared: card images (build_site.py will refetch them)")
        if args.clear in ("all", "tools"):
            tools.clear()
            print("cleared: tool-invocation log")

    if args.warm:
        names = sorted({e.name
                        for f in deckfile.discover([Path(p) for p in args.warm])
                        for e in deckfile.parse(f).entries})
        print(f"warming {len(names)} unique cards...")
        _, missing = q.cards(names)
        print(q.counters())
        if missing:
            print(f"UNRESOLVED: {', '.join(missing)}")

    if args.stats or not any([args.clear, args.warm]):
        for k, v in {**q.stats(), **pages.stats(), **images.stats(), **tools.stats()}.items():
            print(f"{k:>22}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
