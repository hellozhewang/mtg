# Announcer clips

Audio source assets remain in `tts/sounds/`; this guide lives in `docs/development/`.

## FF14 soundtrack (v50)

The original `ff14_theme.wav` (Prelude / Discoveries) loops until cannon/start.
During the active player's turn, **10+** battlefield objects select one looping
WAV in this descending priority:

| Threshold | WAV |
|---|---|
| Goblins | `ff14_titan.wav` |
| Artifacts | `ff14_ultima.wav` |
| White creatures | `ff14_thordan.wav` (Heroes) |
| Black creatures | `ff14_hades.wav` (Who Brings Shadow) |
| Blue creatures | `ff14_alexander.wav` (Locus) |
| Green creatures | `ff14_garuda.wav` |
| Red creatures | `ff14_ifrit.wav` |

Library/exile/graveyard/commander columns and face-down cards do not count.
Multicolor creatures count for each color. Type lines, embedded face-color metadata
and explicit color/type tags drive counts; no runtime Scryfall requests. The normal
site build generates `docs/tts/card-colors.json`; refresh just that snapshot with
`python3 scripts/build_tts_music_metadata.py` before a table-only release.

A retained song pauses/resumes between eligible turns. Switching to another song
restarts it: MusicPlayer exposes no timestamp/seek API for separate playheads.
Custom turn/slow-turn voices are skipped while any battle song is loaded, including
while paused. Native beeps/text remain. `music off` / `music on` controls music
separately from `announcer off`. Each load replaces the playlist with one entry;
cannon fire clears the setup playlist. Original mono PCM16 WAVs at 22050 Hz are
used without conversion or volume changes.

v48's MP3 copies produced repeated sounds on the owner's client; playlist replacement
alone did not fix that. The owner confirmed both original theme/Ultima WAVs work.
The unused `ff14_theme.mp3` and `ff14_ultima.mp3` source/published copies and the
obsolete MP3 encoder were removed on 2026-10-22. Current saves, including Steam
v64, use WAVs exclusively. Old v48 reproduction remains available in Git history.
All 15 WAV assets retain their existing bytes and URLs.

## Turn-change clip (v46)

`change-turn.wav` is the owner-selected 1.696s mono PCM16 clip at 22050 Hz
(SHA-256 prefix `777efbb9`). It plays through the shared Music Player on genuine
reported turn starts after setup, including same-seat events, so everyone hears it
at their own MP3
Volume. `announcer off` mutes it along with the slow-turn clips. It does not loop
or play during the initial loading grace period. Chat `turn sound test` plays it
without advancing the turn. In a one-player table, native End Turn can beep without
firing a Lua turn event; use that test command to check the custom sound solo.
TTS's native incoming-player
ping remains separate; Workshop Lua cannot replace its sound or target a custom
Music Player clip to just one player. The shared channel can interrupt music.

## Current audio: ElevenLabs Voice Design + mastered WAV output (2026-10-21)

The announcer WAVs are generated and mastered via `scripts/make_elevenlabs_announcer.py`
(API key stored locally in `.apikeys/elevenlabsapikey.txt`, which is gitignored).

```sh
python3 scripts/make_elevenlabs_announcer.py --list-profiles
python3 scripts/make_elevenlabs_announcer.py --profile hood_warfare_2 --text "Yo Twin, hurry yo ass up, you tweakin!" -o tts/sounds/slow-5min.wav
python3 scripts/make_elevenlabs_announcer.py --from-audio path/to/beginning-stutter1.mp3 -o tts/sounds/slow-10min.wav --target-lufs -12.0
python3 scripts/make_announcer.py --measure
```

### Saved Voice Personalities (`VOICE_PROFILES` in `scripts/make_elevenlabs_announcer.py`)

All custom and cloned voices created via ElevenLabs are saved both on the ElevenLabs account and in `VOICE_PROFILES` inside `scripts/make_elevenlabs_announcer.py`:

| Profile Key | Voice ID | Name | Source / Prompt (`voice_description`) | Settings (`model_id`, `stability`, `similarity`, `style`, `speed`) |
|---|---|---|---|---|
| `hood_warfare_2` *(active 5-min & change-turn voice)* | `Z7lGZwgkqPHoS758ofO1` | **Hood Warfare 2 Narrator (Chi-Raq)** | Cloned via ElevenLabs Audio Isolation (`/v1/audio-isolation`) + Instant Voice Cloning (`/v1/voices/add`) from *Hood Warfare 2 Official Trailer* (`https://www.youtube.com/watch?v=fXz5DcshZ4g`). | `eleven_multilingual_v2`, `stability=0.40`, `similarity=0.95`, `style=0.65`, `speed=0.92` |
| `chiraq_hood_og` | `b3CripuhV1iIyKkvLG5c` | **Chi-Raq Hood OG** | *"A raw, gritty, deep-voiced South Side Chicago African-American male drill rapper and street OG in his mid-20s. Authentic Chi-Raq street cadence, heavy resonant bass with a sharp, aggressive, impatient Midwest urban attitude, high energy and zero patience."* | `eleven_multilingual_v2`, `stability=0.35`, `similarity=0.88`, `style=0.80`, `speed=0.88` |
| `deep_hood_og` | `RLqZJZ6x0HMKpWcKD2lq` | **Deep Hood OG** | *"A very deep, bass-heavy, gravelly African-American male voice from the hood in his 30s. Authentic urban street attitude, resonant chest bass, impatient and real, like a tough street OG."* | `eleven_multilingual_v2`, `stability=0.38`, `similarity=0.88`, `style=0.75`, `speed=0.82` |
| `west_coast_og` | `PQwuCXrub5CDV6137lkt` | **West Coast OG (Snoop Style)** | *"A laid-back, smooth, unhurried West Coast African-American male hip-hop OG in his 40s from Long Beach California. Slightly nasal, melodic mid-tenor drawl, super chill and relaxed cadence, effortlessly cool and slightly sleepy."* | `eleven_multilingual_v2`, `stability=0.42`, `similarity=0.85`, `style=0.70`, `speed=0.82` |
| `roger_premade` | `CwhRBWXzGAHq8TQ4Fs17` | **Roger - Laid-Back, Casual, Resonant** | ElevenLabs pre-made library voice (pitched `-1.5` semitones with `[laid-back, unhurried West Coast drawl]`). | `eleven_v3`, `stability=0.50`, `similarity=0.75`, `style=0.65`, `speed=0.82`, `pitch=-1.5` |

### Current Clip Measurements

| Clip | Source | Duration | Project meter | Peak | RMS |
|---|---|---|---|---|---|
| `start-game.wav` | ElevenLabs `Z7lGZwgkqPHoS758ofO1` (`hood_warfare_2`) | 1.65 s | -12.1 LUFS | -0.6 dBFS | -13.3 dBFS |
| `change-turn.wav` | ElevenLabs `Z7lGZwgkqPHoS758ofO1` (`hood_warfare_2`) | 1.70 s | -12.1 LUFS | -0.6 dBFS | -12.9 dBFS |
| `slow-5min.wav` | ElevenLabs `Z7lGZwgkqPHoS758ofO1` (`hood_warfare_2`) | 3.09 s | -12.0 LUFS | -0.6 dBFS | -12.0 dBFS |
| `slow-10min.wav` | `beginning-stutter1.mp3` (`--from-audio`) | 10.15 s | -12.0 LUFS | -0.5 dBFS | -11.8 dBFS |
| `sf_3_cursor.wav` | CPS3 *Street Fighter III: 3rd Strike* ROM (`SE_00065.wav`) | 0.10 s | -12.5 LUFS | -0.7 dBFS | -12.2 dBFS |
| `sf_3_select.wav` | CPS3 *Street Fighter III: 3rd Strike* ROM (`SE_00018.wav` + `SE_00019.wav`) | 0.53 s | -12.6 LUFS | -0.6 dBFS | -12.5 dBFS |
| `sf_3_theme.wav` | *Street Fighter III 3rd Strike - Let's Get It On.mp3* | 319.66 s | -15.9 LUFS | -0.8 dBFS | -15.0 dBFS |
| `ff14_theme.wav` | *Final Fantasy XIV Prelude - Discoveries Final Fantasy XIV OST.mp3* | 632.35 s | -16.9 LUFS | -1.0 dBFS | -16.0 dBFS |
| `ff14_ultima.wav` | *FFXIV The Weapon's Refrain (ultimate) Ultima Phase OST.mp3* | 297.17 s | -15.7 LUFS | -0.7 dBFS | -15.3 dBFS |
| `ff14_garuda.wav` | *FFXIV The Weapon's Refrain (ultimate) Full Garuda OST.mp3* | 251.84 s | -15.0 LUFS | -2.1 dBFS | -15.5 dBFS |
| `ff14_ifrit.wav` | *FFXIV The Weapon's Refrain (ultimate) Full Ifrit OST.mp3* | 171.92 s | -16.0 LUFS | -4.4 dBFS | -15.9 dBFS |
| `ff14_titan.wav` | *FFXIV The Weapon's Refrain (ultimate) Full Titan OST.mp3* | 319.90 s | -16.3 LUFS | -5.6 dBFS | -16.1 dBFS |
| `ff14_thordan.wav` | *FFXIV King Thordan's Theme — Heroes (Heavensward OST)* | 512.53 s | -17.0 LUFS | -3.2 dBFS | -15.5 dBFS |
| `ff14_alexander.wav` | *FFXIV Alexander Theme — Locus (Heavensward OST)* | 535.95 s | -16.0 LUFS | -0.6 dBFS | -13.8 dBFS |
| `ff14_hades.wav` | *FFXIV Hades Theme — Who Brings Shadow (Shadowbringers OST)* | 465.92 s | -15.8 LUFS | -2.3 dBFS | -15.0 dBFS |

## Previous local generator: Kokoro-82M neural radio voice (2026-10-19)

The earlier local WAVs used **Kokoro-82M v1.0**, through `kokoro-onnx==0.6.1`, with an
original preset blend: **70% `am_michael` + 30% `am_fenrir`**. Generated locally,
without an account, API key, paid service, voice cloning or reference recording.
Model and voice files come from the
[Kokoro ONNX model release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0).

Regenerate with the local neural generator:

```sh
~/.cache/mtg-announcer/venv/bin/python scripts/make_neural_announcer.py
python3 scripts/make_announcer.py --measure
```

The Cactuar table's slow-turn announcer plays these clips when one player's turn reaches
5 and then 10 minutes.

| File | Line | When |
|---|---|---|
| `slow-5min.wav` | "Yo Twin, hurry yo ass up, you tweakin!" | 5 minutes into a turn |
| `slow-10min.wav` | "In the beninging... In the, in the benin... In the beninging. Yah... In the, in, in..." | 10 minutes into a turn |

The file names, lines and times are in `CZT.lines` in `tts/cactuar_turns.lua`. If you rename
a clip, change it there too.

## How the table plays them

`cztAnnounce` in `tts/cactuar_turns.lua` hands the clip's URL to TTS's Music Player
(`MusicPlayer.setCurrentAudioclip` + `play()`), so everyone at the table hears it. Two
consequences:

- **Loudness has to be in the file.** A script can't set the Music Player's volume: each
  player's own **MP3 Volume** slider decides it. The owner's slider is at maximum and the
  first clips were still too quiet. If a clip is quiet, fix the file.
- **Clips are downloaded from the website, not the save.** The URL is
  `https://hellozhewang.github.io/mtg/tts/sounds/<file>?v=<hash>`. A new clip reaches players
  only after it's pushed to GitHub Pages and a new table build is loaded.

## Legacy placeholder generator

    python3 scripts/make_announcer.py              # re-record both clips into tts/sounds/
    python3 scripts/make_announcer.py --measure    # check their loudness
    python3 scripts/make_announcer.py --measure some/other.wav

This older generator overwrites the neural WAVs with macOS `say` using Ralph. The owner wants a
clearer, in-character arena or radio announcer; see the TODO at the top of `tts/WIP.md`.
To swap in a better voice, replace `speak()` and keep the rest of the chain:

1. `boom()`: a short falling sub-bass hit before the line, kept quiet (0.35) so it sits
   under the voice.
2. `clarity()`: a 140 Hz high-pass, then a +6 dB shelf above 2.2 kHz. It removes rumble
   that wastes headroom and lifts the frequencies that make words understandable.
3. `arena()`: three echoes for a big-room feel. Keep it light, or the words smear.
4. `master()`: a 4:1 compressor from -26 dB, then a 4 ms look-ahead limiter with 18 dB of
   drive (`DRIVE_DB`) into a -0.5 dBFS ceiling.

A new voice engine's output must go through `clarity()` and `master()` too, at
`RATE` = 22050 Hz, mono, 16-bit. Resample engine output that arrives at another rate.

## Targets

Check every new clip with `--measure` before you commit it.

| | Target | First clips (too quiet) | Current |
|---|---|---|---|
| Loudness | about **-12 to -13 LUFS** | -18.6 LUFS | -12.5 / -12.8 LUFS |
| Peak | -0.5 dBFS ceiling, never above | -0.1 dBFS | -2.4 / -1.9 dBFS sample peaks; -0.75 / -0.55 dBTP |

The neural clips leave sample-peak headroom so inter-sample true peaks also stay
below the ceiling. Loudness is matched to the target independently of peak height.

- **Not louder than about -11 LUFS.** Past that the limiter only flattens the voice: 24 dB
  of drive measured only 0.4 LU louder than 18 dB, and sounded worse.
- **Keep clips short**, about 3 to 4 seconds: they interrupt a game.
- **WAV** is the tested, currently published format. Generic publishing tools
  still recognize `.mp3` and `.ogg`, but no such playback assets remain in the
  sound folders. The mastering tool may accept an MP3 input and produce WAV output;
  those input-format examples and TTS's **MP3 Volume** setting are still valid.

## Getting a new clip to the table

Do the steps in this order.

1. Regenerate, and run `--measure`.
2. Listen to both clips, then give the owner the files to judge. The owner's PC Desktop is
   the usual place; `INTERNALS.md` has how to reach it.
3. Copy them to `docs/tts/sounds/`. A site build (`scripts/build_site.py`) does this too.
4. Run `python3 -m unittest discover tests`.
5. Commit, and push **only when the owner says so**: the repo is public.
6. **After** the push is live on Pages, run
   `python3 scripts/release_tts.py --notes "Updated announcer clips"`. It verifies
   the published bytes, builds the next `_vN` save from HEAD, delivers it and records
   the version. Commit and push the resulting `docs/development/tts-changelog.md` entry afterwards
   (see the root README and `tts/WIP.md`).

The build adds `?v=<sha256[:8]>` to each clip URL, because TTS caches audio by URL. If someone
loads the new table before the push is live, TTS caches the old clip under the new URL.

## Rules

- **Never clone a real person's voice or a game's announcer.** An original voice "in the
  style of" an arena announcer is fine.
- **Ask the owner before signing up for anything** or spending money. That includes
  ElevenLabs, OpenAI TTS and similar services.
- **Commit no API keys.** Print the voice and model you used, and record them in
  `tts/WIP.md`.
- **Respect the off switch.** Players can mute the announcer in chat with
  `announcer off`, and it must stay that way.
