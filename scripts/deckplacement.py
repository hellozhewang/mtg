"""Save the category and tier a deck-builder reply declares for a deck it changed.

The deck builder runs sandboxed to the asking user's folder, public/<user>/, so it
can read but not write frontend/deck-themes.json and frontend/deck-tiers.json.
AGENTS.md therefore has it end every new-deck or retuning reply with two lines:

    Categories: Blim-Gifts — control, aggro
    Tier: Blim-Gifts — B — double strike and extra combats multiply donations

For a long time nothing read them, so every deck built over Discord showed as
Unrated until someone copied the lines into the maps by hand. bot.py runs
outside the sandbox and calls `save()` after each model turn.

The builder names decks by stem; the maps key them `<owner>/<Deck>`, and the
owner is always the user the turn worked for, since that is the only folder it
could write. Only decks whose files changed during the turn are placed. A reply that merely
discusses another deck ("Krenko is S tier") must not re-rate it: re-rating a deck
nobody touched is a maintainer's edit, not a side effect of a chat answer.

Older replies wrote `Tier: B — <reasons>` without the stem. Such a line is paired
with the one deck the reply categorised, or failing that the one deck the turn
changed; with several candidates it is skipped and logged rather than guessed.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import deckthemes
import decktiers

# Replies are markdown: tolerate a bullet, bold or code ticks around the line.
_DECORATION = re.compile(r"[`*_]")
_DASH = r"\s*(?:—|–|\s-\s)\s*"
_STEM = r"(?P<stem>[A-Za-z0-9][A-Za-z0-9'-]*)"
_TIER_IDS = "|".join(sorted(decktiers.TIERS, key=len, reverse=True))  # SS before S
CATEGORIES_LINE = re.compile(rf"^Categories:\s*{_STEM}{_DASH}(?P<ids>[a-z]+(?:\s*,\s*[a-z]+)*)")
TIER_LINE = re.compile(rf"^Tier:\s*(?:{_STEM}{_DASH})?(?P<tier>{_TIER_IDS})(?![A-Za-z0-9])")


@dataclass(frozen=True)
class Declared:
    categories: dict[str, tuple[str, ...]]
    tiers: list[tuple[str | None, str]]      # (stem or None for the old form, tier)


def parse(answer: str) -> Declared:
    categories: dict[str, tuple[str, ...]] = {}
    tiers: list[tuple[str | None, str]] = []
    for raw in answer.splitlines():
        line = _DECORATION.sub("", raw).strip().lstrip("-•> ").strip()
        if m := CATEGORIES_LINE.match(line):
            categories[m["stem"]] = tuple(i.strip() for i in m["ids"].split(","))
        elif m := TIER_LINE.match(line):
            tiers.append((m["stem"], m["tier"]))
    return Declared(categories, tiers)


def _themes_error(ids: tuple[str, ...]) -> str | None:
    """The same rules deckthemes.load enforces, so a saved entry never breaks the build."""
    unknown = [i for i in ids if i not in deckthemes.THEMES]
    if unknown:
        return f"unknown categories {unknown}"
    if len(set(ids)) != len(ids):
        return "repeated category"
    if ids[0] not in deckthemes.CANONICAL:
        return f"primary {ids[0]!r} is not one of {', '.join(deckthemes.CANONICAL)}"
    return None


def _write(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# Each map keeps the layout it already has, so a save is a one-line diff.
def _dump_tiers(d: dict[str, str]) -> str:
    return json.dumps(dict(sorted(d.items(), key=lambda kv: kv[0].lower())), indent=2) + "\n"


def _dump_themes(d: dict[str, list[str]]) -> str:
    rows = ",\n".join(f"  {json.dumps(k)}: {json.dumps(v)}" for k, v in sorted(d.items()))
    return "{\n" + rows + "\n}\n"


def save(answer: str, touched: set[str], frontend: Path, owner: str) -> list[str]:
    """Write the reply's declarations for `owner`'s `touched` decks. Returns log lines."""
    declared = parse(answer)
    notes: list[str] = []
    tiers_path, themes_path = frontend / "deck-tiers.json", frontend / "deck-themes.json"
    tiers = json.loads(tiers_path.read_text(encoding="utf-8"))
    themes = json.loads(themes_path.read_text(encoding="utf-8"))
    tiers_changed = themes_changed = False

    for stem, ids in declared.categories.items():
        if stem not in touched:
            notes.append(f"categories for {stem} ignored: deck not changed this turn")
        elif error := _themes_error(ids):
            notes.append(f"categories for {stem} ignored: {error}")
        elif tuple(themes.get(key := f"{owner}/{stem}", ())) != ids:
            notes.append(f"categories {key}: {themes.get(key, 'none')} -> {list(ids)}")
            themes[key] = list(ids)
            themes_changed = True

    for stem, tier in declared.tiers:
        if stem is None:
            candidates = set(declared.categories) or touched
            if len(candidates) != 1:
                notes.append(f"tier {tier} ignored: no stem and {len(candidates)} candidate decks")
                continue
            stem = next(iter(candidates))
        if stem not in touched:
            notes.append(f"tier for {stem} ignored: deck not changed this turn")
        elif tiers.get(key := f"{owner}/{stem}") != tier:
            notes.append(f"tier {key}: {tiers.get(key, 'unrated')} -> {tier}")
            tiers[key] = tier
            tiers_changed = True

    if tiers_changed:
        _write(tiers_path, _dump_tiers(tiers))
    if themes_changed:
        _write(themes_path, _dump_themes(themes))
    return notes


def touched_stems(root: Path, since: float) -> set[str]:
    """Stems of decks in `root`, one owner's folder, whose list or guide was
    written at or after `since` (epoch s)."""
    since_ns = int(since * 1_000_000_000)
    return {
        path.stem
        for path in root.glob("Bracket*/*")
        if path.suffix in (".txt", ".guide") and path.stat().st_mtime_ns >= since_ns
    }
