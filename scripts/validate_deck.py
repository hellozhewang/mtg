#!/usr/bin/env python3
"""Validate decklists against Commander rules and this repo's bracket conventions.

    ./validate_deck.py                       # every .txt under the deck root
    ./validate_deck.py ../Bracket3           # one folder
    ./validate_deck.py ../Bracket3/Zur*.txt  # specific files
    ./validate_deck.py --max-gc 0 ../Bracket1
    ./validate_deck.py --no-cache            # bypass SQLite, always hit the API
    ./validate_deck.py --no-import           # skip the Tabletop Simulator importer
    ./validate_deck.py --recheck-import      # ask the importer about every card again

Checks (all must pass, see README.md):
  1. exactly 100 cards including the commander
  2. every name resolves on Scryfall  -- catches typos that would fail import
  3. every card is LEGAL in Commander -- catches the 83 banned cards
  3b. no NAMED mass land denial in Brackets 1-3 (see commander-brackets-and-rules.md)
  4. every card is inside the commander's colour identity
  5. Game Changer count within the bracket cap
  6. singleton, except Oracle text allowing unlimited copies; no repeated lines
  7. a pinned printing (`1 Sol Ring (SLD) 249`) exists and is that card
  8. Tabletop Simulator's deck importer loads the whole list, pins included --
     asked of the importer itself (ttsimport.py), once the deck passes 1-7. A
     card line that loaded is remembered for 30 days and not asked about again

This module is business logic only: decklist parsing lives in deckfile.py and all
card data access goes through cardlib.CardQuery.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import os

import deckfile
import toollog
import ttsimport
import workspace
from cardlib import CardQuery

ROOT = workspace.deck_root()
RULES = ROOT.parent / "commander-brackets-and-rules.md"


def denial_cards() -> set[str]:
    """Cards the rules file names as mass land denial, read from that file.

    Read rather than restated so the two cannot disagree, and because the wording
    across these cards is genuinely un-matchable by pattern: Winter Orb says
    "more than one LAND", Static Orb says "more than two PERMANENTS", Blood Moon
    says nothing about untapping at all. A regex that caught the first missed the
    second -- which is exactly how Static Orb reached a Bracket 3.5 deck.

    The file calls these "named examples", so this is a floor, not a ceiling. It
    catches the ones that actually turn up in EDHREC seeds.
    """
    try:
        text = RULES.read_text(encoding="utf-8")
    except OSError:
        return set()
    block = re.search(r"\*\*Caught by it\*\*.*?:\s*\n(.*?)(?:\n\n|\Z)",
                      text, re.S)
    if not block:
        return set()
    names = (n.replace("**", "").strip().rstrip(".")
             for n in block.group(1).split("·"))
    return {n for n in names if n}


def gc_cap(path: Path, override: int | None) -> int | None:
    """Bracket cap inferred from the folder name; None means uncapped."""
    if override is not None:
        return override
    folder = path.parent.name.lower()
    # An explicitly named house exception changes only the GC allowance.
    # Keep a finite cap so the existing mass-land-denial checks still apply.
    if folder == "bracket3.5+4gc":
        return 4
    if folder.startswith("bracket"):
        tier = folder.replace("bracket", "").strip()
        if tier.startswith(("4", "5")):
            return None
    return 3


def land_counts(deck: deckfile.Deck, cards: dict[str, dict]) -> tuple[int, int]:
    """(true lands, modal-DFC lands).

    A modal DFC like Malakir Rebirth is `Instant // Land` -- playable as a tapped
    land but not a mana source you can plan around, so it is counted separately
    rather than inflating the land count. Transforming cards such as Ojer Axonil
    cannot be played as lands from hand and are not included in that count.
    """
    lands = flex = 0
    for e in deck.entries:
        card = cards.get(e.name, {})
        type_line = card.get("type_line", "")
        if "Land" in type_line.split(" // ")[0]:
            lands += e.count
        elif card.get("layout") == "modal_dfc" and "Land" in type_line:
            flex += e.count
    return lands, flex


def average_mana_value(deck: deckfile.Deck, cards: dict[str, dict]) -> float:
    """Average nonland mana value, weighting every copy in the decklist."""
    total = count = 0
    for entry in deck.entries:
        card = cards.get(entry.name)
        if not card or "Land" in (card.get("type_line") or "").split(" // ")[0]:
            continue
        total += entry.count * (card.get("cmc") or 0)
        count += entry.count
    return total / count if count else 0.0


def allows_unlimited_copies(card: dict) -> bool:
    """Honor a card's own deck-construction exception, not a name allowlist."""
    name = card.get("name")
    return bool(name and f"A deck can have any number of cards named {name}."
                in (card.get("oracle_text") or ""))


def check(deck: deckfile.Deck, cards: dict[str, dict], missing: list[str],
          cap: int | None) -> tuple[list[str], set[str], list[str]]:
    """Return (problems, colour_identity, game_changers)."""
    cmd = cards.get(deck.commander)
    identity = set(cmd.get("color_identity", [])) if cmd else set()

    # Legality comes from each card's own `legalities.commander`, not a list
    # transcribed into this repo. Wizards updates the ban list a few times a year
    # and Scryfall reflects it the same day, so a hardcoded copy would be wrong
    # without anyone noticing. Anything not "legal" is reported with its status,
    # since `banned` and `restricted` mean different things.
    illegal = [(n, (c.get("legalities") or {}).get("commander", "unknown"))
               for n, c in cards.items()
               if (c.get("legalities") or {}).get("commander") != "legal"]

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
    if illegal:
        problems.append("NOT LEGAL in Commander: " + ", ".join(
            f"{n} [{why}]" for n, why in sorted(illegal)))
    # Brackets 4 and 5 allow mass land denial; a cap of None means we are in one.
    if cap is not None and (denial := denial_cards() & set(deck.names)):
        problems.append("mass land denial, banned below Bracket 4: "
                        + ", ".join(sorted(denial)))
    if off_colour:
        problems.append("off-colour: " + ", ".join(
            f"{n}[{''.join(c['color_identity'])}]" for n, c in off_colour))
    if dupes := [e for e in deck.duplicates()
                 if not allows_unlimited_copies(cards.get(e.name, {}))]:
        problems.append("illegal duplicates: " +
                        ", ".join(f"{e.count}x {e.name}" for e in dupes))
    if repeats := deck.repeated_lines():
        problems.append(f"repeated lines: {', '.join(repeats)}")
    if cap is not None and len(gcs) > cap:
        problems.append(f"{len(gcs)} Game Changers exceeds cap of {cap}")
    return problems, identity, gcs


def _oracle_ids(card: dict) -> set[str]:
    """A card's oracle id, or its faces' ids for the layouts that keep them there."""
    return ({card.get("oracle_id")} | {f.get("oracle_id")
                                        for f in card.get("card_faces") or []}) - {None}


def printing_problems(deck: deckfile.Deck, cards: dict[str, dict],
                      q: CardQuery) -> tuple[list[str], dict[str, str]]:
    """Check the printings a list pins, e.g. `1 Sol Ring (SLD) 249`.

    Returns (problems, {card name: Scryfall id of its pinned printing}). A pin is
    only cosmetic, but a wrong one fails silently in Tabletop Simulator: the
    importer loads some other art without a word. So a set and number that do not
    exist, or that belong to a different card, are errors here.
    """
    pinned = [(e.name, e.printing) for e in deck.entries if e.printing and e.name in cards]
    exact = [(name, p) for name, p in pinned if p.number]
    found = q.printings([(p.set, p.number) for _, p in exact]) if exact else {}
    unknown, wrong, ids = [], [], {}
    for name, p in exact:
        hit = found.get((p.set, p.number))
        if hit is None:
            unknown.append(f"{name} {p}")
        elif not _oracle_ids(cards[name]) & set(hit["oracle_ids"]):
            wrong.append(f"{name} {p} is {hit['name']}")
        else:
            ids[name] = hit["id"]
    for name, p in pinned:
        if p.number:
            continue
        # Set only: any printing of the card in that set will do. Straight to the
        # API, because a banked search result would replace the card's stored art.
        front = cards[name]["name"].split(" // ")[0]
        hits, _ = q.api.search(f'!"{front}" set:{p.set.lower()}', unique="prints", limit=1)
        if not hits:
            unknown.append(f"{name} {p}")
    problems = []
    if unknown:
        problems.append("unknown printing: " + ", ".join(unknown))
    if wrong:
        problems.append("printing is a different card: " + ", ".join(wrong))
    return problems, ids


def import_check(deck: deckfile.Deck, text: str, pinned: dict[str, str],
                 refresh: bool = False) -> tuple[list[str], str]:
    """Send the list to the Tabletop Simulator importer. Returns (problems, note).

    An importer that cannot be reached is a note, never a failure: it is someone
    else's service, and a deck does not become illegal because it is down.
    """
    try:
        result = ttsimport.check(text, expect=pinned, refresh=refresh)
    except ttsimport.ImporterUnavailable as exc:
        return [], f"TTS import not checked: importer unavailable ({exc})"
    problems = [f"TTS importer: {err}" for err in result.errors]
    if result.count != deck.total and not result.errors:
        problems.append(f"TTS importer returned {result.count} of {deck.total} cards")
    swapped = [name for name, want in pinned.items() if want not in result.printing_of(name)]
    if swapped:
        problems.append("TTS importer loads a different printing for: " + ", ".join(swapped))
    note = f"TTS import {result.count}/{deck.total} cards"
    if pinned:
        note += f", {len(pinned) - len(swapped)}/{len(pinned)} pinned printings load"
    # Lines that loaded are remembered for 30 days; say how much was really asked.
    if result.cached:
        note += " (all known good, importer not asked)"
    elif 0 < result.sent < deck.total:
        note += f" (asked the importer about {result.sent})"
    return problems, note


def report(deck: deckfile.Deck, cards: dict[str, dict], problems: list[str],
           identity: set[str], gcs: list[str], cap: int | None,
           notes: list[str] | tuple[str, ...] = ()) -> bool:
    lands, flex = land_counts(deck, cards)
    avg = average_mana_value(deck, cards)

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
    for note in notes:
        print(f"      {note}")
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
    ap.add_argument("--no-import", action="store_true",
                    help="do not ask the Tabletop Simulator importer (also MTG_NO_IMPORT=1)")
    ap.add_argument("--recheck-import", action="store_true",
                    help="ask the importer about every card again, ignoring what is remembered")
    args = ap.parse_args()
    ask_importer = not (args.no_import or os.environ.get("MTG_NO_IMPORT"))

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
        pin_problems, pinned = printing_problems(deck, cards, q)
        problems += pin_problems
        notes = []
        if ask_importer and problems:
            notes.append("TTS import not checked until the problems below are fixed")
        elif ask_importer:
            import_problems, note = import_check(deck, path.read_text(encoding="utf-8"), pinned,
                                                 refresh=args.recheck_import)
            problems += import_problems
            notes.append(note)
        results.append(report(deck, cards, problems, identity, gcs, cap, notes))

    passed = sum(results)
    print(f"{passed}/{len(results)} decks pass   [{q.counters()}]")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
