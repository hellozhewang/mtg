"""Puts scripts/<area>/ on sys.path for the tests (scripts/ is split into common/,
tabletop/ and discord/, with the Discord bot in discord/bot/; module names stay flat)."""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path[:0] = [d for d in (str(SCRIPTS / s) for s in ("common", "tabletop", "discord", "discord/bot"))
                if d not in sys.path]
