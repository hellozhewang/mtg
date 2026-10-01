# Catalog strategies

Builders: follow the [deck placement guide](../deck-catalog-strategies.md) when
creating a deck or changing its plan. It covers primary/secondary selection,
every supported ID, examples, renames, private metadata, and the Discord
builder's access limits. This file is the short implementation reference.

On the first visit, the catalog opens in **List**, with individually collapsible
brackets, open by default. Click a bracket label or use Enter/Space to fold its
decks. **Categories** groups decks by primary Commander strategy, then bracket, with each category
collapsible. Expand all / Collapse all controls appear in Categories. The
separate Rows / Tiles layout applies to either view.

Switching views moves the same deck links between containers, preserving one
tile per deck, bracket/date ordering, filters, and bracket/category collapse states.
The browser remembers List/Categories, Rows/Tiles, and each bracket/category's
collapsed state when returning from a deck or reloading. Preferences are stored
per catalog directory, so public and private catalogs stay independent. New
sections start open. If browser storage is unavailable, the controls still work
within the page. Search opens matching brackets and categories temporarily and
restores their prior collapse states when filters are cleared. Secondary themes
match filters and text search in both views.
Category headings, bracket headings, and strategy options have no deck-count
suffixes. The overall result total remains beside the filters. Main category
titles and List bracket headings share large, bold lavender text (1.5rem), in
normal title case. Bracket labels nested inside Categories use smaller blue-gray
text (.78rem). Theme chips use teal. Rows aligns deck identity, mana, themes, and stats
in columns, stacking them on smaller screens. Keep each theme a separate chip.

Hover a deck name, commander name, or tile artwork to preview the commander's
full card at up to 360px wide. Keyboard focus on a deck link also shows it;
Escape, moving away, or scrolling dismisses it. Both groupings and layouts
support the preview. Touch taps continue to open the deck. Readable images load
on demand from Scryfall, with the local card thumbnail as a network fallback.

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
