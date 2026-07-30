#!/usr/bin/env python3
"""What do other pilots of this commander run that your deck does not?

A gap finder, not a power ranking — pass a decklist and see what EDHREC-listed
cards for that commander aren't in it yet. Run `--help` for the full flag
reference and worked examples; the summary:

    (default)   missing cards, ranked by how many pilots run them
    --new       same, but only EDHREC's "New Cards" section
    --trending  same, but ranked by rising adoption instead of raw popularity
    --mine      INVERTED — what your deck has that EDHREC doesn't mention at all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deckfile
import toollog
import workspace
from cardlib import CardQuery, EdhrecError, EdhrecQuery

EPILOG = """\
examples:
  find_inspiration.py public/Bracket3/Sythis-Enchantress.txt
      what am I missing, most-played first

  find_inspiration.py public/Bracket3/Zur-Voltron.txt --new
      same question, restricted to EDHREC's curated New Cards section

  find_inspiration.py public/Bracket3/Zur-Voltron.txt --trending
      same question, ranked by rising adoption instead of raw popularity —
      catches an old card suddenly getting hot, which --new cannot

  find_inspiration.py public/Bracket3/GrandArbiter-Prison.txt --mine
      the INVERTED question: what does my deck run that EDHREC never
      mentions for this commander at all? (cannot combine with --new/--trending
      — it is a different question, not a different sort of the same one)

  find_inspiration.py --commander "Queen Marchesa"
      browse a commander before any decklist exists

output columns:
  played    fraction of that commander's EDHREC decks running the card.
            THE ONE THAT MATTERS. 77% means almost every pilot runs it.
  trend     EDHREC's recent-adoption z-score for this card+commander pair.
            Positive = gaining traction lately, regardless of how old the
            card is. Independent of the New Cards section — a card can be
            old and trending, or new and flat.
  synergy   played, minus this card's play rate across EVERY commander that
            could legally run it. Measures how CHARACTERISTIC a card is of
            THIS commander, not how strong it is — Sol Ring scores ~0 with
            every commander because everyone plays it everywhere. High
            synergy + low played usually means a niche combo piece, not an
            oversight.

read it together: Jukai Naturalist at played=77%% synergy=+0.65 is a card
almost every Sythis pilot runs and almost nobody else does — a real
omission. A land at played=44%% synergy=+0.07 is just a colour fixer that
happens to be legal; the near-zero synergy says it has nothing to do with
this commander specifically.

three biases to hold in mind, because they all cut against README rule 2
(favour the newest, strongest card — not the popular one):
  - the aggregate is a casual average, so following it makes a deck more
    typical, not more powerful. treat this as a checklist of things you
    forgot, never as a target.
  - inclusion reflects what pilots can afford. this repo ignores price, so
    EDHREC systematically under-recommends Moat, the Tabernacle, and the
    original duals. it will never suggest them.
  - a card needs months of uploads to rank at all. --new and --trending are
    partial correctives, not a substitute for find_cards.py --since.
"""


def resolve_mode(args: argparse.ArgumentParser, ap: argparse.ArgumentParser) -> None:
    """Fail loudly on nonsensical flag combinations instead of silently
    producing a wrong table. --mine asks a different question from
    --new/--trending, not a filtered/sorted version of the same one — combining
    them used to silently narrow --mine's comparison set to just the New Cards
    section, making it claim most of your deck was "unlisted" when it wasn't."""
    if args.mine and (args.new or args.trending):
        ap.error("--mine is a different question from --new/--trending "
                 "(what YOU run that EDHREC never lists, vs. what EDHREC "
                 "lists that you're missing) — it doesn't combine with them")


def report(rows: list[dict], mine: set[str], gc: set[str],
          limit: int, sort_by: str) -> None:
    missing = [r for r in rows if r["name"].lower() not in mine]
    missing.sort(key=lambda r: -r[sort_by])
    if not missing:
        print("nothing EDHREC lists is missing from this deck.")
        return
    print(f"sorted by {sort_by}\n")
    print(f"{'card':<32}{'played':>7}{'trend':>8}{'synergy':>9}   section")
    for r in missing[:limit]:
        tag = "  [GC]" if r["name"] in gc else ""
        print(f"{r['name']:<32}{r['inclusion']:>6.0%}{r['trend']:>+8.2f}"
              f"{r['synergy']:>+9.2f}   {r['section']}{tag}")
    if len(missing) > limit:
        print(f"... {len(missing) - limit} more (raise --limit to see them)")


def main() -> int:
    toollog.record()
    ap = argparse.ArgumentParser(
        description="Show cards other pilots of a commander run that yours does not.",
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", nargs="?", type=Path,
                    help="decklist to compare (omit to just browse a commander)")
    ap.add_argument("--commander",
                    help="browse this commander without a decklist, or override "
                         "the one read from line 1 of the deck (e.g. to check a "
                         "partner/background instead)")
    ap.add_argument("--new", action="store_true",
                    help="restrict to EDHREC's New Cards section only "
                         "(recently printed, still building an inclusion "
                         "history for this commander)")
    ap.add_argument("--trending", action="store_true",
                    help="sort by rising adoption (EDHREC's trend score) "
                         "instead of raw play rate — catches an old card "
                         "suddenly gaining traction, which --new cannot")
    ap.add_argument("--mine", action="store_true",
                    help="INVERT the question: what does your deck run that "
                         "EDHREC does not list for this commander at all? "
                         "(cannot combine with --new/--trending)")
    # -n/--max are synonyms so this matches find_cards.py; see the note there.
    ap.add_argument("--limit", "-n", "--max", type=int, default=25, dest="limit",
                    help="rows to print (default: 25)")
    args = ap.parse_args()
    resolve_mode(args, ap)

    if not args.deck and not args.commander:
        ap.error("give a decklist, or --commander to browse without one")

    mine: set[str] = set()
    commander = args.commander
    if args.deck:
        deck = deckfile.parse(args.deck)
        mine = {e.name.lower() for e in deck.entries}
        commander = commander or deck.commander

    query = CardQuery(db_path=workspace.cache_db())
    edhrec = EdhrecQuery(db_path=workspace.cache_db())
    try:
        rows = edhrec.commander_cards(commander)
    except EdhrecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.new:
        rows = [r for r in rows if "new" in r["section"].lower()]
        if not rows:
            print(f"EDHREC lists no New Cards for {commander} right now.")
            return 0

    print(f"{commander} — EDHREC lists {len(rows)} cards"
          + (f", your deck runs {len(mine)} entries" if mine else ""))
    print()

    if args.mine:
        listed = {r["name"].lower() for r in rows}
        off = sorted(e.name for e in deck.entries
                     if e.name.lower() not in listed
                     and e.name not in deckfile.BASICS)
        print(f"{len(off)} cards in your deck that EDHREC does not list for this "
              f"commander:\n")
        for n in off:
            print(f"  {n}")
        print(f"\n{query.counters()}, {edhrec.counters()}", file=sys.stderr)
        return 0

    # Flag Game Changers so the bracket cap is visible before anything gets added.
    found, _ = query.cards([r["name"] for r in rows])
    gc = {n for n, c in found.items() if c.get("game_changer")}
    report(rows, mine, gc, args.limit, "trend" if args.trending else "inclusion")
    print(f"\n{query.counters()}, {edhrec.counters()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
