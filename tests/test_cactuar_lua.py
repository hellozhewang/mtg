"""Runs the Lua tests of the table's scripts against stand-ins for Tabletop Simulator:
tests/test_cactuar.lua (the deck browser, tts/cactuar.lua, with the real docs/tts/ files)
and tests/test_cactuar_turns.lua (turn totals and the announcer, tts/cactuar_turns.lua)."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("lua"), "lua is not installed (brew install lua)")
class CactuarBrowserTests(unittest.TestCase):
    def test_battlefield_soundtrack(self):
        run = subprocess.run(["lua", "tests/test_cactuar_music.lua"], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_incremental_catalog(self):
        run = subprocess.run(["lua", "tests/test_cactuar_catalog.lua"], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_lazy_sleeves(self):
        run = subprocess.run(["lua", "tests/test_cactuar_sleeves.lua"], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_written_guides(self):
        run = subprocess.run(["lua", "tests/test_cactuar_guide.lua"], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_alphabetical_card_search(self):
        run = subprocess.run(["lua", "tests/test_cactuar_search.lua"], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_browser_session(self):
        run = subprocess.run(["lua", "tests/test_cactuar.lua"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_turn_totals_and_announcer(self):
        run = subprocess.run(["lua", "tests/test_cactuar_turns.lua"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
