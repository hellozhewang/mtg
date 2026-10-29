"""sleever (scripts/discord/bot/sleever.py): turning a model's picture into a published sleeve."""
from __future__ import annotations

import contextlib
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import Mock, patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _paths  # noqa: E402,F401  (scripts/<area>/ on sys.path)

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

    def test_refusal_never_publishes_even_with_a_recent_picture(self):
        f = sleever.prepare("zz")
        png(f / "sleeve.png", 848, 1264)
        reply, slug = sleever.publish(f, "I can't make that sleeve.", "zz", "moon", since=0)
        self.assertIsNone(slug)
        self.assertEqual(reply, "I can't make that sleeve.")
        self.assertEqual(list(self.sleeves.iterdir()), [])

    def test_instructions_use_builtin_images_and_keep_owner_rule(self):
        f = sleever.prepare("zz")
        instructions = (f / "AGENTS.md").read_text()
        self.assertIn(sleever.SLEEVE_CONTENT_RULE, instructions)
        self.assertIn("built-in `image_gen`", instructions)
        self.assertIn("Never use the ChatGPT website", instructions)

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


@unittest.skipUnless(SIPS, "macOS sips only")
class RoutingTests(Isolated):
    def setUp(self):
        super().setUp()
        import bot
        self.bot = bot
        self.primary = SimpleNamespace(name="agy", model="gemini-test", effort=None,
                                       images=True, home=self.dir, run=Mock(), usage=Mock(return_value=""))
        self.codex = SimpleNamespace(name="codex", model="gpt-test", effort="high",
                                     images=True, run=Mock(), usage=Mock(return_value="codex allowance"))
        patches = {
            "HARNESS": self.primary, "SESSIONS": self.dir / "sessions",
            "LEGACY_STATE": self.dir / "legacy.json", "log": Mock(return_value=Mock()),
            "_claim_bot": Mock(), "_release_bot": Mock(), "_autopush": Mock(),
        }
        for key, value in patches.items():
            p = patch.object(bot, key, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(bot.harness, "CodexHarness", return_value=self.codex)
        self.factory = p.start()
        self.addCleanup(p.stop)
        p = patch.object(bot.usage, "is_image_quota_exhausted", return_value=(True, None, None))
        self.quota = p.start()
        self.addCleanup(p.stop)
        self.conv = "cli-zzwang-sleever"

    def picture_turn(self, folder, message, sid, **kwargs):
        png(folder / "sleeve.png", 848, 1264)
        return self.bot.harness.Turn("Made **Moon** sleeves.\nSleeve: Moon", "codex-session", "")

    def test_known_quota_skips_gemini_uses_actual_codex_answer_and_own_session(self):
        self.bot._save(self.conv, {"session_id": "gemini-session", "harness": "agy",
                                  "model": self.primary.model, "effort": None})
        self.codex.run.side_effect = self.picture_turn
        reply = self.bot.send_sleever("make moon sleeves", "zzwang")
        self.primary.run.assert_not_called()
        self.assertIsNone(self.codex.run.call_args.args[2])
        self.assertIn("[[attach:", reply)
        self.assertIn("codex allowance", reply)
        self.assertNotIn("workaround", reply)
        self.assertEqual(self.bot._load(self.conv)["session_id"], "gemini-session")
        self.assertEqual(self.bot._load(self.conv + "-codex")["session_id"], "codex-session")
        self.assertEqual(self.bot._load(self.conv)["sleeve"], "moon")
        self.bot._autopush.assert_called_once()
        self.bot._release_bot.assert_called_once()

    def test_quota_discovered_during_turn_retries_codex(self):
        self.quota.side_effect = [(False, None, None), (True, None, None)]
        self.primary.run.return_value = self.bot.harness.Turn("Image quota exhausted", "gemini-session", "")
        self.codex.run.side_effect = self.picture_turn
        reply = self.bot.send_sleever("moon sleeves", "zzwang")
        self.primary.run.assert_called_once()
        self.codex.run.assert_called_once()
        self.assertIn("[[attach:", reply)
        self.assertEqual(self.bot._load(self.conv)["session_id"], "gemini-session")

    def test_quota_error_during_turn_retries_codex(self):
        self.quota.side_effect = [(False, None, None), (True, None, None)]
        self.primary.run.side_effect = self.bot.harness.QuotaExhausted("image quota")
        self.codex.run.side_effect = self.picture_turn
        self.assertIn("[[attach:", self.bot.send_sleever("moon sleeves", "zzwang"))
        self.codex.run.assert_called_once()

    def test_other_errors_are_not_routed_to_codex(self):
        self.quota.return_value = (False, None, None)
        self.primary.run.side_effect = self.bot.harness.HarnessError("connection failed")
        with self.assertRaises(self.bot.harness.HarnessError):
            self.bot.send_sleever("moon sleeves", "zzwang")
        self.factory.assert_not_called()
        self.bot._autopush.assert_not_called()

    def test_codex_failure_never_reuses_old_picture(self):
        f = sleever.prepare("zzwang")
        png(f / "sleeve.png", 848, 1264)
        self.codex.run.side_effect = self.bot.harness.HarnessError("quota exhausted")
        reply = self.bot.send_sleever("moon sleeves", "zzwang")
        self.assertIn(sleever.UNAVAILABLE, reply)
        self.assertNotIn("[[attach:", reply)
        self.assertEqual(list(self.sleeves.iterdir()), [])
        self.bot._autopush.assert_not_called()

    def test_codex_refusal_never_publishes_or_fabricates_a_title(self):
        self.codex.run.return_value = self.bot.harness.Turn("I can't make that sleeve.", "codex-session", "")
        reply = self.bot.send_sleever("make Trump sleeves", "zzwang")
        self.assertIn("I can't make that sleeve.", reply)
        self.assertNotIn("Made **", reply)
        self.assertNotIn("[[attach:", reply)
        self.bot._autopush.assert_not_called()

    def test_codex_revision_keeps_references_name_and_resumes_its_own_session(self):
        (self.sleeves / "moon.jpg").write_bytes(b"jpg")
        self.bot._save(self.conv, {"sleeve": "moon"})
        self.bot._save(self.conv + "-codex", {"session_id": "previous-codex", "harness": "codex",
                                            "model": self.codex.model, "effort": self.codex.effort,
                                            "folder": str(sleever.folder("zzwang"))})
        def fetch(urls, folder):
            png(folder / "ref-1.png", 64, 64)
            return []
        self.codex.run.side_effect = self.picture_turn
        with patch.object(sleever, "fetch_refs", side_effect=fetch):
            self.bot.send_sleever("make it darker", "zzwang", refs=["https://cdn/ref.png"])
        args = self.codex.run.call_args.args
        self.assertEqual(args[2], "previous-codex")
        self.assertIn("previous sleeve is named moon", args[1])
        self.assertTrue((args[0] / "refs" / "ref-1.png").is_file())
        self.assertIn(sleever.SLEEVE_CONTENT_RULE, (args[0] / "AGENTS.md").read_text())

    def test_a_removed_previous_sleeve_starts_a_fresh_conversation(self):
        # digitalstealth's case: their sleeve was removed, but the bot still called the
        # next request a revision of it and showed the model the old picture.
        f = sleever.prepare("zzwang")
        png(f / "sleeve.png", 848, 1264)
        self.bot._save(self.conv, {"sleeve": "gone", "session_id": "old", "harness": "agy",
                                  "model": self.primary.model, "effort": None, "folder": str(f)})
        self.quota.return_value = (False, None, None)
        self.primary.run.side_effect = self.picture_turn
        self.bot.send_sleever("make me these sleeves", "zzwang")
        folder, prompt, sid = self.primary.run.call_args.args[:3]
        self.assertIsNone(sid)
        self.assertNotIn("previous sleeve", prompt)
        self.assertEqual(self.bot._load(self.conv)["sleeve"], "moon")

    def test_a_session_from_another_folder_is_not_resumed(self):
        self.bot._save(self.conv, {"session_id": "moved", "harness": "agy", "model": self.primary.model,
                                  "effort": None, "folder": "/old/repo/bot/.sleever/zzwang"})
        self.quota.return_value = (False, None, None)
        self.primary.run.side_effect = self.picture_turn
        self.bot.send_sleever("moon sleeves", "zzwang")
        self.assertIsNone(self.primary.run.call_args.args[2])
        self.assertEqual(self.bot._load(self.conv)["folder"], str(sleever.folder("zzwang")))

    def test_normal_gemini_success_does_not_start_codex(self):
        self.quota.return_value = (False, None, None)
        self.primary.run.side_effect = self.picture_turn
        self.assertIn("[[attach:", self.bot.send_sleever("moon sleeves", "zzwang"))
        self.factory.assert_not_called()

    def test_unchanged_picture_is_not_published_even_with_a_sleeve_line(self):
        f = sleever.prepare("zzwang")
        png(f / "sleeve.png", 848, 1264)
        self.codex.run.return_value = self.bot.harness.Turn("Made **Moon** sleeves.\nSleeve: Moon", "codex-session", "")
        reply = self.bot.send_sleever("moon sleeves", "zzwang")
        self.assertIn(sleever.NO_PICTURE, reply)
        self.assertNotIn("Made **", reply)
        self.assertNotIn("[[attach:", reply)
        self.bot._autopush.assert_not_called()

    def test_changed_codex_model_does_not_resume_old_session(self):
        self.bot._save(self.conv + "-codex", {"session_id": "old-codex", "harness": "codex",
                                            "model": "other-model", "effort": self.codex.effort})
        self.codex.run.side_effect = self.picture_turn
        self.bot.send_sleever("moon sleeves", "zzwang")
        self.assertIsNone(self.codex.run.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
