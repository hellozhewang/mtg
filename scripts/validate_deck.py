#!/usr/bin/env python3
"""Validate decklists against Commander rules and this repo's bracket conventions.

    ./validate_deck.py                       # every .txt under the deck root
    ./validate_deck.py ../Bracket3           # one folder
    ./validate_deck.py ../Bracket3/Zur*.txt  # specific files
    ./validate_deck.py --max-gc 0 ../Bracket1
    ./validate_deck.py --no-cache            # bypass SQLite, always hit the API

Checks (all must pass, see README.md):
  1. exactly 100 cards including the commander
  2. every name resolves on Scryfall  -- catches typos that would fail import
  3. every card is inside the commander's colour identity
  4. Game Changer count within the bracket cap
  5. singleton -- no duplicate non-basic entries, no repeated lines

This module is business logic only: decklist parsing lives in deckfile.py and all
card data access goes through cardlib.CardQuery.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deckfile
import toollog
import workspace
from cardlib import CardQuery

ROOT = workspace.deck_root()


def gc_cap(path: Path, override: int | None) -> int | None:
    """Bracket cap inferred from the folder name; None means uncapped."""
    if override is not None:
        return override
    folder = path.parent.name.lower()
    if folder.startswith("bracket"):
        tier = folder.replace("bracket", "").strip()
        if tier.startswith(("4", "5")):
            return None
    return 3


def land_counts(deck: deckfile.Deck, cards: dict[str, dict]) -> tuple[int, int]:
    """(true lands, modal-DFC lands).

    A modal DFC like Malakir Rebirth is `Instant // Land` -- playable as a tapped
    land but not a mana source you can plan around, so it is counted separately
    rather than inflating the land count.
    """
    lands = flex = 0
    for e in deck.entries:
        type_line = cards.get(e.name, {}).get("type_line", "")
        if "Land" in type_line.split(" // ")[0]:
            lands += e.count
        elif "Land" in type_line:
            flex += e.count
    return lands, flex


def check(deck: deckfile.Deck, cards: dict[str, dict], missing: list[str],
          cap: int | None) -> tuple[list[str], set[str], list[str]]:
    """Return (problems, colour_identity, game_changers)."""
    cmd = cards.get(deck.commander)
    identity = set(cmd.get("color_identity", [])) if cmd else set()

    off_colour = [(n, c) for n, c in cards.items()
                  if set(c.get("color_identity", [])) - identity]
    gcs = [n for n in deck.names if cards.get(n, {}).get("game_changer")]

    problems: list[str] = []
    if deck.total != 100:
        problems.append(f"card count is {deck.total}, expected 100")
    if deck.bad_lines:
        problems.append(f"unparseable lines: {deck.bad_lines}")
    if missing:
        problems.append(f"unresolved names: {', '.join(missing)}")
    if off_colour:
        problems.append("off-colour: " + ", ".join(
            f"{n}[{''.join(c['color_identity'])}]" for n, c in off_colour))
    if dupes := deck.duplicates():
        problems.append("illegal duplicates: " +
                        ", ".join(f"{e.count}x {e.name}" for e in dupes))
    if repeats := deck.repeated_lines():
        problems.append(f"repeated lines: {', '.join(repeats)}")
    if cap is not None and len(gcs) > cap:
        problems.append(f"{len(gcs)} Game Changers exceeds cap of {cap}")
    return problems, identity, gcs


def report(deck: deckfile.Deck, cards: dict[str, dict], problems: list[str],
           identity: set[str], gcs: list[str], cap: int | None) -> bool:
    lands, flex = land_counts(deck, cards)
    nonland = [c for c in cards.values()
               if "Land" not in c.get("type_line", "").split(" // ")[0]]
    avg = sum(c.get("cmc", 0) for c in nonland) / len(nonland) if nonland else 0

    try:
        label = deck.path.resolve().relative_to(ROOT)
    except ValueError:
        label = deck.path

    ok = not problems
    print(f"{'PASS' if ok else 'FAIL'}  {label}")
    print(f"      {deck.commander}  |  identity {''.join(sorted(identity)) or 'colourless'}"
          f"  |  {deck.total} cards  |  {lands} lands"
          f"{f' (+{flex} MDFC)' if flex else ''}  |  avg MV {avg:.2f}")
    print(f"      Game Changers {len(gcs)}"
          f"{'/' + str(cap) if cap is not None else ' (uncapped)'}"
          f"{': ' + ', '.join(gcs) if gcs else ''}")
    for p in problems:
        print(f"      !! {p}")
    print()
    return ok


def main() -> int:
    toollog.record()
    ap = argparse.ArgumentParser(description="Validate Commander decklists.")
    ap.add_argument("paths", nargs="*", help="files or folders (default: deck root)")
    ap.add_argument("--max-gc", type=int, help="override the Game Changer cap")
    ap.add_argument("--no-cache", action="store_true",
                    help="ignore the SQLite cache and re-fetch everything")
    args = ap.parse_args()

    targets = deckfile.discover([Path(p) for p in (args.paths or [ROOT])])
    if not targets:
        sys.exit("no .txt decklists found")

    q = CardQuery(db_path=workspace.cache_db(),
                  ttl_days=0 if args.no_cache else 30)
    results = []
    for path in targets:
        deck = deckfile.parse(path)
        cards, missing = q.cards(deck.names)
        cap = gc_cap(path, args.max_gc)
        problems, identity, gcs = check(deck, cards, missing, cap)
        results.append(report(deck, cards, problems, identity, gcs, cap))

    passed = sum(results)
    print(f"{passed}/{len(results)} decks pass   [{q.counters()}]")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
