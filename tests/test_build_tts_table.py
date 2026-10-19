"""The Cactuar table build: the base table's own objects and scripts survive, the browser
is appended once, and the Cactuar tiles that open it sit on the table."""
from __future__ import annotations

import json
import sys
import unittest
import xml.etree.ElementTree as ET
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
            self.assertRegex(t["CustomImage"]["ImageURL"], r"^" + URL + r"cactuar-tile\.jpg\?v=[0-9a-f]{8}$")
            self.assertTrue(t["Locked"])
            self.assertIn('Global.call("czOpenFor"', t["LuaScript"])
        self.assertIn("function czOpenFor(", table["LuaScript"])

    def test_announcer_clips_carry_a_content_version(self):
        lua = build_tts_table.build(json.loads(json.dumps(BASE)), URL)["LuaScript"]
        for name in ("slow-5min.wav", "slow-10min.wav"):
            self.assertRegex(lua, r'"sounds/' + name.replace(".", r"\.") + r'\?v=[0-9a-f]{8}"')

    def test_no_screen_button(self):
        table = build_tts_table.build(json.loads(json.dumps(BASE)), URL)
        self.assertNotIn("cz_open", table["XmlUI"])
        self.assertIn("cz_panel_Purple", table["XmlUI"])

    def test_browser_text_survives_the_importers_xml_roundtrip(self):
        # The base table's importer reads Global UI with getXmlTable(), then
        # writes it back with setXmlTable(). Entity text is decoded, then
        # inserted as markup: &lt; becomes <Button ...><</Button>, breaking UI.
        root = ET.fromstring("<root>" + build_tts_table.browser_xml() + "</root>")
        for element in root.iter():
            if element.text and element.text.strip():
                with self.subTest(tag=element.tag, id=element.get("id"), text=element.text):
                    ET.fromstring("<Text>" + element.text + "</Text>")

    def test_browser_controls_survive_shared_ui_defaults(self):
        root = ET.fromstring("<root>" + build_tts_table.browser_xml() + "</root>")
        ids = [node.get("id") for node in root.iter() if node.get("id")]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("@CHOICES@", build_tts_table.browser_xml())
        # Defaults belong to the table/importer; our controls explicitly style
        # themselves and must not inject changes into another object's UI.
        self.assertIsNone(root.find("Defaults"))
        for color in build_tts_table.SEATS:
            search = root.find(f".//*[@id='cz_search_{color}']")
            self.assertEqual(search.get("onValueChanged"), "czSearch")
            for i in range(1, build_tts_table.ROWS + 1):
                row = root.find(f".//*[@id='cz_row_{i}_{color}']")
                self.assertEqual(row.get("onClick"), f"czPick({i})")
                for label in row.iter("Text"):
                    self.assertEqual(label.get("raycastTarget"), "false")
                    self.assertEqual(label.get("text"), "")

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

    def test_turn_clocks_move_toward_the_middle_to_make_room_for_totals(self):
        base = json.loads(json.dumps(BASE))
        base["ObjectStates"] += [
            {"GUID": "809133", "Name": "BlockSquare", "Nickname": "Timer", "Transform": {"posX": 41.77, "posZ": -2.86}},
            {"GUID": "8a13cc", "Name": "BlockSquare", "Nickname": "Timer", "Transform": {"posX": -41.75, "posZ": 2.86}},
            {"GUID": "0457c5", "Name": "BlockSquare", "Nickname": "Hand Counter", "Transform": {"posZ": -31.0}}]
        table = build_tts_table.build(base, URL)
        z = {o["GUID"]: o["Transform"]["posZ"] for o in table["ObjectStates"] if "Transform" in o}
        self.assertEqual((z["809133"], z["8a13cc"]), (-1.96, 1.96))
        self.assertEqual(z["0457c5"], -31.0)                       # other blocks stay put
        again = build_tts_table.build(json.loads(json.dumps(table)), URL)
        self.assertEqual([o.get("Transform") for o in again["ObjectStates"]],
                         [o.get("Transform") for o in table["ObjectStates"]])

    def test_tile_guids_are_new(self):
        taken = build_tts_table._guids(BASE["ObjectStates"])
        self.assertIn("bbbbbb", taken)                              # nested objects count
        with self.assertRaises(SystemExit):
            build_tts_table.tiles(URL, {build_tts_table.TILES[0][0]})


if __name__ == "__main__":
    unittest.main()
