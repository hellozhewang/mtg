#!/usr/bin/env python3
"""Generate announcer WAV clips via the ElevenLabs Text-to-Speech API.

    python3 scripts/tabletop/make_elevenlabs_announcer.py
    python3 scripts/tabletop/make_elevenlabs_announcer.py --list-voices
    python3 scripts/tabletop/make_elevenlabs_announcer.py --voice Roger --pitch -1.5 --speed 0.85
    python3 scripts/tabletop/make_elevenlabs_announcer.py --text "Yo hurry up man" -o tts/sounds/custom.wav

Reads the API key from `.apikeys/elevenlabsapikey.txt` (or `ELEVENLABS_API_KEY`).
Requests raw 22050 Hz 16-bit mono PCM directly from ElevenLabs (`pcm_22050`),
so no third-party Python packages are required. Outputs 22050 Hz mono PCM16 WAVs
normalized to the table's -12.5 LUFS / -0.5 dBFS target.
"""
from __future__ import annotations

import argparse
import array
import json
import math
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import wave
from pathlib import Path

_SCRIPTS = next(p for p in Path(__file__).resolve().parents if p.name == "scripts")
sys.path[:0] = [d for d in (str(_SCRIPTS / s) for s in ("common", "tabletop", "discord", "discord/bot"))
                if d not in sys.path]          # scripts/ is split by area; module names stay flat
import make_announcer as dsp

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KEY_FILE = REPO_ROOT / ".apikeys" / "elevenlabsapikey.txt"
API_BASE = "https://api.elevenlabs.io/v1"

# Custom-designed & cloned voices saved on the ElevenLabs account:
VOICE_PROFILES: dict[str, dict[str, object]] = {
    "hood_warfare_2": {
        "voice_id": "Z7lGZwgkqPHoS758ofO1",
        "name": "Hood Warfare 2 Narrator (Chi-Raq)",
        "voice_description": (
            "Cloned via ElevenLabs Audio Isolation (/v1/audio-isolation) + Instant Voice Cloning (/v1/voices/add) "
            "from Hood Warfare 2 Official Trailer (https://www.youtube.com/watch?v=fXz5DcshZ4g)."
        ),
        "source_url": "https://www.youtube.com/watch?v=fXz5DcshZ4g",
        "model_id": "eleven_multilingual_v2",
        "stability": 0.40,
        "similarity_boost": 0.95,
        "style": 0.65,
        "speed": 0.92,
    },
    "chiraq_hood_og": {
        "voice_id": "b3CripuhV1iIyKkvLG5c",
        "name": "Chi-Raq Hood OG",
        "voice_description": (
            "A raw, gritty, deep-voiced South Side Chicago African-American male drill rapper and street OG in his mid-20s. "
            "Authentic Chi-Raq street cadence, heavy resonant bass with a sharp, aggressive, impatient Midwest urban attitude, "
            "high energy and zero patience."
        ),
        "sample_text": (
            "Yo Twin, hurry yo ass up, you tweakin! "
            "On folks nem grave, what is taking you so long bro, pass the turn right now man!"
        ),
        "model_id": "eleven_multilingual_v2",
        "stability": 0.35,
        "similarity_boost": 0.88,
        "style": 0.80,
        "speed": 0.88,
    },
    "deep_hood_og": {
        "voice_id": "RLqZJZ6x0HMKpWcKD2lq",
        "name": "Deep Hood OG",
        "voice_description": (
            "A very deep, bass-heavy, gravelly African-American male voice from the hood in his 30s. "
            "Authentic urban street attitude, resonant chest bass, impatient and real, like a tough street OG."
        ),
        "sample_text": (
            "Come on bro, what is taking you so long? "
            "Yo man, hurry up and pass the turn, we ain't got all night out here, for real."
        ),
        "model_id": "eleven_multilingual_v2",
        "stability": 0.38,
        "similarity_boost": 0.88,
        "style": 0.75,
        "speed": 0.82,
    },
    "west_coast_og": {
        "voice_id": "PQwuCXrub5CDV6137lkt",
        "name": "West Coast OG (Snoop Style)",
        "voice_description": (
            "A laid-back, smooth, unhurried West Coast African-American male hip-hop OG in his 40s "
            "from Long Beach California. Slightly nasal, melodic mid-tenor drawl, super chill and "
            "relaxed cadence, effortlessly cool and slightly sleepy."
        ),
        "sample_text": (
            "Come on bro, what is taking you so long? "
            "Bruh, wake me up when you are done with your turn, for real man, we have been waiting all night."
        ),
        "model_id": "eleven_multilingual_v2",
        "stability": 0.42,
        "similarity_boost": 0.85,
        "style": 0.70,
        "speed": 0.82,
    },
    "roger_premade": {
        "voice_id": "CwhRBWXzGAHq8TQ4Fs17",
        "name": "Roger - Laid-Back, Casual, Resonant",
        "voice_description": "ElevenLabs pre-made classy casual male voice (pitched -1.5 st for West Coast drawl).",
        "model_id": "eleven_v3",
        "stability": 0.50,
        "similarity_boost": 0.75,
        "style": 0.65,
        "speed": 0.82,
        "pitch": -1.5,
    },
}

VOICE_5MIN = str(VOICE_PROFILES["hood_warfare_2"]["voice_id"])
VOICE_10MIN = str(VOICE_PROFILES["west_coast_og"]["voice_id"])
VOICE_CHANGE_TURN = str(VOICE_PROFILES["hood_warfare_2"]["voice_id"])
VOICE_START_GAME = str(VOICE_PROFILES["hood_warfare_2"]["voice_id"])
DEFAULT_VOICE = VOICE_5MIN
DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_TAG = "[laid-back, unhurried West Coast drawl]"

LINES: dict[str, tuple[str, str]] = {
    "slow-5min.wav": ("Yo Twin, hurry yo ass up, you tweakin!", VOICE_5MIN),
    "slow-10min.wav": (
        "In the beninging... In the, in the benin... In the beninging. Yah... In the, in, in...",
        VOICE_10MIN,
    ),
    "change-turn.wav": ("Gang, it's yo turn!", VOICE_CHANGE_TURN),
    "start-game.wav": ("Let's get this shit crackin!", VOICE_START_GAME),
}


def load_api_key(key_file: Path) -> str:
    env_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if env_key:
        return env_key
    if not key_file.is_file():
        raise SystemExit(
            f"error: API key file not found at {key_file} "
            "(and ELEVENLABS_API_KEY is not set)"
        )
    key = key_file.read_text(encoding="utf-8").strip()
    if not key:
        raise SystemExit(f"error: API key file {key_file} is empty")
    return key


def api_request(path: str, api_key: str, payload: dict | None = None) -> bytes:
    url = f"{API_BASE}{path}"
    headers = {
        "xi-api-key": api_key,
        "User-Agent": "MtgAnnouncer/1.0",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"ElevenLabs API error (HTTP {exc.code}): {detail}") from exc


def fetch_voices(api_key: str) -> list[dict]:
    raw = api_request("/voices", api_key)
    return json.loads(raw.decode("utf-8")).get("voices", [])


def design_voice(
    description: str,
    save_name: str,
    api_key: str,
    sample_text: str = (
        "Come on bro, what is taking you so long? "
        "Bruh, wake me up when you are done with your turn, for real man, we have been waiting all night."
    ),
) -> tuple[str, str]:
    """Create a custom voice from a text description via ElevenLabs Voice Design API and save it."""
    raw = api_request(
        "/text-to-voice/create-previews",
        api_key,
        {"voice_description": description, "text": sample_text},
    )
    previews = json.loads(raw.decode("utf-8")).get("previews", [])
    if not previews:
        raise SystemExit("error: Voice Design returned no previews")
    generated_id = previews[0]["generated_voice_id"]
    saved_raw = api_request(
        "/text-to-voice",
        api_key,
        {
            "voice_name": save_name,
            "voice_description": description,
            "generated_voice_id": generated_id,
        },
    )
    saved = json.loads(saved_raw.decode("utf-8"))
    return saved["voice_id"], saved.get("name", save_name)


def resolve_voice_id(spec: str, api_key: str) -> tuple[str, str]:
    """Resolve a voice name prefix or voice_id to (voice_id, display_name)."""
    voices = fetch_voices(api_key)
    for v in voices:
        if v.get("voice_id") == spec:
            return v["voice_id"], v.get("name", spec)
    low = spec.lower()
    for v in voices:
        name = v.get("name", "")
        if name.lower() == low or name.lower().startswith(low):
            return v["voice_id"], name
    for v in voices:
        name = v.get("name", "")
        if low in name.lower():
            return v["voice_id"], name
    return spec, spec


def synthesize_pcm(
    text: str,
    *,
    api_key: str,
    voice_id: str,
    model_id: str,
    stability: float,
    similarity_boost: float,
    style: float,
    speed: float,
    previous_text: str | None = None,
    next_text: str | None = None,
) -> array.array:
    """Request 22050 Hz 16-bit mono PCM from ElevenLabs and return float samples in [-1, 1]."""
    settings: dict[str, float | bool] = {
        "stability": stability,
        "similarity_boost": similarity_boost,
        "style": style,
        "speed": speed,
        "use_speaker_boost": True,
    }
    payload: dict[str, object] = {
        "text": text,
        "model_id": model_id,
        "voice_settings": settings,
    }
    if previous_text:
        payload["previous_text"] = previous_text
    if next_text:
        payload["next_text"] = next_text
    pcm_bytes = api_request(
        f"/text-to-speech/{voice_id}?output_format=pcm_{dsp.RATE}",
        api_key,
        payload,
    )
    if len(pcm_bytes) % 2:
        pcm_bytes = pcm_bytes[:-1]
    samples = array.array("h", pcm_bytes)
    if sys.byteorder == "big":
        samples.byteswap()
    return array.array("f", (s / 32768.0 for s in samples))


def decode_audio_file(audio_path: Path) -> array.array:
    """Decode any audio file (MP3, WAV, M4A, etc.) to 22050 Hz mono float32 samples."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            venv_py = Path.home() / ".cache/mtg-announcer/venv/bin/python"
            if venv_py.is_file():
                ffmpeg = subprocess.check_output(
                    [str(venv_py), "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
                    text=True,
                ).strip()
        except Exception:
            ffmpeg = None
    if not ffmpeg:
        raise SystemExit("error: --from-audio requires ffmpeg (or ~/.cache/mtg-announcer/venv)")
    res = subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-i", str(audio_path),
            "-f", "f32le", "-ar", str(dsp.RATE), "-ac", "1", "pipe:1",
        ],
        capture_output=True,
        check=True,
    )
    out = array.array("f", res.stdout)
    if sys.byteorder == "big":
        out.byteswap()
    return out


def pitch_shift(samples: array.array, semitones: float) -> array.array:
    """Shift pitch by `semitones` while preserving tempo via ffmpeg if available."""
    if abs(semitones) < 1e-3:
        return samples
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            venv_py = Path.home() / ".cache/mtg-announcer/venv/bin/python"
            if venv_py.is_file():
                ffmpeg = subprocess.check_output(
                    [str(venv_py), "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
                    text=True,
                ).strip()
        except Exception:
            ffmpeg = None
    if not ffmpeg:
        raise SystemExit("error: --pitch requires ffmpeg (or ~/.cache/mtg-announcer/venv)")
    pitched_rate = round(dsp.RATE * (2.0 ** (semitones / 12.0)))
    tempo = dsp.RATE / pitched_rate
    raw_in = samples.tobytes() if sys.byteorder == "little" else None
    if raw_in is None:
        cp = array.array("f", samples)
        cp.byteswap()
        raw_in = cp.tobytes()
    res = subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-f", "f32le", "-ar", str(dsp.RATE), "-ac", "1", "-i", "pipe:0",
            "-af", f"asetrate={pitched_rate},aresample={dsp.RATE},atempo={tempo:.8f}",
            "-f", "f32le", "-ar", str(dsp.RATE), "-ac", "1", "pipe:1",
        ],
        input=raw_in,
        capture_output=True,
        check=True,
    )
    out = array.array("f", res.stdout)
    if sys.byteorder == "big":
        out.byteswap()
    return out


def trim_silence(samples: array.array, threshold: float = 0.0008) -> array.array:
    first = next((i for i, s in enumerate(samples) if abs(s) > threshold), None)
    if first is None:
        raise ValueError("ElevenLabs returned silence")
    last = next(i for i in range(len(samples) - 1, -1, -1) if abs(samples[i]) > threshold)
    pad_head = int(0.050 * dsp.RATE)
    pad_tail = int(0.220 * dsp.RATE)
    start = max(0, first - pad_head)
    end = min(len(samples), last + pad_tail)
    return samples[start:end]


def compact_pauses(samples: array.array, max_pause_sec: float = 0.20, threshold: float = 0.003) -> array.array:
    """Cap long internal silences (e.g. after '!' or '...') to `max_pause_sec` so short lines stay punchy."""
    max_quiet = int(max_pause_sec * dsp.RATE)
    out = array.array("f")
    quiet_run = 0
    for s in samples:
        if abs(s) < threshold:
            quiet_run += 1
            if quiet_run <= max_quiet:
                out.append(s)
        else:
            quiet_run = 0
            out.append(s)
    return out


def finish_clip(
    voice: array.array,
    *,
    include_boom: bool = False,
    clarity_shelf_db: float = 1.5,
) -> array.array:
    """Clean sub-bass rumble, add a light room reflection (and optional cue thump), and pad."""
    voice = trim_silence(voice)
    # Remove sub-90 Hz rumble while keeping the warm low-mid chest resonance intact.
    voice = dsp.biquad(voice, "highpass", 85.0)
    if clarity_shelf_db:
        voice = dsp.biquad(voice, "highshelf", 2400.0, gain_db=clarity_shelf_db)

    lead = int(0.32 * dsp.RATE) if include_boom else int(0.03 * dsp.RATE)
    tail = int(0.18 * dsp.RATE)
    mix = array.array("f", [0.0] * (lead + len(voice) + tail))
    for i, s in enumerate(voice):
        mix[lead + i] += s

    # Subtle single room reflection so the voice sits naturally in the table space.
    echo_offset = lead + int(0.055 * dsp.RATE)
    for i, s in enumerate(voice):
        if echo_offset + i < len(mix):
            mix[echo_offset + i] += s * 0.035

    if include_boom:
        hit = dsp.boom()
        for i, s in enumerate(hit):
            if i < len(mix):
                mix[i] += s * 0.18

    fade = int(0.015 * dsp.RATE)
    for i in range(min(fade, len(mix))):
        mix[i] *= i / fade
    return mix


def master_to_lufs(
    samples: array.array,
    out_path: Path,
    target_lufs: float = -12.5,
    ceiling_dbfs: float = -0.6,
) -> bytes:
    """Compress, normalize to target LUFS, and enforce a strict peak ceiling."""
    peak = max(abs(s) for s in samples) or 1.0
    normed = array.array("f", (s / peak for s in samples))
    compressed = dsp.compress(normed, threshold_db=-20.0, ratio=2.8, attack=0.005, release=0.10)

    ceiling = 10 ** (ceiling_dbfs / 20.0)
    c_peak = max(abs(s) for s in compressed) or 1.0
    scaled = array.array("f", (s * (ceiling / c_peak) for s in compressed))

    def to_pcm(arr: array.array) -> bytes:
        pcm = array.array(
            "h",
            (int(max(-ceiling, min(ceiling, s)) * 32767) for s in arr),
        )
        if sys.byteorder == "big":
            pcm.byteswap()
        return pcm.tobytes()

    def write(pcm_bytes: bytes) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(dsp.RATE)
            w.writeframes(pcm_bytes)

    pcm = to_pcm(scaled)
    write(pcm)

    # Iteratively adjust gain + gentle limiting to hit target_lufs within ceiling.
    for _ in range(4):
        measured = dsp.loudness(out_path)
        diff_db = target_lufs - measured
        if abs(diff_db) < 0.15:
            break
        gain = 10 ** (diff_db / 20.0)
        updated = array.array("f")
        for s in scaled:
            v = s * gain
            if abs(v) > ceiling:
                v = math.copysign(ceiling * math.tanh(abs(v) / ceiling), v)
            updated.append(v)
        scaled = updated
        pcm = to_pcm(scaled)
        write(pcm)

    return pcm


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--key-file", type=Path, default=DEFAULT_KEY_FILE,
                    help="path to ElevenLabs API key file (default: .apikeys/elevenlabsapikey.txt)")
    ap.add_argument("--list-voices", action="store_true",
                    help="list voices available on the ElevenLabs account and exit")
    ap.add_argument("--list-profiles", action="store_true",
                    help="list saved custom personality profiles in VOICE_PROFILES and exit")
    ap.add_argument("--profile", choices=tuple(VOICE_PROFILES),
                    help="use a saved personality profile (sets voice_id, model, stability, similarity, style, speed)")
    ap.add_argument("--design-voice", metavar="DESCRIPTION",
                    help="design a new custom voice from a text description and save it to your account")
    ap.add_argument("--save-voice-name", default="Custom Announcer Voice",
                    help="name when saving a --design-voice (default: 'Custom Announcer Voice')")
    ap.add_argument("--voice", default=None,
                    help="override voice name or voice_id for all clips (default: per-clip Hood/Snoop voices)")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"ElevenLabs model_id (default: {DEFAULT_MODEL})")
    ap.add_argument("--style-tag", default=DEFAULT_TAG,
                    help="expressive audio tag prepended for eleven_v3/eleven_v4 (pass '' to disable)")
    ap.add_argument("--stability", type=float, default=0.38, help="voice stability 0..1 (default: 0.38)")
    ap.add_argument("--similarity", type=float, default=0.88, help="similarity_boost 0..1 (default: 0.88)")
    ap.add_argument("--style", type=float, default=0.75, help="style exaggeration 0..1 (default: 0.75)")
    ap.add_argument("--speed", type=float, default=0.82, help="speaking speed 0.7..1.2 (default: 0.82)")
    ap.add_argument("--pitch", type=float, default=0.0,
                    help="pitch shift in semitones with tempo preserved (e.g. -1.5 or +1.0)")
    ap.add_argument("--target-lufs", type=float, default=-12.0, help="target loudness in LUFS (default: -12.0)")
    ap.add_argument("--boom", action="store_true", help="add a sub-bass cue hit before the line")
    ap.add_argument("--no-boom", action="store_true", help="omit the sub-bass cue hit (default)")
    ap.add_argument("--from-audio", type=Path, metavar="AUDIO_FILE",
                    help="master an existing MP3/WAV file into 22050 Hz mono PCM16 WAV (requires -o/--out)")
    ap.add_argument("--previous-text", help="preceding context text to steer prosody/inflection without being spoken")
    ap.add_argument("--next-text", help="following context text to steer prosody/inflection without being spoken")
    ap.add_argument("--text", help="custom text to synthesize (requires -o/--out)")
    ap.add_argument("-o", "--out", type=Path, help="output WAV file (when --text or --from-audio is given) or output directory")
    args = ap.parse_args()

    if args.list_profiles:
        for key, prof in VOICE_PROFILES.items():
            print(f"[{key}]  {prof['name']} ({prof['voice_id']})")
            print(f"  Prompt   : {prof['voice_description']}")
            print(f"  Settings : model={prof['model_id']}, stability={prof['stability']}, "
                  f"similarity={prof['similarity_boost']}, style={prof['style']}, speed={prof['speed']}")
        return 0

    if args.profile:
        prof = VOICE_PROFILES[args.profile]
        args.voice = str(prof["voice_id"])
        args.model = str(prof["model_id"])
        args.stability = float(prof["stability"])
        args.similarity = float(prof["similarity_boost"])
        args.style = float(prof["style"])
        args.speed = float(prof["speed"])
        if "pitch" in prof and not args.pitch:
            args.pitch = float(prof["pitch"])

    if args.from_audio:
        out_path = args.out or (dsp.SOUNDS_DIR / "slow-10min.wav")
        if out_path.is_dir():
            out_path = out_path / (args.from_audio.stem + ".wav")
        voice_samples = decode_audio_file(args.from_audio)
        if args.pitch:
            voice_samples = pitch_shift(voice_samples, args.pitch)
        mixed = finish_clip(voice_samples, include_boom=bool(args.boom and not args.no_boom))
        pcm = master_to_lufs(mixed, out_path, target_lufs=args.target_lufs, ceiling_dbfs=-0.5)
        dur = len(pcm) / 2 / dsp.RATE
        print(f"{out_path.name}: {dur:.2f}s, {dsp.loudness(out_path):.1f} LUFS, "
              f"{dsp.level(pcm)}  [from {args.from_audio.name}]")
        return 0

    api_key = load_api_key(args.key_file)

    if args.list_voices:
        for v in fetch_voices(api_key):
            labels = v.get("labels", {})
            desc = (v.get("description") or "").strip()
            print(f"{v['voice_id']}  {v.get('name', ''):<38}  {labels.get('gender', ''):<6}  {desc}")
        return 0

    if args.design_voice:
        override_id, override_name = design_voice(args.design_voice, args.save_voice_name, api_key)
        print(f"Designed & saved voice: {override_name} ({override_id})")
    elif args.voice:
        override_id, override_name = resolve_voice_id(args.voice, api_key)
    else:
        override_id = override_name = None

    print(f"Model : {args.model} (stability={args.stability}, similarity={args.similarity}, "
          f"style={args.style}, speed={args.speed}, pitch={args.pitch:+g} st)")

    if args.text:
        out_path = args.out or (dsp.SOUNDS_DIR / "custom.wav")
        if out_path.is_dir():
            out_path = out_path / "custom.wav"
        jobs = [(out_path, args.text, override_id or DEFAULT_VOICE)]
    else:
        out_dir = args.out or dsp.SOUNDS_DIR
        jobs = [(out_dir / name, line, override_id or v_id) for name, (line, v_id) in LINES.items()]

    tag = args.style_tag.strip() if args.model.startswith(("eleven_v3", "eleven_v4")) else ""
    for out_path, raw_line, v_id in jobs:
        voice_id, voice_name = (override_id, override_name) if override_id else resolve_voice_id(v_id, api_key)
        prompt_text = f"{tag} {raw_line}".strip() if tag and not raw_line.startswith("[") else raw_line
        voice_samples = synthesize_pcm(
            prompt_text,
            api_key=api_key,
            voice_id=voice_id,
            model_id=args.model,
            stability=args.stability,
            similarity_boost=args.similarity,
            style=args.style,
            speed=args.speed,
            previous_text=args.previous_text,
            next_text=args.next_text,
        )
        if args.pitch:
            voice_samples = pitch_shift(voice_samples, args.pitch)
        mixed = finish_clip(voice_samples, include_boom=bool(args.boom and not args.no_boom))
        pcm = master_to_lufs(mixed, out_path, target_lufs=args.target_lufs)
        dur = len(pcm) / 2 / dsp.RATE
        print(f"{out_path.name}: {dur:.2f}s, {dsp.loudness(out_path):.1f} LUFS, "
              f"{dsp.level(pcm)}  [{voice_name}]  {raw_line!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
