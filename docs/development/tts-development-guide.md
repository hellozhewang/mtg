# TTS development guide

Start with [the WIP](../../tts/WIP.md) for current work and the latest saved/Steam
versions. This guide holds lasting implementation and release rules. See also the
[changelog](tts-changelog.md), [troubleshooting record](tts-troubleshooting.md),
[commander image measurements](tts-commander-image-performance.md),
[audio guide](tts-audio-guide.md) and [sleeves guide](tts-sleeves-guide.md).

## Sources and ownership

Runtime Lua and UI templates live in `tts/`; reusable tooling belongs in `scripts/`.
The root [README](../../README.md) describes the catalog and table architecture.
`docs/tts/` is generated catalog output. Author development documentation only in
`docs/development/`: `scripts/build_site.py` explicitly includes its Markdown files
in both normal and alternate-output builds. Other unplanned output is pruned.
`development` is a reserved site namespace, not a deck owner.

Keep `tts/WIP.md` in place. Update it after changes, recording the problem, evidence,
validation, delivered version and remaining work. Do not move private deployment
notes or credentials into public docs. `tts/deploy.local.json` stays gitignored.
Use an isolated checkout when other work is in progress; preserve unrelated edits.

## Data and performance

- Catalog metadata and rendered UI are separate. Keep the full catalog in Lua, but
  paint only the current ten-row page. Cache filtered/sorted results.
- Decode catalog JSONL incrementally with a small per-frame budget. Commander text
  is a separate small cached file, fetched for the selected deck. Fetch written
  guides only on Read guide; selection must not download guides or card artwork.
- Show commander explicitly requests only the current pinned face. Partners/back
  faces load when paged to. Keep the browser text-only otherwise. Sleeves load only
  opened pages; Inspect prepares and paints its alphabetical grid in small batches.
- Reusing an existing image asset is cheap. Updating the shared native asset list
  caused **437–531 ms** pauses in the measured host session. Submitting an unchanged
  list was similarly expensive. Do not repeat `UI.setCustomAssets` just to refresh
  a registered picture. See the measurement report for limits and raw evidence.
- All image features share one native asset list. Merge existing fonts, Inspect,
  sleeves and commander assets, coordinate their loading, invalidate stale paint
  generations, and restore only current open private sessions afterward.
- `UI.loading == false`, a registered URL and an Image sprite name do **not** prove
  artwork rendered. Check actual pixels. The recurring white image is tracked in
  [troubleshooting](tts-troubleshooting.md#white-or-blank-ui-artwork).
- Use a wall-clock measurement and engine frame counter to measure a full stall.
  The game clock/delta capped a measured 440 ms single-frame pause at 150 ms.

## Lua and UI rules that have caused regressions

Never decode and re-encode the raw spawnable deck objects: TTS numeric `CustomDeck`
keys can become JSON arrays. Parse headers only; retain object JSON bytes intact.
Place commander one in the first slot near the life tracker and commander two in
its second slot. Spawn commanders/tokens face down to avoid revealing the library.

Use `UI.setAttribute(id, "text", value)` for dynamic labels. Keep XML static where
possible. Use Unicode ‹ and › for paging: literal angle brackets and round-tripped
entities have broken native XML parsing. Escape only at actual XML construction
boundaries. Avoid broad wildcard Lua `gsub` over the whole XML: MoonSharp has raised
“pattern too complex.” Use bounded plain-string splices when expansion is necessary.

Preserve original lifecycle/event handlers when wrapping them. Zone scripts may
clear deck context menus; attach Inspect after that work and repair it after deck
replacement/merge/split/load. Delay object lookups until objects exist after load
or rewind. Preserve private seat ownership and cancel stale delayed callbacks when
a deck, seat owner or open state changes. Do not log private deck/search information
publicly. Inspect sorts by name, never discloses library order, and resolves current
GUIDs when retrieving cards.

The native Alt zoom binding applies to game objects, not custom UI Images. Inspect
uses a separate left-side hover preview. Do not claim Lua can insert a menu item at
an exact native Search position or reuse the actual native Search window.

## Images and audio

GitHub Pages serves deck metadata, sleeves, tiles and audio. The pinned card face
URLs currently use the external image service `img.klrmngr.com`; it is not our
cache. Build-time image validation verifies the exported URLs/bytes before output
is written. A successful check cannot guarantee future host availability or native
UI sprite binding. Keep the exact pinned printing/face; do not substitute artwork
or add random query strings to hide rendering faults.

Use the tested WAV music/voice assets and publish their bytes before building a
save that references them. MP3 soundtrack trials produced repeated beeps/voice
sounds in this TTS setup. The Music Player is shared; a globally played custom clip
cannot be made audible only to the active player with this API. Preserve battle
music position by suppressing custom turn/slow-turn voice clips while it is loaded.
See the audio guide for soundtrack priorities, battlefield counting and publishing.

## Validate and deliver

Run the relevant Python and Lua suites, compile changed Lua, validate the expanded
XML, and inspect the source diff. For pictures, test a newly registered face and
cached reopen with a screenshot; also test close/change selection during loading,
partners, shared sleeve/Inspect activity, and an image timeout. Mock sprite
attributes alone cannot certify rendered artwork. Avoid a full table reload merely
to test UI code on a live game. Live patches must preserve browser state, music and
outer event wrappers. The live scripting environment does not expose `load`.

Every delivered test build increments the version and is named
`MTG 6 player Cactuar Ver_vN`. Never overwrite a delivered numbered save or create
an unnumbered Preview. Commit/push source first, then run from the repository root:

```sh
python3 scripts/release_tts.py --notes "Describe the resulting behavior"
```

The release tool reads [the changelog](tts-changelog.md), checks the pushed source
and published audio/tile bytes, builds from the committed source, delivers to Saved
Games and records the next version. Commit/push the generated changelog entry and
update the WIP. Verify the remote JSON/PNG by SHA-256 and retain immutable copies
with their source commit/hash manifest under `.cache/tts-builds/vN/`. Do not commit
large base/build saves, private config, credentials or generated upload receipts.

**Workshop upload requires the owner to select the version.** A saved test build
is not automatically a Steam release. To publish an already delivered version,
use the release tool's `--workshop-only` path with the exact archived JSON/PNG
(see `python3 scripts/release_tts.py --help`). Do not rebuild it under the old number.
Use the authorized ordinary interactive temporary task; keep the PC's PowerShell
execution policy. Require a receipt with the expected Workshop item, Steam result
1, no pending legal agreement, and matching content hashes. Record the receipt in
the local archive and report saved and Steam versions separately.
