"""sleever (bot/sleever.py): turning a model's picture into a published sleeve."""
from __future__ import annotations

import contextlib
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))

import sleever

SIPS = Path("/usr/bin/sips").exists()


def png(path: Path, w: int, h: int) -> Path:
    """A plain RGB PNG: left half red, right half blue."""
    row = b"".join(b"\xff\x00\x00" if x < w // 2 else b"\x00\x00\xff" for x in range(w))
    raw = b"".join(b"\x00" + row for _ in range(h))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return path


class Isolated(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.sleeves = self.dir / "sleeves"
        self.sleeves.mkdir()
        for name, value in {"SLEEVES_DIR": self.sleeves, "STAGING": self.dir / "staging",
                            "OWNERS": self.dir / "staging" / "owners.json"}.items():
            patcher = patch.object(sleever, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)


class NamingTests(Isolated):
    def test_the_sleeve_line_names_it_and_leaves_the_reply(self):
        answer = "Made **Sailor Moon** sleeves: a crescent moon on pink.\nSleeve: Sailor Moon\n"
        self.assertEqual(sleever.sleeve_name(answer), "Sailor Moon")
        self.assertEqual(sleever.strip_name_line(answer), "Made **Sailor Moon** sleeves: a crescent moon on pink.")
        self.assertEqual(sleever.slugify("Sailor Moon!"), "sailor-moon")
        self.assertEqual(sleever.slugify("???"), "sleeves")

    def test_never_overwrites_someone_elses_or_a_hand_made_sleeve(self):
        (self.sleeves / "cactuar.jpg").write_bytes(b"x")              # hand-made: no owner
        self.assertEqual(sleever.choose_slug("Cactuar", "zz", None), "cactuar-2")
        sleever.record_owner("moon", "ana")
        (self.sleeves / "moon.jpg").write_bytes(b"x")
        self.assertEqual(sleever.choose_slug("Moon", "zz", None), "moon-2")
        self.assertEqual(sleever.choose_slug("Moon", "ana", None), "moon")    # her own
        self.assertEqual(sleever.choose_slug("Standard", "zz", None), "standard-sleeves")

    def test_a_revision_keeps_the_sessions_sleeve(self):
        (self.sleeves / "cactuar.jpg").write_bytes(b"x")
        sleever.record_owner("cactuar-2", "zz")
        (self.sleeves / "cactuar-2.jpg").write_bytes(b"x")
        self.assertEqual(sleever.choose_slug("Cactuar", "zz", "cactuar-2"), "cactuar-2")
        self.assertEqual(sleever.choose_slug("Desert Bloom", "zz", "cactuar-2"), "desert-bloom")


@unittest.skipUnless(SIPS, "macOS sips only")
class PictureTests(Isolated):
    def test_wide_and_tall_pictures_become_745_by_1040_jpegs(self):
        for w, h in ((1200, 900), (848, 1264), (745, 1040)):
            with self.subTest(size=(w, h)):
                out = self.dir / f"out-{w}.jpg"
                sleever.finish(png(self.dir / f"in-{w}.png", w, h), out)
                self.assertEqual(sleever._size(out), (745, 1040))
                self.assertTrue(out.read_bytes().startswith(b"\xff\xd8\xff"))
                self.assertLessEqual(out.stat().st_size, sleever.MAX_BYTES)

    def test_a_tiny_picture_is_refused(self):
        with self.assertRaises(sleever.SleeveError):
            sleever.finish(png(self.dir / "tiny.png", 64, 64), self.dir / "tiny.jpg")

    def test_publish_installs_names_and_attaches(self):
        f = sleever.prepare("zz")
        self.assertIn("You are sleever", (f / "AGENTS.md").read_text())
        png(f / "sleeve.png", 848, 1264)
        reply, slug = sleever.publish(f, "Made **Sailor Moon** sleeves: moons.\nSleeve: Sailor Moon",
                                      "zz", None, since=0)
        self.assertEqual(slug, "sailor-moon")
        self.assertTrue((self.sleeves / "sailor-moon.jpg").is_file())
        self.assertIn(f"[[attach:{self.sleeves / 'sailor-moon.jpg'}]]", reply)
        self.assertIn("**Sleeves: Sailor Moon**", reply)
        self.assertNotIn("Sleeve: Sailor Moon\n", reply)

    def test_publish_with_secondary_generator_includes_note(self):
        f = sleever.prepare("zz")
        png(f / "sleeve.png", 848, 1264)
        reply, slug = sleever.publish(f, "Made **Sailor Moon** sleeves.\nSleeve: Sailor Moon",
                                      "zz", None, since=0, secondary=True)
        self.assertEqual(slug, "sailor-moon")
        self.assertIn("*(Using secondary image gen workaround)*", reply)
        self.assertIn(f"[[attach:{self.sleeves / 'sailor-moon.jpg'}]]", reply)

    def test_infer_sleeve_name_and_prompt(self):
        self.assertEqual(sleever.infer_sleeve_name("sleever make me sailor moon sleeves"), "Sailor Moon")
        self.assertEqual(sleever.infer_sleeve_name("make me gengar sleeves"), "Gengar")
        self.assertEqual(sleever.infer_sleeve_name("sleever make me a dark gothic castle at night"), "Dark Gothic Castle")
        self.assertEqual(sleever.infer_sleeve_name("sleever make a sleeve of this"), "Sleeves")
        prompt = sleever.sleeve_prompt_for_generator("make me sailor moon sleeves")
        self.assertIn("sailor moon", prompt.lower())
        self.assertIn("custom card back sleeve illustration", prompt.lower())
        self.assertIn("portrait 2:3", prompt.lower())
        ref_prompt = sleever.sleeve_prompt_for_generator("make a sleeve of this", has_refs=True)
        self.assertIn("attached reference image", ref_prompt.lower())

    def test_generate_secondary_image_passes_refs(self):
        script = self.dir / "gen.py"
        script.write_text("#!/usr/bin/env python3")
        with patch.object(sleever.subprocess, "run") as mock_run, \
                patch.object(sleever, "SECONDARY_GENERATOR", script):
            out = self.dir / "out.png"
            ref_file = self.dir / "ref.jpg"
            ref_file.write_bytes(b"image")
            mock_run.side_effect = lambda *args, **kwargs: (out.write_bytes(b"done"), Mock(returncode=0, stdout="", stderr=""))[1]
            sleever.generate_secondary_image("draw this", out, refs=[ref_file])
            cmd = mock_run.call_args[0][0]
            self.assertIn("--prompt", cmd)
            self.assertIn("draw this", cmd)
            self.assertIn("--ref", cmd)
            self.assertIn(str(ref_file.resolve()), cmd)

    def test_no_new_picture_publishes_nothing(self):
        f = sleever.prepare("zz")
        png(f / "sleeve.png", 848, 1264)
        reply, slug = sleever.publish(f, "I can't make pictures right now.", "zz", None,
                                      since=f.joinpath("sleeve.png").stat().st_mtime + 60)
        self.assertIsNone(slug)
        self.assertEqual(reply, "I can't make pictures right now.")
        self.assertEqual(list(self.sleeves.iterdir()), [])


class RefTests(Isolated):
    def test_only_https_pictures_are_downloaded(self):
        dest = self.dir / "refs"
        dest.mkdir()
        bodies = {"https://cdn/a.png": png(self.dir / "a.png", 4, 4).read_bytes(),
                  "https://cdn/page.html": b"<html>not a picture</html>"}

        def fake_open(req, timeout):
            body = bodies[req.full_url]
            return contextlib.nullcontext(Mock(read=lambda n: body))
        with patch.object(sleever.urllib.request, "urlopen", fake_open):
            notes = sleever.fetch_refs(["https://cdn/a.png", "https://cdn/page.html", "http://cdn/x.png"], dest)
        self.assertEqual(sorted(p.name for p in dest.iterdir()), ["ref-1.png"])
        self.assertEqual(len(notes), 2)


class BotTests(unittest.TestCase):
    def test_a_harness_without_pictures_says_so_without_a_turn(self):
        import bot
        with patch.object(bot.HARNESS, "images", False), patch.object(bot, "log", return_value=Mock()), \
                patch.object(bot.HARNESS, "usage", return_value=""), patch.object(bot, "_claim_bot") as claim:
            self.assertEqual(bot.send_sleever("sailor moon", "zzwang"), sleever.UNAVAILABLE)
            claim.assert_not_called()


if __name__ == "__main__":
    unittest.main()
