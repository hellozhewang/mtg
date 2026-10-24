# TTS troubleshooting and recurring issues

Use alongside the [development guide](tts-development-guide.md) and
[WIP](../../tts/WIP.md). This record keeps recurring symptoms and evidence together;
a build passing unit tests is not evidence that a native image rendered.

## White or blank UI artwork

**Status: recurring native UI rendering issue; root cause not established.**
The preview can show a solid white rectangle even when the pinned URL is valid,
the sprite appears in `UI.getCustomAssets()`, `UI.loading` is false, and the Image's
`image` attribute contains the intended sprite name. Treat those as readiness
metadata, not proof of visible artwork. This differs from a failed HTTP download.

Incidents encountered:

- Early commander/guide previews, including v42: missing/white art led to repeated
  UI revisions. Later performance work removed automatic commander/guide images.
- Sleeve chooser previews after their return in v53: white thumbnails recurred;
  lazy page registration, readiness and repaint coordination were needed.
- v61 opt-in commander previews: Ishai initially stayed white after native loading.
  Explicitly clearing the image and assigning its cached sprite on later native
  frames restored it. That transition also visibly rendered the newly loaded Tana
  face in that session. It did **not** prove a universal fix.
- Owner's subsequent Lord Xander report: Show picture again produced a white
  rectangle. The asset remained registered after the browser was closed. This
  invalidates any claim that v61 eliminated the recurring problem.

Current mitigation: **Show commander** requests only the visible pinned face. A
transparent blank is followed by a minimum 0.2-second settling interval and two
native frames before sprite assignment. This replaces the earlier two-frame-only
wait, which could be just milliseconds at high frame rates. **Reload** repeats the
binding for the same URL without resubmitting the whole shared native asset list.
It is a recovery control, not proof that a download or rendering problem is solved.
No automatic retry loop or arbitrary cache-busting URL is used.

Validation on 2026-10-22: Xander rendered on cached reopen in the running table
before the new settling change, so the owner's original white state was not
reproduced consistently. After applying the mitigation, Xander rendered again and
Davros rendered on its first registration (28 → 29 shared assets). Reload retained
28 assets before that new request. Screenshots/diagnostics are retained locally in
`.cache/commander-white-v62/`. These checks establish those successful trials only;
the recurring issue remains open.

When reproducing, record the saved version, deck/face, whether the asset is new or
cached, open/owner state, shared UI activity, generation and native loading status.
Check the exact pinned URL response (status, image content type and actual bytes).
Capture the actual image before and after recovery. Verify first uncached
registration, cached reopen, alternate face/partner paging and another UI feature
updating assets. A native screenshot is the visual acceptance check; unit tests
cover ordering/cancellation/privacy, not Unity's pixels.

Do not retry by continually calling `setCustomAssets`: even an unchanged list
paused the host for roughly half a second. See the
[performance report](tts-commander-image-performance.md). If artwork remains white,
leave this issue open and retain the failed screenshot/diagnostics.

## Show commander label remains dark despite white attributes

In v63, setting the Button's `textColor` to `#FFFFFF` in both XML and runtime
attributes did not make its native label white in the owner's screenshot. Template
and attribute readback checks passed but failed to establish the rendered color.
The replacement uses an explicit child Text with `color="#FFFFFF"`,
centered inside the Button; its built-in label stays empty. The child does not
intercept clicks. Both Show and Hide rendered white in live screenshots on
2026-10-22 (`.cache/commander-label-v64/show-after.png` and `hide-after.png`).
The Hide render check temporarily hid the popup to expose its underlying button,
without requesting a picture; original visibility was restored. Verify actual
Show and Hide pixels, not only serialized values.

## Card image download says unsupported format UNKNOWN

The initial exported cards used direct `cards.scryfall.io` URLs. Deck metadata
arrived from GitHub, but picture downloads could fail afterward; an image extension
does not mean the response body is a usable picture. Do not describe this as GitHub
failing to deliver a deck or assume every Scryfall URL is universally blocked.
Export pinned images through the validated image service and check the bytes at
build time. See `scripts/tabletop/ttsimages.py`. The service is external, not our own cache,
and validation cannot promise later uptime.

## Deck count appears smaller after Refresh

The original screenshot showed 54 filtered results and 149 total catalog decks.
Bracket/category/owner filters and paging affect the visible count; this alone does
not indicate a truncated `decks.json`. Check active filters, total metadata count
and request/parse errors before blaming file size. The current catalog uses
incremental JSONL parsing rather than decoding a large nested catalog in one frame.

## Browser or Inspect freezes on opening

Large one-shot catalog/deck JSON parsing, full-list UI reconstruction and native
shared asset updates have separate costs. Keep the full data structure but paint
only the current page, cache metadata/results, spread preparation over frames and
keep guide/art downloads on explicit demand. Inspect's native object metadata
should not be re-read on every search keystroke. Profile a full wall-clock stall;
do not rely only on the capped game delta. Cold and cached trials must be separate.

## XML errors or “pattern too complex”

Errors included “Name cannot begin with the '<' character,” invalid character 0x3D,
and MoonSharp “pattern too complex” during Inspect XML updates. Use native-safe
Unicode arrows, safe text attributes, bounded plain-string splices and validated
XML templates. Compile/parse the expanded XML; some templates have multiple roots
and require a temporary wrapper for local parsing.

## Inspect missing from a deck menu

Zone scripts can clear custom context menu entries, and replacement deck objects
can lose them after draw/merge/split/load. It happened on the owner's and Red's
decks; reattaching Inspect restored it after closing/reopening the menu. Preserve
other entries, attach after the zone's menu setup and repair the live replacement
object. Lua cannot guarantee an exact position beside native Search.

## Audio regressions and testing limits

- MP3 theme/Ultima trials produced repeated beep/voice-like sounds; the owner
  confirmed the original WAV files worked. Keep the tested WAVs.
- The native turn beep is separate from our voice clip. Passing a turn to oneself
  does not establish a real transition to another player; test actual seat changes.
- Custom Music Player audio is shared. Do not claim it is recipient-only.
- Battle music uses active-player battlefield counts, excluding library, exile,
  graveyard and commander columns. Threshold tracks loop/pause/resume; preserve
  position by skipping custom voice clips while battle music is retained.

## Workshop uploader cannot connect

Desktop Steam and SteamCMD sessions can replace each other. SteamCMD login alone
is not evidence that the desktop API session is connected. Keep the logged-in
normal desktop client and inspect the uploader receipt/log; do not repeatedly
request login when the actual API connection is the unknown. Preserve the existing
PowerShell policy. A process starting is not an upload: require successful Steam
result 1 for the intended item and no pending legal agreement.

## Errors escape pcall: never index player hands

`Player[color].getHandObjects(i)` (and the base table's `deal(..., 2)`) can throw
"Index was out of range" on this table, and that error is NOT caught by `pcall`: it
propagates, and the broken script state then makes unrelated calls fail too (v66
showed "Function required for context menu" for Inspect right after). To find cards in
hand, ask the zones: `Hands.getHands()` then `zone.getObjects()`. Treat any TTS API call
that takes an index as able to escape `pcall`.

