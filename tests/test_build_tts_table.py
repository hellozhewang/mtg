"""The Cactuar table build: the base table's own objects and scripts survive, the browser
is appended once, and the Cactuar tiles that open it sit on the table."""
from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _paths  # noqa: E402,F401  (scripts/<area>/ on sys.path)

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
    def test_soundtrack_versions_every_wav(self):
        lua = build_tts_table.build(json.loads(json.dumps(BASE)), URL)["LuaScript"]
        self.assertNotIn("CZM_CARDS", lua)                    # music needs no card colour table
        for name in ("theme", "titan", "ultima", "omega", "thordan", "hades", "alexander", "garuda", "ifrit",
                     "shiva", "leviathan", "ramuh", "answers", "gilgamesh", "dragonsong", "footfalls"):
            self.assertRegex(lua, r'"sounds/ff14_' + name + r'\.wav\?v=[0-9a-f]{8}"')
        self.assertRegex(lua, r'"sounds/ff11_chocobo\.wav\?v=[0-9a-f]{8}"')

    def test_text_details_and_lazy_sleeves_are_private(self):
        table = build_tts_table.build(json.loads(json.dumps(BASE)), URL)
        self.assertIn("function czgRender(", table["LuaScript"])
        root = ET.fromstring("<root>" + table["XmlUI"] + "</root>")
        for color in build_tts_table.SEATS:
            panel = root.find(f".//*[@id='cz_panel_{color}']")
            self.assertEqual(panel.get("visibility"), color)
            self.assertEqual((panel.get("width"), panel.get("height")), ("1080", "864"))
            chooser = panel.find(f".//*[@id='cz_sleeves_{color}']")
            self.assertIsNotNone(chooser)
            self.assertEqual(chooser.get("active"), "False")
            self.assertEqual(len(chooser.findall(".//Image")), 8)
            picture = panel.find(f".//*[@id='cz_picture_{color}']")
            self.assertEqual(picture.get("active"), "False")
            self.assertEqual(len(picture.findall(".//Image")), 1)
            self.assertEqual(panel.findall(".//Image"), picture.findall(".//Image") + chooser.findall(".//Image"))
            self.assertEqual(panel.find(f".//*[@id='cz_sl_1_{color}']").get("onClick"), "czSleevePick(1)")
            show = panel.find(f".//*[@id='cz_commander_show_{color}']")
            self.assertEqual(show.get("onClick"), "czPictureShow")
            self.assertEqual(show.get("interactable"), "False")
            self.assertEqual(panel.find(f".//*[@id='cz_guide_{color}']").get("onClick"), "czGuide")
            self.assertIsNotNone(panel.find(f".//*[@id='cz_guide_scroll_{color}']"))
            commander = panel.find(f".//*[@id='cz_commander_{color}']")
            self.assertEqual(commander.get("active"), "False")
            self.assertEqual(commander.findall(".//Image"), [])
            self.assertIsNotNone(commander.find(f".//*[@id='cz_commander_scroll_{color}']"))
            self.assertIsNotNone(commander.find(f".//*[@id='cz_commander_text_{color}']"))

    def test_alphabetical_search_is_private_and_included_in_the_build(self):
        table = build_tts_table.build(json.loads(json.dumps(BASE)), URL)
        root = ET.fromstring("<root>" + table["XmlUI"] + "</root>")
        self.assertIn("function czsOpen(", table["LuaScript"])
        self.assertIn("function CZRegex.compile(", table["LuaScript"])
        self.assertNotIn("@INSPECT_CELL@", table["LuaScript"])
        self.assertIn('id="czs_card_{I}_{C}"', table["LuaScript"])
        for color in build_tts_table.SEATS:
            panel = root.find(f".//*[@id='czs_panel_{color}']")
            self.assertEqual(panel.get("visibility"), color)
            self.assertEqual(panel.get("active"), "False")
            self.assertEqual(panel.get("width"), "480")
            self.assertIsNotNone(panel.find(".//VerticalScrollView"))
            zoom = panel.find(f".//*[@id='czs_zoom_{color}']")
            self.assertEqual(zoom.get("active"), "False")
            self.assertEqual(zoom.get("raycastTarget"), "false")
            self.assertTrue(all(node.get("raycastTarget") == "false" for node in zoom.iter()))
            grid = panel.find(".//GridLayout")
            self.assertEqual(grid.get("constraintCount"), "4")
            self.assertEqual(len(grid.findall("Button")), build_tts_table.SEARCH_CELLS)
            self.assertIsNone(panel.find(f".//*[@id='czs_next_{color}']"))
            self.assertEqual(root.find(f".//*[@id='czs_query_{color}']").get("onValueChanged"), "czsSearch")
            self.assertEqual(root.find(f".//*[@id='czs_regex_{color}']").get("onClick"), "czsToggleRegex")
            self.assertEqual(root.find(f".//*[@id='czs_refresh_{color}']").get("onClick"), "czsRefreshClick")
            for i in range(1, build_tts_table.SEARCH_CELLS + 1):
                card = root.find(f".//*[@id='czs_card_{i}_{color}']")
                self.assertEqual(card.get("onClick"), "czsPick")
                self.assertEqual(card.get("onMouseEnter"), "czsHover")
                self.assertEqual(card.get("onMouseExit"), "czsUnhover")

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

    def test_a_second_clock_start_never_leaves_a_loop_running(self):
        # A stand-in shaped like the base Timer's onPlayerTurn (CRLF, as the base is).
        timer = "\r\n".join([
            "owner='Blue'", "turnN=0", "function updateSave() end", "function updateButtons(s) end",
            "self={editButton=function() end}",
            "function onPlayerTurn(player)",
            "  if player~=nil and player.color==owner then",
            "    tdiff=0",
            "    timerID=Wait.time(function() end,1,5999)",
            "    turnN=turnN+1",
            "  else",
            "    if timerID~=nil then",
            "      pcall(function() Wait.stop(timerID) end)",
            "    end",
            "    updateButtons('     ')",
            "  end",
            "end", ""])
        harness = """
local live, n = {}, 0
Wait = {time = function() n = n + 1; live[n] = true; return n end,
        stop = function(id) live[id] = nil end}
dofile(arg[1])
onPlayerTurn({color = "Blue"}); onPlayerTurn({color = "Blue"})   -- started twice
onPlayerTurn({color = "Green"})                                  -- the turn passes
local left = 0
for _ in pairs(live) do left = left + 1 end
print(left, timerID == nil)
"""
        import shutil, subprocess, tempfile
        if not shutil.which("lua"):
            self.skipTest("lua is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run.lua"
            run.write_text(harness)
            results = []
            for script in (timer, build_tts_table.fix_timer_script(timer)):
                (Path(tmp) / "timer.lua").write_bytes(script.encode())
                out = subprocess.run(["lua", str(run), str(Path(tmp) / "timer.lua")],
                                     capture_output=True, text=True, timeout=20)
                self.assertEqual(out.returncode, 0, out.stderr)
                results.append(out.stdout.split())
        self.assertEqual(results[0], ["1", "false"])     # the bug: one loop keeps counting
        self.assertEqual(results[1], ["0", "true"])      # fixed: none, and stopped reads as stopped
        fixed = build_tts_table.fix_timer_script(timer)
        self.assertEqual(build_tts_table.fix_timer_script(fixed), fixed)

    def test_the_edge_strip_is_cleared_for_a_five_slot_stack(self):
        base = json.loads(json.dumps(BASE))
        base["ObjectStates"] += [
            {"GUID": "222541", "Name": "Custom_Tile", "Transform": {"posX": 48.2, "posZ": 12.7}},  # importer
            {"GUID": "b7ccfb", "Name": "Custom_Model_Bag", "Transform": {"posX": 51.5, "posZ": -22.9}},
            {"GUID": "c2e905", "Name": "Custom_Token", "Transform": {"posX": 41.8, "posZ": -5.7}},  # a seat's tracker
        ]
        base["SnapPoints"] = [{"Position": {"x": 41.77, "y": 0.96, "z": -23.7}, "Rotation": {"x": 0, "y": 180, "z": 0}}]
        old = {"points3": [{"x": 47, "y": 0.97, "z": -15}, {"x": 49, "y": 0.97, "z": -15}],
               "color": dict(build_tts_table.OLD_STACK_COLOR), "thickness": 0.12}
        base["VectorLines"] = [old, {"points3": [], "color": {"r": 1, "g": 0, "b": 0}, "thickness": 0.1}]
        table = build_tts_table.build(base, URL)
        guids = {o["GUID"] for o in table["ObjectStates"]}
        self.assertNotIn("222541", guids)
        self.assertNotIn("b7ccfb", guids)
        self.assertIn("c2e905", guids)                      # the neighbouring seat is untouched
        self.assertEqual(len(table["VectorLines"]), 1)     # v68/v69's stack lines go; others stay
        self.assertNotEqual(table["VectorLines"][0]["color"], build_tts_table.OLD_STACK_COLOR)
        slots = table["SnapPoints"][1:]
        self.assertEqual(len(slots), 5)
        self.assertEqual(table["SnapPoints"][0]["Position"]["x"], 41.77)   # existing snap points kept
        self.assertEqual({s["Position"]["x"] for s in slots}, {build_tts_table.STACK_X})
        again = build_tts_table.build(json.loads(json.dumps(table)), URL)
        self.assertEqual((len(again["VectorLines"]), len(again["SnapPoints"])), (1, 6))

    def test_stack_panel_matches_the_lua_decal_and_its_picture(self):
        g = build_tts_table.stack_geometry()
        lua = (build_tts_table.SOURCE / "cactuar_lines.lua").read_text()
        decal = re.search(r'CZL\.stack = \{url = "table/stack-panel\.png", x = ([-\d.]+), z = ([-\d.]+), '
                          r'width = ([-\d.]+), height = ([-\d.]+)\}', lua)
        self.assertIsNotNone(decal)
        self.assertEqual(tuple(float(v) for v in decal.groups()), (g["x"], g["z"], g["width"], g["height"]))
        snaps = sorted(s["Position"]["z"] for s in build_tts_table.stack_snaps())
        self.assertEqual(snaps, sorted(g["slots"]))
        self.assertTrue(all(g["top"] - g["height"] < z < g["top"] for z in snaps))
        art = build_tts_table.SOURCE / "table" / "stack-panel.png"
        width, height = struct.unpack(">II", art.read_bytes()[16:24])
        self.assertAlmostEqual(width / height, g["width"] / g["height"], places=3)   # not stretched
        built = build_tts_table.browser_lua(URL)
        self.assertRegex(built, r'"table/stack-panel\.png\?v=[0-9a-f]{8}"')
        for seat in build_tts_table.SEATS:
            self.assertRegex(built, r'"table/triggers-' + seat + r'\.png\?v=[0-9a-f]{8}"')

    def test_each_seat_gets_a_trigger_area_switch_off_by_default(self):
        base = json.loads(json.dumps(BASE))
        lua = []
        for i, color in enumerate(("White", "Purple")):
            z, rot, dx = (-26.9, 180.0, 1.9) if color == "White" else (26.9, 0.0, -2.0)
            base["ObjectStates"] += [
                {"GUID": f"r{i}0000", "Name": "Custom_Model", "Transform": {"posX": 33.3, "posZ": z, "rotY": rot}},
                {"GUID": f"m{i}0000", "Name": "Custom_Model", "Transform": {"posX": 33.3 - dx, "posZ": z, "rotY": rot}}]
            lua += [f'data["{color}"]["revealButton"] = getObjectFromGUID("r{i}0000")',
                    f'data["{color}"]["millButton"] = getObjectFromGUID("m{i}0000")']
        base["LuaScript"] = "\n".join(lua)
        table = build_tts_table.build(base, URL)
        switches = {o["Description"]: o for o in table["ObjectStates"] if o.get("Nickname") == "Trigger area"}
        self.assertEqual(len(switches), 2)
        white = switches["Shows White's trigger area."]
        # Past the reveal button, its whole label clear of it (button width / 500 units).
        left = white["Transform"]["posX"] - white["Transform"]["scaleX"] / 2
        self.assertGreater(left, 33.3 + 1.0)
        self.assertIn("width = 1300", white["LuaScript"])
        self.assertAlmostEqual(1300 / 500, white["Transform"]["scaleX"])
        self.assertEqual((white["Memo"], white["Locked"]), ("off", True))
        self.assertIn('Global.call("czlRegister"', white["LuaScript"])
        self.assertIn("function czlToggle", table["LuaScript"])
        again = build_tts_table.build(json.loads(json.dumps(table)), URL)
        self.assertEqual(sum(o.get("Nickname") == "Trigger area" for o in again["ObjectStates"]), 2)

    def test_a_sound_switch_sits_below_each_cactuar_tile(self):
        table = build_tts_table.build(json.loads(json.dumps(BASE)), URL)
        tiles = {o["GUID"]: o["Transform"] for o in table["ObjectStates"] if o.get("Nickname") == "Cactuar decks"}
        sound = [o for o in table["ObjectStates"] if o.get("Nickname") == "Cactuar sound"]
        self.assertEqual(len(sound), 2)
        for tile, guid in build_tts_table.SOUND_GUIDS.items():
            o = next(s for s in sound if s["GUID"] == guid)
            t, at = tiles[tile], o["Transform"]
            self.assertEqual((at["posX"], at["rotY"]), (t["posX"], t["rotY"]))
            self.assertLess(abs(at["posZ"]), abs(t["posZ"]))            # toward the middle
            self.assertGreater(abs(t["posZ"] - at["posZ"]), build_tts_table.TILE_SCALE)
            self.assertIn('Global.call("czmRegister"', o["LuaScript"])
        self.assertIn("function czmToggleSound", table["LuaScript"])
        again = build_tts_table.build(json.loads(json.dumps(table)), URL)
        self.assertEqual(sum(o.get("Nickname") == "Cactuar sound" for o in again["ObjectStates"]), 2)

    def test_tile_guids_are_new(self):
        taken = build_tts_table._guids(BASE["ObjectStates"])
        self.assertIn("bbbbbb", taken)                              # nested objects count
        with self.assertRaises(SystemExit):
            build_tts_table.tiles(URL, {build_tts_table.TILES[0][0]})

    @unittest.skipUnless(shutil.which("lua"), "Lua is required")
    def test_cannon_stops_music_at_fire_before_launch_and_still_starts_the_game(self):
        cannon = "\r\n".join([
            "function FireCannon()", "  if isFiring then return end", "  if power > 0 then",
            "\t\tisFiring = true", "    launches = launches + 1", "  end", "end",
            "function choose(ply)", "\t" * 7 + "Turns.enable = true",
            "\t" * 7 + "Turns.turn_color = ply.color", "end"])
        fixed = build_tts_table.fix_cannon_script(cannon)
        self.assertEqual(build_tts_table.fix_cannon_script(fixed), fixed)
        probe = """
isFiring=false;power=0;launches=0;fires=0;starts=0;Turns={}
Global={call=function(name,color)
  if name=='czmCannonFired' then
    assert(launches==0);fires=fires+1
  elseif name=='cztStartGame' then assert(color=='Blue');starts=starts+1 end
end}
""" + fixed + """
FireCannon();assert(fires==0)
power=1;FireCannon();assert(fires==1 and launches==1)
FireCannon();assert(fires==1)
choose({color='Blue'});assert(starts==1)
"""
        out = subprocess.run(["lua", "-"], input=probe, text=True, capture_output=True, timeout=10)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
