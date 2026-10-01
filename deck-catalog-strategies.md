# Placing decks in the Commander catalog

Every new deck needs a deliberate catalog placement. Revisit it when tuning
changes the plan. Read the finished decklist and guide before choosing labels:
a commander, filename, or single card does not establish a strategy.

The catalog defaults to **List**, showing decks directly under their brackets.
Switch to **Categories** to group by **primary strategy, then bracket**, with
collapsible strategy sections and Expand all / Collapse all controls. For example,
Stax / Prison contains its own Bracket 3, Bracket 3.5, and Bracket 4 subsections
when those brackets have decks. Empty subsections are omitted. Each deck appears
once. Secondary themes appear on its tile and match the strategy filter and text
search in either view. Rows / Tiles controls the layout separately. These rules
apply to both the public and local catalogs; classification determines placement
in Categories and filtering in both views.

## File placement and metadata

Keep decklists and matching `.guide` files in `public/Bracket*/` or
`private/Bracket*/`, following the [bracket rules](README.md#core-rules).
**Do not create strategy directories or move a deck into another bracket to
change its group.** Theme labels do not change legality or Game Changer caps.

| Deck visibility | Assignment file |
|---|---|
| Public | [`frontend/deck-themes.json`](frontend/deck-themes.json) |
| Private | `private/deck-themes.json` (ignored; local only) |

The key is the **exact filename stem**, without a directory or extension, not
the printed commander name. The value is a nonempty array of theme IDs:

```json
{
  "Krenko-Combo": ["goblins", "tribal", "tokens", "combo", "aristocrats"],
  "Cloud-Attacks": ["artifacts", "combat", "tokens"],
  "Cloud-Equipment": ["voltron", "artifacts"],
  "Kinnan-Infinite": ["combo", "ramp"]
}
```

**The first ID chooses the section; the remaining IDs are secondary filters.**
Preserve that intentional order. Sort deck keys for readability, but do not
alphabetize a deck's theme array or duplicate IDs.

Public and private maps are independent. A private deck may share a filename
with a public deck and have a different strategy. Never put private deck names
or assignments in the public map. Because keys omit brackets, public versions
sharing a stem also share an assignment; give genuinely different plans distinct
`Commander-Theme` names when creating them.

## Choosing the primary strategy and secondary themes

1. Describe the deck's normal route to a win in one sentence. Check the guide's
   engines, finishers, opening hands, and sequencing against the actual cards.
2. Choose the group a player seeking that experience would expect. Favor the
   defining engine or plan over a secondary support package. Apply the Goblins
   placement rule below before choosing a broader strategy.
3. Add secondary themes when a meaningful package of cards supports them and the
   pilot regularly uses that plan. Most decks need two to four total labels;
   use fewer or more when the list warrants it.
4. Keep the primary group when ordinary tuning preserves the deck's identity.
   Reclassify when the main plan changes. Remove tags whose engines or win
   conditions have been cut.

Examples from this collection:

- **Krenko-Combo:** `goblins` first for the dedicated Goblins category;
  `tribal`, `tokens`, `combo`, and `aristocrats` remain secondary tags.
- **Kinnan-Infinite:** `combo` first because assembling a mana loop is the main
  plan; `ramp` also applies.
- **Shorikai-Prison:** `stax` first; the defensive wall and artifact engine also
  justify `pillowfort` and `artifacts`.
- **Cloud-Attacks:** `artifacts` with `combat` and `tokens`; Equipment is spread
  across a team. **Cloud-Equipment** is `voltron` with `artifacts` because it
  builds one lethal attacker.

Useful distinctions:

- **Stax / pillowfort:** taxing spells or disabling resources supports `stax`;
  discouraging attacks supports `pillowfort`. A deck can do both.
- **Tribal / tokens:** shared creature-type payoffs support `tribal`; building
  a wide army supports `tokens`. Token production alone does not establish a
  tribal plan.
- **Combo / synergy:** use `combo` for an actual assembled win or decisive
  engine. Ordinary synergy or one standalone alternate-win card is not enough.
  The combo need not be infinite.
- **Artifacts / enchantress:** ordinary mana rocks do not make an artifact
  deck. A few strong enchantments do not make an enchantress deck.
- **Spellslinger / storm:** the shared group includes spell-based engines;
  only describe a deck as storm when casting many spells in a turn matters.
- **Punisher / lifegain:** punishing opponents' actions or repeatedly damaging
  the table supports `punisher`; a life-resource or lifegain-to-drain engine
  supports `lifegain`. Check the actual triggers.
- **Reanimator / recovery:** a sustained graveyard threat or copy plan supports
  `reanimator`; one recovery spell does not.

## Special category: Goblins

**All Goblin decks belong under Goblins, with `goblins` as the first theme ID.**
This owner-requested category takes precedence over broader primary labels such
as `tribal`, `tokens`, `combo`, `aristocrats`, or `counters`. It includes Goblin
hybrids whose engines use counters, sacrifice, or tokens, and Goblin decks led
by a non-Goblin commander. Keep each supported broader strategy as a secondary
tag so those filters still find the deck. A few incidental Goblin cards or a
Goblin commander without a Goblin plan do not establish a Goblin deck.

In Categories, the hierarchy is **Goblins → bracket → decks**, in both catalogs.
List still puts these decks directly under their brackets. Preserve the
bracket folders and visibility; assign private decks only in the private map.
Do not rename an existing deck to add the category: `Krenko-Combo`, for example,
gets it through its explicit assignment. New `Commander-Goblins` filenames fall
back to `goblins` when no explicit entry exists; builders with access to the
map should still save the full reviewed set of tags. Other creature types stay
in the existing strategy groups unless a separate category is requested.

## Supported theme IDs

[`scripts/deckthemes.py`](scripts/deckthemes.py) defines accepted IDs, display
labels, ordering, and filename fallbacks. Use IDs in JSON, not display labels
or invented synonyms.

| ID | Catalog label | Use when the deck is built around… |
|---|---|---|
| `stax` | Stax / Prison | Taxes, hatebears, resource restrictions, or locks. |
| `pillowfort` | Pillowfort | Making attacks against its pilot difficult or costly. |
| `voltron` | Voltron | Turning one creature into a lethal attacker. |
| `goblins` | Goblins | Any Goblin deck, including token, sacrifice, counter, and combo hybrids; always primary. |
| `tribal` | Tribal / Kindred | A shared creature type and its payoffs. |
| `tokens` | Tokens / Go-wide | A broad army of tokens or small creatures. |
| `aristocrats` | Aristocrats | Sacrifices, death triggers, and related value engines. |
| `reanimator` | Reanimator | Returning or copying threats from the graveyard. |
| `spellslinger` | Spellslinger / Storm | Instants, sorceries, noncreature spells, or spell chains. |
| `punisher` | Group Slug / Punisher | Table-wide damage or punishing opponents' actions. |
| `goad` | Goad / Forced Combat | Compelling attacks and directing opponents' combat. |
| `combo` | Combo | Assembling interacting pieces for a decisive engine or win. |
| `lands` | Lands / Landfall | Land drops, land recursion, or lands as an engine. |
| `artifacts` | Artifacts / Vehicles | Artifact synergies, Equipment, Treasures, or Vehicles. |
| `enchantress` | Enchantress | Enchantments as a sustained card and board engine. |
| `counters` | Counters / Proliferate | Adding, manipulating, or multiplying counters. |
| `lifegain` | Lifegain / Drain | Life as a resource or turning lifegain into life loss. |
| `discard` | Discard / Wheels | Hand disruption, discarding for value, or replacing hands. |
| `superfriends` | Superfriends | Protecting and repeatedly activating planeswalkers. |
| `theft` | Theft / Gifts | Playing opponents' cards or giving away harmful permanents. |
| `blink` | Blink / ETB | Repeating enter abilities through flicker or copies. |
| `combat` | Combat / Attack Triggers | Attack triggers, combat abilities, or extra attacks. |
| `ramp` | Ramp / Big Mana | Accelerating into expensive threats and spells. |
| `toolbox` | Toolbox / Value | Flexible tutors, repeatable abilities, and adaptable engines. |
| `other` | Other Strategies | A plan that genuinely does not fit an existing category. |

Check for an existing fit before adding a category. A full-workspace maintainer
adding an ID must update `THEMES`, this table, relevant assignments, and any
appropriate filename fallback in `HINTS`, then rebuild and check the catalog.
Do not use `other` merely to avoid reviewing a deck.

## New decks, changes, and fallbacks

- **New deck:** add an explicit entry after validating the list and writing its
  guide. Full-workspace builders should not rely on filename guesses as the
  finished classification.
- **Tuned deck:** review the assignment when engines, finishers, or supported
  themes change. A routine land swap normally needs no tag change.
- **Bracket move:** keep the key when the filename stem is unchanged.
- **Rename:** move the entry to the new stem. Remove the old entry once no deck
  in that visibility scope uses it.
- **Delete:** remove the assignment only when no remaining deck in that scope
  uses its stem.

The renderer uses explicit assignments first. Without one, it checks the word
after the last hyphen against `HINTS` in `scripts/deckthemes.py`; an unknown word
becomes `other`. Fallbacks supply a primary group only. They do not infer secondary
themes from card text or the guide. A statement in a `.guide` or chat message
does not update JSON metadata. Invalid IDs, empty arrays, and duplicate tags fail
the build.

## Discord builder access

The bot's builder works in `public/` and cannot write `frontend/` or `scripts/`.
It can read this guide, the public map, and the classifier. Inspect the existing
assignment, choose an honest filename theme for a new deck, and check its fallback
before finishing. Do not rename an existing deck solely to manipulate a label;
an explicit assignment takes precedence anyway.

Complete the authorized decklist and guide work inside that workspace. If the
intended placement needs a new or changed explicit entry, include the exact stem
and ordered IDs in the handoff, for example:
`Krenko-Combo: goblins, tribal, tokens, combo, aristocrats`. State that the map
still needs a full-workspace update. Do not claim the tags were saved, bypass the sandbox,
or ask the user to repeat authorization already given. The current bot publishes
deck files using existing assignments/fallbacks; it does not parse theme proposals
from the builder's reply.

## Finish and verify

For a full-workspace build or tune:

1. Validate the deck and update its `.guide`.
2. Save the reviewed assignment in the correct public or private map.
3. Run `python3 scripts/build_site.py`, then
   `python3 scripts/build_site.py --check` from the repository root. The check
   covers the public build; inspect the local catalog too for private changes.
4. Confirm the deck appears once under its bracket in List and under its primary
   strategy and correct bracket in Categories,
   and remains discoverable when selecting a secondary theme. Check author and
   private badge, plus both views, Rows/Tiles, category collapse, and search.
5. Publish authorized public changes with the generated frontend. Keep `private/`
   and `docs/private/` out of the commit and preserve unrelated working-tree edits.
   Private-only assignments stay local.

When changing classification or rendering code, also run
`python3 -m unittest discover -s tests` and check filters in a browser. Tests cover
metadata validation, fallback behavior, grouping, secondary tags, and
public/private rendering separation. They do not judge whether a deck's cards
support its labels; that review remains part of deckbuilding.

Never hand-edit generated HTML to move a tile. Update source metadata and rebuild
so the placement survives the next automated publication.
