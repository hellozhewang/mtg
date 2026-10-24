# Catalog strategies

Builders: follow the [deck placement guide](../deck-catalog-strategies.md) when
creating a deck or changing its plan. It covers primary/secondary selection,
every supported ID, examples, renames, map keys, and the Discord
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
per catalog directory, so two copies of the catalog on one origin stay independent. New
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

**Random** (topbar, every page) draws from the deck picker's own options, minus
the current deck, when the page loads, and prefetches that deck's bare `.txt`
list, which the build writes beside every deck page. The click then copies
synchronously, like Copy decklist: `writeText` in a secure context, otherwise
`execCommand('copy')`, the only option on plain `http` from another device on
the network. If the list is not back yet, a promise-valued `ClipboardItem` tries
to keep the click's permission. The page opens with `?random=copied` or
`?random=manual`. It shows a one-line note, with a one-click Copy decklist when
the automatic copy failed (always on `file://`, where fetch is blocked), then
strips the query.

Hover a deck name, commander name, or tile artwork to preview the commander's
full card at up to 360px wide. Keyboard focus on a deck link also shows it;
Escape, moving away, or scrolling dismisses it. Both groupings and layouts
support the preview. Touch taps continue to open the deck. Readable images load
on demand from Scryfall, with the local card thumbnail as a network fallback.

Categories are a fixed set of seven (`aggro`, `gowide`, `combo`, `control`,
`graveyard`, `spells`, `value`) plus the `other` catch-all; a deck's first ID
must be one of those eight.
**Goblins** is a local-only extra: Goblin decks carry `goblins` as a secondary
tag, and only the owner's local index (`docs/index.local.html`, gitignored, the
LAN server's home page) renders a Goblins section. Its tiles are static copies
with class `mirror`, which the script never moves and the result count skips;
the real tile stays in the deck's canonical category. The category is marked
`local`: a `.chip.local` on its heading, a dashed `.theme-tag.local` on tiles,
and "(local)" in the filter. The published index drops the tag from chips,
filters and `data-themes`. See the placement guide for the full rule.

Every deck shows its owner, the folder it lives in (`public/<owner>/`), as the
tile's byline; deck pages are at `<owner>/<Bracket>/<Deck>.html`, and each
pre-2026-10-18 page path holds a redirect built from `redirects.json` and
`redirect.html`.

`deck-themes.json` maps **`<owner>/<filename stem>`** to lists of theme IDs. The first ID is the primary group. Review the decklist and guide when
assigning themes; the commander or filename alone can be misleading. Names stay
the same when a deck moves to another bracket.

Category labels, descriptions, and conservative filename fallbacks are defined
in `scripts/common/deckthemes.py`. A deck with no entry and an unrecognised filename word
falls back to Other Strategies. Unknown IDs, a non-canonical first ID and
duplicate tags fail the build, and the tests fail for any deck without an entry.

Two owners' decks of the same name have separate keys, and so separate
categories and tiers.

## Power tiers

**Tiers** is the third grouping: one collapsible section per tier, strongest
first (GOD, SS, S, A, B, C, D, TRASH), then Unrated. It is remembered like the
other two, and Expand all / Collapse all work in it as they do in Categories.
Every deck name carries a small coloured tier mark in all views and on its deck
page; the colour comes from `data-tier` alone (`--tier-*` tokens in style.css).
Search finds a tier by its folded `S-tier` token.

`deck-tiers.json` maps the same `<owner>/<filename stem>` keys to a tier ID. A
tier, like a category, can be `local_only`, shown only on the local index. Tier IDs
and their one-line descriptions are defined in `scripts/common/decktiers.py`. There is
no filename fallback: an unplaced deck renders as Unrated ("?"), the build warns,
and `tests/test_deck_tiers.py` fails for any deck missing from its map.
How to choose a tier is in [deck-tiers.md](../deck-tiers.md).

Run `python3 scripts/common/build_site.py` to regenerate the catalog, then
`python3 scripts/common/build_site.py --check`. Generated files in `docs/` must not be
edited by hand.
The template loader versions stylesheet and script URLs by content hash, so
browsers refresh changed assets while repeated builds stay deterministic.
