# Catalog strategies

Builders: follow the [deck placement guide](../deck-catalog-strategies.md) when
creating a deck or changing its plan. It covers primary/secondary selection,
every supported ID, examples, renames, private metadata, and the Discord
builder's access limits. This file is the short implementation reference.

The index groups decks by primary Commander strategy, then by bracket.
Each deck appears once. Its secondary themes remain visible on the tile and
match the strategy dropdown and text search in both Tiles and List views.

All Goblin decks use the dedicated **Goblins** category (`goblins` first), with
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
