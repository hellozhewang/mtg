"""Runs tests/test_cactuar.lua, which plays the table's deck browser (tts/cactuar.lua)
against stand-ins for Tabletop Simulator and the real docs/tts/ files."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("lua"), "lua is not installed (brew install lua)")
class CactuarBrowserTests(unittest.TestCase):
    def test_browser_session(self):
        run = subprocess.run(["lua", "tests/test_cactuar.lua"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
