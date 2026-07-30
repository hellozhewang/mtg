#!/usr/bin/env python3
"""Search Scryfall for cards that fit a deck's requirements.

    # strong cheap enchantments Zur can tutor, best-played first
    ./find_cards.py "t:enchantment mv<=3" --commander "Zur the Enchanter"

    # attack triggers in Mardu, excluding Game Changers
    ./find_cards.py "o:'whenever' o:'attacks'" --ci brw --no-gc

    # power-creep check: genuinely new elf cards
    ./find_cards.py "t:elf" --ci bg --since 2025

    # the current Game Changers list
    ./find_cards.py --gc-only

Defaults that encode this repo's rules (see README.md):
  * `legal:commander` is always added -- banned cards never show up.
  * Results are ordered by EDHREC rank, the best available proxy for "most
    powerful / most played", so the top of the list is what you actually want.
  * Game Changers are flagged [GC] straight off each card's `game_changer`
    field -- no separate is:gamechanger query needed.
  * Price is never shown or filtered on -- build for power, not budget.

This module is business logic only: query construction and presentation. All card
access goes through cardlib.CardQuery.
Full query syntax: https://scryfall.com/docs/syntax
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import toollog
import workspace
from cardlib import CardQuery


def build_query(args: argparse.Namespace, identity: str | None) -> str:
    parts = ["legal:commander"]
    if args.query:
        parts.append(f"({args.query})")
    if identity:
        parts.append(f"id<={identity.lower()}")
    if args.since:
        # `year>=` matches ANY printing, so a 2010 card reprinted last year would
        # slip through and pollute a power-creep search. `not:reprint` restricts
        # to first printings, i.e. cards that are genuinely new.
        parts.append(f"year>={args.since}")
        if not args.include_reprints:
            parts.append("not:reprint")
    if args.no_gc:
        parts.append("-is:gamechanger")
    if args.gc_only:
        parts.append("is:gamechanger")
    return " ".join(parts)


def commander_identity(name: str, q: CardQuery) -> str:
    card = q.card(name)
    if not card:
        sys.exit(f"commander not found: {name}")
    identity = "".join(card.get("color_identity") or [])
    print(f"# commander {card['name']} -> colour identity {identity or 'colourless'}\n",
          file=sys.stderr)
    return identity.lower() or "c"


def oneline(text: str, width: int) -> str:
    t = " | ".join((text or "").split("\n"))
    return t if len(t) <= width else t[: width - 1] + "…"


def show_full(card: dict) -> None:
    """Everything Scryfall knows that matters for deckbuilding.

    Used by --names, where you are asking about a specific card rather than
    browsing search hits, so verbosity is the point. `--json` remains the escape
    hatch for the raw object.

    Two things here are not cosmetic:
      * COMMANDER LEGALITY. --names does not apply the `legal:commander` filter
        that searches do, so a banned card (Mana Crypt, Golos) resolves happily.
        It is printed, and flagged loudly when it is not `legal`.
      * ALL card faces. The compact renderer shows only the front face, which
        silently hides the back of every modal DFC — exactly the cards whose back
        face decides whether they count as a land.
    """
    p = print
    gc = "  [GAME CHANGER]" if card.get("game_changer") else ""
    p(f"{card.get('name', '?')}  {card.get('mana_cost') or '—'}"
      f"  mv={card.get('cmc')}{gc}")
    p(f"    type       {card.get('type_line', '')}")

    if card.get("power") is not None:
        p(f"    p/t        {card.get('power')}/{card.get('toughness')}")
    for field, label in (("loyalty", "loyalty"), ("defense", "defense")):
        if card.get(field) is not None:
            p(f"    {label:<10} {card[field]}")

    ident = "".join(card.get("color_identity") or []) or "C"
    colors = "".join(card.get("colors") or []) or "C"
    p(f"    identity   {ident}" + (f"   colors {colors}" if colors != ident else ""))
    if card.get("produced_mana"):
        p(f"    produces   {''.join(card['produced_mana'])}")
    if card.get("keywords"):
        p(f"    keywords   {', '.join(card['keywords'])}")

    # Legality: the whole reason to print this is that --names skips the filter.
    legal = (card.get("legalities") or {}).get("commander", "unknown")
    flag = "" if legal == "legal" else "   <-- NOT LEGAL IN COMMANDER"
    p(f"    commander  {legal}{flag}")
    if card.get("reserved"):
        p("    reserved   yes (Reserved List)")

    rank = card.get("edhrec_rank")
    p(f"    edhrec     {f'#{rank}' if rank else '—'}")
    # "printing", NOT "first printed": released_at belongs to whichever printing
    # happens to be cached, so Sol Ring reports 2026 off a Marvel Commander
    # reprint despite being from 1993. Use `--since` (which adds not:reprint) to
    # ask about original print dates.
    p(f"    printing   {(card.get('released_at') or '????')[:4]}"
      f"   {card.get('rarity', '')} in {card.get('set_name', '')}"
      f"{'   (a reprint)' if card.get('reprint') else ''}")
    if card.get("layout") and card["layout"] != "normal":
        p(f"    layout     {card['layout']}")

    faces = card.get("card_faces") or []
    if faces:
        for face in faces:                       # never hide a DFC's back face
            p(f"    -- {face.get('name','?')}  {face.get('mana_cost') or ''}"
              f"  {face.get('type_line','')}")
            for line in (face.get("oracle_text") or "").splitlines():
                p(f"       {line}")
    else:
        for line in (card.get("oracle_text") or "(no oracle text)").splitlines():
            p(f"    {line}")

    related = [x["name"] for x in card.get("all_parts") or []
               if x.get("name") != card.get("name")]
    if related:
        p(f"    related    {', '.join(related)}")
    p()


def show(card: dict, full_text: bool) -> None:
    gc = "  [GC]" if card.get("game_changer") else ""
    year = (card.get("released_at") or "????")[:4]
    cost = card.get("mana_cost") or ("—" if "Land" in card.get("type_line", "") else "")
    rank = card.get("edhrec_rank")
    print(f"{card['name']}  {cost}  [{year}]  edhrec {f'#{rank}' if rank else '—'}{gc}")
    print(f"    {card.get('type_line', '')}")
    body = card.get("oracle_text") or ""
    if not body and card.get("card_faces"):
        body = card["card_faces"][0].get("oracle_text", "")
    if body:
        print(f"    {body if full_text else oneline(body, 110)}")
    print()


def main() -> int:
    toollog.record()
    ap = argparse.ArgumentParser(
        description="Search Scryfall for deck-building candidates.",
        epilog="Query syntax: https://scryfall.com/docs/syntax")
    ap.add_argument("query", nargs="?", default="", help="Scryfall query fragment")
    # Lookup-by-name is a different operation from search: exact names, no
    # ranking, cache-first rather than always-live. It lives here rather than in
    # cache.py because "tell me about these cards" is a card question, not cache
    # administration — and because its absence is why an agent hand-wrote
    # sqlite3 queries against cards.db instead of using the toolchain.
    ap.add_argument("--names", nargs="+", metavar="NAME",
                    help="look up exact card names instead of searching "
                         "(bulk, cache-first; pair with --text for oracle text)")
    ap.add_argument("--ci", help="colour identity, e.g. wub (adds id<=wub)")
    ap.add_argument("--commander", help="derive --ci from this commander's identity")
    ap.add_argument("--since", type=int, metavar="YEAR",
                    help="cards FIRST PRINTED from YEAR onward (power-creep check)")
    ap.add_argument("--include-reprints", action="store_true",
                    help="with --since, also match reprints of older cards")
    ap.add_argument("--no-gc", action="store_true", help="exclude Game Changers")
    ap.add_argument("--gc-only", action="store_true", help="only Game Changers")
    # All three spellings accepted on purpose: find_inspiration.py uses --limit,
    # and an agent that learns one tool's flag will try it on the other. Costing
    # a failed call and a retry over a synonym is a self-inflicted wound.
    ap.add_argument("-n", "--max", "--limit", type=int, default=25,
                    dest="max", help="max results (default 25)")
    ap.add_argument("--order", default="edhrec",
                    help="edhrec|cmc|released|name (default: edhrec)")
    ap.add_argument("--text", action="store_true", help="show full oracle text")
    ap.add_argument("--json", action="store_true", help="raw JSON out")
    args = ap.parse_args()

    q = CardQuery(db_path=workspace.cache_db())

    if args.names:
        # One bulk resolve: chunked at 75 per POST by api.py and cache-first, so
        # a 20-card lookup is usually zero API calls.
        found, missing = q.cards(args.names)
        if args.json:
            print(json.dumps([found[n] for n in args.names if n in found], indent=2))
            return 0
        for name in args.names:
            if name in found:
                show_full(found[name])
            else:
                print(f"not found: {name}\n")
        print(f"# {q.counters()}")
        return 1 if missing else 0

    identity = args.ci or (commander_identity(args.commander, q) if args.commander else None)
    query = build_query(args, identity)

    cards, total, banked = q.search(query, order=args.order, limit=args.max)

    if args.json:
        print(json.dumps(cards, indent=2))
        return 0

    print(f"# query: {query}")
    print(f"# {total} match{'' if total == 1 else 'es'}, showing {len(cards)}"
          f" (ordered by {args.order})")
    print(f"# {banked} card{'' if banked == 1 else 's'} cached\n")
    if not cards:
        print("no results — loosen the query or check the syntax")
        return 0
    for c in cards:
        show(c, args.text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
