# Cactuar table: versions and patch notes

One entry per table build delivered as **MTG 6 player Cactuar Ver_vN**, newest first.
`scripts/release_tts.py` reads the latest version here, builds the next one and adds
its entry. Details of how each change works live in [WIP.md](WIP.md).

Data changes don't need a new version: decks and sleeves reach every table through the
published site (press **Refresh** in the deck browser). A new version is only for changes
to the table itself: its Lua, its panel, the tiles, and clip or tile URLs.

## v32 — 2026-10-19 (commit 413a5e2d)
- Opening the deck browser fetches the list again when it's over 2 minutes old, so new decks and sleeves show without Refresh

## v31 — 2026-10-19 (commit 0b85e52e)
- Sleeves menu is a paged grid of thumbnails (8 a page, the chosen one ticked)

## v30 — 2026-10-19 (commit 856d1f8b)
- Deeper radio announcer at 5 and 10 minutes: three semitones below v29, with the same pacing and loudness.
- Audio URLs use the new clip hashes so TTS downloads the updated recordings.

## v29 — 2026-10-19 (commit 44402762)
- Card back menu renamed Sleeves; reads the site's new sleeves list, including sleeves made with sleever in Discord
- Codex's clearer, deeper announcer voice at about -12.5 LUFS, played from the site (v28 played from the Mac)

## v28 — 2026-10-19 (test build)
- Louder announcer clips (about -12.5 LUFS, was -18.6). Clip URLs carry a content hash.
- Test build only: its clips came from the owner's Mac instead of the site.

## v27 — 2026-10-19
- New painted Cactuar tile art; the tile URL is versioned so TTS doesn't show the cached old one.

## v26 — 2026-10-19
- Timer totals are restored after the table's objects exist (fixes totals at 0 after a load).

## v25 — 2026-10-19
- Timer state lives in the Cactuar tile's memo, so a rewind keeps it.

## v24 — 2026-10-19
- Timers survive rewinds.

## v23 — 2026-10-19
- Timers start on the first player's turn after the "Who goes first?" roll, never on load.

## v22 — 2026-10-19
- The die rebuilding itself on load no longer counts as a roll.

## v21 — 2026-10-19
- `timers on` resumes the timers without a new roll.

## v20 — 2026-10-18
- Hidden information: chat never names the deck a player loads; commanders and tokens spawn face down.

## v19 — 2026-10-18
- Fixes from the first live game: tokens go on slot 2 or the exile spot, so they no longer
  block the mulligan; seats reset when a player changes seats.

## v18 — 2026-10-18
- The total turn time label is drawn (needed a font alpha of 100).

## v17 — 2026-10-18
- The total turn time sits under each clock and survives reloads.

## v16 — 2026-10-18
- Both turn timers are visible after a load.

## v15 — 2026-10-18
- Tournament mode (all-pick, draft of 5, random) over a 24-deck pool; everything is logged.

## v14 — 2026-10-18
- Total turn time per seat, and the slow-turn announcer at 5 and 10 minutes.

## v13 — 2026-10-18
- The card back menu can be opened again.

## v12 — 2026-10-18
- Card back menu (now called Sleeves).

## v11 — 2026-10-18
- Tokens beside the commander; Newest is the default sort; no Owner sort.

## v3–v10 — 2026-10-18
- Importer XML fixes, card images from img.klrmngr.com, commander slot order, and the
  browser's layout and colours.

## v2 — 2026-10-18
- Two locked "Cactuar decks" tiles replace the screen button; button labels render.

## v1 — 2026-10-18
- The deck browser on top of "MTG 6 player table - scripted" (Workshop 2293586471).
