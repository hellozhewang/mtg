# Cactuar table: versions and patch notes

One entry per table build delivered as **MTG 6 player Cactuar Ver_vN**, newest first.
`scripts/tabletop/release_tts.py` reads the latest version here, builds the next one and adds
its entry. Details of how each change works live in [WIP](../../tts/WIP.md).

Data changes don't need a new version: decks and sleeves reach every table through the
published site (press **Refresh** in the deck browser). A new version is only for changes
to the table itself: its Lua, its panel, the tiles, and clip or tile URLs.

## v70 — 2026-10-24 (commit 54a0c475)
- Guide switches now draw a trigger area: the far corner of the playmat on the library side, boxed in that player's playmat colour and labelled TRIGGERS
- Switch moved clear of the reveal (magnifier) button and relabelled Triggers
- Stack area on the edge strip is now a graphite-and-silver panel picture with five numbered slots

## v69 — 2026-10-24 (commit cef79a96)
- Each seat has a Guide lines switch next to its buttons (off by default): turning it on draws a divider splitting the playmat into creature and noncreature rows, for everyone to see; decorative only

## v68 — 2026-10-24 (commit 58443497)
- Right-hand edge strip cleared (importer, dice, counters, commander damage markers, Turn Order, Planechase bag) and redrawn as a stack area with five card slots that cards snap into

## v67 — 2026-10-24 (commit b93dd1cd)
- Fix v66 script errors (czmTick trace and Inspect 'Function required' menu errors): hand cards are found through hand zones, never by hand index
- music off now also stops the battlefield scan

## v66 — 2026-10-23 (commit 1705975e)
- Cards in hand (or being dragged) no longer start battle music; only the battlefield counts
- Opening Inspect deselects whatever that player had selected

## v65 — 2026-10-23 (commit 52ce3a05)
- Battle music follows named cards on the active player's battlefield instead of permanent counts
- New songs: Omega (eScape), Shiva (Oblivion), Leviathan (Through the Maelstrom), Ramuh (Thunder Rolls), Bahamut (Answers), Gilgamesh (Battle on the Big Bridge), Dragonsong, Footfalls; Dash de Chocobo as the lowest-priority fallback
- Y'shtola and G'raha Tia call Hades; card-colour table removed from the save

## v64 — 2026-10-22 (commit 876a4fe7)
- Fix dark Show commander and Hide commander labels by using explicit white child Text elements; preserve button clicks and background. Both labels visually checked in the running table. Published unchanged to Steam Workshop item 3822623414 on 2026-10-22; Steam confirmed EResult 1.

## v63 — 2026-10-22 (commit 4e426ad0)
- Make Show commander and Hide commander text white; retain the existing button background and on-demand picture behavior. Saved build for testing; Steam remains v60.

## v62 — 2026-10-22 (commit 63ad5ee4)
- Rename Show picture to Show commander; add Reload and a longer settling interval for recurring white commander previews.
- Consolidate TTS guides, changelog and image troubleshooting under docs/development, retaining tts/WIP.md and preserving authored docs during site builds.
- Cached Xander and first-request Davros visually checked; recurring white-image root cause remains open. Saved build for testing; not uploaded to Steam.

## v61 — 2026-10-22 (commit b071f558)
- Add Show picture beside commander text; deck browsing stays text-only until explicitly requested.
- Load only the current commander face, with ordered partner/back-face paging and cached URL reuse; repair white sprites with a post-load blank-to-picture transition.
- Retain cached catalog/Inspect rendering, written guides and lazy sleeves. Saved build for testing; not uploaded to Steam.

## v60 — 2026-10-22 (commit 75c525d4)
- Reduce Inspect opening bursts with cached metadata and preparation/painting in small frame batches.
- Search cached full text without native deck reads; combine grid and face assets into one rebuild and add Refresh for metadata edits.
- Keep alphabetical order, private hover previews and safe GUID retrieval. Published unchanged to Steam Workshop item 3822623414 on 2026-10-22; Steam confirmed EResult 1.

## v59 — 2026-10-22 (commit 72b4df77)
- Add a scrolling text-only commander section below Strategy: mana cost/value, type, full rules and creature/planeswalker/battle stats.
- Support ordered partners and multiple faces. Fetch only the selected deck’s small cached text file; no commander images or guide downloads.
- Retain incremental catalog loading, cached ten-row pagination and sleeve fixes. Saved build for testing; not uploaded to Steam.

## v58 — 2026-10-22 (commit aaea17e2)
- Avoid the first-open full-catalog JSON decode stall: load catalog.jsonl and decode small records over multiple frames with progress.
- Keep full metadata for search/filtering, atomically replace validated catalogs, and retain old data on refresh failures.
- Retain cached ten-row pagination and sleeve fixes. Saved build for testing; not uploaded to Steam.

## v57 — 2026-10-22 (commit f1601e48)
- Keep the full metadata catalog in Lua and cache filtered/sorted results; paging and selection reuse the list.
- Format only the visible ten reusable rows, update selection highlights without rebuilding row text, and skip closed-panel UI writes.
- Retain demand-loaded sleeves and white-preview binding repair. Saved build for testing; not uploaded to Steam.

## v56 — 2026-10-22 (commit 7ed7739b)
- Fix white sleeve previews by binding images after native UI asset rebuilding settles and invalidating stale UI writes.
- Retain eight-per-page demand loading, visited-page caching and preservation of shared assets; repair verified visually on the running table.
- Saved build for testing; not uploaded to Steam.

## v55 — 2026-10-22 (commit 0e4ec05b)
- Load sleeve thumbnails only when opening or paging to their eight-choice page; shared redraws never prefetch other pages.
- Keep visited pages cached, skip superseded pending pages and preserve shared Inspect assets while loading.
- Saved build for testing; not uploaded to Steam.

## v54 — 2026-10-22 (commit 18f147ff)
- Fix Inspect pattern-too-complex errors by replacing its target grid with bounded plain XML searches; preserve other seats and base UI exactly.
- Retain the live zone-menu repair and on-demand sleeve thumbnails from v53; commander/guide images remain disabled.
- Applied the grid fix live while preserving current Inspect queries and outer event hooks. Saved build for testing; not uploaded to Steam.

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
