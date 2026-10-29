"""make_choruses: every battle song has a 10-second chorus clip, cut from its start."""
from __future__ import annotations

import array
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _paths  # noqa: E402,F401  (scripts/<area>/ on sys.path)

import make_choruses as mc


def frames(path: Path) -> tuple[int, array.array]:
    with wave.open(str(path), "rb") as w:
        return w.getframerate(), array.array("h", w.readframes(w.getnframes()))


class CutTests(unittest.TestCase):
    def test_a_clip_is_ten_seconds_from_the_start_and_faded(self):
        with tempfile.TemporaryDirectory() as tmp:
            song, clip = Path(tmp) / "song.wav", Path(tmp) / "clip.wav"
            rate = 1000
            with wave.open(str(song), "wb") as w:              # 30 s; sample = its second
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
                w.writeframes(array.array("h", [1000 * (i // rate) for i in range(30 * rate)]).tobytes())
            mc.cut(song, 12.0, clip)
            got_rate, data = frames(clip)
            self.assertEqual((got_rate, len(data)), (rate, int(mc.SECONDS * rate)))
            self.assertEqual(data[0], 0)                                  # faded in
            self.assertEqual(data[rate * 2], 14000)                       # 12 s + 2 s, untouched
            self.assertLess(abs(data[-1]), 100)                           # faded out
            mc.cut(song, 25.0, clip)                                      # past the end: the last 10 s
            self.assertEqual(frames(clip)[1][rate * 2], 22000)


class RepoTests(unittest.TestCase):
    def test_every_song_has_a_start_and_a_published_clip(self):
        starts = json.loads(mc.STARTS.read_text(encoding="utf-8"))
        songs = sorted(p.name for p in mc.FULL.glob("*.wav"))
        self.assertEqual(len(songs), 16)
        self.assertEqual(sorted(starts), songs)
        for name in songs:
            with wave.open(str(mc.SOUNDS / name), "rb") as w:
                self.assertAlmostEqual(w.getnframes() / w.getframerate(), mc.SECONDS, places=2, msg=name)
        self.assertGreater((mc.SOUNDS / "ff14_theme.wav").stat().st_size, 10_000_000)   # prelude stays whole


if __name__ == "__main__":
    unittest.main()
