#!/usr/bin/env python3
"""Cut each battle song down to its chorus, the 10 seconds the table plays.

The full recordings live in tts/sounds/full/ (not published). Their chorus starts
are in tts/sounds/full/choruses.json; each clip is written to tts/sounds/ under the
song's own name, which is what cactuar_music.lua plays.

    make_choruses.py               cut every clip from choruses.json
    make_choruses.py --analyze     find starts for songs without an owner-set one, then cut

--analyze runs chorus.swift (macOS: AVFoundation + Accelerate): the loud stretch a
song repeats most. To move a chorus by ear, set that song's "start" in the JSON and
its "picked" to "owner"; --analyze then leaves it alone.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import subprocess
import sys
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOUNDS = REPO / "tts" / "sounds"
FULL = SOUNDS / "full"
STARTS = FULL / "choruses.json"
SWIFT = Path(__file__).with_name("chorus.swift")
SECONDS = 10.0
FADE_IN, FADE_OUT = 0.05, 1.0                       # no click in, a short tail out


def analyzer() -> Path:
    """chorus.swift, compiled once per version of its source."""
    tag = hashlib.sha256(SWIFT.read_bytes()).hexdigest()[:12]
    exe = REPO / ".cache" / f"chorus-{tag}"
    if not exe.exists():
        exe.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", "-o", str(exe), str(SWIFT)], check=True)
    return exe


def analyze(song: Path) -> dict:
    out = subprocess.run([str(analyzer()), str(song), str(SECONDS)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def cut(song: Path, start: float, dest: Path) -> None:
    """SECONDS of `song` from `start`, faded in and out, in the song's own format."""
    with wave.open(str(song), "rb") as w:
        rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        if width != 2:
            sys.exit(f"{song.name}: expected 16-bit PCM")
        first = min(int(start * rate), max(0, w.getnframes() - int(SECONDS * rate)))
        w.setpos(first)
        data = array.array("h", w.readframes(int(SECONDS * rate)))
    if sys.byteorder == "big":
        data.byteswap()
    frames = len(data) // channels
    fade_in, fade_out = int(FADE_IN * rate), int(FADE_OUT * rate)
    for i in range(frames):
        gain = min(1.0, i / fade_in if fade_in else 1.0, (frames - 1 - i) / fade_out if fade_out else 1.0)
        if gain < 1.0:
            for c in range(channels):
                data[i * channels + c] = int(data[i * channels + c] * gain)
    if sys.byteorder == "big":
        data.byteswap()
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(data.tobytes())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--analyze", action="store_true",
                    help="find chorus starts for songs the owner has not set")
    args = ap.parse_args()
    starts = json.loads(STARTS.read_text(encoding="utf-8")) if STARTS.exists() else {}
    songs = sorted(FULL.glob("*.wav"))
    if args.analyze:
        for song in songs:
            entry = starts.get(song.name) or {}
            if entry.get("picked") == "owner":
                continue
            found = analyze(song)
            best = found["candidates"][0]
            starts[song.name] = {
                "start": best["start"], "picked": "auto",
                "duration": round(found["duration"], 2),
                "others": [c["start"] for c in found["candidates"][1:]],
            }
        STARTS.write_text(json.dumps(starts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    missing = [s.name for s in songs if s.name not in starts]
    if missing:
        sys.exit(f"no chorus start for {', '.join(missing)}: run with --analyze")
    for song in songs:
        start = float(starts[song.name]["start"])
        cut(song, start, SOUNDS / song.name)
        print(f"{song.name:22} {int(start // 60)}:{start % 60:05.2f} -> tts/sounds/{song.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
