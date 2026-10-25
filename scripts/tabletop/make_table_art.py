#!/usr/bin/env python3
"""Render the Cactuar table's decal pictures into tts/table/ with headless Chrome.

    ./make_table_art.py

    tts/table/stack-panel.png        the edge-strip stack area, under its five snap points
    tts/table/triggers-<Seat>.png    the trigger-area label, in that seat's playmat colour

The pictures are laid out in HTML at 100 px per table unit (rendered at twice that)
from build_tts_table.py's stack geometry, so the slots line up with the snap points.
cactuar_lines.lua lays them on the table as decals. Re-run after changing the stack
geometry or the seat colours, and commit the PNGs.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

_SCRIPTS = next(p for p in Path(__file__).resolve().parents if p.name == "scripts")
sys.path.insert(0, str(_SCRIPTS / "tabletop"))
import build_tts_table as table  # noqa: E402

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
OUT = table.SOURCE / "table"
PX = 100                                   # CSS pixels per table unit
FONT = '"Avenir Next", "Helvetica Neue", Helvetica, Arial, sans-serif'
SILVER, SILVER_DIM = "#cfd4db", "rgba(207, 212, 219, 0.42)"
# Playmat border colours: Tabletop Simulator's seat colours, except White's cream mat.
SEAT_RGB = {"White": (0.92, 0.88, 0.78), "Red": (0.856, 0.1, 0.094),
            "Yellow": (0.905, 0.898, 0.172), "Green": (0.192, 0.701, 0.168),
            "Blue": (0.118, 0.53, 1.0), "Purple": (0.627, 0.125, 0.941)}
LABEL_W, LABEL_H = 5.6, 1.3                # the trigger label, in table units


def render(html: str, width: float, height: float, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "art.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=2", "--default-background-color=00000000",
                        f"--window-size={round(width)},{round(height)}",
                        f"--screenshot={out}", page.as_uri()],
                       check=True, capture_output=True)
    print(f"{out.relative_to(table.REPO)}")


def stack_panel() -> None:
    g = table.stack_geometry()
    w, h = g["width"] * PX, g["height"] * PX
    slots = []
    for i, z in enumerate(g["slots"], 1):
        top = (g["top"] - z - table.SLOT_H / 2) * PX
        left = (w - table.SLOT_W * PX) / 2
        slots.append(f'<div class="slot" style="left:{left}px;top:{top}px"><span>{i}</span>'
                     '<i class="c tl"></i><i class="c tr"></i><i class="c bl"></i><i class="c br"></i></div>')
    html = f"""<!doctype html><meta charset="utf-8"><style>
html, body {{ margin: 0; width: {w}px; height: {h}px; background: transparent; overflow: hidden; position: relative; }}
.panel {{ position: absolute; inset: 0; border-radius: 24px; box-sizing: border-box;
  background: linear-gradient(180deg, rgba(33, 37, 44, 0.95), rgba(20, 22, 27, 0.95));
  border: 3px solid {SILVER}; box-shadow: inset 0 0 0 8px rgba(20, 22, 27, 0.0), inset 0 0 0 9.5px {SILVER_DIM}; }}
.head {{ position: absolute; left: 0; right: 0; top: 0; height: {g["header"] * PX + 30}px;
  display: flex; align-items: center; justify-content: center; gap: 14px;
  font: 600 31px/1 {FONT}; letter-spacing: 11px; color: {SILVER}; }}
.head b {{ display: block; width: 46px; height: 2px; background: {SILVER_DIM}; }}
.slot {{ position: absolute; width: {table.SLOT_W * PX}px; height: {table.SLOT_H * PX}px; box-sizing: border-box;
  border-radius: 14px; border: 2px solid {SILVER_DIM};
  background: radial-gradient(ellipse at 50% 40%, rgba(207, 212, 219, 0.07), rgba(207, 212, 219, 0.02)); }}
.slot span {{ position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  font: 600 128px/1 {FONT}; color: rgba(207, 212, 219, 0.13); }}
.c {{ position: absolute; width: 30px; height: 30px; border: 0 solid {SILVER}; }}
.tl {{ left: -2px; top: -2px; border-width: 4px 0 0 4px; border-top-left-radius: 14px; }}
.tr {{ right: -2px; top: -2px; border-width: 4px 4px 0 0; border-top-right-radius: 14px; }}
.bl {{ left: -2px; bottom: -2px; border-width: 0 0 4px 4px; border-bottom-left-radius: 14px; }}
.br {{ right: -2px; bottom: -2px; border-width: 0 4px 4px 0; border-bottom-right-radius: 14px; }}
.foot {{ position: absolute; left: 0; right: 0; bottom: 18px; text-align: center;
  font: 600 14px/1 {FONT}; letter-spacing: 4px; color: rgba(207, 212, 219, 0.5); }}
</style><div class="panel"></div><div class="head"><b></b>STACK<b></b></div>{"".join(slots)}
<div class="foot">RESOLVES FROM THE TOP</div>"""
    render(html, w, h, OUT / "stack-panel.png")


def trigger_label(seat: str) -> None:
    r, g, b = (round(c * 255) for c in SEAT_RGB[seat])
    w, h = LABEL_W * PX, LABEL_H * PX
    html = f"""<!doctype html><meta charset="utf-8"><style>
html, body {{ margin: 0; width: {w}px; height: {h}px; background: transparent; overflow: hidden; position: relative; }}
div {{ height: 100%; display: flex; align-items: center; justify-content: center; gap: 18px;
  font: 700 62px/1 {FONT}; letter-spacing: 13px; padding-left: 13px; box-sizing: border-box;
  color: rgb({r}, {g}, {b}); text-shadow: 0 2px 7px rgba(0, 0, 0, 0.65), 0 0 2px rgba(0, 0, 0, 0.5); }}
</style><div>TRIGGERS</div>"""
    render(html, w, h, OUT / f"triggers-{seat}.png")


def main() -> int:
    if not CHROME.exists():
        sys.exit(f"needs Google Chrome at {CHROME}")
    OUT.mkdir(exist_ok=True)
    stack_panel()
    for seat in table.SEATS:
        trigger_label(seat)
    return 0


if __name__ == "__main__":
    sys.exit(main())
