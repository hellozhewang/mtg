#!/usr/bin/env python3
"""Build "MTG 6 player Cactuar Ver": a scripted 6-player table plus our deck browser.

    ./build_tts_table.py BASE.json -o OUT.json
    ./build_tts_table.py BASE.json -o OUT.json --base-url http://192.168.0.100:5588/tts/

BASE is the Workshop table "MTG 6 player table - scripted" (2293586471), as Tabletop
Simulator stores it under Mods/Workshop/. It is someone else's work, so neither it
nor the output is committed: this script is, along with what it adds, tts/cactuar.lua
and tts/cactuar.xml. Everything the table already does is left exactly as it was;
the browser is appended to its Global script and Global UI.

The browser reads the deck index and deck files build_site.py publishes under
docs/tts/ (see ttsdecks.py), from GitHub Pages by default.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "tts"
NAME = "MTG 6 player Cactuar Ver"
DEFAULT_BASE_URL = "https://hellozhewang.github.io/mtg/tts/"
SEATS = ("White", "Red", "Yellow", "Green", "Blue", "Purple")
ROWS = 12                                   # must match CZ.rows in cactuar.lua
MARKER = "-- ==== Cactuar deck browser"     # how a second build recognises the first


def _section(xml: str, name: str) -> str:
    """The template between `<!-- @NAME@ -->` and the next marker (or the end)."""
    m = re.search(rf"<!-- @{name}@ -->\n(.*?)(?=\n<!-- @\w+@ -->|\Z)", xml, re.S)
    if not m:
        sys.exit(f"tts/cactuar.xml has no @{name}@ section")
    return m.group(1).rstrip() + "\n"


def browser_xml() -> str:
    template = (SOURCE / "cactuar.xml").read_text(encoding="utf-8")
    row = _section(template, "ROW")
    panel = _section(template, "PANEL")
    out = ["<!-- Cactuar deck browser: github.com/hellozhewang/mtg, tts/ -->",
           _section(template, "OPEN")]
    for color in SEATS:
        rows = "".join(row.replace("{I}", str(i)) for i in range(1, ROWS + 1))
        out.append(panel.replace("@ROWS@", rows.rstrip("\n")).replace("{C}", color))
    return "\n".join(out)


def browser_lua(base_url: str) -> str:
    lua = (SOURCE / "cactuar.lua").read_text(encoding="utf-8")
    return f"\n\n{MARKER} (appended by scripts/build_tts_table.py) ====\n" + \
        lua.replace("@BASE_URL@", base_url)


def build(base: dict, base_url: str) -> dict:
    table = dict(base)
    lua = table.get("LuaScript") or ""
    if MARKER in lua:                       # rebuilding from an earlier output
        lua = lua[:lua.index(MARKER)].rstrip()
    xml = table.get("XmlUI") or ""
    if "<!-- Cactuar deck browser" in xml:
        xml = xml[:xml.index("<!-- Cactuar deck browser")].rstrip()
    table.update({"SaveName": NAME, "GameMode": NAME,
                  "LuaScript": lua + browser_lua(base_url),
                  "XmlUI": xml + "\n\n" + browser_xml()})
    return table


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("base", type=Path, help="the base table's save JSON")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL,
                    help=f"where the deck index lives (default {DEFAULT_BASE_URL})")
    args = ap.parse_args()
    base = json.loads(args.base.read_text(encoding="utf-8-sig"))
    url = args.base_url if args.base_url.endswith("/") else args.base_url + "/"
    table = build(base, url)
    # UTF-8 without a BOM, indented like Tabletop Simulator's own saves.
    args.out.write_text(json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{NAME} -> {args.out} ({args.out.stat().st_size // 1024} KB, "
          f"decks from {url})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
