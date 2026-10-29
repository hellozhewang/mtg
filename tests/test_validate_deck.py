"""validate_deck.py's legality rule."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _paths  # noqa: E402,F401  (scripts/<area>/ on sys.path)

import validate_deck


def card(status: str, released: str) -> dict:
    return {"legalities": {"commander": status}, "released_at": released}


class LegalityTests(unittest.TestCase):
    # Owner rule: a release date never affects legality.
    def test_an_unreleased_card_counts_as_legal(self):
        self.assertTrue(validate_deck.commander_legal(card("not_legal", "2026-11-13"), "2026-10-28"))

    def test_banned_stays_banned_even_before_release(self):
        self.assertFalse(validate_deck.commander_legal(card("banned", "2026-11-13"), "2026-10-28"))

    def test_a_released_not_legal_card_is_still_not_legal(self):
        self.assertFalse(validate_deck.commander_legal(card("not_legal", "2020-01-01"), "2026-10-28"))
        self.assertTrue(validate_deck.commander_legal(card("legal", "2020-01-01"), "2026-10-28"))


if __name__ == "__main__":
    unittest.main()
