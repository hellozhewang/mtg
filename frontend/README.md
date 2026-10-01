# Catalog strategies

Builders: follow the [deck placement guide](../deck-catalog-strategies.md) when
creating a deck or changing its plan. It covers primary/secondary selection,
every supported ID, examples, renames, private metadata, and the Discord
builder's access limits. This file is the short implementation reference.

The catalog opens in **List**, the original bracket-first view. **Categories**
groups decks by primary Commander strategy, then bracket, with each category
collapsible. Expand all / Collapse all controls appear in Categories. The
separate Rows / Tiles layout applies to either view.

Switching views moves the same deck links between containers, preserving one
tile per deck, bracket/date ordering, filters, and category collapse states.
Each visit defaults to List; only the Rows/Tiles layout is saved. Search opens
matching categories temporarily and restores their prior collapse states when
filters are cleared. Secondary themes match filters and text search in both views.
Category headings, bracket headings, and strategy options have no deck-count
suffixes. The overall result total remains beside the filters. Main category
titles are large lavender text (1.5rem); bracket labels are smaller blue-gray
text (.78rem) in both views. Theme chips use teal. Rows aligns deck identity, mana, themes, and stats
in columns, stacking them on smaller screens. Keep each theme a separate chip.

In Categories, all Goblin decks use **Goblins** (`goblins` first), with
brackets nested inside it. Keep their supported broader strategies as secondary
tags. This includes Goblin hybrids and decks with non-Goblin commanders; a few
incidental Goblin cards are not enough. New `-Goblins` filenames fall back to
this category. See the placement guide for the full rule.

`deck-themes.json` maps **public deck filenames without extensions** to lists of
theme IDs. The first ID is the primary group. Review the decklist and guide when
assigning themes; the commander or filename alone can be misleading. Names stay
the same when a deck moves to another bracket.

Theme labels, descriptions, and conservative filename fallbacks are defined in
`scripts/deckthemes.py`. New decks with an unrecognized theme appear under Other
Strategies until an assignment is added. Unknown IDs and duplicate tags fail
the build rather than silently disappearing.

Private assignments belong in the ignored `private/deck-themes.json`. They are
read only for the local catalog and are independent of public assignments, even
when two decks share a filename. Never add private deck names to the public map.

Run `python3 scripts/build_site.py` to regenerate both catalogs, then
`python3 scripts/build_site.py --check`. Generated files in `docs/` must not be
edited by hand. The private output remains ignored under `docs/private/`.
The template loader versions stylesheet and script URLs by content hash, so
browsers refresh changed assets while repeated builds stay deterministic.
