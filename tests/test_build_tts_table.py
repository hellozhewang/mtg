"""The Cactuar table build: the base table's own objects and scripts survive, the browser
is appended once, and the Cactuar tiles that open it sit on the table."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_tts_table

URL = "https://example.test/tts/"
BASE = {"SaveName": "MTG 6 player table - scripted", "LuaScript": "function onload() end",
        "XmlUI": "<Panel id=\"theirs\"/>",
        "ObjectStates": [{"GUID": "ddf5de", "Name": "Custom_Tile"},
                         {"GUID": "aaaaaa", "Name": "Bag",
                          "ContainedObjects": [{"GUID": "bbbbbb", "Name": "Card"}]}]}


def tiles(table: dict) -> list[dict]:
    return [o for o in table["ObjectStates"] if o.get("Nickname") == "Cactuar decks"]


class TableBuild(unittest.TestCase):
    def test_tiles_open_the_browser(self):
        table = build_tts_table.build(json.loads(json.dumps(BASE)), URL)
        placed = tiles(table)
        self.assertEqual(len(placed), 2)
        sides = sorted((t["Transform"]["posX"] > 0, t["Transform"]["rotY"]) for t in placed)
        self.assertEqual(sides, [(False, 180.0), (True, 0.0)])     # each faces its seats
        for t in placed:
            self.assertEqual(t["CustomImage"]["ImageURL"], URL + "cactuar-tile.jpg")
            self.assertTrue(t["Locked"])
            self.assertIn('Global.call("czOpenFor"', t["LuaScript"])
        self.assertIn("function czOpenFor(", table["LuaScript"])

    def test_no_screen_button(self):
        table = build_tts_table.build(json.loads(json.dumps(BASE)), URL)
        self.assertNotIn("cz_open", table["XmlUI"])
        self.assertIn("cz_panel_Purple", table["XmlUI"])

    def test_base_table_is_kept(self):
        table = build_tts_table.build(json.loads(json.dumps(BASE)), URL, "Cactuar_v2")
        self.assertTrue(table["LuaScript"].startswith("function onload() end"))
        self.assertTrue(table["XmlUI"].startswith('<Panel id="theirs"/>'))
        self.assertEqual([o["GUID"] for o in table["ObjectStates"][:2]], ["ddf5de", "aaaaaa"])
        self.assertEqual(table["SaveName"], "Cactuar_v2")

    def test_rebuild_is_stable(self):
        once = build_tts_table.build(json.loads(json.dumps(BASE)), URL)
        twice = build_tts_table.build(json.loads(json.dumps(once)), URL)
        self.assertEqual(once, twice)

    def test_tile_guids_are_new(self):
        taken = build_tts_table._guids(BASE["ObjectStates"])
        self.assertIn("bbbbbb", taken)                              # nested objects count
        with self.assertRaises(SystemExit):
            build_tts_table.tiles(URL, {build_tts_table.TILES[0][0]})


if __name__ == "__main__":
    unittest.main()
