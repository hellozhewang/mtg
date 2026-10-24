#!/usr/bin/env python3
"""Record the slow-turn announcer lines as WAV files in tts/sounds/.

    python3 scripts/tabletop/make_announcer.py              # re-record every clip
    python3 scripts/tabletop/make_announcer.py --measure    # loudness of the clips (or named files)

See docs/development/tts-audio-guide.md for the loudness targets and how clips reach the table.

macOS only: the voice is `say`. Each clip is a low "boom", then the line spoken deep
and slow, with an arena-style echo, normalised loud: the "Double kill!" announcer of a
shooter. The table (tts/cactuar_turns.lua) plays them through Tabletop Simulator's
music player, so everyone hears them. The catalog build publishes tts/sounds/*.wav
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

SOUNDS_DIR = Path(__file__).resolve().parents[2] / "tts" / "sounds"
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
        out.append(math.sin(phase) * math.exp(-4.5 * t) * 0.35)   # under the voice, not over it
    return out


def arena(dry: array.array) -> array.array:
    """Two echoes and a short reverb tail: a voice in a big empty stadium."""
    taps = [(int(RATE * 0.11), 0.35), (int(RATE * 0.23), 0.22), (int(RATE * 0.37), 0.12)]
    out = array.array("f", dry) + array.array("f", [0.0] * (taps[-1][0] + RATE // 2))
    for delay, gain in taps:
        for i, s in enumerate(dry):
            out[i + delay] += s * gain
    return out


def biquad(x: array.array, kind: str, f0: float, q: float = 0.707, gain_db: float = 0.0) -> array.array:
    """An RBJ-cookbook filter: "highpass" or "highshelf"."""
    w = 2 * math.pi * f0 / RATE
    cw, alpha, a = math.cos(w), math.sin(w) / (2 * q), 10 ** (gain_db / 40)
    if kind == "highpass":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        d = [1 + alpha, -2 * cw, 1 - alpha]
    else:
        sq = 2 * math.sqrt(a) * alpha
        b = [a * ((a + 1) + (a - 1) * cw + sq), -2 * a * ((a - 1) + (a + 1) * cw),
             a * ((a + 1) + (a - 1) * cw - sq)]
        d = [(a + 1) - (a - 1) * cw + sq, 2 * ((a - 1) - (a + 1) * cw), (a + 1) - (a - 1) * cw - sq]
    b = [v / d[0] for v in b]
    d = [v / d[0] for v in d]
    out, x1, x2, y1, y2 = array.array("f"), 0.0, 0.0, 0.0, 0.0
    for s in x:
        y = b[0] * s + b[1] * x1 + b[2] * x2 - d[1] * y1 - d[2] * y2
        x2, x1, y2, y1 = x1, s, y1, y
        out.append(y)
    return out


def clarity(voice: array.array) -> array.array:
    """Cut the rumble that eats headroom, lift the 2-4 kHz band that carries words."""
    return biquad(biquad(voice, "highpass", 140), "highshelf", 2200, gain_db=6)


def compress(x: array.array, threshold_db: float = -26, ratio: float = 4.0,
             attack: float = 0.004, release: float = 0.12) -> array.array:
    """Even out syllables so the quiet ones are as loud as the loud ones."""
    ka, kr = 1 - math.exp(-1 / (RATE * attack)), 1 - math.exp(-1 / (RATE * release))
    env, out = 0.0, array.array("f")
    for s in x:
        level = abs(s)
        env += (level - env) * (ka if level > env else kr)
        over = 20 * math.log10(env) - threshold_db if env > 1e-6 else -1
        out.append(s * (10 ** (-over * (1 - 1 / ratio) / 20) if over > 0 else 1.0))
    return out


# Loudness. TTS plays these through each player's Music volume, usually set low, so
# the voice must sit near full scale on its own. A peak normalise alone left it at
# -16 dBFS RMS: a look-ahead limiter lets it be driven ~10 dB hotter without the
# tanh crunch that muddied the first version.
DRIVE_DB = 18.0          # gain into the limiter
CEILING = 0.94           # -0.5 dBFS
LOOKAHEAD = 0.004        # seconds: the gain is down before a peak arrives
RELEASE = 0.06           # seconds for the gain to recover


def limit(x: array.array) -> array.array:
    drive = 10 ** (DRIVE_DB / 20)
    look = max(1, int(RATE * LOOKAHEAD))
    recover = 1 - math.exp(-1 / (RATE * RELEASE))
    y = [s * drive for s in x]
    peaks = [abs(s) for s in y] + [0.0] * look
    # Sliding maximum over the look-ahead window, then a gain that drops at once and
    # recovers smoothly.
    window, gain, out = [], 1.0, array.array("f")
    from collections import deque
    window = deque()
    for i in range(len(peaks)):
        while window and peaks[window[-1]] <= peaks[i]:
            window.pop()
        window.append(i)
        if i < look:
            continue
        j = i - look
        while window[0] < j:
            window.popleft()
        need = min(1.0, CEILING / peaks[window[0]]) if peaks[window[0]] > 0 else 1.0
        gain = need if need < gain else gain + (need - gain) * recover
        out.append(max(-CEILING, min(CEILING, y[j] * gain)))
    return out


def master(x: array.array) -> bytes:
    peak = max(abs(s) for s in x) or 1.0
    x = compress(array.array("f", (s / peak for s in x)))
    peak = max(abs(s) for s in x) or 1.0
    y = limit(array.array("f", (s / peak for s in x)))
    pcm = array.array("h", (int(s * 32767) for s in y))
    if sys.byteorder == "big":
        pcm.byteswap()
    return pcm.tobytes()


def level(pcm: bytes) -> str:
    a = array.array("h", pcm)
    if sys.byteorder == "big":
        a.byteswap()
    rms = math.sqrt(sum(s * s for s in a) / len(a)) / 32768
    return f"peak {20 * math.log10(max(abs(s) for s in a) / 32768):.1f} dBFS, rms {20 * math.log10(rms):.1f} dBFS"


def loudness(path: Path) -> float:
    """Integrated loudness in LUFS, BS.1770-style: K-weighting, 400 ms blocks, -70 LUFS
    absolute and -10 LU relative gates. Approximate (mono, filters designed at RATE), but
    it is what the targets in README.md were measured with."""
    with wave.open(str(path)) as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, RATE):
            raise SystemExit(f"{path.name}: expected mono 16-bit {RATE} Hz")
        a = array.array("h", w.readframes(w.getnframes()))
    if sys.byteorder == "big":
        a.byteswap()
    x = array.array("f", (s / 32768 for s in a))
    k = biquad(biquad(x, "highshelf", 1682, gain_db=4.0), "highpass", 38, q=0.5)
    block, hop = int(RATE * 0.4), int(RATE * 0.1)
    if len(k) < block:
        ms = [sum(v * v for v in k) / max(1, len(k))]
    else:
        ms = [sum(v * v for v in k[i:i + block]) / block for i in range(0, len(k) - block + 1, hop)]
    lufs = lambda m: -0.691 + 10 * math.log10(m)
    ms = [m for m in ms if m > 0 and lufs(m) > -70]
    relative = lufs(sum(ms) / len(ms)) - 10
    ms = [m for m in ms if lufs(m) > relative]
    return lufs(sum(ms) / len(ms))


def main() -> int:
    if sys.argv[1:2] == ["--measure"]:
        for name in sys.argv[2:] or sorted(p.name for p in SOUNDS_DIR.glob("*.wav")):
            path = Path(name) if Path(name).exists() else SOUNDS_DIR / name
            with wave.open(str(path)) as w:
                pcm = w.readframes(w.getnframes())
            print(f"{path.name}: {loudness(path):.1f} LUFS, {level(pcm)}")
        return 0
    for name, text in LINES.items():
        clip = boom() + array.array("f", [0.0] * int(RATE * 0.08)) + arena(clarity(speak(text)))
        pcm = master(clip)
        with wave.open(str(SOUNDS_DIR / name), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm)
        print(f"{name}: {len(clip) / RATE:.1f}s  {level(pcm)}  {text!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
