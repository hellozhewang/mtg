"""Where the decks live — the single owner of path policy.

The scripts sit OUTSIDE the workspace they operate on:

    mtg/
    ├── scripts/     <- here. Codex reads and executes these; it cannot write them.
    └── public/      <- the workspace. Codex's working root, and the only writable tree.

That layout means a script must NOT derive the deck root from its own location
(`__file__`) — doing so would point at `mtg/`, which would make Codex's writable
root the whole repo. The deck root is therefore explicit here. Other writable
state is explicit too: the card cache is separately granted to the sandbox, while
trusted deck provenance is kept outside both writable locations.

Override with MTG_DECKS to point the tools at a different workspace:

    MTG_DECKS=~/decks ./scripts/validate_deck.py
"""
from __future__ import annotations

import os
import subprocess
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


def deck_metadata_db() -> Path:
    """Trusted metadata written by the bot parent, currently deck authorship.

    This deliberately does NOT live in `.cache/`: that whole directory is
    granted to the sandboxed model so card tools can bank Scryfall results. An
    author attribution is provenance, not a cache entry, and the model must not
    be able to forge it or erase it with `cache.py --clear`.

    `MTG_DECK_METADATA` exists for tests and alternate deployments.
    """
    override = os.environ.get("MTG_DECK_METADATA")
    if override:
        return Path(override).expanduser().resolve()
    return _REPO / "bot" / ".deck-metadata.db"


def private_dir() -> Path:
    """The owner's decks. Published and committed like the ones in `deck_root()`;
    what sets them apart is that the Discord builder does not work on them.

    Repo root, OUTSIDE the deck workspace. The builder's sandbox allows writes
    only under `public/`, so it cannot change these. It CAN read them (the
    sandbox does not bound reads), so keeping them out of its deckbuilding, so
    that it never tunes, copies or dedupes against them, rests on its
    instructions (AGENTS_MD in build_agents.py), which never name this folder.

    Mirror the bracket folders in here (`private/Bracket3/Foo.txt`); the bracket
    folder is what marks a file as a deck (see `deckfile.discover_private`), and
    the bracket rules apply as usual. Nothing else in here is a deck: the owner
    keeps tools and scratch files alongside."""
    return Path(os.environ.get("MTG_PRIVATE") or _REPO / "private").expanduser().resolve()


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
    same rule build_site.py uses to write it. An owner's deck in `private_dir()`
    gets a `private/` prefix, so it cannot share a page with a public deck of the
    same bracket and name."""
    owner, _, name = repo_url().removeprefix("https://github.com/").partition("/")
    base = f"https://{owner.lower()}.github.io/{name}/"
    if deck is None:
        return base
    path = deck.resolve()
    if private_dir() in path.parents:
        rel = "private/" + path.relative_to(private_dir()).with_suffix(".html").as_posix()
    else:
        rel = path.relative_to(deck_root().resolve()).with_suffix(".html").as_posix()
    return base + rel


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
