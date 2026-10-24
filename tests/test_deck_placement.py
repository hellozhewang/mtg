from __future__ import annotations

import difflib
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _paths  # noqa: F401  (scripts/<area>/ on sys.path)

import deckplacement

# The tail of a real reply (Blim-Gifts, 2026-10-04) in the old stem-less form,
# renamed to a deck no map will ever hold.
OLD_REPLY = """Validation passed: 100 cards.

Categories: Test-Gifts — control, aggro
Tier: B — double strike, Roaming Throne, and extra combats multiply donations.

A full-workspace maintainer must save those category and tier entries.
"""


class Maps:
    """Copies of the real maps in a temp frontend dir."""

    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        for name in ("deck-tiers.json", "deck-themes.json"):
            shutil.copy(ROOT / "frontend" / name, self.dir / name)
        return self.dir

    def __exit__(self, *exc) -> None:
        self._tmp.cleanup()


def changed_lines(before: str, after: str) -> list[str]:
    return [l for l in difflib.ndiff(before.splitlines(), after.splitlines())
            if l.startswith(("+ ", "- "))]


class ParseTests(unittest.TestCase):
    def test_reads_new_and_old_forms_through_markdown(self):
        declared = deckplacement.parse(
            "- **Categories:** `Krenko-Combo — combo, gowide`\n"
            "**Tier:** Krenko-Combo — SS — Kiki-Jiki + Zealous Conscripts\n"
            "Tier: S — Smothering Tithe and four tutors\n"
            "Tier: A — Sol Ring early\n")
        self.assertEqual(declared.categories, {"Krenko-Combo": ("combo", "gowide")})
        self.assertEqual(declared.tiers, [("Krenko-Combo", "SS"), (None, "S"), (None, "A")])

    def test_prose_mentioning_tiers_is_not_a_declaration(self):
        declared = deckplacement.parse("This sits at Tier: B in my view.\nTiers: S and A\n")
        self.assertEqual(declared.tiers, [])


class SaveTests(unittest.TestCase):
    def test_old_reply_places_the_one_categorised_deck(self):
        with Maps() as fdir:
            before = {n: (fdir / n).read_text() for n in ("deck-tiers.json", "deck-themes.json")}
            notes = deckplacement.save(OLD_REPLY, {"Test-Gifts"}, fdir, "tester")
            self.assertEqual(len(notes), 2, notes)
            # One added line per map, nothing reformatted around it.
            self.assertEqual(changed_lines(before["deck-tiers.json"], (fdir / "deck-tiers.json").read_text()),
                             ['+   "tester/Test-Gifts": "B",'])
            self.assertEqual(changed_lines(before["deck-themes.json"], (fdir / "deck-themes.json").read_text()),
                             ['+   "tester/Test-Gifts": ["control", "aggro"],'])

    def test_untouched_decks_are_never_rerated(self):
        with Maps() as fdir:
            before = (fdir / "deck-tiers.json").read_text()
            notes = deckplacement.save(
                "Categories: Krenko-Combo — spells\nTier: Krenko-Combo — TRASH — ugh\n",
                {"Test-Gifts"}, fdir, "tester")
            self.assertTrue(all("not changed this turn" in n for n in notes), notes)
            self.assertEqual((fdir / "deck-tiers.json").read_text(), before)

    def test_bad_categories_are_dropped_but_the_tier_still_saves(self):
        with Maps() as fdir:
            reply = "Categories: Test-Newdeck — goblins, value\nTier: Test-Newdeck — A — x\n"
            notes = deckplacement.save(reply, {"Test-Newdeck"}, fdir, "tester")
            self.assertIn("primary 'goblins'", notes[0])
            self.assertIn('"tester/Test-Newdeck": "A"', (fdir / "deck-tiers.json").read_text())
            self.assertNotIn("Test-Newdeck", (fdir / "deck-themes.json").read_text())

    def test_stemless_tier_with_two_candidates_is_skipped(self):
        with Maps() as fdir:
            notes = deckplacement.save("Tier: B — fine\n", {"Test-Gifts", "Test-Newdeck"}, fdir, "tester")
            self.assertEqual(notes, ["tier B ignored: no stem and 2 candidate decks"])

    def test_a_placement_lands_on_the_asking_owners_deck_only(self):
        # zzwang owns a Krenko-Combo; tester building their own must not re-rate it.
        with Maps() as fdir:
            before = (fdir / "deck-tiers.json").read_text()
            deckplacement.save("Categories: Krenko-Combo — gowide\nTier: Krenko-Combo — C — x\n",
                               {"Krenko-Combo"}, fdir, "tester")
            after = (fdir / "deck-tiers.json").read_text()
            self.assertIn('"tester/Krenko-Combo": "C"', after)
            self.assertEqual(before.count('"zzwang/Krenko-Combo"'), after.count('"zzwang/Krenko-Combo": "S"'))

    def test_resaving_the_same_placement_writes_nothing(self):
        with Maps() as fdir:
            deckplacement.save(OLD_REPLY, {"Test-Gifts"}, fdir, "tester")
            self.assertEqual(deckplacement.save(OLD_REPLY, {"Test-Gifts"}, fdir, "tester"), [])


class TouchedTests(unittest.TestCase):
    def test_only_files_written_since_the_turn_began(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Bracket3").mkdir()
            old = root / "Bracket3" / "Old-Deck.txt"
            old.write_text("1 X\n")
            past = time.time() - 3600
            os.utime(old, (past, past))
            started = time.time() - 1
            (root / "Bracket3" / "New-Deck.guide").write_text("intro\n")
            self.assertEqual(deckplacement.touched_stems(root, started), {"New-Deck"})


if __name__ == "__main__":
    unittest.main()
