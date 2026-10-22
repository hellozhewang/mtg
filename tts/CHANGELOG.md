# Cactuar table: versions and patch notes

One entry per table build delivered as **MTG 6 player Cactuar Ver_vN**, newest first.
`scripts/release_tts.py` reads the latest version here, builds the next one and adds
its entry. Details of how each change works live in [WIP.md](WIP.md).

Data changes don't need a new version: decks and sleeves reach every table through the
published site (press **Refresh** in the deck browser). A new version is only for changes
to the table itself: its Lua, its panel, the tiles, and clip or tile URLs.

## v53 — 2026-10-22 (commit 26ab03fc)
- Restore Inspect after the base table clears and rebuilds deck menus on zone entry and exit; preserve Cascade/basic-land actions and existing startup/spawn retries.
- Restore sleeve thumbnails only on opening the Sleeves chooser, eight per page; cache visited pages and preserve other private windows. Commander and guide pictures remain disabled.
- Applied the Inspect zone hook to the running game. Saved build for testing; not uploaded to Steam.

## v52 — 2026-10-21 (commit f17111b9)
- Restore Inspect menu registration across browser/Global reloads without duplicating entries on Inspect-only hot patches.
- Retry late-forming decks and transient native menu readiness; preserve other menus, deck order, the text-only browser and battlefield music.
- Saved build for testing; not uploaded to Steam.

## v51 — 2026-10-21 (commit c7f39892)
- Make the Cactuar browser text-only: remove commander previews and guide pictures; keep written guides on Read guide and choose sleeves by name.
- Skip closed-seat rendering and unchanged UI writes; eliminate browser picture registration and shared XML rebuilding. Start hidden Inspect grids at 32 cells and grow on demand.
- Keep v50 battlefield music priorities. Saved build for testing; not uploaded to Steam.

## v50 — 2026-10-21 (commit 45472f47)
- Prioritized battlefield music on qualifying active turns (10+ permanents): Goblins (Titan), artifacts (Ultima), White (Thordan), Black (Hades), Blue (Alexander/Locus), Green (Garuda), Red (Ifrit)
- Use original FF14 WAV tracks with pause/resume across qualifying turns and trimmed start on Hades
- Embed card color metadata for accurate creature color detection

## v49 — 2026-10-21 (commit 17949770)
- Use the original FF14 WAV recordings; v48’s MP3 copies produced incorrect repeated sounds on the owner’s client.
- Keep one soundtrack playlist entry, enable looping only after load, and clear the prelude playlist when the cannon fires. Retain artifact/turn gating and Ultima pause/resume.
- Saved build for testing; not uploaded to Steam.

## v48 — 2026-10-21 (commit a6e5c0ba)
- Loop the FF14 prelude until the cannon fires; play one looping Ultima only during turns with 10+ artifacts in that player’s battlefield.
- Pause/resume Ultima without reloading between qualifying turns; skip custom voice clips to preserve its playhead. Exclude library, exile, graveyard and commander columns.
- Add music on/off and smaller content-versioned MP3 music files. Saved build for testing; not uploaded to Steam.

## v47 — 2026-10-21 (commit e4c4d3af)
- Load illustrated guides only on Read guide; selecting commanders uses pinned faces already in the catalog.
- Cache recent commander/guide pictures and avoid redundant image clears and shared UI asset reloads on revisits.
- Saved build for testing; not uploaded to Steam.

## v46 — 2026-10-21 (commit b1b53868)
- Play custom audio on reported turn starts, including first and same-seat events; add turn sound test for solo audio testing.
- Record audio playback/load diagnostics; native solo End Turn may emit no Lua event.
- Saved build for testing; not uploaded to Steam.

## v45 — 2026-10-21 (commit ac40727f)
- Play change-turn.wav for everyone on genuine turn changes; announcer off mutes the custom clip.
- Keep TTS native incoming-player ping; avoid duplicate/setup sounds and stale audio playback callbacks.
- Saved build for testing; not uploaded to Steam.

## v44 — 2026-10-21 (commit 0c313b98)
- Commander images are 15% smaller and centered; guide-card hover previews retain their full readable size.
- Saved build for testing; not uploaded to Steam.

## v43 — 2026-10-21 (commit d52abf22)
- Fix commander preview sizing and blank images; retain full-size partner and double-faced previews.
- Illustrated guides match the website with card pictures, combo/chain strips and readable hover previews.
- Saved build for testing; not uploaded to Steam.

## v42 — 2026-10-21 (commit 1d6fea03)
- Larger deck browser with a readable pinned commander preview; switch partners and flip double-faced commanders.
- Read the selected deck guide inside TTS while keeping the commander visible.
- Updated the 5-minute and 10-minute announcer recordings and matching chat lines.
- Workshop item 3822623414 updated.

## v41 — 2026-10-21 (commit 2668166e)
- Inspect searches full stored card names, types, descriptions/rules, tags and alternate faces.
- Use the .* toggle for regex patterns such as creature|artifact, draw.*card, or word boundaries; invalid patterns show an inline error.
- Automatic hover previews remain beside the list; searching preserves deck order and seat privacy.
- Workshop item 3822623414 updated.

## v40 — 2026-10-21 (commit 0490eba7)
- Inspect automatically enlarges hovered cards to the left; moving away hides the preview, with no zoom key or binding needed.
- Hovering another thumbnail resumes automatic previews after clicking a card; existing retrieval and privacy safeguards remain.
- Workshop item 3822623414 updated.

## v39 — 2026-10-21 (commit cb94246a)
- Card click previews open immediately to the left of Inspect, leaving the search field and card list accessible.
- Workshop item 3822623414 updated.

## v38 — 2026-10-20 (commit c33196c7)
- Inspect supports hold-to-zoom beside the card list; bind Inspect zoom to Alt once in Options > Game Keys.
- Moving between thumbnails updates the enlarged image; releasing the key or leaving the card dismisses it, with no change to deck contents or order.
- Zoom works with GUID-less imports and preserves click previews, private seats, existing image assets and other key bindings.
- Workshop item 3822623414 updated.

## v37 — 2026-10-20 (commit 72be2e47)
- Inspect now matches the native Search layout with a narrow dark window, one search field, and four continuously scrolling columns.
- Inspect reads live decks and bags alphabetically without revealing positions or changing their order; larger containers expand the view automatically.
- Fixed missing cards from imports with empty GUIDs and blank WebP thumbnails; anonymous objects support safe preview, with retrieval disabled.
- Workshop item 3822623414 updated.

## v36 — 2026-10-20 (commit 53bb0a1f)
- Renamed the alphabetical deck browser to Inspect in the right-click menu and window title.
- Workshop item 3822623414 updated.

## v35 — 2026-10-20 (commit 342fb397)
- Right-click a deck and choose Search A-Z for a private alphabetical card gallery with live name search, previews and Take to hand.
- Browsing preserves the real library order and never shows card positions; draws and seat changes refresh the private view.
- Workshop item 3822623414 updated.

## v34 — 2026-10-20 (commit eb2af491)
- Pirate Cannon starts the game through cztStartGame, resetting totals and starting turn 1 even when the winner already holds the turn.
- Workshop item 3822623414 updated.

## v33 — 2026-10-20 (commit b8c5b02b)
- Turn clocks no longer keep running after a double start (a seat's clock could count through other players' turns)
- Workshop item 3822623414 updated.

## v32 — 2026-10-19 (commit 413a5e2d)
- Opening the deck browser fetches the list again when it's over 2 minutes old, so new decks and sleeves show without Refresh
- Uploaded programmatically to Workshop item 3822623414; Steam confirmed success (EResult 1).

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
