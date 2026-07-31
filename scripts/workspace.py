"""Where the decks live — the single owner of path policy.

The scripts sit OUTSIDE the workspace they operate on:

    mtg/
    ├── scripts/     <- here. Codex reads and executes these; it cannot write them.
    └── public/      <- the workspace. Codex's working root, and the only writable tree.

That layout means a script must NOT derive the deck root from its own location
(`__file__`) — doing so would point at `mtg/`, which would make Codex's writable
root the whole repo. The deck root is therefore explicit here, and everything
writable (notably the SQLite cache) lives inside it so that
`codex -s workspace-write -C <deck root>` can actually write it.

Override with MTG_DECKS to point the tools at a different workspace:

    MTG_DECKS=~/decks ./scripts/validate_deck.py
"""
from __future__ import annotations

import os
from pathlib import Path

# scripts/ lives one level above the workspace it operates on.
_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_ROOT = _REPO / "public"


def deck_root() -> Path:
    """The workspace: where decklists live and where writes are allowed."""
    return Path(os.environ.get("MTG_DECKS") or _DEFAULT_ROOT).expanduser().resolve()


def cache_dir() -> Path:
    """Directory holding the SQLite cache. Lives at the repo root, OUTSIDE the deck
    workspace, so the sandboxed session needs it granted explicitly — bot.py passes
    `--add-dir` for exactly this path. Without that grant, writes fail and the tools
    fall back to a read-only cache."""
    override = os.environ.get("MTG_CACHE")
    if override:
        return Path(override).expanduser().resolve().parent
    return _REPO / ".cache"


def cache_db() -> Path:
    override = os.environ.get("MTG_CACHE")
    if override:
        return Path(override).expanduser().resolve()
    return cache_dir() / "cards.db"


def site_dir() -> Path:
    """Generated GitHub Pages catalog. `docs/` is not arbitrary — Pages serves a
    branch subfolder only from `/docs`, so this name is what lets the site deploy
    with no workflow file and no second branch.

    It sits at the repo root, OUTSIDE the deck workspace, so the sandboxed session
    cannot write it. Publishing is bot.py's job, from outside the sandbox."""
    return Path(os.environ.get("MTG_SITE") or _REPO / "docs").expanduser().resolve()


def frontend_dir() -> Path:
    """Hand-written markup, CSS and JS for the catalog. Source, not output —
    `site_dir()` is what gets generated from it."""
    return Path(os.environ.get("MTG_FRONTEND") or _REPO / "frontend").expanduser().resolve()


def log_dir() -> Path:
    """Where tool invocations and bot requests are logged. Repo root, OUTSIDE the
    deck workspace and NOT granted via --add-dir, so a sandboxed session cannot
    rewrite its own history. Tools therefore log here only when run directly;
    under the bot they fall back to stderr, which bot.py captures from codex's
    output and re-logs from outside the sandbox. See toollog.py."""
    return _REPO / "logs"


def agents_target() -> Path:
    """Generated AGENTS.md inside the workspace. Codex auto-injects AGENTS.md only
    from its working directory, so the deployed copy must live here even though
    that is the writable root — hence the 0444 mode and the rebuild-before-send.

    Its source is the AGENTS_MD string in build_agents.py, not another file."""
    return deck_root() / "AGENTS.md"


def rel(path: Path) -> Path | str:
    """Path relative to the deck root when possible, for tidy output."""
    try:
        return path.resolve().relative_to(deck_root())
    except ValueError:
        return path
