"""Where the decks live — the single owner of path policy.

The scripts sit OUTSIDE the decks they operate on:

    mtg/
    ├── scripts/            <- here. Codex reads and executes these; it cannot write them.
    └── public/             <- every deck, one folder per owner:
        └── <user>/           the Discord builder runs here for that user, so its
            └── Bracket3/     sandbox can write that user's decks and nobody else's.

That layout means a script must NOT derive the deck root from its own location
(`__file__`) — doing so would point at `mtg/`, which would make Codex's writable
root the whole repo. The deck root is therefore explicit here. Other writable
state is explicit too: the card cache is separately granted to the sandbox.

Override with MTG_DECKS to point the tools at a different workspace:

    MTG_DECKS=~/decks ./scripts/common/validate_deck.py
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

# scripts/ lives one level above the workspace it operates on.
_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_ROOT = _REPO / "public"


def deck_root() -> Path:
    """Every deck, in one folder per owner: `<root>/<user>/<Bracket>/<Deck>.txt`."""
    return Path(os.environ.get("MTG_DECKS") or _DEFAULT_ROOT).expanduser().resolve()


# Owner folders sit beside the site's own top-level names once rendered into
# docs/, so a Discord user called `img` or `Bracket3` must not get a folder.
# `Bracket*` is also where every pre-2026-10-18 deck URL lived; those paths now
# hold redirects (see build_site.redirect_pages).
_RESERVED = {"img", "mana", "tts", "private", "docs", "development", "index.html", "index.local.html"}
_USERNAME = re.compile(r"[a-z0-9_][a-z0-9_.]{0,31}")


def owner_name(username: str) -> str | None:
    """The folder name for a Discord username, or None if it cannot have one.

    Discord usernames are already lowercase letters, digits, `_` and `.`, at most
    32 long. Anything else (a legacy name, a path trick like `..`) is refused
    rather than folded, because two people must never map to one folder."""
    name = (username or "").strip().lower()
    if (not _USERNAME.fullmatch(name) or ".." in name or name in _RESERVED
            or name.startswith("bracket")):
        return None
    return name


def owner_dir(username: str) -> Path | None:
    """`public/<user>/`: that user's decks, and the builder's only writable folder
    while it works for them. None for a username that cannot have a folder."""
    name = owner_name(username)
    return deck_root() / name if name else None


def owner_of(deck: Path) -> str:
    """Whose deck this is: the folder directly under the deck root."""
    return deck.resolve().relative_to(deck_root()).parts[0]


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


REPO_FALLBACK = "https://github.com/hellozhewang/mtg"


def repo_url() -> str:
    """The GitHub URL for this checkout, derived from the git remote.

    Local config only — no network — so it is safe inside a bot turn and gives
    the same answer every run. Lives here because it is a location fact, and both
    the site builder and the Discord commands need it; two copies would drift."""
    try:
        out = subprocess.run(["git", "-C", str(_REPO), "config",
                              "--get", "remote.origin.url"],
                             capture_output=True, text=True, timeout=10)
        url = out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        url = ""
    if not url:
        return REPO_FALLBACK
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url[len("git@github.com:"):]
    return url[:-4] if url.endswith(".git") else url


def raw_url(deck: Path) -> str:
    """raw.githubusercontent link for a decklist — one paste, however long it is."""
    rel = deck.resolve().relative_to(deck_root().parent).as_posix()
    return (repo_url().replace("https://github.com/",
                               "https://raw.githubusercontent.com/")
            + f"/main/{rel}")


def site_url(deck: Path | None = None) -> str:
    """The published catalog (GitHub Pages for this repo), or one deck's page on it.

    `https://github.com/<owner>/<repo>` publishes at `https://<owner>.github.io/<repo>/`,
    and a deck's page is its path under public/ with .txt swapped for .html — the
    same rule build_site.py uses to write it: `<user>/<Bracket>/<Deck>.html`."""
    owner, _, name = repo_url().removeprefix("https://github.com/").partition("/")
    base = f"https://{owner.lower()}.github.io/{name}/"
    if deck is None:
        return base
    return base + deck.resolve().relative_to(deck_root()).with_suffix(".html").as_posix()


def log_dir() -> Path:
    """Where tool invocations and bot requests are logged. Repo root, OUTSIDE the
    deck workspace and NOT granted via --add-dir, so a sandboxed session cannot
    rewrite its own history. Tools therefore log here only when run directly;
    under the bot they fall back to stderr, which bot.py captures from codex's
    output and re-logs from outside the sandbox. See toollog.py."""
    return _REPO / "logs"


def agents_target(folder: Path) -> Path:
    """Generated AGENTS.md inside an owner's folder, the builder's working
    directory for that user. Codex auto-injects AGENTS.md only from its working
    directory, so the deployed copy must live there even though that is the
    writable root — hence the 0444 mode and the rebuild-before-send.

    Its source is the AGENTS_MD string in build_agents.py, not another file."""
    return folder / "AGENTS.md"


def rel(path: Path) -> Path | str:
    """Path relative to the deck root when possible, for tidy output."""
    try:
        return path.resolve().relative_to(deck_root())
    except ValueError:
        return path
