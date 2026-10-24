# Commander picture A/B measurement — 2026-10-22

**New picture registration still causes a visible hitch on this host. Cached picture
switching shows no clear added cost in this run.** Keep the released v60 text-only;
if pictures return, make first loading explicit and retain already registered assets.
An opt-in button contains when the first-load hitch happens; it does not eliminate it.

| Action | Measured result |
| --- | --- |
| Register a previously unregistered commander URL (3 trials) | Largest Lua callback gap **437–531 ms**; asset-ready after **470–564 ms** |
| Register a fresh query URL (3 trials) | Largest gap **435–509 ms**; ready after **466–547 ms** |
| Re-submit the unchanged asset list, no commander pictures (3 controls) | Largest gap **430–501 ms**; ready after **459–530 ms** |
| Switch cached commanders with pictures (36 switches, two windows) | **1.72 ms** mean frame time; p95 **1.95–2.04 ms** |
| Switch cached commanders with text only (36 switches, two windows) | **1.74 ms** mean frame time; p95 **1.92–2.08 ms** |
| Reopen cached browser, pictures vs text (18 each) | Mean frame time **1.83 vs 1.77 ms**; both had an isolated ~66–68 ms callback gap |

The unchanged-asset negative control is the key result: adding no image at all still
produced approximately the same pause when calling `UI.setCustomAssets`. This points
to the shared native UI/asset update path as the dominant observed cost. The test does
not distinguish native XML parsing, sprite/atlas construction, loading existing fonts,
texture decoding, or GC inside that path. Do not attribute it to one of those causes.
Normal cached switching never calls `setCustomAssets` or replaces XML.

An independent frame-counter check re-submitted the original 25 assets and observed
**440.16 ms** between Lua frame callbacks with the engine frame counter advancing
**exactly one frame**. `Time.delta_time` and the game clock reported only **150 ms**
for that interval. Thus the reported delta is capped during these stalls; a frame-time
maximum of 150 ms understates the observed pause. Evidence is retained alongside the
main experiment in `frame-counter-check.json`.

## Method and limits

- Used the running host with v60 browser/Inspect changes applied, its existing 164-deck
  catalog, White's open browser, 25 original UI assets, no open Inspect sessions.
- Warmed only the three small commander text files first. No guide fetches, deck
  JSON decoding, card spawns/moves, turn changes, or changes to the music system.
- Tested Be'lakor, Yuna and Giada's pinned WebP URLs: **93,894 / 67,014 / 61,652 bytes**.
  Fresh query variants returned exactly the same bytes and content types. First normal
  registration may already use TTS's disk cache; fresh URLs exercise a new URL without
  deleting user caches. This is not proof of an empty HTTP/CDN/disk cache.
- Added one temporary private preview control per seat in a single harness XML setup.
  Only White's picture was active. The setup's own ~505 ms gap is reported separately
  and is **not** a cost required on every commander selection in a production build.
- Sampled `Time.delta_time`, `os.clock()` gaps, synchronous action duration and asset
  readiness via `Wait.frames`, including frame settling after UI.loading clears.
  [TTS Time API](https://api.tabletopsimulator.com/time/) documents the frame delta;
  [TTS UI API](https://api.tabletopsimulator.com/ui/) documents asynchronous UI loading.
- Each switching window used 18 actions spaced 180 ms apart. Repeated text-only and
  image windows bracket the result. Background ~30–68 ms spikes occurred in both
  variants; cached images are not proven cost-free or statistically equivalent.
- A held Be'lakor preview was visually checked in a screenshot: actual artwork, not
  a white/missing sprite. Other trial images passed native readiness and HTTP byte
  checks but were not individually inspected in screenshots.
- This was one host, the current mostly empty table and an **880×719 window capture**.
  Remote clients, lower-end hardware, a busy six-player game, large expanded Inspect
  grids, full-resolution play, full new-game startup and a redesigned layout are
  outside the measurement. This experiment cannot promise a hitch-free image feature.
- The Lua sampler and small editor status polls add measurement overhead. Mean frame
  times compare the two variants on this host, not expected FPS on other machines.

## Reproduce and inspect

Scripts live in `scripts/` and do not participate in the table builder:

```sh
python3 scripts/tabletop/profile_tts_commander_images.py --hold
# Capture/check the temporary picture, then restore the original UI:
python3 scripts/tabletop/profile_tts_commander_images.py --cleanup
```

Requires the private local deploy config, running TTS scripting connection, an open
White Cactuar browser, and no open Inspect windows or pending UI/catalog loading.
The default (without --hold) cleans up automatically. Do not run multiple editor
connections simultaneously. The report includes readiness, callback timing and frame
statistics; future runs also record engine frame steps at their largest callback gap.

Local evidence: `.cache/commander-image-profile/` contains `results.json`, original
`before-ui.json`, `picture-check.png`, `frame-counter-check.json`, `restored.json`
and `restored-final.json`. Cleanup verified **25 original assets, zero test assets,
no test panel, loading false, White still open on the original Be'lakor selection**.
Benchmark globals/sampling were released. Archived v60 JSON/PNG SHA-256 values are
unchanged. **Saved Games v60 and Steam v60 remain unchanged; no new build/upload.**

## Per-window data

Frame means/p95 below use the engine's reported delta. Callback gap/ready measurements
use `os.clock`; the frame-counter check above validates a real engine-frame gap.
Zero readiness means the action did not register/rebuild assets. There is no reliable
pure-download time separated from native rebuild and settling in these measurements.

| Window | Frames | Mean frame ms | p95 frame ms | Largest callback gap ms | Ready ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| text_only_idle | 1253 | 1.60 | 1.82 | 4.1 | 0.0 |
| text_only_switch | 2073 | 1.69 | 1.92 | 29.6 | 0.0 |
| text_only_reopen | 1977 | 1.77 | 1.88 | 66.6 | 0.0 |
| harness_layout_setup | 239 | 2.83 | 10.76 | 505.4 | 530.7 |
| empty_image_controls_idle | 1243 | 1.61 | 1.83 | 4.0 | 0.0 |
| unchanged_assets_rebuild_1 | 401 | 2.33 | 1.83 | 500.7 | 530.3 |
| unchanged_assets_rebuild_2 | 361 | 2.65 | 10.99 | 432.4 | 483.1 |
| unchanged_assets_rebuild_3 | 366 | 2.55 | 10.60 | 430.1 | 459.2 |
| first_registration_1 | 570 | 2.08 | 1.82 | 520.4 | 551.2 |
| first_registration_2 | 480 | 2.48 | 2.50 | 437.4 | 469.7 |
| first_registration_3 | 577 | 2.06 | 1.85 | 531.1 | 563.9 |
| fresh_url_registration_1 | 515 | 2.31 | 2.14 | 445.9 | 477.5 |
| fresh_url_registration_2 | 440 | 2.71 | 2.98 | 509.3 | 546.8 |
| fresh_url_registration_3 | 523 | 2.27 | 1.99 | 435.0 | 466.2 |
| cached_image_idle | 1196 | 1.67 | 1.85 | 66.6 | 0.0 |
| cached_image_switch | 2010 | 1.75 | 2.04 | 30.5 | 0.0 |
| cached_image_reopen | 1913 | 1.83 | 1.94 | 68.1 | 0.0 |
| cached_image_switch_repeat | 2060 | 1.70 | 1.95 | 8.0 | 0.0 |
| text_only_switch_repeat | 1971 | 1.78 | 2.08 | 65.7 | 0.0 |
| text_only_idle_repeat | 1228 | 1.63 | 1.88 | 3.1 | 0.0 |
