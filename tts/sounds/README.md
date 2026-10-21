# Announcer clips

## Current slow-turn clips (2026-10-21)

The 5-minute clip is the prepared `hood_warfare_2` recording: **"Yo Twin, hurry yo
ass up, you tweakin!"** The 10-minute clip is the supplied `beginning-stutter1.mp3`
recording, converted/mastered as **"In the beninging..."**. Both are mono PCM16 WAV,
22050 Hz. The timer's chat messages match the recordings.

| Clip | Duration | Project loudness | Sample peak | URL version |
|---|---|---|---|---|
| `slow-5min.wav` | 3.089 s | -12.0 LUFS | -0.6 dBFS | `bb39d5f0` |
| `slow-10min.wav` | 10.151 s | -12.0 LUFS | -0.5 dBFS | `bd36607e` |

The new source files and the published files must match before building the table.
The local neural generator below describes the previous recordings; running it
would replace these current clips.

## Previous audio: deep radio voice, second revision (2026-10-19)

The two WAVs now use **Kokoro-82M v1.0**, through `kokoro-onnx==0.6.1`, with an
original preset blend: **70% `am_michael` + 30% `am_fenrir`**. Generated locally,
without an account, API key, paid service, voice cloning or reference recording.
Model and voice files come from the
[Kokoro ONNX model release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0).

Regenerate with the new generator, not the legacy Ralph command below:

```sh
~/.cache/mtg-announcer/venv/bin/python scripts/make_neural_announcer.py
python3 scripts/make_announcer.py --measure
```

The owner asked for a deeper voice again. The current pair uses a **five-semitone pitch
drop with tempo compensation** (three semitones below the first radio pair), stronger
160 Hz body, light presence EQ and a restrained upper
roll-off. A single quiet room reflection replaces the arena echoes. The bass accent
is quieter too. This is a full, warm radio-host voice rather than a narrow telephone
effect. The existing `clarity()` / `master()` chain, loudness trim and independent
FFmpeg true-peak check remain. Model/voice hashes are printed on regeneration.

| Clip | Duration | Project meter | Independent EBU loudness | True peak |
|---|---|---|---|---|
| `slow-5min.wav` | 2.96 s | -12.5 LUFS | -12.45 LUFS | -0.75 dBTP |
| `slow-10min.wav` | 3.10 s | -12.8 LUFS | -12.95 LUFS | -0.55 dBTP |

Both remain mono PCM16 WAV, 22050 Hz, with the same filenames and words. These are the
v30 source clips. Publish them through the catalog build, then use
`scripts/release_tts.py` to verify Pages and deliver the new table, as described below.
Owner listening and in-game approval remain.

The Cactuar table's slow-turn announcer plays these clips when one player's turn reaches
5 and then 10 minutes.

| File | Line | When |
|---|---|---|
| `slow-5min.wav` | "Yo Twin, hurry yo ass up, you tweakin!" | 5 minutes into a turn |
| `slow-10min.wav` | "In the beninging..." | 10 minutes into a turn |

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

    python3 scripts/make_announcer.py              # re-record both clips into this folder
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
- **WAV** is what's tested in game. `.mp3` and `.ogg` are published too
  (`ttsdecks.SOUND_TYPES`), but test a new format in TTS before relying on it.

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
   the version. Commit and push the resulting `tts/CHANGELOG.md` entry afterwards
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
