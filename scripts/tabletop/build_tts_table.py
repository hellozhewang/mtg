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

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "tts"
NAME = "MTG 6 player Cactuar Ver"
DEFAULT_BASE_URL = "https://hellozhewang.github.io/mtg/tts/"
SEATS = ("White", "Red", "Yellow", "Green", "Blue", "Purple")
ROWS = 10                                   # must match CZ.rows in cactuar.lua
CHOICES = 10                                # paged filter menu; matches CZ.menuRows
SLEEVE_CELLS = 8                            # explicit chooser, matches CZ.sleeveCells
SEARCH_CELLS = 32                           # initial scrolling pool; grows for larger containers
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
    cell = _section(template, "SLEEVECELL")
    panel = _section(template, "PANEL")
    out = ["<!-- Cactuar deck browser: github.com/hellozhewang/mtg, tts/ -->"]
    for color in SEATS:
        rows = "".join(row.replace("{I}", str(i)) for i in range(1, ROWS + 1))
        choices = "".join(choice.replace("{I}", str(i)) for i in range(1, CHOICES + 1))
        cells = "".join(cell.replace("{I}", str(i)) for i in range(1, SLEEVE_CELLS + 1))
        out.append(panel.replace("@ROWS@", rows.rstrip("\n"))
                   .replace("@CHOICES@", choices.rstrip("\n"))
                   .replace("@SLEEVECELLS@", cells.rstrip("\n")).replace("{C}", color))
    search_template = (SOURCE / "cactuar_search.xml").read_text(encoding="utf-8")
    for color in SEATS:
        cells = "".join(_section(search_template, "CARD").replace("{I}", str(i))
                        for i in range(1, SEARCH_CELLS + 1))
        out.append(_section(search_template, "SEARCH").replace("@CARDS@", cells.rstrip("\n"))
                   .replace("{C}", color))
    return "\n".join(out)


# Appended to Global in this order: the browser, then the turn totals and
# announcer, which use the browser's CZ.seats and CZ.base.
GLOBAL_SCRIPTS = ("cactuar.lua", "cactuar_catalog.lua", "cactuar_commander.lua", "cactuar_pictures.lua", "cactuar_sleeves.lua", "cactuar_guide.lua", "cactuar_turns.lua", "cactuar_regex.lua", "cactuar_search.lua", "cactuar_music.lua")


def browser_lua(base_url: str) -> str:
    lua = "\n\n".join((SOURCE / name).read_text(encoding="utf-8") for name in GLOBAL_SCRIPTS)
    # TTS caches audio by URL too: a content hash on each announcer clip makes a
    # re-recorded clip a new URL, so tables built after it play the new one.
    for clip in sorted((SOURCE / "sounds").glob("*")):
        if clip.suffix.lower() in (".wav", ".mp3", ".ogg"):
            version = hashlib.sha256(clip.read_bytes()).hexdigest()[:8]
            lua = lua.replace(f'"sounds/{clip.name}"', f'"sounds/{clip.name}?v={version}"')
    cell = _section((SOURCE / "cactuar_search.xml").read_text(encoding="utf-8"), "CARD")
    lua = lua.replace("@INSPECT_CELL@", cell)
    return f"\n\n{MARKER} (appended by scripts/tabletop/build_tts_table.py) ====\n" + \
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


def fix_timer_script(lua: str) -> str:
    """The base turn clock keeps one `timerID` and never stops a running loop before
    starting another. A second start for the same seat (a turn event plus our own
    start, or a solo player's consecutive turns) orphaned the first loop, which went
    on counting through everyone else's turns. Stop any running loop first, and clear
    the id once stopped, so `timerID ~= nil` means "running"."""
    nl = "\r\n" if "\r\n" in lua else "\n"
    stop = nl.join(["    if timerID~=nil then",
                    "      pcall(function() Wait.stop(timerID) end)",
                    "    end",
                    "    updateButtons('     ')"])
    start = nl.join(["    tdiff=0", "    timerID=Wait.time("])
    if not lua.strip() or "-- Cactuar: one loop per clock" in lua:
        return lua                                              # no script, or already fixed
    if lua.count(stop) != 1 or lua.count(start) != 1:
        sys.exit("the base table's Timer script changed: review fix_timer_script()")
    lua = lua.replace(stop, stop.replace("    end", "      timerID=nil" + nl + "    end", 1))
    return lua.replace(start, nl.join([
        "    -- Cactuar: one loop per clock. A second start replaces the running loop.",
        "    if timerID~=nil then pcall(function() Wait.stop(timerID) end) end", start]))


def fix_cannon_script(lua: str) -> str:
    """The Pirate Cannon fires the "goes first!" die and, once it rests, hands the turn to
    the winner itself (`Turns.turn_color = ...`). That skipped our game start: no totals
    reset, no turn 1 on the clock, and when the winner already held the turn (common
    after a load), no turn event at all until they passed. Hand the winner to
    cztStartGame instead, which handles both; keep the cannon's own lines as a fallback
    for a table without our script."""
    if not lua.strip():
        return lua
    nl = "\r\n" if "\r\n" in lua else "\n"
    if 'Global.call("czmCannonFired")' not in lua:
        fire = "\t\tisFiring = true"
        if lua.count(fire) != 1:
            sys.exit("the base table's cannon firing changed: review fix_cannon_script()")
        lua = lua.replace(fire, fire + nl +
                          '\t\tpcall(function() Global.call("czmCannonFired") end)')
    if "cztStartGame" in lua:
        return lua                                              # winner hook already fixed
    pad = "\t" * 7
    old = nl.join([pad + "Turns.enable = true", pad + "Turns.turn_color = ply.color"])
    if lua.count(old) != 1:
        sys.exit("the base table's Pirate Cannon script changed: review fix_cannon_script()")
    return lua.replace(old, nl.join([
        pad + "-- Cactuar: start the game through Global (totals, turn 1 on the clock).",
        pad + "local started = pcall(function() Global.call(\"cztStartGame\", ply.color) end)",
        pad + "if not started then",
        pad + "\tTurns.enable = true",
        pad + "\tTurns.turn_color = ply.color",
        pad + "end"]))


def _make_room_under_timers(objects: list) -> list:
    out = []
    for o in objects:
        if o.get("Name") == "BlockSquare" and o.get("Nickname") == "Timer":
            o = dict(o)
            t = dict(o.get("Transform") or {})
            t["posZ"] = TIMER_Z if t.get("posZ", 0) > 0 else -TIMER_Z   # absolute: rebuilds agree
            o["Transform"] = t
            o["LuaScriptState"] = "0"      # turn 0: cactuar_turns.lua reads >0 as a game in progress
            o["LuaScript"] = fix_timer_script(o.get("LuaScript") or "")
        elif o.get("Nickname") == "Pirate Cannon":
            o = dict(o)
            o["LuaScript"] = fix_cannon_script(o.get("LuaScript") or "")
        out.append(o)
    return out


# The right-hand edge strip between the Purple and White seats (x 45..54, z -24..14),
# below the Cactuar tile: rikrassen's importer, dice, counter/keyword bags, commander
# damage markers, Turn Order card, Turn Skipper puck and the Planechase bag. The owner
# asked (2026-10-24) to clear it and draw a plain stack area with five card slots.
# Only the base's "Table Instructions" tile names these, in its optional clutter
# remover, which skips missing objects (pcall), so removing them breaks nothing.
STRIP_GUIDS = frozenset({
    "222541", "098c38", "1e0d2b", "40f9d3", "aa184e", "3cba4d", "94b67a", "916ad9", "576ccd", "6c6f29",
    "1d9a7a", "bbcbc1", "b3961f", "b2b54e", "2fff0c", "5cf32d", "9c3ffe", "da1b48", "5035f1", "8aab65",
    "1de175", "51e7af", "383659", "29d31b", "beb998", "418ec8", "dd259e", "327b82", "3cab4b", "56a44e",
    "855d09", "fcb171", "fcbaf4", "d3198d", "df61a3", "e76686", "b02684", "de25ac", "aaf003", "9cf532",
    "0beb07", "4256ba", "9ca38a", "401fc2", "7071ce", "7bf068", "eab9bb", "63bc71", "3d7912", "b34886",
    "3c7ad3", "d7dc8e", "a4868a", "ed330c", "295538", "633ed3", "7dd5e3", "dc19a6", "818de4", "b7ccfb",
})
# The stack area drawn there: five portrait card slots in one column under the Cactuar
# tile (x 48.2). Cards on this table are about 2.25 x 3.15; the slots leave a margin.
STACK_X, STACK_Z, STACK_Y = 48.2, -5.0, 0.97        # centre of the column; table surface
SLOT_W, SLOT_H, SLOT_STEP, SLOTS = 2.6, 3.5, 4.2, 5
STACK_COLOR = {"r": 0.92, "g": 0.88, "b": 0.78}     # soft cream, like the playmat lines


def _rect(cx: float, cz: float, w: float, h: float, thickness: float) -> dict:
    corners = [(cx - w / 2, cz - h / 2), (cx + w / 2, cz - h / 2),
               (cx + w / 2, cz + h / 2), (cx - w / 2, cz + h / 2)]
    return {"points3": [{"x": round(x, 3), "y": STACK_Y, "z": round(z, 3)} for x, z in corners],
            "color": dict(STACK_COLOR), "thickness": thickness,
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0}, "loop": True, "square": True}


def stack_area() -> tuple[list[dict], list[dict]]:
    """Vector lines (outer rectangle + one per slot) and a snap point per slot."""
    first = STACK_Z - SLOT_STEP * (SLOTS - 1) / 2
    centres = [first + i * SLOT_STEP for i in range(SLOTS)]
    margin = 0.6
    lines = [_rect(STACK_X, STACK_Z, SLOT_W + 2 * margin,
                   SLOT_STEP * (SLOTS - 1) + SLOT_H + 2 * margin, 0.12)]
    lines += [_rect(STACK_X, z, SLOT_W, SLOT_H, 0.06) for z in centres]
    snaps = [{"Position": {"x": STACK_X, "y": 0.961135, "z": round(z, 3)},
              "Rotation": {"x": 0.0, "y": 180.0, "z": 0.0}} for z in centres]
    return lines, snaps


def build(base: dict, base_url: str, name: str = NAME) -> dict:
    table = dict(base)
    ours = {guid for guid, *_ in TILES}
    objects = _make_room_under_timers(
        [o for o in table.get("ObjectStates") or []
         if o.get("GUID") not in ours           # rebuilding from an earlier output
         and o.get("GUID") not in STRIP_GUIDS])  # the cleared edge strip
    lines, snaps = stack_area()
    stack = {(round(s["Position"]["x"], 3), round(s["Position"]["z"], 3)) for s in snaps}
    old_lines = [l for l in table.get("VectorLines") or [] if l.get("color") != STACK_COLOR]
    old_snaps = [s for s in table.get("SnapPoints") or []
                 if (round(s["Position"]["x"], 3), round(s["Position"]["z"], 3)) not in stack]
    lua = table.get("LuaScript") or ""
    if MARKER in lua:                       # rebuilding from an earlier output
        lua = lua[:lua.index(MARKER)].rstrip()
    xml = table.get("XmlUI") or ""
    if "<!-- Cactuar deck browser" in xml:
        xml = xml[:xml.index("<!-- Cactuar deck browser")].rstrip()
    table.update({"SaveName": name, "GameMode": name,
                  "VectorLines": old_lines + lines, "SnapPoints": old_snaps + snaps,
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
