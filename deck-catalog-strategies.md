# Placing decks in the Commander catalog

Every new deck needs a deliberate catalog placement, and a power tier as well
(see [deck-tiers.md](deck-tiers.md)). Revisit the placement when tuning changes
the plan. Read the finished decklist and guide before choosing: a commander,
filename, or single card does not establish a strategy.

**The categories are fixed.** There are exactly seven canonical categories, an
**Other Strategies** catch-all for a plan that genuinely fits none of them, and
Goblins as a private-only extra. Builders choose from this set and never invent,
rename or add a category; changing the set is the owner's decision (owner
instruction, 2026-10-04).

The catalog initially opens in **List**, showing decks under individually collapsible
brackets. Brackets start open; click their label to collapse or expand them.
The browser remembers the chosen view, layout, and collapsed sections on return.
Switch to **Categories** to group by **category, then bracket**, with collapsible
category sections and Expand all / Collapse all controls. Empty subsections are
omitted. **Tiers** groups by power tier instead. Secondary categories appear on a
deck's tile and match the category filter and text search in every view.
Rows / Tiles controls the layout separately.

## The seven categories

Each category is defined by **how the deck wins**, so every deck has one obvious
primary.

| ID | Catalog label | The deck wins by… |
|---|---|---|
| `aggro` | Aggro & Voltron | Attacking: one huge threat, attack triggers, extra combats, evasive or tribal beatdown. |
| `gowide` | Tokens & Aristocrats | An army of tokens or small creatures, or sacrificing it for value and drain. |
| `combo` | Combo | Assembling a loop or an alternate win condition. |
| `control` | Stax & Control | Denying the table: taxes, locks, hatebears, pillowfort, counterspells, theft and goad. |
| `graveyard` | Graveyard | Using the graveyard as a resource: reanimation, recursion, self-mill, discard and wheels. |
| `spells` | Spells & Burn | Never needing combat: spellslinger and storm engines, burn, drain and punisher effects. |
| `value` | Value & Ramp | Out-resourcing the table with engines: big mana, lands, artifacts, enchantments, counters, blink, planeswalkers. |
| `other` | Other Strategies | The catch-all: a plan that genuinely fits none of the seven. Try every one first; a deck here should be rare. |

| Private-only | Catalog label | Use |
|---|---|---|
| `goblins` | Goblins | A secondary tag on every Goblin deck. The local catalog mirrors those decks into a Goblins section; the published catalog ignores the tag. Never a primary. |

[`scripts/deckthemes.py`](scripts/deckthemes.py) defines the IDs, labels, order
and filename fallbacks. Use the IDs in JSON, not labels or synonyms.

## File placement and metadata

Keep decklists and matching `.guide` files in `public/Bracket*/` or
`private/Bracket*/`, following the [bracket rules](README.md#core-rules).
**Do not create category directories or move a deck into another bracket to
change its group.** Categories do not change legality or Game Changer caps.

| Deck visibility | Assignment file |
|---|---|
| Public | [`frontend/deck-themes.json`](frontend/deck-themes.json) |
| Private | `private/deck-themes.json` (ignored; local only) |

The key is the **exact filename stem**, without a directory or extension, not
the printed commander name. The value is a nonempty array of category IDs:

```json
{
  "Krenko-Combo": ["combo", "gowide", "goblins"],
  "Cloud-Equipment": ["aggro", "value"],
  "Greasefang-Vehicles": ["graveyard", "aggro", "value"],
  "Kinnan-Infinite": ["combo", "value"]
}
```

**The first ID is the primary category and must be one of the seven or `other`;
the rest are secondary filters.** Keep that order. Sort deck keys for readability, but do
not alphabetise a deck's array or repeat an ID. Every public deck needs an
explicit entry; the test suite fails for one without.

Public and private maps are independent. A private deck may share a filename
with a public deck and have a different category. Never put private deck names
or assignments in the public map.

## Choosing the primary and secondary categories

1. Describe the deck's normal route to a win in one sentence, checked against
   the guide's engines, finishers and the actual cards.
2. The category that sentence describes is the primary. A deck whose combo is a
   backup to an attacking plan is `aggro` with `combo` secondary; a deck built
   to assemble the combo is `combo`.
3. Add secondary categories only for a real supporting package the pilot uses.
   Most decks need one to three in total.
4. A Goblin deck adds `goblins` as a secondary tag (see below).
5. Keep the primary when ordinary tuning preserves the deck's identity.
   Reclassify when the main plan changes.

Examples from this collection:

- **Krenko-Combo:** `combo` (built to untap Krenko and loop), `gowide`, `goblins`.
- **Najeela-Warriors:** `aggro` (the Warriors attack every turn), with `combo`
  for the infinite-combat finish and `gowide`.
- **Greasefang-Vehicles:** `graveyard`: the Vehicles come back from the graveyard
  to attack, so the graveyard is the engine; `aggro` and `value` are secondary.
- **Cloud-Attacks** and **Cloud-Equipment** are both `aggro`: one spreads
  Equipment across a team, the other builds one lethal attacker.

Useful distinctions:

- **Aggro or go-wide:** a few strong attackers, attack triggers or extra combats
  are `aggro`. A wide board of tokens whose number is the point, or sacrifice
  engines, is `gowide`.
- **Control or spells:** taxes, locks, counterspells and theft are `control`.
  Damage to the table from spells or punisher triggers is `spells`, even in a
  creature deck such as Ruric Thar.
- **Combo:** use it as a primary only when assembling the win IS the plan, and as
  a secondary for any deck with a real assembled win. One standalone alternate-win
  card is not enough.
- **Graveyard or value:** reanimation, recursion, discard and wheels are
  `graveyard`. Engines that grind through ramp, artifacts, enchantments,
  counters, blink or planeswalkers are `value`. Ordinary mana rocks make
  nothing an artifact deck.
- **Creature types are not categories.** An Elf or Vampire deck goes where its
  plan puts it. Goblins is the one owner-requested exception, and only as a
  private mirror.

## Goblins: the private-only eighth category

**Every Goblin deck carries `goblins` as a secondary tag, after its canonical
primary.** That includes Goblin hybrids and Goblin decks led by a non-Goblin
commander. A few incidental Goblin cards, or a Goblin commander without a Goblin
plan, do not make a Goblin deck.

The tag works differently in the two catalogs:

- **Local (private) catalog:** each Goblin deck appears in its canonical category
  AND in a Goblins section (Goblins → bracket → decks), for public and private
  Goblin decks alike. The Goblins copy is a mirror: it is not moved between
  views and does not add to the deck count. Goblins also appears in the filter.
- **Published catalog:** the tag is ignored. No Goblins section, chip or filter
  option; Krenko-Combo sits only under Combo.

A new `Commander-Goblins` filename falls back to `gowide` + `goblins`, but give it
a reviewed explicit entry.

## New decks, changes, and fallbacks

- **New deck:** add an explicit entry after validating the list and writing its
  guide. Filename guesses are not a finished classification.
- **Tuned deck:** review the assignment when engines or finishers change. A
  routine card swap normally needs no change.
- **Bracket move:** keep the key when the filename stem is unchanged.
- **Rename:** move the entry to the new stem.
- **Delete:** remove the entry when no remaining deck in that scope uses it.

Without an explicit entry, the renderer matches the word after the last hyphen
against `HINTS` in `scripts/deckthemes.py` (for example `-Prison` gives
`control` and `-Reanimator` gives `graveyard`); an unknown word falls back to
`other`, which is a reason to add a reviewed entry, not a placement. A statement in a `.guide` or a chat message does not update the map.
Unknown IDs, a non-canonical primary, empty arrays and repeated IDs fail the build.

## Discord builder access

The bot's builder works in `public/` and cannot write `frontend/` or `scripts/`.
It can read this guide, the public map and the classifier. Choose an honest
filename theme word for a new deck, and in the handoff give the exact stem and
ordered IDs from the fixed set, for example:
`Krenko-Combo: combo, gowide, goblins`. State that the map still needs a
full-workspace update. Do not claim the categories were saved, and do not invent
a category outside the fixed set.

## Finish and verify

For a full-workspace build or tune:

1. Validate the deck and update its `.guide`.
2. Save the reviewed assignment in the correct public or private map, and the
   deck's tier in the matching `deck-tiers.json`.
3. Run `python3 scripts/build_site.py`, then
   `python3 scripts/build_site.py --check` from the repository root. The check
   covers the public build; inspect the local catalog too for private changes.
4. Confirm the deck appears once under its bracket in List, under its primary
   category and bracket in Categories (plus Goblins locally, for a Goblin deck),
   and under its tier in Tiers, and that the filter finds it by each secondary
   category.
5. Publish authorized public changes with the generated frontend. Keep `private/`
   and `docs/private/` out of the commit and preserve unrelated working-tree edits.

When changing classification or rendering code, also run
`python3 -m unittest discover -s tests`. Tests cover the fixed set, map
validation, fallbacks, grouping, the Goblins mirror and public/private
separation. They do not judge whether a deck's cards support its labels; that
review remains part of deckbuilding.

Never hand-edit generated HTML to move a tile. Update source metadata and rebuild
so the placement survives the next automated publication.
