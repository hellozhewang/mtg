#!/usr/bin/env python3
"""Seed a decklist from EDHREC's aggregate deck for a commander.

    ./scripts/new_deck.py "Sythis, Harvest's Hand"                    # preview
    ./scripts/new_deck.py "Sythis, Harvest's Hand" -o public/Bracket3/Sythis-Enchantress.txt
    ./scripts/new_deck.py "Krenko, Mob Boss" --flavour average        # budget-weighted
    ./scripts/new_deck.py "Lord Windgrace" --lands 40                 # force a land count

This is a STARTING POINT, not a finished deck. What it gives you is the consensus
shell so you are not typing 99 lines from memory; the tuning is the actual work.

Two things to know before trusting the output.

**It defaults to the `expensive` cut, on purpose.** EDHREC's plain average is
dragged down by what players can afford, and price is not a constraint here
(README rule 3), so the expensive cut is strictly closer
to what this repo wants — it is where Chrome Mox, Lotus Petal, the fetch suite and
the original duals live. Pass `--flavour average` if you want the popular build
instead.

**It regresses to the mean by construction.** The aggregate is a casual average, so
it under-weights new printings (a card needs months of uploads to rank) and it will
never suggest the unpopular-but-strong pick. It is a floor to build up from, not a
target to hit. Run `find_inspiration.py --new` afterwards for the power-creep view.

EDHREC omits basic lands from its averages, so the fetched list lands 79-99 cards
short of 100. The shortfall is padded with basics in the commander's colours,
split as evenly as possible. That split is a guess — fix it against the real curve.
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

DECK_SIZE = 100
BASIC_FOR = {"W": "Plains", "U": "Island", "B": "Swamp",
             "R": "Mountain", "G": "Forest"}


def pad_basics(identity: list[str], shortfall: int) -> dict[str, int]:
    """Split `shortfall` basics across the commander's colours, evenly."""
    if shortfall <= 0:
        return {}
    basics = [BASIC_FOR[c] for c in identity if c in BASIC_FOR]
    if not basics:                                  # colourless commander
        return {"Wastes": shortfall}
    per, extra = divmod(shortfall, len(basics))
    # Remainder goes to the colours listed first — WUBRG order from Scryfall.
    return {b: per + (1 if i < extra else 0)
            for i, b in enumerate(basics) if per or i < extra}


def build(commander: str, flavour: str, lands: int | None,
          edhrec: EdhrecQuery, query: CardQuery) -> tuple[str, dict[str, int], list[str]]:
    """Returns (commander name, {card: count}, notes)."""
    notes: list[str] = []
    name, cards = edhrec.average_deck(commander, flavour=flavour)

    # Resolve the commander through Scryfall for its real name and colour
    # identity. EDHREC's name is usually right but Scryfall is the authority the
    # validator will use, and a mismatch here becomes a failed import later.
    card = query.card(name)
    if card is None:
        raise EdhrecError(f"EDHREC returned commander {name!r}, which Scryfall "
                          f"does not resolve — check the spelling")
    name = card["name"].split(" // ")[0]
    identity = card.get("color_identity") or []

    cards.pop(name, None)                            # never duplicate the commander
    for b in [c for c in cards if c in deckfile.BASICS]:
        del cards[b]                                 # basics are ours to decide

    # Counting lands needs type lines, so resolve the whole list. These all land
    # in the card cache, which makes the validate run straight after this free.
    found, unresolved = query.cards(list(cards))
    if unresolved:
        notes.append(f"{len(unresolved)} name(s) Scryfall could not resolve: "
                     + ", ".join(sorted(unresolved)[:5]))
    nonbasic_lands = sum(n for c, n in cards.items()
                         if "Land" in found.get(c, {}).get("type_line", ""))

    if lands is None:
        basics = DECK_SIZE - 1 - sum(cards.values())
        why = f"filling to {DECK_SIZE}"
    else:
        basics = lands - nonbasic_lands
        why = f"--lands {lands} minus {nonbasic_lands} nonbasic"
        if basics < 0:
            notes.append(f"EDHREC's list already has {nonbasic_lands} nonbasic "
                         f"lands, more than --lands {lands}. No basics added; "
                         f"cut {-basics} lands yourself.")
            basics = 0

    if basics > 0:
        added = pad_basics(identity, basics)
        for b, n in added.items():
            cards[b] = cards.get(b, 0) + n
        notes.append(f"added {basics} basics ({why}): "
                     + ", ".join(f"{n} {b}" for b, n in added.items()))

    total = 1 + sum(cards.values())
    notes.append(f"{nonbasic_lands} nonbasic + {basics} basic = "
                 f"{nonbasic_lands + basics} lands")
    if total != DECK_SIZE:
        verb = "cut" if total > DECK_SIZE else "add"
        notes.append(f"{total} cards — {verb} {abs(total - DECK_SIZE)} to reach "
                     f"{DECK_SIZE}")
    return name, cards, notes


def main() -> int:
    toollog.record()
    ap = argparse.ArgumentParser(
        description="Seed a decklist from EDHREC's aggregate deck.")
    ap.add_argument("commander")
    ap.add_argument("-o", "--out", type=Path,
                    help="write here (default: print to stdout)")
    ap.add_argument("--flavour", default="expensive",
                    choices=["average", "expensive", "budget", "cheap"],
                    help="EDHREC cut to seed from (default: expensive, see docstring)")
    ap.add_argument("--lands", type=int,
                    help="discard EDHREC's basics and pad to this total land count")
    ap.add_argument("--force", action="store_true", help="overwrite an existing file")
    args = ap.parse_args()

    query = CardQuery(db_path=workspace.cache_db())
    edhrec = EdhrecQuery(db_path=workspace.cache_db())
    try:
        name, cards, notes = build(args.commander, args.flavour, args.lands,
                                   edhrec, query)
    except EdhrecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    body = deckfile.render(name, cards)
    total = 1 + sum(cards.values())

    if args.out:
        if args.out.exists() and not args.force:
            print(f"error: {args.out} exists — pass --force to overwrite",
                  file=sys.stderr)
            return 1
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(body, encoding="utf-8")
        print(f"wrote {args.out} — {total} cards")
    else:
        print(body, end="")

    # Game Changers are the bracket's hard cap, so report them up front rather
    # than letting the user discover the overage in the validator.
    found, _ = query.cards(list(cards))
    gc = sorted(n for n, c in found.items() if c.get("game_changer"))
    print(f"\ncommander : {name}  ({args.flavour} cut)", file=sys.stderr)
    for n in notes:
        print(f"note      : {n}", file=sys.stderr)
    print(f"game chg  : {len(gc)}" + (f" — {', '.join(gc)}" if gc else ""),
          file=sys.stderr)
    if len(gc) > 3:
        print(f"            Bracket 3 allows 3. Cut {len(gc) - 3}.", file=sys.stderr)
    print(f"cache     : {query.counters()}; {edhrec.counters()}", file=sys.stderr)
    if args.out:
        print(f"next      : ./scripts/validate_deck.py {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
