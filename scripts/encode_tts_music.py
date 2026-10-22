#!/usr/bin/env python3
"""Reproduce the historical v48 MP3s (not used by v49+).

The owner's TTS client did not play these MP3 derivatives correctly. Runtime music
now uses the original WAVs; retain this only to reproduce the old v48 artifacts.

No synthesis, API calls, volume changes or edits to the source recordings.
    python3 scripts/encode_tts_music.py
"""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        python = Path.home() / ".cache/mtg-announcer/venv/bin/python"
        ffmpeg = subprocess.check_output(
            [str(python), "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
            text=True).strip()
    for name in ("ff14_theme", "ff14_ultima"):
        source = ROOT / "tts/sounds" / (name + ".wav")
        target = source.with_suffix(".mp3")
        temporary = target.with_suffix(".tmp.mp3")
        try:
            subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                            "-i", str(source), "-map_metadata", "-1", "-c:a", "libmp3lame",
                            "-q:a", "2", str(temporary)], check=True)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        published = ROOT / "docs/tts/sounds" / target.name
        published.parent.mkdir(parents=True, exist_ok=True)
        published.write_bytes(target.read_bytes())
        print(f"{target.relative_to(ROOT)}: {source.stat().st_size:,} -> {target.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
