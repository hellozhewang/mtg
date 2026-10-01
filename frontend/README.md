# Catalog strategies

The index groups decks by bracket, then by their primary Commander strategy.
Each deck appears once. Its secondary themes remain visible on the tile and
match the strategy dropdown and text search in both Tiles and List views.

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
