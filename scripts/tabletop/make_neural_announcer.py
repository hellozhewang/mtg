#!/usr/bin/env python3
"""Generate the two announcer clips using local Kokoro-82M v1.0 (no API).

Run in a Python 3.12 environment with kokoro-onnx==0.6.1, numpy, scipy,
imageio-ffmpeg==0.6.0:
    ~/.cache/mtg-announcer/venv/bin/python scripts/tabletop/make_neural_announcer.py

Download kokoro-v1.0.onnx and voices-v1.0.bin from the project's model release
to ~/.cache/mtg-announcer/ first (or pass --models). No automatic downloads.
Model: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0
Retains the existing 22050 Hz mono/PCM16 format and clarity()/master() chain.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave

import imageio_ffmpeg
import numpy as np
from scipy.signal import resample_poly
from kokoro_onnx import Kokoro

import make_announcer as dsp

VOICE = {"am_michael": 0.70, "am_fenrir": 0.30}
LINES = {
    "slow-5min.wav": ("C'mon bro, what's taking so long?", 0.80),
    "slow-10min.wav": ("Bruh! Wake me up when you're done.", 0.65),
}
PITCH_SEMITONES = -5.0


def audio_filter(samples: np.ndarray, rate: int, filters: str) -> np.ndarray:
    result = subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
        "-f", "f32le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0",
        "-af", filters, "-f", "f32le", "-ar", str(rate), "-ac", "1", "pipe:1",
    ], input=samples.astype("<f4").tobytes(), capture_output=True, check=True)
    return np.frombuffer(result.stdout, dtype="<f4").copy()


def write_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(dsp.RATE)
        output.writeframes(pcm)


def attenuate(pcm: bytes, gain_db: float) -> bytes:
    samples = array.array("h", pcm)
    if sys.byteorder == "big":
        samples.byteswap()
    gain = 10 ** (gain_db / 20)
    samples = array.array("h", (round(v * gain) for v in samples))
    if sys.byteorder == "big":
        samples.byteswap()
    return samples.tobytes()


def ebu_levels(path: Path) -> dict:
    result = subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path), "-af",
        "loudnorm=I=-12.5:TP=-0.5:LRA=7:print_format=json", "-f", "null", "-",
    ], capture_output=True, text=True, check=True)
    return json.JSONDecoder().raw_decode(result.stderr[result.stderr.rfind("{"):])[0]


def finish(samples: np.ndarray, rate: int) -> bytes:
    # A pronounced pitch drop with tempo compensation gives a bass radio-host
    # delivery without slowing the words or the turn announcement.
    pitched_rate = round(rate * 2 ** (PITCH_SEMITONES / 12))
    samples = audio_filter(samples, rate,
                           f"asetrate={pitched_rate},aresample={rate},atempo={rate / pitched_rate:.8f}")
    voice = resample_poly(samples, dsp.RATE, rate).astype(np.float32)
    audible = np.flatnonzero(np.abs(voice) > 0.002)
    if not len(audible):
        raise ValueError("The voice engine returned silence")
    voice = voice[max(0, audible[0] - int(0.035 * dsp.RATE)):
                  min(len(voice), audible[-1] + int(0.09 * dsp.RATE))]
    voice = np.asarray(dsp.clarity(array.array("f", voice)), dtype=np.float32)
    # Warm broadcast body and presence; retain a full voice rather than an AM
    # telephone effect. The existing master supplies broadcast-style density.
    voice = audio_filter(voice, dsp.RATE,
                         "equalizer=f=160:t=q:w=0.8:g=3.5,"
                         "equalizer=f=3200:t=q:w=1:g=1,lowpass=f=8500:p=2")
    start = int(0.10 * dsp.RATE)
    tail = int(0.18 * dsp.RATE)
    mix = np.zeros(start + len(voice) + tail, dtype=np.float32)
    mix[start:start + len(voice)] += voice
    for seconds, gain in [(0.060, 0.035)]:
        offset = start + int(seconds * dsp.RATE)
        mix[offset:offset + len(voice)] += voice * gain
    hit = np.asarray(dsp.boom(), dtype=np.float32) * 0.12
    mix[:len(hit)] += hit
    mix[:int(0.025 * dsp.RATE)] *= np.linspace(0, 1, int(0.025 * dsp.RATE))
    return dsp.master(array.array("f", mix))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, default=Path.home() / ".cache/mtg-announcer")
    parser.add_argument("--out", type=Path, default=dsp.SOUNDS_DIR)
    args = parser.parse_args()
    model, voices = args.models / "kokoro-v1.0.onnx", args.models / "voices-v1.0.bin"
    kokoro = Kokoro(str(model), str(voices))
    style = sum(kokoro.get_voice_style(name) * weight for name, weight in VOICE.items())
    print("Model: Kokoro-82M v1.0 / kokoro-onnx 0.6.1 (local CPU)")
    print("Voice blend:", VOICE)
    print(f"Radio finish: {PITCH_SEMITONES:g} semitones, tempo preserved; warm EQ, minimal room echo")
    print("Model SHA-256:", hashlib.sha256(model.read_bytes()).hexdigest())
    print("Voice bank SHA-256:", hashlib.sha256(voices.read_bytes()).hexdigest())
    args.out.mkdir(parents=True, exist_ok=True)
    for name, (text, speed) in LINES.items():
        samples, rate = kokoro.create(text, voice=style, speed=speed, lang="en-us",
                                      sentence_pause=0.28, clause_pause=0.12)
        pcm = finish(samples, rate)
        path = args.out / name
        write_wav(path, pcm)
        # The old master is intentionally very hot. Trim its output to the
        # brief's loudness, preserving its peak ceiling and all dynamics.
        measured = dsp.loudness(path)
        if measured > -12.5:
            pcm = attenuate(pcm, -12.5 - measured)
            write_wav(path, pcm)
        # Sample peaks alone miss inter-sample overs. Measure independently at
        # FFmpeg's oversampled true-peak rate, then leave a little safety margin.
        levels = ebu_levels(path)
        if float(levels["input_tp"]) > -0.55:
            pcm = attenuate(pcm, -0.55 - float(levels["input_tp"]))
            write_wav(path, pcm)
            levels = ebu_levels(path)
        print(f"{name}: {len(pcm) / 2 / dsp.RATE:.2f}s, "
              f"{dsp.loudness(path):.1f} LUFS (project meter), {dsp.level(pcm)}; "
              f"EBU {levels['input_i']} LUFS / {levels['input_tp']} dBTP; {text!r}", flush=True)


if __name__ == "__main__":
    main()
