"""bot._autopush: a deck the validator fails is never committed or built into the site."""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _paths  # noqa: E402,F401  (scripts/<area>/ on sys.path)

import bot

OUTPUT = """\
PASS  amy/Bracket3/Good.txt
      Sonic  |  identity U  |  100 cards

FAIL  amy/Bracket3/Bad.txt
      Amy  |  identity W  |  99 cards
      !! unresolved names: Kellan, the Fae-Clothed
      !! card count is 99, expected 100

1/2 decks pass
"""


class ValidateTests(unittest.TestCase):
    def setUp(self):
        p = patch.object(bot, "log", return_value=Mock())
        p.start()
        self.addCleanup(p.stop)

    def test_failing_decks_are_keyed_by_path_with_their_problems(self):
        done = subprocess.CompletedProcess([], 1, OUTPUT, "")
        with patch.object(bot, "WORKSPACE", Path("/w")), \
                patch.object(bot.subprocess, "run", return_value=done):
            failing = bot._validate([Path("/w/amy/Bracket3/Good.txt"),
                                     Path("/w/amy/Bracket3/Bad.txt")])
        self.assertEqual(list(failing), [Path("/w/amy/Bracket3/Bad.txt").resolve()])
        self.assertEqual(failing[Path("/w/amy/Bracket3/Bad.txt").resolve()],
                         "FAIL  amy/Bracket3/Bad.txt\n"
                         "!! unresolved names: Kellan, the Fae-Clothed\n"
                         "!! card count is 99, expected 100")

    def test_a_validator_that_cannot_run_holds_nothing(self):
        with patch.object(bot.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired("x", 1)):
            self.assertEqual(bot._validate([Path("/w/a.txt")]), {})


class GateTests(unittest.TestCase):
    def setUp(self):
        for p in (patch.object(bot, "log", return_value=Mock()),
                  patch.object(bot, "AUTOPUSH", True),
                  patch.object(bot, "_dblock", contextlib.nullcontext)):
            p.start()
            self.addCleanup(p.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name).resolve()
        self.deck = self.repo / "public" / "amy" / "Bracket3"
        self.deck.mkdir(parents=True)
        (self.repo / "frontend").mkdir()
        for name in ("deck-tiers.json", "deck-themes.json"):
            (self.repo / "frontend" / name).write_text("{}\n")
        for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", str(self.repo), *args], check=True)
        self.write("Old.txt", "1 Good Card\n")
        self.write("Old.guide", "old guide\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "seed")
        for p in (patch.object(bot, "REPO", self.repo),
                  patch.object(bot, "WORKSPACE", self.repo / "public"),
                  patch.object(bot.workspace, "frontend_dir", return_value=self.repo / "frontend")):
            p.start()
            self.addCleanup(p.stop)

    def write(self, name, text):
        (self.deck / name).write_text(text, encoding="utf-8")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args],
                              capture_output=True, text=True, check=True).stdout

    def push(self, failing):
        seen = {}

        def build():
            seen.update({p.name: p.read_text() for p in self.deck.iterdir()})
            return None

        bad = {self.deck / name: f"FAIL  {name}" for name in failing}
        with patch.object(bot, "_validate", return_value=bad), \
                patch.object(bot, "_build_site", side_effect=build) as site:
            bot._autopush("chan")
        return seen, site

    def committed(self):
        return set(self.git("ls-files", "public").split())

    def test_a_failing_new_deck_stays_out_of_the_commit_and_the_site(self):
        self.write("Good.txt", "1 Good Card\n")
        self.write("Bad.txt", "1 Kellan, the Fae-Clothed\n")
        self.write("Bad.guide", "guide\n")
        seen, _ = self.push(["Bad.txt"])
        self.assertNotIn("Bad.txt", seen)                       # site never saw it
        self.assertIn("public/amy/Bracket3/Good.txt", self.committed())
        self.assertFalse({"public/amy/Bracket3/Bad.txt",
                          "public/amy/Bracket3/Bad.guide"} & self.committed())
        self.assertTrue((self.deck / "Bad.txt").exists())       # still there to fix
        self.assertFalse((self.deck / "Bad.txt.held").exists())

    def test_a_failing_edit_publishes_the_last_good_version(self):
        self.write("Old.txt", "1 Kellan, the Fae-Clothed\n")
        self.write("Old.guide", "new guide\n")
        os.utime(self.deck / "Old.txt", ns=(1, 1_000_000_000))
        self.write("Good.txt", "1 Good Card\n")
        seen, site = self.push(["Old.txt"])
        site.assert_called_once()
        self.assertIn("public/amy/Bracket3/Good.txt", self.committed())
        self.assertEqual(seen["Old.txt"], "1 Good Card\n")
        self.assertEqual(seen["Old.guide"], "old guide\n")
        self.assertEqual((self.deck / "Old.txt").read_text(), "1 Kellan, the Fae-Clothed\n")
        self.assertEqual((self.deck / "Old.guide").read_text(), "new guide\n")
        self.assertEqual((self.deck / "Old.txt").stat().st_mtime_ns, 1_000_000_000)
        self.assertEqual(self.git("show", "HEAD:public/amy/Bracket3/Old.txt"), "1 Good Card\n")
        self.assertIn("Old.txt", self.git("status", "--porcelain"))

    def test_nothing_is_committed_when_only_held_decks_changed(self):
        self.write("Bad.txt", "1 Kellan, the Fae-Clothed\n")
        _, site = self.push(["Bad.txt"])
        site.assert_not_called()
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), "1")


if __name__ == "__main__":
    unittest.main()
