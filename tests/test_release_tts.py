"""scripts/release_tts.py: version numbers and patch notes (the PC side is not run here)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import release_tts

LOG = "# Cactuar table\n\nIntro.\n\n## v28 — 2026-10-19 (test build)\n- Louder.\n\n## v3–v10 — 2026-10-18\n- Old.\n"


class ChangelogTests(unittest.TestCase):
    def test_the_current_version_is_the_highest_entry(self):
        self.assertEqual(release_tts.current_version(LOG), 28)
        self.assertGreaterEqual(release_tts.current_version(release_tts.CHANGELOG.read_text()), 29)

    def test_a_new_entry_goes_above_the_newest(self):
        out = release_tts.add_entry(LOG, 29, ["Sleeves menu", " ", "Louder clips"], "abc1234", "2026-10-20")
        self.assertIn("Intro.\n\n## v29 — 2026-10-20 (commit abc1234)\n- Sleeves menu\n- Louder clips\n\n## v28", out)
        self.assertEqual(release_tts.current_version(out), 29)

    def test_the_pc_details_are_not_in_the_repo(self):
        text = (ROOT / "scripts" / "release_tts.py").read_text()
        self.assertNotRegex(text, r"\d+\.\d+\.\d+\.\d+")
        self.assertNotIn("cloak", text)


if __name__ == "__main__":
    unittest.main()
