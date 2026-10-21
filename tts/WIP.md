# WIP: Cactuar table (hand-off)

Living status doc for the Tabletop Simulator table work. Whoever picks this up (Claude or
Codex) reads it first and updates it with every change. The README's "Tabletop Simulator
table" section is the lasting description; this file tracks what is in flight.

Last updated 2026-10-21 (Codex): preparing v41 with full-card text search and an optional Regex mode in Inspect. See `tts/CHANGELOG.md` for released versions.

## v41: full-card text and Regex search (preparing release)

Owner requested regex and searching all card text, including descriptions and types.
Previously Inspect only searched the first line of the nickname. It now searches full
names (including type/mana-value lines), descriptions/rules/stats, tags and alternate
card faces from the container's live and serialized metadata. Rich-text formatting is
stripped; display names and alphabetical ordering remain unchanged. No network lookup
or card movement is needed. Text missing from an import cannot be recovered from its
picture. GM notes, scripts, identifiers, physical indexes and nested container contents
are deliberately excluded from the search corpus.

The **.* button** beside the search field switches between plain text (default) and
Regex for each private Inspector. Regex supports `creature|artifact`, `draw.*card`,
`\belf\b`, ordinary/noncapturing groups, character classes and ranges, `\d/\w/\s`
and their uppercase complements, `* + ? {n,m}`, and line anchors. Literal matching
remains case/accent insensitive; regex normalization preserves escapes such as `\D`.
No lookarounds or backreferences. Invalid patterns show an inline error and clear
results instead of leaving stale cards selectable; correcting the query recovers.

`tts/cactuar_regex.lua` is a bundled boolean Thompson NFA matcher. It does not evaluate
user code or use backtracking. Pattern length, group depth, expansion and per-search
operations are bounded; excessive work reports an error, never partial results.
`scripts/build_tts_table.py` embeds it before Inspect. Search metadata participates
in refresh detection, so description/type edits update matches without a card draw.

Validation: **152 regex checks**, **115 Inspect checks**, and all **217 Python tests**
pass (including table builds and generated-pattern comparisons with Python's regex).
The running Yuna deck has descriptions and multiline names on all **99 cards**.
Live plain-text searches: `creature` finds 58 (including rules-text mentions), `draw`
finds 19. Regex: `creature|artifact` finds 62, `draw.*card` finds 16, `\belf\b` finds 3.
An unclosed `[` returns an inline error and zero results; the previous query/mode
was restored afterward. Physical contents stayed byte-for-byte unchanged.
First-character filtering reduced the tested regex searches from roughly 0.5–0.7s
to 0.22–0.31s in the live TTS runtime. Report: `.cache/inspect-text-live/report.json`.
During the live XML/module replacement, named image registrations remained present
but thumbnails rendered white. Re-registering the existing asset list and rebinding
the visible images restored them, including all unrelated assets. The final capture
`.cache/inspect-text-live/restored.png` confirms card faces and the new search/Regex
controls. This was a live-update recovery; fresh loads use the normal asset registration.

## v40: automatic hover preview (released)

Owner explicitly changed the requested behavior: automatically enlarge cards on
mouse-over; no zoom button/key needed. Hover now shows the face to the left of Inspect,
moving between thumbnails changes it, and leaving the thumbnail hides/clears it.
Click still pins a preview with retrieval actions; hovering another thumbnail dismisses
that pinned preview and clears its retrieval target before showing the hovered card.

Fresh loads no longer register an Inspect Game Key. A no-op `czsZoomKey` keeps old
callbacks harmless when updating a running v38/v39 session; other modules' keys are
preserved. Card order, named image assets, private seat visibility and retrieval guards
remain intact. This request supersedes the earlier native Object Zoom investigation.

Validation: **84 Inspect Lua checks pass**, including automatic enter/exit, stale
exits, old-key callbacks, switching from a pinned preview, retrieval protection,
GUID-less images, filtering and seat privacy. All **11 table-build tests pass**.
The updated module compiles and was applied to the running game; no Inspect sessions
were open during the update. Native zoom-key integration is no longer a release goal.

Released from `0490eba7`: **MTG 6 player Cactuar Ver_v40** and thumbnail delivered to
Saves with matching checksums; v39's canonical save/thumbnail removed. Workshop item
**3822623414** updated with **Steam EResult 1** and the temporary task removed.
Result: `.cache/workshop/3822623414-d747f29fd60942a69f0795892c0a27b3-result.json`.
The delivered save was read back: combined Lua/XML parse, no Inspect key requirement
or registration remains, and all six private hover panels sit to the left.
The running game already has automatic hover; load v40 for the saved revision.

## v39: click preview beside Inspect (released)

Owner's screenshot showed that clicking a card still opened its larger preview over
the Inspect grid. The click preview now anchors immediately to the **left** of Inspect,
with a 12-pixel logical gap, matching the side used by the separate hold-key preview.
The search field and card list stay accessible so another card can be selected while
the preview is open. It remains a child of the private Inspect panel and moves with it.

This is a layout change in `tts/cactuar_search.xml`; preview/retrieval callbacks and
native zoom support are unchanged. Validation: all **11 table-build tests pass**;
the existing Inspect Lua harness passes **82 checks**, zero failures.
Applied the same layout to the running game's six Inspect panels. A live capture
(`.cache/inspect-side-live/after.png`) shows **Bountiful Promenade** enlarged to the
left, with the Yuna-Counters search bar and all four thumbnail columns unobstructed.

Released from `cb94246a`: **MTG 6 player Cactuar Ver_v39** and thumbnail delivered to
Saves with matching checksums; v38's canonical save/thumbnail removed. Workshop item
**3822623414** updated with **Steam EResult 1** and the temporary task removed.
Result: `.cache/workshop/3822623414-a40d86a98d554f998fa648f26124c902-result.json`.
The running game already has the layout adjustment; load v39 for the saved revision.

## Earlier request: existing native Object Zoom binding (superseded by v40)

Historical investigation below. On 2026-10-21 the owner chose automatic mouse-over
zoom instead and dropped the requirement to use the existing zoom key.

Owner clarified after v38: Inspect must follow the player's **existing TTS Object
Zoom binding**, whatever key that player uses. Holding that key enlarges the hovered
card; releasing it closes the enlargement. **No second key to configure and no
unconditional hover-to-zoom.** Keep the previously chosen Workshop-compatible scope.

v38 does **not** satisfy automatic reuse of the existing native binding. Its separate
`Inspect zoom` Game Key is an optional workaround. The earlier completion report
should have distinguished this from hooking native Object Zoom. Successful simulated
press/release callbacks and a screenshot do not establish native-key integration.

Rechecked the supported APIs: XML UI pointer events expose mouse events, not keyboard
modifier state; `Player.Action` has no Object Zoom action; `addHotkey` creates a
separate player-configured Game Key and cannot read or inherit Settings bindings.
There is no documented native-zoom listener/binding getter for the current custom
Inspect panel. Do not claim native integration is complete, ask the owner to configure
another key as though it meets this requirement, or silently substitute automatic hover.
No table-source change or release was made for this clarification. The later temporary
native-window experiment is documented below. Any future solution
must demonstrate real native key-down/key-up behavior, including a remapped native key,
without changing library order or adding client-mod requirements.

References: https://api.tabletopsimulator.com/events/#actions ,
https://api.tabletopsimulator.com/ui/attributes/#event-attributes and
https://api.tabletopsimulator.com/base/#addhotkey .

### Native Search preview experiment after the clarification (not released)

Tested a different architecture: disposable copies with copied metadata sorted A–Z,
then `preview.Container.search(Player.White)` so the engine's actual Search window
could provide native zoom without reading key bindings. The real deck was only read;
no sort, take, shuffle or reconstruction operation was called on it.

Live attempts used a small copied deck and a full alphabetical copied library,
varied locking/interaction/visibility, waited for spawning/custom loading, and called
the documented API from Global and the copied object's script context. API calls
returned without a Lua error, but window captures did **not** demonstrate an open
native Search window. The probe's status string `native Search opened` was assigned
after the API call; it is **not evidence that the client displayed it**. Do not treat
this experiment as a working implementation or a general proof the API is broken.
Actual in-game callback context remains an untested variable; native key-down/up and
read-only extraction prevention were not demonstrated.

All disposable probe containers were removed/expired, the temporary probe script was
removed, and the existing Inspect view was restored. Final cleanup reported
`remainingCopies: 0`, `sourcePresent: true` (`.cache/inspect-native-live/cleanup.json`).
Diagnostic captures are under `.cache/inspect-native-live/`. No table-source change,
new build or Workshop upload was made. Native zoom integration remains unresolved.

## v38: hold a key to zoom Inspect (released)

Owner requested the familiar Alt + hover zoom on Inspect thumbnails. Workshop custom
UI exposes mouse enter/exit but no raw Alt-key state. TTS's **Game Keys** API provides
both key press and release callbacks, so this revision adds a bindable **Inspect zoom**
key. **Each player must bind Inspect zoom to Alt once in Options → Game Keys.** The
binding then persists by label across table loads. It is not automatically bound and
we do not alter client settings or install a client mod. Any chosen key also works.
This implements separately configured hold-to-zoom. It does not inherit the existing
native Object Zoom binding; see the unresolved clarification above. Unconfigured
clients retain the existing click preview.

- Hover a card, then hold the configured key, or hold it before entering a thumbnail:
  a larger face appears beside Inspect. Moving between thumbnails changes the image;
  releasing the key or leaving the card hides and clears it.
- Uses the existing named UI image assets, including GUID-less imported cards. It
  neither selects nor retrieves an object, reloads assets per hover, nor changes
  physical contents or order. Entries without a supported face do not show a blank
  enlarged panel; click preview still provides their name.
- The enlarged panel and children do not intercept raycasts, and sit outside the
  scroll viewport, so zoom cannot cover its own hover target and cause flicker.
- Hover callbacks carry stable identities, not physical indexes. A late exit cannot
  hide a newer hover; filtering, closing, seat changes, membership removal and click
  preview clear/suppress transient zoom. The hotkey is registered once on live reload
  and preserves other Game Keys and native Alt behavior.

Validation: all **216 unit tests pass**; Inspect harness **82 checks, 0 failed**.
Checks include press/release, both hover/key ordering cases, moving between cards,
private seat callbacks, stale events, filtering, removed cards, anonymous imports,
non-selection/retrieval, asset reuse, and hotkey reload preservation. The running game
registered the new hotkey, and callbacks displayed an enlarged **An Offer You Can't
Refuse** from the actual 99-card Yuna deck. A full-window capture at
`.cache/inspect-zoom-live/zoom-live.png` confirms the card is readable beside the list,
without covering the thumbnails. Physical metadata stayed byte-for-byte unchanged;
release/close callbacks clear the preview. The temporary visual check was closed.
Combined real-table Global Lua and generated XML parse. Release details follow below. **Actual Alt binding/input must be
confirmed by the owner after configuring the key**; simulated callbacks alone do not
prove the client's binding or keyboard focus behavior.

Primary API references: https://api.tabletopsimulator.com/base/#addhotkey and
https://api.tabletopsimulator.com/ui/attributes/#event-attributes .

Released from `c33196c7`: **MTG 6 player Cactuar Ver_v38** and thumbnail delivered to
Saves with matching checksums; v37's canonical save/thumbnail removed. Workshop item
**3822623414** updated with **Steam EResult 1** and the temporary task removed.
Result: `.cache/workshop/3822623414-12272c8c6b7248e5af8ff94d2c4986cc-result.json`.
The delivered save was read back: Global Lua/XML parse, all six private zoom panels
and one hotkey are present, and its encoded payload matches the staged upload.
WIP and changelog copied to the PC Desktop. Load v38, then configure **Inspect zoom →
Alt** under **Options → Game Keys**. Existing native object Alt zoom remains available.

## v37: scrolling Inspect (released)

Owner clarified that Inspect should match the native Search screenshot: a narrow dark
window with the container name, one live search field, and four columns of continuously
scrolling thumbnails. The earlier six-column, 12-card paged gallery was too different.
Owner explicitly chose **Workshop-compatible; match the screenshot** after the native
UI limitation was explained. No client mod is involved.

- Replaced paging, the extra toolbar and explanatory footer with the requested layout.
  Soft-white text, a dark neutral background, full-name hover labels, and optional
  click-to-preview remain. The initial 128-cell pool grows for larger containers;
  there is no 128-object limit. Typing does not rebuild shared UI or reload images.
- Uses live deck/bag contents and their actual image URLs, independently of our deck
  catalog. Opening, sorting, filtering and closing copy only metadata, never objects.
  Neither physical indexes nor order-based fallback identifiers reach the UI.
- **Empty GUID issue found in-game:** all 99 cards in the owner's imported Yuna deck
  have empty GUIDs. Earlier Inspect skipped them. Serialized contents now supply
  names, matching textures and duplicate counts. Stable preview tokens use content
  identity, never physical position. Cards without a physical GUID are preview-only;
  retrieval is disabled even if a callback is forged. No cards are taken out or given
  new GUIDs to make inspection work. Identified cards still support Take to hand;
  identified bag objects use Take out beside the bag.
- **Blank WebP UI faces found in-game:** a direct URL rendered white even though the
  same URL works on a physical card. A controlled JPEG/direct versus WebP/named-asset
  comparison confirmed that registering the WebP as a named UI asset fixes it. Inspect
  now merges its faces into the existing asset list, preserves all other modules'
  assets, and retains only faces needed by open inspectors on the next registration.
- **Scroll sizing issue found in-game:** implicit ScrollView dimensions produced an
  oversized white viewport. Explicit 100% width/height fixes clipping and placement.
  Header/search/footer use explicit anchors to avoid layout sizing surprises.
- Growing the grid edits only its serialized XML section, keeping unrelated panels
  and escaping intact. UI reloads restore active views and check seat ownership;
  closing/changing seats during a rebuild cannot reopen a previous private view.

Remaining engine limitations: custom context actions cannot be anchored next to native
Search, and the actual native Search panel cannot be reused/re-sorted by Workshop Lua.
TTS owns menu placement. This is a matching custom panel, not native drag-and-drop.
Multi-card atlas faces and built-in 3D object thumbnails have no supported crop/render
path in the custom Image element; their names remain searchable without an incorrect
whole-sheet image. See https://api.tabletopsimulator.com/object/#addcontextmenuitem ,
https://api.tabletopsimulator.com/behavior/container/ and
https://api.tabletopsimulator.com/ui/attributes/#image-attributes .

Validation: **216 unit tests pass**; the Inspect Lua harness passes **66 checks**,
including 257/400-object containers, live filtering, order preservation, duplicates,
empty GUIDs, matching faces, retrieval guards, asset preservation/bounds, stale
callbacks and closing during asynchronous UI loading. Live Yuna Inspector lists all
99 cards alphabetically. A window capture (`.cache/inspect-live/final.png`) confirms
four clipped scrolling columns, real card faces, soft-white labels and the dark
layout. Live filtering for `swan` produces one match and a byte-for-byte comparison
of the physical deck metadata stays unchanged. All **41 pre-existing UI assets**
are preserved, alongside 99 named faces. The temporary preview was closed after
validation; no physical cards were moved. Combined Global Lua from the real table
and complete shared XML parse successfully.

Released from `72be2e47`: **MTG 6 player Cactuar Ver_v37** and its thumbnail delivered
to Saves with matching checksums; v36's canonical save and thumbnail removed.
Workshop item **3822623414** updated with **Steam EResult 1**; temporary upload task
removed. Result: `.cache/workshop/3822623414-e0e4900b44fc49f28d1ac85d3044f143-result.json`.
The delivered save was read back, its six private scrolling panels and combined Lua
validated, and its encoded Workshop payload checked against the staged upload.
WIP and changelog copied to the PC Desktop. Load v37 for the persistent revision;
the running game's physical objects were not replaced or reordered.

## v36: Inspect naming (released)

Owner asked to call the alphabetical browser **Inspect** and place it directly below
native **Search**. The custom context-menu label and the window title are now Inspect;
all search, preview, privacy, retrieval and order-preserving behavior stays the same.

**Menu placement limitation:** TTS's documented `addContextMenuItem(label, callback,
keep_open)` exposes no insertion index or native-menu anchor. We cannot force this
entry immediately below native Search through the scripting API. Existing native and
custom items are preserved; no duplicate Search entry or replacement menu is added.
Reference: https://api.tabletopsimulator.com/object/#addcontextmenuitem . This part of
the request remains unsupported by TTS, rather than implemented or promised.

Validation: the existing alphabetical-search harness passes **41 checks**, and all
**11 table-build tests pass**. In-game menu placement is engine-owned.

Released from `53bb0a1f`: **MTG 6 player Cactuar Ver_v36** and its thumbnail delivered
with matching checksums; v35's save/thumbnail removed. Workshop item **3822623414**
updated with **Steam EResult 1**; temporary task removed. Result:
`.cache/workshop/3822623414-7e01824406fb46d8966d8a3f9b2306f0-result.json`.
WIP and changelog copied to the PC Desktop. Load v36 to use the renamed menu entry.

## v35: Search A–Z (released)

Owner request: another deck-search window showing cards alphabetically, with a search
bar and without revealing the library order. TTS's native `Container.search` has no
sort parameter, so this is a separate **Search A–Z** item on each deck's context menu.

- Private, per-seat card gallery, 12 cards per page, live case/accent-insensitive name
  search, larger preview and **Take to hand**. Standard Search stays available.
- Reads the actual container's metadata and sorts a copy by name, then GUID for equal
  names. No deck positions are stored/displayed; opening, filtering, paging and closing
  never shuffle, reorder, clone or take cards. Retrieval uses the selected card's GUID.
- Each displayed button sends its GUID, so a late click cannot select a new occupant
  of a stale page slot. Missing/drawn cards are rejected; duplicate names remain distinct.
- The original deck is refreshed while open. Destroyed/collapsed decks close the view.
  Seat changes clear private state immediately; existing Global handlers are preserved.
- UI text is stored in attributes to survive the base importer's XML round-trip, and
  colours follow the owner's soft-white preference. Direct image URLs avoid reloading
  the shared custom-asset list and disturbing other panels.
- Single-card textures (our catalog and rikrassen's importer) show pictures. Atlas
  imports remain searchable by name and support retrieval, but pictures are omitted
  rather than showing the wrong whole sheet. This is a known preview limitation.

Sources: `tts/cactuar_search.lua`, `tts/cactuar_search.xml`; included by
`scripts/build_tts_table.py`. Opening the catalog closes the player's card search.
Validation: the real base table builds with the new module; combined Global Lua and
XML parse. The Lua harness checks sorting, literal searches, accents, unchanged physical
order, duplicates, stale clicks, simultaneous players, retrieval, membership changes,
seat privacy, existing event/menu preservation and reload cleanup: **41 checks,
0 failed**. All **216 unit tests pass**. In-game layout/image checks remain for the owner.

Released from commit `342fb397` with `scripts/release_tts.py --workshop`.
**MTG 6 player Cactuar Ver_v35** and its thumbnail are in TTS Saves, checksum verified;
v34's save and thumbnail were removed. Workshop item **3822623414** was updated with
**Steam EResult 1**, and the temporary task was removed. Result:
`.cache/workshop/3822623414-6d468f4a76194a5aac885dcefb5f73db-result.json`.
WIP and changelog are copied to the PC Desktop. The running game was not changed.
To test: load v35, import a deck, right-click it, choose **Search A–Z**, type a card
name, select a card and use **Take to hand**. Confirm the remaining library retains
its order, previews load, and other seats cannot see the search panel.

## v34: Pirate Cannon starts the game (released)

Resumed the interrupted release from the already pushed commit `eb2af491`. The
repository WIP still described v32, while the changelog and PC showed v33 as the
latest release. No v34 save had been delivered yet.

The build patches the Pirate Cannon to pass the die's winner to `cztStartGame`
instead of setting the turn directly. This resets totals and starts turn 1 even
when the winner already holds the turn and no turn-change event fires. The cannon's
original turn-setting behavior remains as a fallback if the Global call fails.

Released with `python3 scripts/release_tts.py --workshop --notes "..."`:

- **MTG 6 player Cactuar Ver_v34** and matching thumbnail delivered to TTS Saves;
  SHA-256 checks matched. The previous v33 save and thumbnail were removed.
- Workshop item **3822623414** updated; Steam returned **EResult 1**. The temporary
  task was removed, with no execution-policy change.
- Success result: `.cache/workshop/3822623414-e1960e9e209444cfb7c7e457f32381b4-result.json`.
- **214 unit tests pass**. The release verified HEAD was pushed and Pages served
  matching audio/tile bytes before delivery. The release is recorded in
  `tts/CHANGELOG.md`; WIP and changelog are copied to the PC Desktop.

Remaining manual check: load v34 from Saves or the Workshop, fire the Pirate Cannon,
and confirm totals reset and the winner's clock shows turn 1 immediately, including
when that player already holds the turn. The running game was not changed.

## v32 Workshop automation: uploaded successfully

**Goal:** update Workshop item **3822623414** (`workshop_id` in the gitignored
`tts/deploy.local.json`) programmatically, including v32. The owner authorized uploading
to this existing item and chose **automatic launch with a temporary task** on 2026-10-19.
The PC's effective PowerShell policy is already **RemoteSigned**. No execution-policy
bypass or policy change is needed or used; tasks run with ordinary user privileges.

### Current implementation

- `scripts/tts_bson.py` encodes the save as BSON, including int64 `OwnerSteamID`.
  Earlier investigation re-encoded the real base Workshop file byte for byte.
- `scripts/tts_workshop.ps1` uses TTS's own `steam_api64.dll` and the legacy
  ISteamRemoteStorage API. It waits for `BLoggedOn` before writing the cloud files,
  uploads `WorkshopUpload` and its preview, commits the update and polls callback 1316.
  It validates EResult, returned item ID and legal-agreement status, writes its JSON
  result atomically and shuts down Steam's API.
- `scripts/release_tts.py --workshop` replaces the failed SteamCMD path. It discovers
  TTS's DLL, stages and checksums the payload, validates PowerShell syntax, then uses
  a uniquely named, on-demand **InteractiveToken / LeastPrivilege** task. No password,
  elevation, persistent trigger, encoded command or execution-policy change is used.
  It checks Steam's result and removes the task in `finally`; staged files remain for
  diagnosis. Results are also saved under `.cache/workshop/`.
- `--workshop-only` uploads the **existing delivered save and thumbnail** for the current
  version. It does not rebuild from a newer HEAD, deliver new files, increment the
  version or edit the changelog. The next attempt is:

  ```sh
  python3 scripts/release_tts.py --workshop-only
  ```

### Live attempts and resolution

1. SteamCMD `workshop_build_item` failed with **"no workshop depot found"**. TTS's
   legacy single-file Workshop format needs the RemoteStorage API instead.
2. `schtasks /Create /XML` rejected UTF-8 task XML as **"unable to switch the encoding"**.
   Writing UTF-16 XML with its matching declaration and BOM fixed task registration.
3. The task successfully ran the native Steam API uploader in the logged-in session.
   Steam returned **EResult 21 (not logged on)** for item 3822623414; no success was claimed.
4. Added a 60-second callback/connection wait before any cloud writes. The subsequent
   attempt still reported **Steam client is not connected to Steam servers** and
   stopped before uploading. Its temporary task was removed.

5. Owner confirmed desktop Steam looked online. Its `connection_log.txt` showed
   **Session Replaced at 14:28:56**, followed by **not auto reconnecting**. SteamCMD's
   successful login did not reconnect the desktop client's session.
6. After the owner closed SteamCMD and restarted desktop Steam, the exact same
   programmatic command succeeded: **Steam EResult 1**, returned item **3822623414**.
   The temporary task was removed. Success result:
   `.cache/workshop/3822623414-201907b61d3a4f5e9552ec49332d98b1-result.json`.

**Released:** v32's existing delivered save and thumbnail were uploaded to item
3822623414 with its v32 changelog note. No v33 was created; no local save was rebuilt
or changed. The original table source is still commit `413a5e2d` (recorded by
`e9e1f8b8`). Only the release helper and its documentation/tests are being changed.
**Remaining manual check:** load the subscribed Workshop item in TTS and confirm v32
and its browser refresh behavior. Steam's successful response confirms the upload;
it does not replace an in-game test.

Validation: **213 unit tests pass**, including failure-result validation, task cleanup,
unchanged policy, and uploading the exact delivered bytes without rebuilding or
advancing the version. PowerShell parsed successfully and the uploader ran on Windows.

### Notes for recovery

- `.cache/workshop/3822623414-before.json` is the backup from before the first attempts.
  Encode it with `tts_bson.encode()` to restore the earlier item if needed.
- `.cache/workshop/*-result.json` holds each completed live uploader result. Staged PC
  folders are under the deployment config's `workshop_dir` (default `C:\cactuar-workshop`).
- EResult **15** means access denied; **21** means Steam isn't logged on/connected.
- Public `GetPublishedFileDetails` returned **9 (file not found)** before and after
  the upload, so unauthenticated metadata cannot currently verify this item. The
  authenticated Steam API confirmed its update. Do not change the target automatically.
- Claude's earlier approval check rejected a launch including `ExecutionPolicy Bypass`.
  The owner subsequently chose the temporary task; the implementation respects the
  existing policy instead of bypassing it.
- `C:\steamcmd` is left in place; it is no longer used by the release tool.
- PC address, account and paths stay in `INTERNALS.md` / `tts/deploy.local.json`, never
  in committed code.

## v30 release: deeper radio announcer (delivered)

The owner asked Codex to integrate the latest clips and deliver a new build for testing,
using the updated release instructions. Both source WAVs use the deep radio revision
below (-5 semitones from the neural voice, three below v29), with the same words and
timing. The audio generators now live in `scripts/`; assets remain in `tts/sounds/`.

Released from commit `856d1f8b` using `scripts/release_tts.py`, after publishing and
verifying the exact audio and tile bytes on Pages. **MTG 6 player Cactuar Ver_v30**
and its thumbnail are in the owner's TTS Saves folder, with matching SHA-256 checks.
The tool removed v29's save and thumbnail and copied this WIP and the changelog to
the Desktop. The release notes are recorded in `tts/CHANGELOG.md`.

Validation: **204 unit tests pass**; the catalog build and `--check` pass with 4,344
image URLs accepted by the verifier. Generated audio equals the source WAVs. The
save's versioned audio URLs end in `a4d85e5e` (5-minute) and `e1ddc601` (10-minute),
and it uses Pages with no LAN audio override. No running game or Workshop upload was
changed. Load v30 to test; chat `announcer test` plays the 5-minute clip. Owner listening
and in-game approval remain.

## Announcer voice revisions

**Read `tts/sounds/README.md` first:** it covers how to generate and measure clips, the loudness targets, and the order for publishing them.

### Audio generators moved to scripts — 2026-10-19

Per the owner’s convention, both audio generators now live in `scripts/`:
`make_neural_announcer.py` and the legacy `make_announcer.py`. Default generation
and measurement still use `tts/sounds/`, resolved from the repository location
regardless of the working directory. Generator commands and references below and
in the audio README are updated.

### Latest audio revision: substantially deeper radio voice — 2026-10-19

The owner said the first radio voice was still not deep enough. The generator now
uses **-5 semitones from the neural voice**, three semitones deeper than the preceding
radio pair, with tempo preserved. Body EQ is +3.5 dB at 160 Hz. Everything else stays
the same: words, preset blend, minimal reflection, file names, PCM format and level checks.

| Source WAV | Duration | Project meter | Independent EBU | True peak |
|---|---|---|---|---|
| `slow-5min.wav` | 2.96 s | -12.5 LUFS | -12.45 LUFS | -0.75 dBTP |
| `slow-10min.wav` | 3.10 s | -12.8 LUFS | -12.95 LUFS | -0.55 dBTP |

SHA-256: 5-minute `a4d85e5eb6c373c987e1f8e2cb23fe5d6391b398f1058099a23c3abe1ccdf301`;
10-minute `e1ddc60198d5cea49ddde1269bc9433755c2d0550366fc83fcf2e74ef63ecdd9`.
Validation: 201 unit tests pass; both WAVs meet duration/format/loudness/true-peak checks.

Listening copies: **Cactuar announcer (deep radio)** on the PC Desktop and under
Downloads. The earlier radio and neural folders remain for comparison; the preceding
source WAVs are backed up at `~/.cache/mtg-announcer/previous-radio-20261019/`.
Owner audition still determines the preferred depth. Claude handles the next table
version; no game/table code, `docs/` audio, save, commit or push changed.

### First radio revision — 2026-10-19 (superseded)

After the first neural pair, the owner asked for a more radio-like sound and clarified
that the voice should be **a little deeper**. The source WAVs and neural generator now
apply a two-semitone pitch reduction with tempo compensation, warm 180 Hz EQ, light
presence and an 8.5 kHz roll-off. Echo is reduced to one very quiet reflection; the
low hit is quieter. The base voice is still the same local Kokoro preset blend below.
Words, file names, PCM format, loudness targets and playback/off-switch code are unchanged.

| Source WAV | Duration | Project meter | Independent EBU | True peak |
|---|---|---|---|---|
| `slow-5min.wav` | 2.96 s | -12.5 LUFS | -12.45 LUFS | -1.15 dBTP |
| `slow-10min.wav` | 3.11 s | -12.6 LUFS | -12.63 LUFS | -0.55 dBTP |

SHA-256: 5-minute `f25b95f561bcb4bc33e466283df2a1084d6446d2b49967502e8118e3607a379b`;
10-minute `c7478eff3387d07bae0a6030f2f4a038c2d4e1589c81b4c01fb63cdc15f954c9`.
Validation: 192 unit tests pass; WAV format/duration, the project meter and independent
EBU loudness/true-peak checks pass. Owner audition/in-game approval remain.

Listening copies are supplied separately in **Cactuar announcer (radio)** on the PC
Desktop and under Downloads, preserving the earlier **Cactuar announcer (neural)**
pair for comparison. Earlier source audio is backed up outside git at
`~/.cache/mtg-announcer/previous-neural-20261019/`. Claude still owns the next table
build and publishing. No game/table code, save, `docs/` audio, commit or push changed.
The earlier neural handoff below records the first pair; its hashes are historical.

### First neural audio handoff from Codex — 2026-10-19 (superseded by radio revision)

The owner asked Codex to **generate the sounds only**; Claude will create the next
table version. The two source WAVs are now generated with local **Kokoro-82M v1.0**,
`kokoro-onnx 0.6.1`, blending **70% `am_michael` / 30% `am_fenrir`**. No account,
paid service, API key, reference recording or voice cloning was used.

- `slow-5min.wav`: 3.02 s, project meter -12.5 LUFS; independent EBU -12.74 LUFS,
  true peak -0.90 dBTP. SHA-256 `d4c27e9f789f61a5ff82e7a063f5d2c11ccd92a3ea1ce632dfc004bc78ad6f6d`.
- `slow-10min.wav`: 3.17 s, project meter -12.9 LUFS; independent EBU -13.03 LUFS,
  true peak -0.55 dBTP. SHA-256 `5fdc2f5e732136b67722d86a4ac24f03c4ee2085382d2cd13383efc4d0e49a3d`.
- Same spoken words and filenames, 22050 Hz mono PCM16 WAV. The second line's
  exclamation mark only steers delivery; the displayed wording need not change.
- Regenerator: `scripts/make_neural_announcer.py`, using the existing
  `make_announcer.clarity()` and `master()`, lighter reflections, quiet bass accent,
  measured loudness trim and an independent true-peak guard. The old Ralph generator
  is preserved; **do not run its default recording command** over these new clips.
- Runtime/model environment is outside the repo at `~/.cache/mtg-announcer/`; use
  `~/.cache/mtg-announcer/venv/bin/python scripts/make_neural_announcer.py`.
  Model SHA-256 `7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5`;
  voice-bank SHA-256 `bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d`.
- Previous uncommitted Ralph clips were backed up outside git at
  `~/.cache/mtg-announcer/previous-ralph-20261019/` before replacement.

Owner audition and in-game testing remain; these measurements do not establish the
owner's preferred voice character. Listening copies go on the PC Desktop in
`Cactuar announcer (neural)`. No table/game scripts, saved table, timer/off-switch,
`docs/` audio, commit, push or Workshop upload changed. Claude should copy the source
clips to the published sounds folder, get approval, and follow the README's
publish-before-loading-new-URL order for the next build.

Validation: **192 unit tests pass**, both files have valid mono PCM16/22050 Hz WAV
headers and roughly three-second durations; the existing `--measure` and independent
FFmpeg EBU/true-peak measurements pass the brief. Listening copies are also supplied
under the PC Downloads folder, with SHA-256 checked against the source files.

The original brief and earlier placeholder notes below are retained for context.

**Asked by the owner on 2026-10-18.** The slow-turn announcer works, but its voice clips
are placeholders, and the owner found them hard to understand. Make them clear and in
character: a real radio or arena announcer, like the "Double kill!" voice in shooters.

What exists (pushed in 0fe29d2f):
- **Lines.** Keep the meaning, and keep the on-screen text in `CZT.lines` in sync:
  - `tts/sounds/slow-5min.wav`: "C'mon bro, what's taking so long?"
  - `tts/sounds/slow-10min.wav`: "Bruh, wake me up when you're done."
- **Generator:** `scripts/make_announcer.py`. It's macOS `say`, the classic voice Ralph
  pitched down, at 22 kHz mono, with a sub-bass boom, three echo taps and a `tanh` limiter. The
  low-quality voice and the distortion are what make it muddy, so don't build on them.
- **Playback:** `tts/cactuar_turns.lua`, function `cztAnnounce`, plays
  `CZ.base .. "sounds/<file>"` through `MusicPlayer.setCurrentAudioclip` + `play()`.
  `CZT.soundBase` overrides the base for testing from the Mac's catalog server
  (`http://192.168.0.100:5588/tts/`). In chat, `announcer test` plays the 5-minute line.

What to do:
1. **Pick a voice engine. Ask the owner before anything that needs an account or costs money.**
   Researched options:
   - **ElevenLabs:** the most character, with announcer and commentator voices in its library.
     It needs a free account plus an API key. `ELEVENLABS_API_KEY` isn't set.
   - **OpenAI `gpt-4o-mini-tts`:** steerable with `instructions` ("hype esports announcer,
     booming, mocking"). It needs an OpenAI API key, which a ChatGPT login doesn't provide.
     `OPENAI_API_KEY` isn't set.
   - **Chatterbox:** local and MIT-licensed, with an expressiveness or exaggeration control.
     It runs on the M4 through MPS, but needs Python 3.10+ (the system has 3.9.6) and PyTorch.
   - **Kokoro:** local, Apache-licensed, very clean but calm.
   - Don't clone a real person's or a game's announcer voice.
2. **Make clean clips.** No distortion; at most a light arena reverb. Use 44.1 kHz, normalised,
   about 2–4 s each, with a short silence at the start. Keep the file names, or update
   `CZT.lines`.
3. **Format:** WAV is proven: the owner heard the current clip in game. If you switch to
   `.mp3`/`.ogg` to save size, test it in game first. `ttsdecks.SOUND_TYPES` already publishes
   all three.
4. **Replace the generator,** or add a new script beside it, so the clips can be regenerated.
   Commit no API keys, and print the voice/model used.
5. **Rebuild and check:** `python3 scripts/build_site.py`, which copies the clips to
   `docs/tts/sounds/`. Run `python3 -m unittest discover tests`; `test_announcer_clips_are_published`
   expects both `.wav` names and `RIFF` headers, so update it if names or format change.
6. **Test in the owner's game, then hand them the files to judge.** Set `CZT.soundBase` to the
   Mac (see `INTERNALS.md` for the External Editor client) and type `announcer test`.
   Also put both clips in the PC's Downloads so the owner can listen.
7. **Publish:** clips are fetched at runtime, so a push is enough, with no table rebuild or
   Workshop upload. Commit and push only when the owner says so.

Also worth fixing while there:
- **The clip replaces whatever music the table is playing.** Capture
  `MusicPlayer.getCurrentAudioclip()` before playing and restore it afterwards. In a test,
  `getCurrentAudioclip()` reported the table's playlist track right after
  `setCurrentAudioclip`, yet the owner heard the clip; check how the player behaves.
- **Totals reset when a save is reloaded:** `CZT` isn't saved. Optional; ask the owner.

## Current status

- **Published 2026-10-18 in 93748154** (all of Codex's v3–v10 work and Claude's v11–v13).
  Pages serves `decks.json` with 3 backs (standard, cactuar, girly_pop), and TTS's client
  gets HTTP 200 for the pictures. The running game was switched back to the Pages
  `CZ.base`. Left to do: upload the v13 save to Workshop item 3822623414 (still v1).
- **Current build: v13** = v12 plus a guard: when the deck list has no `backs` (Pages
  before the push), the Card back button is disabled and a click is ignored.
- v12 = v11 plus a **Card back** menu in the details column. Pick
  Standard or any picture in `tts/backs/` (ships with `cactuar.jpg`); the choice is per
  player and applies to the next deck loaded. **Needs a push to work from the saved
  table**: until then Pages has no back list and the button stays disabled. The running
  game was patched to serve the Cactuar back from the Mac's catalog server for testing.
- v11 = v10 (off-white `#E2E5EA` text, regular-weight names, v7 layout)
  plus three changes. Tokens spawn in the battlefield beside the first commander slot;
  v1–v10 dropped them on the Life Tracker. New panels sort newest first. The sort row is
  Tier / Name / Newest, with no Owner button; the Owner *filter* stays. Applied to the
  running game, and a versioned save and thumbnail were delivered to the owner's PC.
- **Two agents, one set of files.** On 2026-10-18 Codex (v9, v10) and Claude (v11) worked
  on `tts/` at the same time. Nothing was lost, because Claude's edits landed after
  Codex's, but don't run both on this work at once. Re-read this file and
  `git status` before editing.
- **149 decks**, with an index of about 51 KB. The previously reported 54 was a filter
  result, not a download cap or an oversized JSON file.
- **Image host: third-party `img.klrmngr.com`**, the cache used by the other importer.
  We pin printing UUIDs and faces; we do not own that host or freeze its image bytes.
  Our SQLite verification records support conditional requests, not offline availability.
  The full build-time scan passed 4,272 URLs, and its repeat passed 4,272 HTTP 304s.
- **Publication:** committed and pushed in 93748154. The Workshop item still holds v1; the
  owner must upload a v13 save for subscribers.
- **Remaining manual checks:** Workshop publication, tile click/size/facing feedback,
  and full live loading across all six occupied seats. Automated placement tests cover
  all six; do not confuse those with six separate live playtests.

## v28: louder announcer clips (TEST build delivered; final build after the push)

**v28 as delivered is a test build.** The owner wanted to test before any push, so
`CZT.soundBase` is set to the Mac's catalog server (`http://192.168.0.100:5588/tts/`) in the
saved Lua. That edit was made by hand to the built JSON, not in the repo. The clips play only on
the owner's LAN; decks still come from Pages. After the push, build the next version (v29) with
no soundBase, so every player hears the clips from Pages.


The owner found the announcer too quiet with every TTS volume slider (Game, MP3) at maximum,
so the clips themselves were the problem. A peak normalise left the voice at about -18.6 LUFS
(K-weighted, gated), because the sub-bass boom set the peak. `scripts/make_announcer.py`
now:
- turns the boom down to sit under the voice;
- high-passes the voice at 140 Hz and adds a +6 dB shelf above 2.2 kHz for clarity;
- compresses (4:1 from -26 dB);
- runs a 4 ms look-ahead limiter with 18 dB of drive into a -0.5 dBFS ceiling.

The result is about -12.5 LUFS, 6 LU louder, with no clipping. More drive gains little: 24 dB
measured only 0.4 LU louder. The voice is still the placeholder `say` Ralph; the Codex TODO
above still stands, and its new clips should go through the same `master()`.

`build_tts_table.py` now adds `?v=<sha256[:8]>` to each `sounds/<clip>` URL in the Lua,
because TTS caches audio by URL as it does pictures.

**Order matters:** push the new clips to Pages BEFORE anyone loads v28. Loading it first would
cache the old clip under the new URL.

## v27: new tile art, versioned tile URL (delivered)

The owner replaced `tts/cactuar-tile.jpg` with painted art in a gold frame ("CACTUAR DECKS";
f7a5b02a, already pushed and on Pages). TTS caches images by URL, so tables built with the
plain `…/tts/cactuar-tile.jpg` would keep the old picture. `build_tts_table.tiles` now
appends `?v=<sha256[:8]>` of the source image (currently `?v=15a4e1b1`, HTTP 200 on Pages),
the same scheme the card backs use. The test checks the pattern. **MTG 6 player Cactuar
Ver_v27** delivered; v26 removed. It also carries everything from v26.

## v26: restore after the objects exist (delivered, not live-applied)

v25 still showed 0 after a rewind, even with cards moved in between. Live: the tile memo
held fresh state (written every 10 s), but `noSavedState` was true at load.

`cztSaved()` ran at the script's top level. After a load or rewind that's before the
objects exist, so `getObjectFromGUID("c4c7a1")` was nil. The fallback
`Global.script_state` is empty after a rewind, so the game looked new. The earlier probe
"survived" only because it was read later, over the External Editor API.

- `cztRestore()` now runs once, at attach. By then the six Timers have their buttons and
  the tiles exist. It does all the restoring: started, totals, turn numbers, and the
  running turn continued.
- `onPlayerTurn` doesn't run the first-turn reset until `CZT.restored`.
- The live-patch path sets `restored = true`.
- Test: with objects unavailable at load, nothing is decided; once the tile exists the state
  is restored. The old code fails this. `tests/test_cactuar_turns.lua` 1348 checks.
- **Still unverified in game:** load v26, start, play about 30 s, rewind one step.

**MTG 6 player Cactuar Ver_v26** delivered; v25 removed.

## v25: the timer state lives in the tile's memo (delivered, not live-applied)

v24 still reset after rewinds ("always resets to 0", "my turn timer went back to 0").

**Experiment:**
1. Started the timers in the owner's solo session and confirmed `Global.script_state` was
   written.
2. Wrote `probe-1792403552` to tile `c4c7a1`'s `memo` and GM notes.
3. The owner rewound.

**Result:** the memo and GM notes kept the probe; `Global.script_state` was empty
(`noSavedState = true`). The base Timers' own `turnN` looked reset too.

**Changes:**
- `cztState()` stores: `cactuar_started`, `cactuar_turn_totals`, `cactuar_turn_numbers`
  (every seat's base `turnN`), and `cactuar_turn = {color, elapsed}` (the running turn).
- `cztPersist()` writes that to the tile's memo, and to `Global.script_state`.
  `cztSaved()` reads the memo first.
- **On load or rewind:**
  - If the saved running turn is the current one, `CZT.start = now - elapsed`, and
    `elapsed` comes out of that seat's stored total so it counts once.
  - Lines already announced this turn are marked.
  - At attach, the base `turnN` values are restored. After `cztStartTableClock`, the
    current Timer's `tdiff` is set to `elapsed`, so the base clock continues.
- The old probe text in the live session's tile memo is harmless. A fresh v25 table's tiles
  have no memo.

Tests: `tests/test_cactuar_turns.lua` 1335 checks. A tile stand-in's memo now carries the saved
state (`setSaved`). Reload continues the turn at 0:20, the total isn't double-counted and the
base clock `tdiff` is 20. The full suite has 2 failures that aren't ours:
`ratdos/Kwia-Lifegain` is a Discord build in progress, with no theme or tier yet.
**MTG 6 player Cactuar Ver_v25** delivered; v24 removed from Saves.

## v24: timers survive rewinds (delivered, not live-applied)

After a rewind the group "ended up in turn 1 again". Live (v23): `Global.script_state` was
empty. Rewind snapshots don't call Global `onSave`, so `cactuar_started` was lost. The
table loaded as "waiting", and the next turn change ran `cztFirstTurn`, which resets
everything to turn 1.

- `cztPersist()` writes the same JSON as `onSave` (now `cztState()`) to
  `Global.script_state`. It runs on every turn switch, first turn, new game, resume and
  roll reset, and every 10 ticks while started.
- **Safety net:** when a loaded table has no `cactuar_started` key (`CZT.noSavedState`) and
  any base Timer's `turnN` > 0 (`cztTurnsPlayed`), attaching runs `cztResume()` instead of
  waiting. The base Timers persist `turnN` in their own `script_state`. The build sets
  every Timer's `LuaScriptState` to "0", so a fresh table always waits.
- The rewound game's real turn numbers weren't recoverable. Each seat's turn number can be
  corrected with the base Timer's turn button (click +1, right-click −1).
- Tests: suite OK; `tests/test_cactuar_turns.lua` 1279 checks (state written without a save;
  a no-state snapshot with counted turns resumes and keeps `turnN`; a fresh table waits).
  **MTG 6 player Cactuar Ver_v24** delivered.

## v23: timers start on the first player's turn (delivered, not live-applied)

v22 waited for a counted die roll. In practice the group just started playing (the turn
passed to Red), so nothing ever started. The owner: "timer should start as soon as its
first players turn".

- `onPlayerTurn`: when the game isn't started and the turn goes to a seated colour more
  than 5 s after load (guarding against load-time events), `cztFirstTurn(color)` runs.
  It zeroes every total and every base `turnN`, re-enables the base clocks and times this
  turn.
  - The Timer object's own `onPlayerTurn` may run before or after Global's, so a
    `Wait.frames(…, 1)` then sets that Timer's `turnN` to 1, starts its clock if needed, and
    shows "turn 1".
  - It broadcasts "X takes the first turn. Timers started."
- Later turns just switch. The die roll (`cztStartGame`) is still a new-game reset, and
  `timers on` still resumes a waiting game.
- Tests: `tests/test_cactuar_turns.lua` 1241 checks: no start from a load-time event; first
  turn = turn 1 even after setup turns; other seats at 0; later turns switch.
  **MTG 6 player Cactuar Ver_v23** delivered.

## v22: the die rebuilding itself is not a roll (delivered, not live-applied)

The owner loaded v20 for a new game and saw "turn 1 / 0:22 / total 0:25" before anyone
rolled. Live: started=true, starting about 3 s after the script loaded, with empty
script_state.

Cause: the "Who goes first?" die script (0rganics) calls `setCustomObject` +
`self.reload()` on load and on every `onPlayerChangeColor`, to put seated names on its
faces. TTS reports that as `onObjectRandomize`, and `cztRolled` treated it as a roll and
started turn 1. Mid-game, a seat change could therefore restart the game.

Fix: `onObjectRandomize` starts a game only if the randomizing `color` is one of the six
seats, and only more than 10 s after the script loaded (`CZT.loadedAt`, kept across live
patches). Tests: a rebuild with no player, a Grey roll and a roll in the first seconds all
start nothing. `tests/test_cactuar_turns.lua` 1197 checks. **MTG 6 player Cactuar Ver_v22**
delivered.

## v21: resume timers without a roll (delivered; the running match was resumed live, on request)

- **Rewind lost the timers.** TTS Rewind restored a snapshot from just after Claude's
  mistaken "waiting for the roll" reset, where `cactuar_started` was false, so every clock
  went idle. Rolling would restart the game at turn 1 and pass the turn.
- **Fix:** `cztResume()`, run by the chat command `timers on`. When the game isn't started,
  it starts timing the current turn, re-enables the base clocks, starts the current player's
  clock and keeps its `turnN`. It broadcasts "Timers resumed from the current turn." and
  does nothing if the game is already started.
- **Live:** the owner asked "did you fix it?", and the same resume ran in the match. White
  showed `0:04`, turn 1, and every seat's total.
- **Open issue, not fixed:** other players' clicks on the base's Global-owned buttons fail
  on the host. The errors are `Error Network Remote LuaObject/ClickButtonRPC … Exception has
  been thrown by the target of an invocation`, and `Lua Error <playerScry>: Index was out of
  range … Parameter name: index`.
  - Hover + typing a number works, the host's own clicks work, and Life Tracker buttons
    (object-owned) work.
  - It started after this session's live patching. That's the suspected cause, unproven.
  - Recommended fix: save the match, upgrade that save's scripts with `build_tts_table.py`
    (it re-appends v21 and keeps the objects and state), and load it.
  - A recorder wraps `playerDraw`/`draw1` in that session (`CZ_DEBUG`, `CZ_ORIG`). It
    disappears on reload.
- Tests: suite OK; `tests/test_cactuar_turns.lua` 1188 checks. **MTG 6 player Cactuar Ver_v21**
  delivered.

## v20: hidden information (delivered, not live-applied, not pushed)

The owner: "change the logging so … other players can't see what they loaded and also put
the commanders face down; just say player loaded a deck in the chat."

- The load broadcast is "<name> loaded a deck." It used to name the deck and commander.
- Tournament logs keep every action and count, without deck names, commanders, draft
  offers, rolls or search text. For example: "switched to Draft (5 decks dealt)",
  "REDREW the draft (redraw #1, 5 new decks dealt)", "REROLLED (reroll #1)",
  "selected a deck", "searched the list", "LOADED a deck (card back X)". `czNames` was removed.
- Commander(s) and the token pile spawn face down (rotation z 180); the library already did.
- Tests: suite OK; `tests/test_cactuar.lua` 1100 checks.
- **MTG 6 player Cactuar Ver_v20** delivered. NOT applied to the running match: per the
  live-game rule, waiting for the owner.

Also answered: the owner's Tundra is unpinned (`1 Tundra`), so it's Scryfall's default,
Vintage Masters 322. The website shows the same printing; pin a printing to change it.

## v19: fixes from the first live game (delivered, live-applied, not pushed)

The owner's first real game: EggRolls, Digitalstealth, Kupo, Ratdos and Em0k1ller.

- **"Purple couldn't mulligan" / "clicked the Cactuar thing and it didn't load".**
  1. Kupo, in Purple, loaded Sheoldred-Drain. v11–v18 put the token pile into the
     battlefield, inside `data.Purple.playmat`.
  2. The base `playerMulligan` refuses on a single click while any Card or Deck is in the play
     area, so the mulligan failed.
  3. Kupo moved to Yellow and loaded again; the Purple copy was deleted. The other seats had
     dragged their tokens onto commander slot two by hand.

  Fix: tokens go to slot two, or the exile spot for partner decks. The playmat zones were
  checked live: they end left of the column at every seat.
- **A seat's browser carried the last player's state.** Em0k1ller saw Kupo's selection and
  "Loaded Sheoldred-Drain". `czState` now records the seat's `steam_id` and starts fresh
  when a different player sits there. `czOpen` clears a stale search box and status.
- **Timers auto-started on load.** The owner wants nothing to run until the "Who goes first?"
  roll.
  - `CZT.started`, saved as `cactuar_started`. Before the roll: nothing is timed, there's no
    announcer, no totals are shown, and the base Timers are kept quiet (`timerOn = false`,
    blank labels).
  - `cztRolled(die)` resets everything and waits for the die to rest (`Wait.condition`, 15 s).
    It reads `getRotationValue()`, a Steam name or an empty seat's colour (`cztDieColor`).
    "Roll again…" starts nothing.
  - `cztStartGame(color)` zeroes every base `turnN`, re-enables the clocks and sets
    `Turns.turn_color`, or starts both clocks by hand if it's already that player's turn.
    The broadcast reads "New game! X goes first. Turn 1."
  - A started game, loaded or live-patched, switches the base clocks back on and re-shows
    the running clock's turn number (`cztStartTableClock`).
- **Live incident (Claude):** while live-applying the "wait for the roll" change I reset the
  running game, which had four players. That cleared the totals and switched the base clocks
  off. Resuming then switched nothing on, because the new `CZT.timers` was still empty, so
  "the turn number is not showing". It was fixed by the attach-time re-enable above, applied
  live. Green (Em0k1ller) showed `1:10`, turn 1, with a total; earlier totals were lost.
  **Before any live patch that changes game state, check whether a game is in progress
  (`Player.getPlayers()`, decks on the table) and ask the owner.**
- Tests: suite OK; `tests/test_cactuar.lua` 652 checks (token spots, seat change);
  `tests/test_cactuar_turns.lua` 1168 checks (roll start, roll again, saves, clock re-enable).
  **MTG 6 player Cactuar Ver_v19** delivered to Saves.

## v18: the total label is actually drawn (delivered, live-applied, screenshot-verified)

After v17 the owner reset and rolled, reached turn 2, and still saw no total. Live state:
the White Timer's button 7 held "total 0:39", yet nothing was drawn.

Screenshots of the TTS window (method below) settled it:
- Moving the label above "turn" with alpha 100 made it visible.
- Back below the clock with alpha 100: visible ("total 2:36" under "2:37").

So the alpha was the problem; the position was fine. `CZT_LABEL.alpha = 100` is used for
create and restyle, and the test checks `font_color[4] == 100`. Applied live to all seats;
the screenshot shows "turn 2 / 3:18 / total 3:16". **MTG 6 player Cactuar Ver_v18**
delivered. Not pushed.

**Screenshot method** (no tooling kept in the repo):
1. A PowerShell `PrintWindow(hwnd, hdc, 3)` of the window whose title matches
   "Tabletop Simulator" saves a PNG to `%TEMP%`.
2. It must run in the logged-on session: create a one-off
   `schtasks /Create /TN cz_shot /TR "powershell … -File …" /SC ONCE /ST 23:59 /IT /F`,
   then `/Run` and `/Delete`. Give every `schtasks.exe` call `< /dev/null`, or it swallows
   the rest of the SSH stdin script.
3. Stream the PNG back with `cat` (3440×1440) and crop with `sips -c H W --cropOffset Y X`.

## v17: the total sits under the clock, always, and survives reloads (delivered and live-applied)

Owner feedback:
- A v16 screenshot of the Red seat showed "turn 1 / 0:02" but no total.
- "the total timer should just stick on the table until you reset".

Causes and fixes:
- **Hidden under the Life Tracker.** The base clock ("Timer", z ±2.86) sits right above
  the heart. Our label at local z +0.95 landed on the heart, whose XML overlay covers it.
  `build_tts_table.TIMER_Z = 1.96` moves all six Timers toward the middle strip, which
  was checked clear at every seat. It's absolute, so rebuilds agree. The label stays at
  local z +0.95, directly under the digits.
- **Always visible:** every seated player's total shows, from "total 0:00", whether or not
  it's their turn. Seats with banked time show it even when empty. `cztShowAll` runs
  every 5 ticks to follow players sitting and standing.
- **Saved:** Global `onSave` (the base defines none; `CZT_BASE.save` is captured anyway)
  writes `{"cactuar_turn_totals": {...}}`, with the running turn included. A fresh load
  restores it from `Global.script_state`; an unreadable state starts empty. Only the
  "Who goes first?" roll resets it.

Live: Timers moved with `setPosition` and the script re-run. The Red seat showed clock
` 2:33`, turn 1, "total 2:33". Tests: suite OK, including the timers moving and staying
put on rebuild; `lua tests/test_cactuar_turns.lua` 1056 checks (seated 0:00, save
round trip, bad save). **MTG 6 player Cactuar Ver_v17** delivered. Not pushed.

## v16: both turn timers visible after a load (delivered and live-applied)

The owner loaded v15 and saw neither timer. Causes:
1. **The base Timer's own clock starts only in its `onPlayerTurn`.** A game loaded mid-turn
   (turns on, the turn already White's) never gets that event, so the digits stay blank
   until the turn passes.
2. **The total label was there** ("total 0:32") but small (font 240, alpha 0.85), and the
   owner's hover tooltip covered it.

Fixes in `tts/cactuar_turns.lua`:
- `cztStartTableClock()` runs once after attaching. If the current player's Timer has no
  `timerID`, it calls the Timer's own `onPlayerTurn` with `Player[color]`. When the
  saved `turnN` was above 0, it then restores `turnN`, calls `updateSave` and relabels
  button 6, so a reload doesn't count an extra turn.
- The label is now `CZT_LABEL` (font 320, alpha 1). An existing label from an older
  version is restyled with `editButton`.

Live: applied; the White Timer showed ` 0:04`, "turn 1", "total 2:10". The total had
counted from the load, and the base clock from the patch. Tests: suite OK;
`lua tests/test_cactuar_turns.lua` 1023 checks. **MTG 6 player Cactuar Ver_v16** delivered to
Saves. Not pushed.

## v15: Tournament mode, catalog tags, cached image checks (delivered, not pushed)

What the owner asked for:
- A **Tournament** button beside Refresh, which became per player.
- Three modes: **All pick** (any pool deck), **Draft** (offered 5, pick 1) and **Random**.
- A pool of 24 "most honest and fair" Bracket 3 decks, of any tier, with variety.
- "We're not restricting anything besides just seeing the logs": log everything a player in
  Tournament mode does.
- A Tournament tag on the website.

- **Pool:** `tts/tournament.json` (24 ids + `_about`).
  - Rules: no combo-tagged decks, no tier S/D, no prison/stax/lockdown/theft/hatebear decks.
  - Variety: 19 archetypes (auras, ninjas, vehicles, merfolk, mutate, aristocrats, elves,
    slivers, tokens, blink, reanimator, demons, burn, spells, ramp, discover, counters,
    dragons, control), all colours and all five owners.
  - Mix: tiers B13 A6 C5, average MV 2.91.
  - `ttsdecks.tournament()` publishes it in `decks.json` `tournament`. A missing id prints a
    warning, and the build doesn't fail. `tournament_keys()` drives the catalog tags.
- **Browser** (`tts/cactuar.lua`):
  - `s.tour = {mode, offer, random, redraws, rerolls}`. `czTournament`, `czTourMode(all|draft|random)`
    and `czTourRedraw` (Redraw 5 / Reroll) are always allowed and always logged.
  - The XML has `cz_tour_{C}` beside Refresh. `cz_filters_{C}` is hidden and `cz_tourbar_{C}`
    shown in Tournament mode; filters are ignored there.
  - Search and sort apply to All pick only. A draft offer persists until redrawn.
- **Logging:** `czLog` uses `printToAll` with `[Tournament HH:MM:SS] Name (Seat): …`, in the seat
  colour, and only while that player is in Tournament mode. It covers:
  - entering and leaving; mode switches with the dealt or standing offer or roll;
  - redraws and rerolls, with counts;
  - search (debounced 1.5 s via `Wait.time`), reset, sort, page, select, Surprise me;
  - card back and filter choices;
  - opening, closing and refresh;
  - load pressed, LOADED (with back), and load refused or failed.
  The broadcast line for a load uses `czPlayerName` when the player has no `steam_name`.
- **Website:**
  - Tiles get a gold `theme-tag tournament`, and "tournament" is added to `data-search`.
  - Deck pages get `chip tournament`. The CSS is `.theme-tag.tournament, .chip.tournament`.
- **Image checks cached** (owner: "we should cache img.klr"). Earlier, a build failed on
  "Connection reset by peer" from img.klrmngr.com; a retry passed.
  - `ttsimages.validate` now trusts a URL verified within `RECHECK_DAYS` (7; env
    `MTG_TTS_IMAGE_RECHECK_DAYS`, 0 = check all) and makes no request for it.
  - Older checks renew with a conditional GET; new URLs are always downloaded.
  - Records gain `checked_at`, so the first build after this checks everything once.
  - The report adds "recently verified".
- **Tests:** suite OK. `tests/test_cactuar.lua` 643 checks, including tournament and logs.
  `test_ttsdecks` covers the pool, the warning, the repo pool and the site tags.
  `test_ttsimages` covers the cache window, expiry and new URLs.
- **Saved table:** `MTG 6 player Cactuar Ver_v15` + thumbnail in Saves, SHA-256
  `6be6ca42589461ce`. It reads Pages, so **the Tournament button stays disabled until the
  push** puts `tournament` in the published `decks.json`.
- **Not pushed:** everything from v14 and v15. Owner's choice is still open: push the v14
  voice clips as they are, or leave them out.

## v14: turn totals and the slow-turn announcer (delivered, live-applied, not pushed)

The owner asked for two things:
- Under each seat's turn timer, that player's total time across all turns, reset by the new-game
  die roll.
- A mocking announcer at 5 minutes ("C'mon bro, what's taking so long?") and 10 minutes
  ("Bruh, wake me up when you're done") of a single turn.

- **Code:** `tts/cactuar_turns.lua`, appended to Global after `cactuar.lua`
  (`build_tts_table.GLOBAL_SCRIPTS`).
  - It wraps Global `onPlayerTurn`, `onObjectRandomize` and `onChat`. The base defines only
    `onChat`. The originals are captured once in `CZT_BASE`, so a live re-run doesn't
    double-wrap them.
  - It adds button index 7 ("total m:ss") to each base "Timer" object (description = seat colour),
    only after that object's own 7 buttons exist, so their indexes don't move.
  - A `Wait.time` ticker runs every second.
  - Totals reset on `onObjectRandomize` of the "Who goes first?" die (0rganics; name
    "Who goes first?"/"goes first!", description "Who goes first dice…").
  - Chat: `announcer off|on|test`. `timers off|on` also hides our totals.
- **Audio:** `tts/sounds/slow-5min.wav` and `slow-10min.wav`, made by
  `scripts/make_announcer.py` (macOS `say` Ralph, a bass boom, echo, tanh limiter). They play
  through `MusicPlayer.setCurrentAudioclip`, which replaces whatever music is playing.
  `CZT.soundBase` overrides `CZ.base` for testing. **The owner heard it and wants a clearer,
  more in-character "radio announcer"** voice. Options were researched: ElevenLabs (needs an
  account/key), OpenAI gpt-4o-mini-tts (needs an API key; none set), Chatterbox (local, MIT,
  M4), Kokoro (local, clean but calm). The owner will handle the voice later (2026-10-18). Don't regenerate the clips unasked. When it's redone, drop the distortion.
- **MoonSharp gotcha (found live):** a bare `local index` inside a loop isn't reset to nil in
  TTS. It held `getAllObjects()`'s list. Always initialise locals; `tests/test_cactuar_turns.lua`
  fails on any bare `local x` in the tts/*.lua files. Also, TTS's `os.time()` returns
  fractional seconds, so elapsed time is floored.
- **Live:** applied to the running game with `CZT.soundBase` pointing at the Mac. Totals
  attach to all six timers ("total 2:05" verified). One test clip was played. Afterwards
  `getCurrentAudioclip` still reported the table's playlist track, but the owner did hear the clip.
- **Saved table:** `MTG 6 player Cactuar Ver_v14` + thumbnail in Saves, SHA-256 `fe28622701045efc`.
- **Not pushed:** `tts/cactuar_turns.lua`, `tts/sounds/`, `docs/tts/sounds/`,
  `tests/test_cactuar_turns.lua`, and the edits to `build_tts_table.py` and `test_cactuar_lua.py`.
  **Caveat:** commit 7ba98621 (made outside this session) already pushed the sound-publishing
  part of `ttsdecks.py` and its test `test_announcer_clips_are_published`. That test fails in a
  clean checkout until `tts/sounds/` is pushed.
- Tests: whole suite OK; `lua tests/test_cactuar_turns.lua` reports 826 checks, 0 failed (incl. the
  bare-local scan).



This is the current resolution index. The version sections below preserve the original
investigation and evidence; their older “pending” notes describe that point in time.

| Issue / symptom | Cause and resolution | Verification / remaining work |
|---|---|---|
| Native Alt-hover did nothing over Inspect thumbnails | Custom UI is not a native scene object and exposes no raw Alt state. v38 adds a bindable Inspect zoom Game Key with press/release callbacks plus private thumbnail hover handlers. | v38 is only a separately configured workaround. The owner requires automatic reuse of the existing native Object Zoom binding; that requirement remains unresolved. |
| Inspect looked unlike native Search | v35/v36 used a wide, six-column paged gallery. v37 replaces it with a narrow dark four-column scrolling view and a single live search field, reading actual deck/bag contents. | Live screenshot and 99-card Yuna view checked. Exact native-menu placement/window reuse is unavailable; owner chose Workshop compatibility. |
| Inspect showed no cards in an imported deck | All 99 contained GUIDs in the live Yuna deck were empty; the earlier code skipped them. v37 uses serialized metadata and stable preview identities without taking cards out or exposing positions. | All 99 display A–Z, including duplicates. Entries without physical GUIDs are preview-only; unsafe retrieval callbacks are rejected. |
| Inspect WebP thumbnails were white boxes | Direct UI URL decoding did not display the cache's WebP; registering the same URL as a named custom asset did. v37 merges named faces while preserving existing assets. | Real card faces verified in the running game; all 41 previous UI assets retained. Asset sets stay bounded to open views on registration. |
| Inspect scrolling area overflowed as a white rectangle | ScrollView's implicit sizing did not fill its intended parent. v37 explicitly sizes it to 100% of the viewport and anchors the header/search/count. | Full-window capture confirms clipping and placement; large-container pool growth and asynchronous close privacy covered by the harness. |
| Refresh appeared to load only 54 decks | Bracket 3 + Aggro & Voltron filters matched 54 of 149; refresh retained those filters. Reset clears them; v7 shows filtered and total counts together. | Complete 149-entry index read; filter/count regression checks pass. |
| Blank deck rows and button labels in v1 | `UI.setValue` does not label a Button. Use `UI.setAttribute(id, "text", ...)`. | Browser harness rejects `setValue` on Buttons; rows confirmed in game. |
| “Load image failed unsupported format: UNKNOWN” | Direct Scryfall card-image URLs return HTTP 400 JSON (`generic_user_agent`) to UnityPlayer. GitHub delivered valid deck data; the later image requests failed. Removing query strings does not fix this. Exporter and runtime repair use the importer's WebP cache with the same printing UUID and face. | Failing UUIDs and DFC backs served HTTP 200 images to UnityPlayer; the full build scan passed. Standard `backs.scryfall.io` card back also verified separately. |
| Card-name/printing validation did not prove images would load | Importer validation checks card JSON, not picture responses. Every catalog build and `--check` now GETs the exact exported front/back URLs with TTS headers, deduplicating library, commanders, tokens and DFC states. Failures stop publication before writing/pruning files. | 4,272 downloads passed, then 4,272 conditional 304s passed. Errors, bad bodies and publication gate covered by tests. Availability is verified at build time, not guaranteed forever. |
| Lua re-encoding can break otherwise valid card images | Numeric-keyed `CustomDeck` maps become arrays after Lua `JSON.decode` / `JSON.encode`. Spawn object lines stay raw NDJSON; URL repair only replaces `FaceURL` strings. | Full spawned JSON comparisons preserve every property except repaired URLs; current exports pass through unchanged. |
| Global XML error at line 181, position 130 | The importer decoded `&lt;` and reinserted the previous-page label as raw `<`, producing malformed XML. Use Unicode `‹` / `›`. | Decoded-text regression check and actual importer round-trips pass. |
| Another XML error at line 186, position 115; browser stretched across the screen | The arrow fix was incomplete: raw rich text such as `<size=17>` and `&` in Text element values also broke importer rebuilding. Store all dynamic text in attributes, with empty inner values. Stretching was a failed UI rebuild symptom. | Rich text and ampersands verified in the running game; panel and importer dimensions remain intact after rebuilding shared UI. |
| Fixes seemed absent after a new local build | A copied save is not automatically the loaded game; local generated exports are not Pages until pushed, and the Workshop upload is separate. Inspect actual running Global source/XML via External Editor API and apply runtime repair where needed. | Current source and UI verified live; v8 save delivered. GitHub and Workshop publication remain outstanding. |
| First commander landed in the second slot | Nearest-to-library order is opposite the owner's slot numbering. Select the nearest two own zones, then return the farther/life-tracker slot first. Partners use slot two; tokens remain beyond slot one. Fallback offsets use the same order. | All-six-seat, single/paired, unrelated-zone and token/fallback tests pass; live White Captain Sisay was safely moved into slot one. |
| Dark/black names and controls under importer styles | Shared importer Defaults can affect nested text when controls are updated. Rows now use separate Text labels; dynamic Button labels use explicit rich-text colours, including paging/Random/Reset controls. | Real screenshots caught the remaining paging/Random case; corrected and covered by a regression check. Do not remove explicit colouring while tuning brightness. |
| Cycling filters, crowded details, empty results and stale actions | v7 added direct filter menus, live search, a separate details column, total counts, empty-state help and correct page bounds. Filtering a selected deck out disables Load; pending requests cannot duplicate; errors permit retry. | Tests cover choices/All/dismissal, menu overflow pages, separate players, stale selections and loading errors. Actual game layout inspected. |
| "Tokens are not loading" (owner had loaded Beamtown-Gifts) | Two things. Beamtown-Gifts is the only deck of 149 whose cards make no tokens (`"tokens":false`), so it correctly spawns none. Every other deck's token pile was aimed 3.8 units past the first commander slot along the column, exactly where each seat's Life Tracker sits (z ±5.7), so the pile landed on its heart under its overlay. v11 spawns tokens 4.2 units into the battlefield from the first slot (`slot1 - getTransformRight() * 4.2`), and the status says "It makes no tokens." when there are none. | The Lua stand-ins now put a Life Tracker at every seat (the old stand-in was at a wrong spot, z -12, which is why the tests never caught this). They check tokens clear it and land beside slot one at all six seats, and cover the no-token deck. The new spots were checked clear in the live game. A real token load still needs an in-game look. |
| Owner wanted newest first and no Owner sort | v11: new panels default to `newest`; `CZ_SORTS` is tier/name/newest. The XML has no `cz_sort_owner_*`, and `czSort(owner)` is ignored. In the live game, existing panels were switched to Newest and the old Owner buttons hidden. | Harness checks the default order, the active button, the missing button and the ignored key. Live UI verified through the External Editor API. |
| Owner wanted to pick card back art, committed to the repo | v12: `tts/backs/*.jpg/.jpeg/.png` are published to `docs/tts/backs/`, and `decks.json` gets `backs` with Standard (Scryfall's back, absolute `url`) first and the rest by name (relative `file`). The browser's details column has a **Card back** button opening the same menu component as the filters (`czMenuChoices`; `s.back` per player). On load, `czBackJSON` replaces only `"BackURL"` string values, after `czImageJSON`, never decoding objects. | Python: listing order, file types, publishing, missing folder. Lua: menu, choice, label, filters untouched, every BackURL swapped with nothing else changed, Standard restores the original objects. Live: 6 buttons inserted with a fresh child list (in-place `table.insert` on `getXmlTable()` children fails in MoonSharp), UI reloads, the arrow survives, the panel stays open. |
| "I can't click into" the Card back button (v12, live) | A Refresh re-fetched `decks.json` from Pages, which has no `backs` yet, replacing the list set by hand. The menu then had no choices and never showed. Fix: set the live `CZ.base` to the Mac's catalog (which has `backs`) and refresh; v13 also disables the button and ignores the click when there are fewer than two backs. Also: `UI.getAttribute` read in the same frame as a click can show stale menu state; read in a separate External Editor call. | Live: click in one call, read in the next. Menu active, title "Choose a card back", Standard ✓, Cactuar, no third row. Lua: 562 checks, including the no-backs case. |
| v7 text was too bright and heavy | Owner requested a softer appearance. v8 replaces near-white `#EDF4FC` with `#686C72`, uses muted secondary text/accent colours and darker green controls, and changes row names from Bold to Normal. Live screenshot pixel checks showed the first lighter-grey attempt still clipped to white; the final native values render grey. Both XML defaults and Lua label wrappers use the palette. | v8 checked in game and after shared UI rebuild; owner can judge the softer rendering. |
| v8 grey text became too dark | Owner feedback showed the dimming went too far, especially in commander/owner captions. v9 raises primary text to `#76797D`, headings to `#7B7D80`, captions to `#646B75` and muted labels to `#5D6672`. This is an intermediate grey rather than returning to v7's clipped white. Static XML and Lua wrappers change together. | Applied live and checked after a shared UI round-trip. Keep the v8 feedback in the history; pixel measurements alone do not establish comfortable readability. |
| v9 was still dark grey; remote capture brightness misled tuning | The owner's screenshot showed dark text despite the brighter remote `PrintWindow` capture. Earlier capture pixel values were not a reliable representation of the owner's displayed brightness; do not infer a universal TTS colour correction from them. The owner explicitly requested white, only slightly less bright. v10 restores near-white `#E2E5EA`, title `#E6E9EE`, captions `#CDD3DC` and muted labels `#C0C8D2`. | Follow the owner's screenshots and preference, not remote capture histograms. Preserve regular row weight and explicit XML/Lua colours. |
| Warm catalog builds no longer finish almost instantly | Every build now makes thousands of real image-host checks; local metadata is never proof of current availability. Conditional GETs save bandwidth. Bot timeout increased from 180 to 600 seconds. | Full warm `--check` took 1m57s; all 4,775 catalog files were up to date. |

### Operational debugging pitfalls

- **Windows SSH uses WSL bash:** command arguments can arrive as one word; send commands
  through stdin. `scp` closes the connection, so stream files into `cat` and compare
  SHA-256. Keep host/key/path details in `INTERNALS.md`.
- **External Editor API replies are not EOF-framed:** use a Windows dual-stack listener,
  keep the request socket open, parse a complete JSON message and match the return ID.
  Ignore autosave messages. Large Lua requests belong in a temp request file, avoiding
  PowerShell command-line limits.
- **UI changes are asynchronous:** wait until UI loading completes before rendering
  restored state or inspecting a rebuild. Reading and rewriting `getXmlTable()` in the
  same frame as new labels can capture stale values; verify across separate frames.
- **Screenshot capture is session-sensitive:** SSH's noninteractive session reports no
  game window. A short-lived hidden task in the logged-in session, using the actual
  Windows user SID, can capture only the TTS window with `PrintWindow` while it is in the
  background. Wait for the PNG writer to release its file; clean up tasks/temp files.
  A cleanup-only PowerShell nonzero exit can coexist with a valid PNG on stdout.

## What this is

**MTG 6 player Cactuar Ver** is someone else's Workshop table with a deck browser added.
The base is "MTG 6 player table - scripted", Workshop 2293586471, by Oops I Baked a Pie.
A player clicks a Cactuar tile on the table and gets their own panel. The panel lists every
deck in this repo, with search, sort (tier, name, newest, owner) and filters (bracket, tier,
category, owner). **Load into my seat** spawns the chosen deck into that player's seat.

- Steam Workshop item **3822623414**: https://steamcommunity.com/sharedfiles/filedetails/?id=3822623414
  It's private and owned by the repo owner, and still holds the first build (v1, broken).
  Only the owner can update it, in TTS: load the save → **Modding → Workshop Upload** →
  update item 3822623414.
- Deck data is live: the table fetches `https://hellozhewang.github.io/mtg/tts/decks.json`
  and the deck files at runtime. Deck changes never need a table rebuild or an upload.
- Table code or layout changes need a rebuild, a fresh copy on the owner's PC, and later a
  Workshop upload.

## Files

| file | role |
|---|---|
| `tts/cactuar.lua` | the browser, appended to the table's Global script. Everything is prefixed `cz`/`CZ`. Entry points: `czOpenFor` (from tiles), `czOpen`, `czRender`, `czLoad` → `czSpawn` |
| `tts/cactuar.xml` | the panel template: `@PANEL@` once per seat colour (`{C}`), `@ROW@` × 10 and `@CHOICE@` × 10 (`{I}`), appended to the Global UI |
| `tts/cactuar_tile.lua` | the script on each tile: a transparent whole-tile button that runs `Global.call("czOpenFor", {color = clicker})` |
| `tts/backs/` | card back pictures players can choose (cactuar, girly_pop so far). Specs and flow are in its `README.md`, which the build also publishes to `docs/tts/backs/README.md`. Never drop pictures in `docs/`: the build prunes them. |
| `tts/cactuar-tile.jpg` | the tile picture. `ttsdecks.files()` publishes it at `docs/tts/cactuar-tile.jpg` |
| `scripts/build_tts_table.py` | base save JSON → our table. `TILES` holds the tile GUIDs, positions and facing; `TILE_SCALE`; `--name`, `--base-url` |
| `scripts/ttsdecks.py` | builds `docs/tts/` (`decks.json` and one `.ndjson` per deck) during `build_site.py` |
| `scripts/ttsimages.py` | verifies every exact exported image URL with UnityPlayer headers before catalog publication; conditional GETs reuse verified image metadata |
| `tests/test_cactuar.lua` | runs the browser against TTS stand-ins and the real `docs/tts/`. `tests/test_cactuar_lua.py` runs it in the suite when `lua` is installed |
| `tests/test_build_tts_table.py`, `tests/test_ttsdecks.py` | the build and the deck-object format |
| `tests/test_ttsimages.py` | image download failures, conditional rechecks, all exported roles and the publication failure gate |

## Rules that bite

- **All dynamic labels use `UI.setAttribute(id, "text", ...)`, including Text.**
  `setValue` does nothing on Button (v1's blank rows). On Text, it stores raw Unity
  rich-text markup in the element value; the importer emits that as XML and fails
  on `<size=17>`/`<color=...>` or unescaped `&`. Text attributes are XML-escaped and
  survive the rebuild. All dynamic Text nodes have no inner values in the
  template. The Lua test rejects raw XML metacharacters in any `setValue` call.
- **Never decode and re-encode a TTS object in Lua.** `JSON.encode` turns CustomDeck's numeric
  keys into an array, and the cards lose their pictures. Only the header line is decoded.
  Deck-object lines stay raw JSON: v4 only substitutes direct Scryfall `FaceURL` string
  values before passing them to `spawnObjectJSON`.
- **Don't use direct Scryfall URLs for card faces.** Its CDN returns HTTP 400 JSON
  (`generic_user_agent`) to TTS's default UnityPlayer client, which TTS reports as
  "Load image failed unsupported format: UNKNOWN". `ttsdecks._image` maps the printing
  and front/back face to the importer's cache, `https://img.klrmngr.com/display/...webp`.
  Removing Scryfall's query string does not fix the client rejection. The standard back
  at `backs.scryfall.io` was tested separately and still returns a JPEG to UnityPlayer.
- **Don't use `&lt;`/`&gt;` as page-button labels.** The base table's importer reads
  the shared Global UI through `UI.getXmlTable()` and rebuilds it with `UI.setXmlTable()`.
  The decoded `<` value becomes `<Button ...><</Button>` and breaks XML. Use the
  literal Unicode arrows `‹`/`›`, as v3 does. The build test checks decoded text
  remains valid when reinserted as markup.
- **Button labels on the base Timer blocks need font_color alpha 100**, as the Timer's own
  labels use. With alpha 1 (or 0.85) the label exists, `getButtons` shows its text, and
  nothing is drawn. Found 2026-10-18 by A/B screenshots: the same label became visible
  only when the alpha changed.
- **Nothing spawned by the loader may land in a play area** (`data[color].playmat`, the mat
  left of the column). The base mulligan refuses while any Card/Deck is in it ("accidental
  mulligan press", double-click to override). Tokens therefore go on commander slot two,
  or on the exile spot for partner decks.
- **After a load or rewind, Global's script runs before the objects exist.** At top level,
  `getObjectFromGUID` returns nil for the tile, so anything read from objects must wait
  until they're there (the attach tick; `cztRestore`).
- **A TTS rewind wipes scripts' saved data and keeps object fields.** Tested 2026-10-19 with
  probe values: `Global.script_state` came back empty, while a tile's `memo` and GM notes
  survived. Rewinds don't call `onSave` either. So state that must survive a rewind goes
  in an object's `memo`. Ours is the Cactuar tile `c4c7a1` (then `c4c7a2`), written by
  `cztPersist` on every change and every 10 s. `Global.script_state` is kept as a fallback.
- **Hidden information:** nothing the table sees may name a player's deck, commander or
  search. That covers broadcasts, tournament logs and face-up spawns. Logs describe actions only
  ("selected a deck", "REROLLED (reroll #2)"). Commanders and tokens spawn face down
  (rotZ 180). The player's own panel may show their deck. `tests/test_cactuar.lua` checks
  that no log line contains any pool deck's name or commander.
- **Leave the base table's behaviour alone.** Don't redefine its `onload` or other globals;
  only append. Its seats are `data[color].libraryZone` (a ScriptingTrigger), plus two objects
  named "Commander Zone" per seat (≤20 units from the library zone).
- **Facing.** South seats are White, Red, Yellow (library zone rotY 0). North seats are Green,
  Blue, Purple (rotY 180). Face-up rotY = zone rotY + 180, with rotZ 0. Face down adds rotZ 180.
- **Commander slot order:** first is toward the life tracker, farther from the library;
  second is toward the library. Find the nearest two Commander Zones first, then reverse
  their distance order. A lone commander also goes in slot one. The fallback offsets are
  10.5, then 6.8, along the library's forward.
- **Tokens stay in the column:** slot two for a single commander, the exile spot (midway
  between slot two and the library) for partners. Never past slot one (the Life Tracker,
  v1–v10), and never into the battlefield (v11–v18, which blocked the mulligan).
- **Tile GUIDs** `c4c7a1`/`c4c7a2` must not exist in the base; the build exits if they do.
  A rebuild from an earlier output replaces our tiles and appended script/UI, never doubling them.
- **Never commit the base table or any built table JSON.** They're someone else's mod.
  Only commit our sources.
- **Commits:** don't commit or push unless the owner asks. The repo is public. Pages
  publishes `docs/` on push, so the table can't see new data or a new tile picture until then.

## Build, test, deliver

```sh
python3 -m unittest discover tests
python3 scripts/build_site.py                # rebuilds docs/, including docs/tts/
# Commit and push the changes; allow Pages to publish before delivery.
python3 scripts/release_tts.py --notes "what changed"
# Commit and push the new tts/CHANGELOG.md entry afterwards.
```

- Use `scripts/release_tts.py` for releases (see the root README). It reads the current
  version from `tts/CHANGELOG.md`, checks that HEAD is pushed and its audio/tile bytes
  are live on Pages, then builds the next version from HEAD, never the working tree.
- The release tool fetches Workshop file `2293586471.json` from the owner's PC. It and
  the generated save stay out of the repo. Deployment details live in the gitignored
  `tts/deploy.local.json` and `INTERNALS.md`.
- For a local experiment, use `python3 scripts/release_tts.py --dry-run`; this does not
  deliver or advance the changelog. Never bypass publication checks for a normal release.
- Keep only the latest build in the owner's Saves folder. On 2026-10-19 the owner asked to
  clean it up, and v1–v23 were deleted. When delivering a new version, delete the previous
  `MTG 6 player Cactuar Ver_vN.json/.png`. Never touch `Saved Objects/` (the decks),
  `TS_AutoSave*`, `SaveFileInfos.json` or `steam_autocloud.vdf`.
- Deliver to the owner's PC TTS Saves folder, with a `.png` thumbnail of the same name:
  the current tile art, `tts/cactuar-tile.jpg` converted to PNG (`sips -s format png`). The
  owner asked on 2026-10-19 for the thumbnail to match the new tile. Send a copy of this file to their Desktop as
  `Cactuar table WIP.md`. Host, paths and the copy method are in `INTERNALS.md`.

## State at v2

Done in c0acd73:
1. Deck rows and filter buttons are labelled with `setAttribute(..., "text", ...)`. v1 showed
   149 decks but blank rows.
2. The screen button is gone. Two locked "Cactuar decks" tiles (scale 2.2) sit where the owner
   drew arrows, beside the deck importers:
   - `c4c7a1` at x -48.2, z -24.5, rotY 180: south side, below the Card Importer model.
   - `c4c7a2` at x 48.2, z 24.5, rotY 0: north side, above rikrassen's importer tile.
3. The README links the Workshop item. `tests/test_build_tts_table.py` is new.

Delivered to the owner's PC as **MTG 6 player Cactuar Ver_v2**. Not uploaded to the Workshop yet.

## v3: Global XML rebuild fix (delivered)

The next screenshot showed "Error Building Xml UI on Global: Name cannot begin with
the '<' character ... Line 181, position 130". The delivered v2 and the owner's autosave
both contain valid saved XML. The importer's Global UI table round-trip decodes the
previous-page button's `&lt;` and reinserts it as markup. A local reproduction against
the complete v2 XML produced `<Button ...><</Button>` at exactly line 181, character 130.

`tts/cactuar.xml` now uses `‹` and `›`. A regression test checks all browser text after
entity decoding; the complete v3 Global UI (including the base table) also passes this
check. All 139 unit tests pass. The base table's script and original 282 objects are
preserved. **MTG 6 player Cactuar Ver_v3** and its thumbnail were delivered to the owner's
Saves folder and SHA-256 verified. Load v3 for this UI fix; in-game confirmation is pending.

V3 still fetches from Pages. The separate image-source fix below is only in the local
exports until the owner authorizes commit/push. No Workshop upload has been performed.

## v4: load-time image fix (delivered)

The owner continued seeing Scryfall image errors because v3 still read the old exports
on Pages. V4 now fixes those URLs in the table itself: `czImageJSON` changes only
`FaceURL` string values from `cards.scryfall.io/<size>/...jpg` to
`img.klrmngr.com/display/...webp`. It preserves the printing UUID and front/back side,
drops scan-version queries, and works on library cards, commanders, tokens and nested
double-faced states. It never decodes or re-encodes object JSON. Corrected exports
already using the cache pass through unchanged.

**MTG 6 player Cactuar Ver_v4** and its thumbnail were delivered to the owner's Saves
folder and SHA-256 verified. Load v4, then load a deck: this fix works with the currently
published data and does not require a GitHub push first. V4 includes v3's XML fix.
The new Lua regression cases failed seven object comparisons before the fix and now
pass: 273 checks, 0 failed. All 139 unit tests pass. Three image UUIDs from the latest
screenshot were also checked at the cache with UnityPlayer headers: HTTP 200 WebP.
In-game confirmation is pending. No commit, push or Workshop upload has been performed.

## v5: formatted Text survives the importer's UI rebuild (delivered and live-tested)

After loading v4, the importer still stretched the browser over the screen. Its error
had moved to line 186, position 115: `<size=17>` in the selected deck's detail Text.
The arrow fix was necessary but incomplete. This time the running script was checked
through TTS's External Editor API: v4's image repair and both Unicode arrows were active.

All dynamic Text updates (details, pager, status) now use `UI.setAttribute(..., "text", ...)`,
just like the working row buttons. The template also stores their initial text in
attributes with no inner value. Regression checks failed six times on the old detail
updates and now pass. All 139 unit tests pass; the Lua session reports 227 checks,
0 failed.

Applied the new browser functions and clean UI to the running game without reloading
or moving table objects, preserving CZ's state and selected deck. Also updated the
Global script source. Opened the Cactuar browser and invoked the actual `ddf5de`
importer's `click_show_import(self, "White")`, then performed another full Global UI
table round-trip. The resulting live XML parses: Cactuar remains 620×720, the importer
modal is 600×600, importer defaults are present, and the object count stays 275.
The selected Animar detail includes both rich text and "Value & Ramp", exercising the
previously failing content. This verifies the real importer interaction, beyond stubs.

**MTG 6 player Cactuar Ver_v5** and its thumbnail were delivered to Saves and SHA-256
verified. The repair is also active in the current session. Use v5 for future loads.
No commit, push or Workshop upload has been performed.

### External Editor API debugging

The owner's PC exposes the local TTS API described at
https://api.tabletopsimulator.com/externaleditorapi/ . A Windows-side dual-stack TCP
listener on localhost:39998 receives responses; keep the client to localhost:39999
open until the response arrives. Execute messages need `messageID: 3`, `guid: "-1"`
(or an object's GUID), `script`, and a nonzero `returnID` to receive message 5. Read a
complete JSON message rather than waiting for EOF: TTS can keep the socket open.
Ignore unrelated notifications such as autosave (`messageID: 6`); wait for the return
message whose `returnID` matches the request.
Large requests should be read from a Windows temp file rather than put in an encoded
PowerShell command, which has a command-line length limit. Host details stay in
`INTERNALS.md`. Read-only probes of `Global.getLuaScript()`, `UI.getXml()` and
`UI.getXmlTable()` are useful for distinguishing an old loaded save from a new bug.

## v6: first commander in first slot, second in second (delivered and live-applied)

The owner marked the first Commander Zone in a screenshot: above the other commander
slot, toward the life tracker. The loader had ordered zones nearest-to-library first,
so even a single commander went into slot two. `czCommanderSpots` now selects the
nearest two zones, then returns the farther one first. This works on both sides of the
table and avoids choosing a farther unrelated zone merely because it is in the radius.
Tokens still anchor beyond the outer slot. Fallback positions use the same slot order.

Regression cases failed 16 placement checks before the fix and now pass. They cover a
single commander, partner order, all six seats, north/south facing, an unrelated zone,
tokens beyond both slots and fallback positions. All 139 unit tests pass; the Lua
session reports 260 checks, 0 failed.

Applied the new functions to the live game while preserving CZ state, and updated the
Global script source. Checked both zone coordinates for all six seats using the actual
objects. Moved the already-loaded Captain Sisay (`33c8de`) from White's second slot to
the empty first slot, with a guard against moving it if it was no longer in slot two.
No other card was moved. The verified slot GUIDs are:

| seat | first slot | second slot |
|---|---|---|
| White | `40584f` | `9d380e` |
| Red | `9cb4b6` | `f9be00` |
| Yellow | `48daef` | `ba751d` |
| Green | `2fa3e2` | `206ce5` |
| Blue | `399da3` | `144ccc` |
| Purple | `47e079` | `2af6c5` |

**MTG 6 player Cactuar Ver_v6** and its thumbnail were delivered to Saves and SHA-256
verified. The change is active in the current session; use v6 for future loads.
No commit, push or Workshop upload has been performed.

## Build-time image validation (local)

The owner requested image verification during the catalog build. Card-name/printing
validation in `ttsimport.py` only checks importer JSON; it does not prove the picture
host will serve a usable image to TTS.

`build_site.py`, including `--check`, now calls `ttsimages.validate` after planning the
output and before writing or pruning anything. It recursively collects exact `FaceURL`
and `BackURL` values from the generated NDJSON, including both commanders, tokens and
double-faced states. URLs are checked once across all decks, with four workers and
bounded downloads/timeouts. Requests use TTS's UnityPlayer User-Agent. HTTP failures,
HTML/JSON responses and incomplete/unsupported image containers fail the entire build
and identify affected deck paths, roles and URLs. This checks signatures and container
boundaries; it does not run Unity's pixel decoder or guarantee future service uptime.

Successful verification metadata lives in `.cache/cards.db`'s `pages` table under
`tts:image-check:v1:`. This stores format, byte count, ETag and Last-Modified, not image
bytes. Every build still contacts the image host: HTTP 304 is accepted only after a
previously successful byte check and a conditional request. Failed checks are never
cached as successes. `cache.py --clear pages` also clears this metadata safely.

The bot's default catalog timeout is now ten minutes (`MTG_SITE_TIMEOUT` can override),
allowing time for thousands of remote image checks instead of assuming instant warm
builds. Image validation itself required no table change; v7 below changes the browser UI.

Verification: all 150 unit tests pass, including all image roles, HTTP/network
failures, invalid bodies, conditional rechecks and keeping published files intact when
either normal or `--check` builds fail. The first real build passed all 4,272 unique URLs
across all 149 decks (4,272 downloaded, zero failed). It wrote or removed no catalog
files. A full subsequent `--check` also passed: zero downloads, 4,272 unchanged (HTTP
304), all 4,775 catalog files up to date. That warm check took 1 minute 57 seconds on
the owner's Mac, so remote checks now account for most build time even with warm caches.
`git diff --check` and Python compilation checks passed. Nothing committed or pushed.

## v7: browser layout and usability (delivered and live-applied)

The owner requested a more usable, modern browser. The panel is now 880×656 with
ten readable rows and a separate details column, instead of a narrow list stacked
above the details. Deck names and commander/owner captions use separate Text elements
with explicit light colours. Selected rows and active controls use a teal accent;
buttons have hover/pressed/disabled styles. No custom image assets are required.

- Search filters as the user types; Enter is no longer required.
- Each filter opens a menu with direct choices and All, instead of cycling values.
  Clicking outside dismisses it. Menus paginate if future owners/options exceed ten,
  and reopen on the page containing the current value. They use static Button slots
  and text attributes, so labels containing ampersands survive importer UI rebuilds.
- Filtered results say e.g. `54 of 149 decks`; Reset clears both search and filters.
- Empty searches explain how to recover. Previous/Next respect page bounds; Surprise
  me selects a matching deck and navigates to its page.
- The details panel shows commander(s), tier, bracket, owner, strategies, three stats
  and dates. Load stays disabled without a selection or while fetching. Filtering a
  selected deck out clears it; refresh replaces selected metadata with the latest entry.
- Load errors are red and allow retry. Choosing a new deck clears an older status.
  Panels, menus, selections and filters remain separate for each player.

Verification: 151 unit tests pass; the Lua browser harness reports 290 checks, zero
failures. It exercises menu choices/All/dismissal, overflow menu pages, separate player
state, result totals, empty results, stale-selection prevention and pending-load retries,
alongside all existing commander, token and image-source checks. Changed files pass
`git diff --check`.

Applied to the running game without reloading or changing any objects (282 objects
before/after). Captured the actual TTS window to inspect the layout, text contrast,
selected row and open strategy menu. The real importer reopened successfully beside
the browser; a subsequent full `getXmlTable`/`setXmlTable` round-trip preserved the open
menu and `Aggro & Voltron` label, the deck rows, selection and Load control. The visual
check caught dark paging/Random labels after importer styling; those labels now use the
same explicit rich-text colour protection as the dynamic filter and sort controls. XML parses,
UI loading completed, the browser remains 880×656 and the importer 600×600.

The running Global script is updated, with the current browser state preserved.
**MTG 6 player Cactuar Ver_v7** and its thumbnail are delivered to Saves; the Desktop
handoff is refreshed. No commit, push or Workshop upload has been performed.

## v8: softer text (delivered and live-applied)

The owner found v7's white text too bright. Main labels and body text now use
`#686C72`; the title uses `#6E7278`, secondary captions `#515861`, muted labels
`#48515D` and the desaturated accent `#3D6554`. Deck names use regular weight, with
bold reserved for hierarchy such as headings, tier markers and stat values.
Live screenshot sampling found that the first grey attempt (`#BAC4D1`) still rendered
solid white in this Windows TTS session. The final lower native colour values avoid
that clipping: the same first-row text region has zero pure-white pixels, with common
glyph colours around RGB 201/208/219. Green active/load controls were darkened to keep
the softer text readable. Static XML and runtime rich-text colour wrappers were updated
together so the importer cannot silently restore near-white labels. Refresh/Close also
receive runtime colouring.

All 151 unit tests and 290 Lua harness checks pass. The change was applied in the
running game while preserving the browser state and other UI. After opening the actual
importer, live XML still parses, palette and regular row weight are preserved, UI loading
completes, and all 282 objects remain. The final game screenshot was inspected.
Versioned v8 save and
matching thumbnail delivered and SHA-256 verified; the Desktop WIP copy was updated.
No commit, push or Workshop upload performed.

## v9: brighter intermediate grey (delivered and live-applied)

The owner found v8's grey text too dark. Primary text is now `#76797D`, the title
`#7B7D80`, commander/owner captions `#646B75`, and muted labels `#5D6672`. Secondary
text received a larger brightness increase so it is easier to scan. The regular font
weight and darker green controls from v8 remain. Both static XML colours and runtime
rich-text wrappers use the new palette.

All 151 unit tests and 290 Lua harness checks pass. The update preserves the current
browser state and the current session's 272 objects. Live XML is checked after the
shared UI table round-trip, and the rendered game window is inspected before delivery.
Versioned v9 save and matching thumbnail delivered with SHA-256 verification; Desktop
WIP copy refreshed. Nothing committed, pushed or uploaded to the Workshop.

Temporary debugging helpers from the preceding session were gone. The v8 save was
recovered from the owner's PC and used as the rebuild input, which the builder supports
without duplicating our scripts/UI/tiles. The External Editor bridge and window-capture
helper were recreated outside the repository; do not depend on temp helpers surviving
between sessions.

## v10: restore white, slightly softened (delivered and live-applied)

The owner said v9 was still too dark and explicitly requested white with slightly less
brightness. Primary text is now off-white `#E2E5EA` (v7 was `#EDF4FC`), the title
`#E6E9EE`, secondary captions `#CDD3DC` and muted labels `#C0C8D2`. The regular row
font weight remains. This is a small reduction from the original white, reversing the
overly dark grey palettes in v8/v9.

The earlier remote screenshot measurements did not match the owner's screenshots and
should not have driven native colours down so far. Treat the pixel/clipping discussion
in v8 as historical debugging evidence, not a proven display transfer function or a
reason to darken the text again. Owner feedback is the readability criterion.

All 151 unit tests pass. Source/template and runtime label wrappers use the same
off-white palette. Applied live while preserving browser state and game objects;
versioned v10 save, matching thumbnail and Desktop WIP delivered with SHA-256 checks.
Nothing committed, pushed or uploaded to the Workshop.

## v12: card back menu (delivered and live-applied; needs a push)

The owner asked for a small menu to change the card back art, with the art committed to
the repo and pulled from there.

- **Art:** `tts/backs/cactuar.jpg` (745×1040). A sunset oval with the Cactuar, five mana
  pips and "CACTUAR", drawn as SVG and rendered with headless Chrome; the generator isn't
  kept. Add more backs by dropping pictures into `tts/backs/`: the label comes from the
  file name (`zebra_stripes.png` → "Zebra Stripes"). They need a catalog build and a push,
  but no table rebuild.
- **Code:** `ttsdecks.backs()` and `back_files()`, `decks.json` `backs`, published files.
  In the browser: `czBacks`/`czBack`/`czBackLabel`/`czBackJSON`, and `czMenuChoices`
  generalises the filter menu (filters keep All first; the back menu has no All).
  `cz_back_{C}` sits above Load.
- **Live apply:** the browser source was re-run keeping state. `CZ.index.backs` was set by
  hand with the Cactuar back at `http://192.168.0.100:5588/tts/backs/cactuar.jpg` (the
  Mac's LaunchAgent catalog server; HTTP 200 from the PC). The Card back buttons were
  added to the live UI. The first attempt failed at `kids[at].attributes` (in-place
  insert), before `setXmlTable`; the second rebuilt the children as new tables and added 6.
- **Saved table:** **MTG 6 player Cactuar Ver_v12** + thumbnail in Saves, SHA-256
  `565c8ab35d003ce1`. It reads backs from Pages, so the menu lists only Standard until
  the push.
- Verification: 155 unit tests pass; the Lua harness reports 560 checks, 0 failed.
  Catalog rebuilt (2 files written: `decks.json`, `backs/cactuar.jpg`; image check
  4,272 verified).

## v11: tokens beside the commander, newest first (delivered and live-applied)

The owner's v8 screenshot: basics work; "tokens are not loading"; default the sort to
newest; no Owner tab in the sort row.

- **Tokens.** See the issue table. The pile spawns at `slot1 - right * 4.2`:
  - White (37.57, -9.58), Red (8.16, -9.59), Yellow (-21.24, -9.59);
  - Green (-37.55, 9.57), Blue (-8.14, 9.57), Purple (21.26, 9.57).
  Each spot had nothing within 3 units in the live game. A deck without tokens reports
  "It makes no tokens."
- **Sort.** Newest is the default for new panels, and Owner is gone from the sort row. The
  owner filter menu is unchanged. README updated.
- **Live apply.** Ran the browser source in the running game through the External Editor
  API. It already included v10's colours, because Codex's edits were in the files first.
  Kept `CZ.index` and every seat's state, switched every panel to Newest and hid the old
  `cz_sort_owner_*` buttons (`active=False`). Verified through `UI.getAttribute`: Newest is
  active, Owner hidden, and the list starts with Obeka-Upkeep. The Global script *source* in
  that session wasn't rewritten, so a later save of that session reloads older code: use
  the v11 save.
- **Tooling.** The External Editor client this round was a PowerShell script (listener on
  39998, request to 39999, match `returnID`). It was streamed to the PC's temp folder and
  deleted after each run, and isn't in the repo.

Verification: 151 unit tests pass; the Lua harness reports 452 checks, 0 failed. **MTG 6
player Cactuar Ver_v11** and its thumbnail were delivered to Saves and SHA-256 verified
(`79a9397f65d2f570`). Nothing committed or pushed; no Workshop upload.

Still to see in-game: load a deck that has tokens (e.g. Giada-Angels) and check where the
pile lands.

## In-game feedback on v2 and unpublished export fix (historical)

The owner's screenshots confirm the tiles open the browser and the rows, tier colours,
filters and detail panel render. Refresh loaded all 149 decks; the pager's 54 was the
Bracket 3 + Aggro & Voltron filter result. Clear resets those filters.

Loading a deck produced image errors for direct `cards.scryfall.io` URLs. Reproduced
with the exact first failing URL: an application User-Agent gets HTTP 200 `image/jpeg`,
while UnityPlayer gets HTTP 400 JSON, both with and without the scan-version query.
The importer's backend currently returns `img.klrmngr.com/display/...webp` card faces.
That cache returned HTTP 200 images to UnityPlayer for the four failing pictures and
a double-faced back checked during diagnosis.

Local fix: `scripts/ttsdecks.py` now uses that cache for all Scryfall card faces,
including library cards, commanders, tokens and double-faced backs. Printing UUIDs and
front/back sides stay the same. Regression tests cover those roles, normal-size fallback,
custom URLs and leaving the catalog's Scryfall URLs unchanged. No table rebuild is needed:
once the regenerated `docs/tts/` is published, remove the failed deck and load it again.
The fix has not been published yet; commit/push needs the owner's request.

Verification: 138 unit tests pass, the Lua browser harness reports 258 checks with no
failures, and `build_site.py --check` passes. All 149 deck exports were regenerated;
the only object changes are 15,246 face URLs, with printing UUIDs and front/back sides
preserved. In-game confirmation of the corrected image source is still pending.

Still check in-game:
- **Tiles:** size, position and facing. The button is 1000×1000, sized like rikrassen's tile
  button (1000×750 on a 4:3 tile). If clicks miss, adjust width/height in `cactuar_tile.lua`.
- **Load into my seat**, after publishing the image fix:
  - the library spawns face down at the library zone and gets shuffled;
  - commanders land on the nearest Commander Zones (partners take both);
  - tokens land 3.8 units beyond them;
  - loading is refused when the library zone already holds a Deck or Card.

## Open options (not started; ask the owner first)

- **Self-updating table:** the tile fetches its script from Pages, then runs
  `self.setLuaScript(new)` and `self.reload()` when its version changes, like the Card
  Importer. The panels go into the Global UI with `UI.setXmlTable` and
  `onClick="<guid>/czFn"`. After that the Workshop item only needs uploads when objects
  move. Trade-off: every copy of the table runs whatever is on Pages.
- A Workshop link on the catalog page (`frontend/index.html`).
- A real screenshot with the browser open for the Workshop page. The current screenshots
  are the base mod's, credited.
- The discord-bot repo's `/deck-random` description still mentions Bracket 3.5. It's a
  separate repo, unrelated to TTS.
