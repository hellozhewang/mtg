#!/usr/bin/env python3
"""Build "MTG 6 player Cactuar Ver": a scripted 6-player table plus our deck browser.

    ./build_tts_table.py BASE.json -o OUT.json
    ./build_tts_table.py BASE.json -o OUT.json --base-url http://192.168.0.100:5588/tts/
    ./build_tts_table.py BASE.json -o OUT.json --name "MTG 6 player Cactuar Ver_v2"

BASE is the Workshop table "MTG 6 player table - scripted" (2293586471), as Tabletop
Simulator stores it under Mods/Workshop/. It is someone else's work, so neither it
nor the output is committed: this script is, along with what it adds, tts/cactuar.lua,
tts/cactuar_turns.lua, tts/cactuar.xml and tts/cactuar_tile.lua. Everything the table already does is left
exactly as it was: the browser is appended to its Global script and Global UI, and two
Cactuar tiles that open it are added beside the deck importers, one per side.

The browser reads the deck index and deck files build_site.py publishes under
docs/tts/ (see ttsdecks.py), from GitHub Pages by default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "tts"
NAME = "MTG 6 player Cactuar Ver"
DEFAULT_BASE_URL = "https://hellozhewang.github.io/mtg/tts/"
SEATS = ("White", "Red", "Yellow", "Green", "Blue", "Purple")
ROWS = 10                                   # must match CZ.rows in cactuar.lua
CHOICES = 10                                # paged filter menu; matches CZ.menuRows
MARKER = "-- ==== Cactuar deck browser"     # how a second build recognises the first
TILE_IMAGE = "cactuar-tile.jpg"             # published beside decks.json (ttsdecks.py)
TILE_SCALE = 2.2
# One tile per side, where the owner asked: below the Card Importer on the south
# seats' side, above rikrassen's importer on the north side. Each faces its seats.
TILES = (("c4c7a1", -48.2, -24.5, 180.0),   # GUID, x, z, rotY
         ("c4c7a2", 48.2, 24.5, 0.0))
# The base's turn clocks ("Timer", z ±2.86) sit right above each seat's Life Tracker,
# which leaves no room for the total turn time cactuar_turns.lua shows beneath them.
# Move them toward the middle strip (clear at every seat) by this much.
TIMER_Z = 1.96


def _section(xml: str, name: str) -> str:
    """The template between `<!-- @NAME@ -->` and the next marker (or the end)."""
    m = re.search(rf"<!-- @{name}@ -->\n(.*?)(?=\n<!-- @\w+@ -->|\Z)", xml, re.S)
    if not m:
        sys.exit(f"tts/cactuar.xml has no @{name}@ section")
    return m.group(1).rstrip() + "\n"


def browser_xml() -> str:
    template = (SOURCE / "cactuar.xml").read_text(encoding="utf-8")
    row = _section(template, "ROW")
    choice = _section(template, "CHOICE")
    panel = _section(template, "PANEL")
    out = ["<!-- Cactuar deck browser: github.com/hellozhewang/mtg, tts/ -->"]
    for color in SEATS:
        rows = "".join(row.replace("{I}", str(i)) for i in range(1, ROWS + 1))
        choices = "".join(choice.replace("{I}", str(i)) for i in range(1, CHOICES + 1))
        out.append(panel.replace("@ROWS@", rows.rstrip("\n"))
                   .replace("@CHOICES@", choices.rstrip("\n")).replace("{C}", color))
    return "\n".join(out)


# Appended to Global in this order: the browser, then the turn totals and
# announcer, which use the browser's CZ.seats and CZ.base.
GLOBAL_SCRIPTS = ("cactuar.lua", "cactuar_turns.lua")


def browser_lua(base_url: str) -> str:
    lua = "\n\n".join((SOURCE / name).read_text(encoding="utf-8") for name in GLOBAL_SCRIPTS)
    return f"\n\n{MARKER} (appended by scripts/build_tts_table.py) ====\n" + \
        lua.replace("@BASE_URL@", base_url)


def _guids(objects: list) -> set[str]:
    out = set()
    for o in objects:
        out.add(o.get("GUID"))
        out |= _guids(o.get("ContainedObjects") or [])
    return out


def tiles(base_url: str, taken: set[str]) -> list[dict]:
    """The Cactuar tiles: a click opens the clicker's own browser panel."""
    lua = (SOURCE / "cactuar_tile.lua").read_text(encoding="utf-8")
    # TTS caches pictures by URL: a content hash makes a new tile picture a new URL,
    # so players see it instead of the cached old one.
    version = hashlib.sha256((SOURCE / TILE_IMAGE).read_bytes()).hexdigest()[:8]
    image = f"{base_url}{TILE_IMAGE}?v={version}"
    out = []
    for guid, x, z, rot_y in TILES:
        if guid in taken:
            sys.exit(f"the base table already has an object {guid}: pick new GUIDs in TILES")
        out.append({
            "GUID": guid, "Name": "Custom_Tile",
            "Transform": {"posX": x, "posY": 0.97, "posZ": z, "rotX": 0.0, "rotY": rot_y,
                          "rotZ": 0.0, "scaleX": TILE_SCALE, "scaleY": 1.0,
                          "scaleZ": TILE_SCALE},
            "Nickname": "Cactuar decks",
            "Description": "Click to browse the Cactuar decks and load one into your seat.",
            "GMNotes": "", "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
            "Locked": True, "Grid": False, "Snap": False, "IgnoreFoW": False,
            "MeasureMovement": False, "DragSelectable": True, "Autoraise": True,
            "Sticky": False, "Tooltip": True, "GridProjection": False,
            "HideWhenFaceDown": False, "Hands": False,
            "CustomImage": {"ImageURL": image, "ImageSecondaryURL": image,
                            "ImageScalar": 1.0, "WidthScale": 0.0,
                            "CustomTile": {"Type": 3, "Thickness": 0.1,
                                           "Stackable": False, "Stretch": True}},
            "LuaScript": lua, "LuaScriptState": "", "XmlUI": "",
        })
    return out


def _make_room_under_timers(objects: list) -> list:
    out = []
    for o in objects:
        if o.get("Name") == "BlockSquare" and o.get("Nickname") == "Timer":
            o = dict(o)
            t = dict(o.get("Transform") or {})
            t["posZ"] = TIMER_Z if t.get("posZ", 0) > 0 else -TIMER_Z   # absolute: rebuilds agree
            o["Transform"] = t
            o["LuaScriptState"] = "0"      # turn 0: cactuar_turns.lua reads >0 as a game in progress
        out.append(o)
    return out


def build(base: dict, base_url: str, name: str = NAME) -> dict:
    table = dict(base)
    ours = {guid for guid, *_ in TILES}
    objects = _make_room_under_timers(
        [o for o in table.get("ObjectStates") or []
         if o.get("GUID") not in ours])       # rebuilding from an earlier output
    lua = table.get("LuaScript") or ""
    if MARKER in lua:                       # rebuilding from an earlier output
        lua = lua[:lua.index(MARKER)].rstrip()
    xml = table.get("XmlUI") or ""
    if "<!-- Cactuar deck browser" in xml:
        xml = xml[:xml.index("<!-- Cactuar deck browser")].rstrip()
    table.update({"SaveName": name, "GameMode": name,
                  "LuaScript": lua + browser_lua(base_url),
                  "XmlUI": xml + "\n\n" + browser_xml(),
                  "ObjectStates": objects + tiles(base_url, _guids(objects))})
    return table


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("base", type=Path, help="the base table's save JSON")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL,
                    help=f"where the deck index lives (default {DEFAULT_BASE_URL})")
    ap.add_argument("--name", default=NAME, help=f"the save's name (default {NAME!r})")
    args = ap.parse_args()
    base = json.loads(args.base.read_text(encoding="utf-8-sig"))
    url = args.base_url if args.base_url.endswith("/") else args.base_url + "/"
    table = build(base, url, args.name)
    # UTF-8 without a BOM, indented like Tabletop Simulator's own saves.
    args.out.write_text(json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{args.name} -> {args.out} ({args.out.stat().st_size // 1024} KB, "
          f"decks from {url})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
