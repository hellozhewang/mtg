#!/usr/bin/env python3
"""Record the slow-turn announcer lines as WAV files beside this script.

    python3 tts/sounds/make_announcer.py

macOS only: the voice is `say`. Each clip is a low "boom", then the line spoken deep
and slow, with an arena-style echo, normalised loud: the "Double kill!" announcer of a
shooter. The table (tts/cactuar_turns.lua) plays them through Tabletop Simulator's
music player, so everyone hears them. The catalog build publishes this folder's .wav
files to docs/tts/sounds/.
"""
from __future__ import annotations

import array
import math
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
RATE = 22050
VOICE = "Ralph"                     # a deep classic voice that honours [[pbas]]/[[rate]]
LINES = {
    "slow-5min.wav": "Come on bro... what's taking so long?",
    "slow-10min.wav": "Bruh... wake me up when you're done.",
}


def speak(text: str) -> array.array:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "line.wav"
        # Lower pitch, slower, louder: embedded speech commands of the classic voices.
        subprocess.run(["say", "-v", VOICE, "--file-format=WAVE", f"--data-format=LEI16@{RATE}",
                        "-o", str(out), f"[[pbas 28]] [[rate 135]] [[volm 1.0]] {text}"], check=True)
        with wave.open(str(out)) as w:
            assert w.getnchannels() == 1 and w.getsampwidth() == 2, "expected mono 16-bit"
            samples = array.array("h", w.readframes(w.getnframes()))
    if sys.byteorder == "big":
        samples.byteswap()
    return array.array("f", (s / 32768 for s in samples))


def boom(seconds: float = 0.45) -> array.array:
    """A falling sub-bass hit, the 'BWOMM' before the line."""
    n = int(RATE * seconds)
    out, phase = array.array("f"), 0.0
    for i in range(n):
        t = i / n
        phase += 2 * math.pi * (70 - 35 * t) / RATE
        out.append(math.sin(phase) * math.exp(-4.5 * t) * 0.9)
    return out


def arena(dry: array.array) -> array.array:
    """Two echoes and a short reverb tail: a voice in a big empty stadium."""
    taps = [(int(RATE * 0.11), 0.35), (int(RATE * 0.23), 0.22), (int(RATE * 0.37), 0.12)]
    out = array.array("f", dry) + array.array("f", [0.0] * (taps[-1][0] + RATE // 2))
    for delay, gain in taps:
        for i, s in enumerate(dry):
            out[i + delay] += s * gain
    return out


def master(x: array.array) -> bytes:
    peak = max(abs(s) for s in x) or 1.0
    gain = 0.95 / peak
    pcm = array.array("h", (int(max(-1.0, min(1.0, math.tanh(s * gain * 1.6) / math.tanh(1.6))) * 32767) for s in x))
    if sys.byteorder == "big":
        pcm.byteswap()
    return pcm.tobytes()


def main() -> int:
    for name, text in LINES.items():
        clip = boom() + array.array("f", [0.0] * int(RATE * 0.08)) + arena(speak(text))
        with wave.open(str(HERE / name), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(master(clip))
        print(f"{name}: {len(clip) / RATE:.1f}s  {text!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
