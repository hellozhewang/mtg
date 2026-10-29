"""build_site.released_art: set previews show a released printing's pictures."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _paths  # noqa: E402,F401  (scripts/<area>/ on sys.path)

import build_site


class FakeQuery:
    def __init__(self, printing):
        self.printing, self.asked = printing, []

    def released_printing(self, card, today):
        self.asked.append(card["name"])
        return self.printing


def card(name, released, ident="new"):
    return {"name": name, "id": ident, "oracle_id": "o-" + name, "released_at": released,
            "image_uris": {"large": f"https://cards.scryfall.io/large/front/{ident}.jpg"}}


class ReleasedArtTests(unittest.TestCase):
    def test_a_preview_reprint_shows_its_newest_released_printing(self):
        old = {"id": "old", "oracle_ids": ["o-Lightning Greaves"],
               "image_uris": {"large": "https://cards.scryfall.io/large/front/old.jpg"}, "face_images": []}
        q = FakeQuery(old)
        out = build_site.released_art({"Lightning Greaves": card("Lightning Greaves", "2026-11-13"),
                                       "Sol Ring": card("Sol Ring", "2020-01-01", "sol")}, q, "2026-10-28")
        self.assertEqual(out["Lightning Greaves"]["image_uris"], old["image_uris"])
        self.assertEqual(out["Lightning Greaves"]["released_at"], "2026-11-13")   # only the picture
        self.assertEqual(q.asked, ["Lightning Greaves"])                         # released cards untouched

    def test_a_brand_new_card_keeps_its_preview(self):
        new = card("Brand New", "2026-11-13")
        self.assertIs(build_site.released_art({"Brand New": new}, FakeQuery(None), "2026-10-28")["Brand New"], new)

    def test_a_pinned_printing_is_left_alone(self):
        pinned = {**card("World at War", "2026-11-13"), build_site.PINNED: "x"}
        q = FakeQuery(None)
        build_site.released_art({"World at War": pinned}, q, "2026-10-28")
        self.assertEqual(q.asked, [])


if __name__ == "__main__":
    unittest.main()
