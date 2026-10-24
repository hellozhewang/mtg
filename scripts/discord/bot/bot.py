#!/usr/bin/env python3
"""Persistent deck-builder session for the Discord bot to talk to.

The model runs on a swappable harness (scripts/discord/bot/harness.py): Antigravity (`agy`, Gemini by
default) or Codex. MTG_BOT_HARNESS / MTG_BOT_MODEL pick it. What follows describes the
mechanics in Codex terms where they started; the harness module has each one's details.

    from bot import send, reset, session_id
    reply = send("Which Game Changers is Zur-Voltron running?", "discord_username")

Or from a shell, for testing:

    ./bot.py --user discord_username "swap Moat out of Zur-Voltron for something legal"
    ./bot.py --reset            # start a fresh session
    ./bot.py --status
    ./bot.py --usage            # account allowance; no model turn

One long-lived Codex session is pinned PER CHANNEL AND USER. State lives in
`.sessions/<channel>-<user>.json`; the first call records its session UUID and
every later call uses `codex exec resume <uuid>`, so each person in each Discord
channel or thread keeps their own conversation context. Per user, because each
user's session runs in that user's own deck folder (below). Pass the channel id:

    reply = send("...", message.author.username, channel=message.channel.id)

Omitting it uses the "cli" channel, which is what the command line uses.

Operating instructions: edit the AGENTS_MD string in `scripts/discord/build_agents.py`,
which deploys it to `public/<user>/AGENTS.md` as mode 0444 before every send, because
codex auto-injects AGENTS.md only from its working directory — under an
`# AGENTS.md instructions for <dir>` / `<INSTRUCTIONS>` header, on every invocation
including resumes. So the rules cost no turn, apply to fresh sessions, and take
effect mid-conversation when edited. The source lives outside `-C public` so the
session cannot alter it.

After each model turn, decklist changes under `public/` are committed and pushed
automatically — see `_autopush`. Detection is scoped to that directory only; when
something there did change, `docs/` (the published catalog) is regenerated from
it and staged in the same commit, so the site never lags the decks.

The caller also supplies the Discord username, and it decides where the session
works: `public/<user>/`, that user's own deck folder, created on first use. The
folder is the deck's owner, so authorship needs no record of its own and cannot
be wrong: a deck is credited to whoever's folder it is in.

Codex has no flag to name a session, so the UUID is scraped from the startup
banner (`session id: <uuid>`) and persisted here. Note `codex exec resume` filters
by cwd, so every invocation of one session must run from the same directory —
one more reason sessions are per user: each always runs in its own user folder.

Sandbox: `-s workspace-write -C <public/<user>/>` confines writes to the asking
user's decks. Other users' decks, `../../scripts`, `../../logs` and the docs are
readable and runnable but not writable. Reads are not bounded, so "start from
ratdos's Giada" works; writing someone else's deck does not. The cache lives at `<repo>/.cache`, outside the workspace, so it is
granted explicitly with `--add-dir` — without that the tools would still run but
could not bank Scryfall results.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:                                   # POSIX advisory locking
    import fcntl
except ImportError:                    # Windows: degrade to no locking
    fcntl = None


HERE = Path(__file__).resolve().parent               # scripts/discord/bot/ — OUTSIDE the workspace
REPO = HERE.parents[2]

# The AGENTS.md generator lives in scripts/ (outside the writable root) so the
# session cannot edit the thing that writes its own instructions.
_SCRIPTS = next(p for p in Path(__file__).resolve().parents if p.name == "scripts")
sys.path[:0] = [d for d in (str(_SCRIPTS / s) for s in ("common", "tabletop", "discord", "discord/bot"))
                if d not in sys.path]          # scripts/ is split by area; module names stay flat
import build_agents
import deckplacement
import toollog
import workspace

import commands
import harness
import postprocess
import sleever
import usage

# Ask workspace.py; do NOT derive these from __file__. scripts/discord/bot/ sits outside the tree
# it drives, so `HERE.parent` is the repo root — using it as the workspace would
# silently hand the Codex session write access to scripts/, docs/ and logs/.
WORKSPACE = workspace.deck_root()                    # public/ — every owner's folder
CACHE_DIR = workspace.cache_dir()                    # outside WORKSPACE; needs --add-dir
SESSIONS = HERE / ".sessions"                        # one JSON per channel and user
LEGACY_STATE = HERE / ".session.json"                # pre-per-channel; migrated on load
LOG_DIR = REPO / "logs"                              # one text log per UTC day

# Channel key used when nothing is supplied — CLI testing, mostly. Discord passes
# the channel or thread id so each conversation gets its own Codex session.
DEFAULT_CHANNEL = "cli"

# The harness and model: MTG_BOT_HARNESS (default agy), MTG_BOT_MODEL, MTG_BOT_EFFORT.
# Discord users are waiting on this, so the defaults sit below the ceiling.
HARNESS = harness.from_env()
MODEL = HARNESS.model
EFFORT = HARNESS.effort
TIMEOUT = int(os.environ.get("MTG_BOT_TIMEOUT", "600"))

# ---------- session state (per channel) ----------

def _key(channel: str | int | None) -> str:
    """Filesystem-safe key for a channel id.

    Discord snowflakes are digits, but this is defensive: the key becomes a
    filename, so anything outside [A-Za-z0-9_-] is folded to '_' and the result is
    length-capped. Prevents a caller-supplied id from escaping SESSIONS via '..'
    or a slash.
    """
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", str(channel or DEFAULT_CHANNEL))[:64]
    return cleaned or DEFAULT_CHANNEL


def _state_path(channel: str | int | None) -> Path:
    return SESSIONS / f"{_key(channel)}.json"


def _migrate_legacy() -> None:
    """Move a pre-per-channel .session.json to the default channel, once.

    Without this, switching to per-channel state would silently abandon the
    existing conversation rather than carrying it over.
    """
    if not LEGACY_STATE.exists():
        return
    target = _state_path(DEFAULT_CHANNEL)
    try:
        SESSIONS.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text(LEGACY_STATE.read_text())
            log().info("migrated legacy .session.json -> %s", target.name)
        LEGACY_STATE.unlink()
    except OSError as exc:
        log().warning("legacy session migration failed: %s", exc)


def _load(channel: str | int | None) -> dict:
    _migrate_legacy()
    try:
        return json.loads(_state_path(channel).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(channel: str | int | None, data: dict) -> None:
    SESSIONS.mkdir(parents=True, exist_ok=True)
    _state_path(channel).write_text(json.dumps(data, indent=2) + "\n")


def session_id(channel: str | int | None = DEFAULT_CHANNEL) -> str | None:
    """The pinned session for a channel, or None if there is nothing to resume.

    A session pinned under a DIFFERENT model or effort is treated as nothing to
    resume. `_save` has always recorded both alongside the id, but nothing ever
    read them back, so changing MODEL left every channel resuming a conversation
    created under the old one — and whether `codex exec resume` honours a new
    `-m` is not documented. Returning None here forces a fresh session, which
    makes the switch actually take effect.

    The cost is one lost conversation per channel, once, at the moment the model
    changes. That is the right trade against a model change that silently does
    nothing.
    """
    state = _load(channel)
    sid = state.get("session_id")
    if not sid:
        return None
    # A session belongs to the harness that made it; sessions saved before harnesses
    # existed are Codex's.
    was = (state.get("harness", "codex"), state.get("model"), state.get("effort"))
    now = (HARNESS.name, MODEL, EFFORT)
    if state.get("model") and was != now:
        log().info("[%s] pinned under %s/%s/%s but running %s/%s/%s; starting fresh",
                   _key(channel), *was, *now)
        return None
    return sid


def channels() -> list[tuple[str, dict]]:
    """Every channel with a pinned session, for --status."""
    _migrate_legacy()
    out = []
    for f in sorted(SESSIONS.glob("*.json")) if SESSIONS.exists() else []:
        try:
            out.append((f.stem, json.loads(f.read_text())))
        except json.JSONDecodeError:
            out.append((f.stem, {"session_id": "(corrupt)"}))
    return out


@contextlib.contextmanager
def _flock(path: Path):
    """Exclusive advisory lock on `path`, blocking until acquired.

    Used where locks must be PER CHANNEL — one file per channel gives that for
    free. Best-effort no-op on non-POSIX, where fcntl is unavailable; see
    `_dblock` for the global lock, which has no such gap.
    """
    if fcntl is None:
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# Global mutex, held only briefly. Lives in scripts/discord/bot/ and NOT in .cache/cards.db,
# deliberately: the cache is handed to the sandbox via --add-dir, so a lock kept
# there would be one the sandboxed session could take, hold or corrupt.
LOCK_DB = HERE / ".locks.db"
# Separate file from LOCK_DB on purpose. The busy lock is held for a WHOLE turn
# (minutes), while _dblock is taken briefly inside that turn by _autopush — one
# file for both would mean a turn deadlocking against itself.
BUSY_DB = HERE / ".busy.db"
# Users reach this agent by typing `builder <request>` as a plain Discord
# message (see deckBuilder.ts in the discord-bot project), so name that, not a
# slash command — there isn't one.
BUSY_REPLY = "Builder is busy with another request. Try again in a minute."
LOCK_TIMEOUT = 120


@contextlib.contextmanager
def _dblock(timeout: int = LOCK_TIMEOUT):
    """Cross-platform exclusive lock, via SQLite's own writer lock.

    `BEGIN IMMEDIATE` takes the database-wide RESERVED lock, so a second caller
    blocks until the first commits or rolls back — a real mutex, with two
    properties `_flock` cannot match:

      * it works on Windows, where `fcntl` is missing and `_flock` silently
        degrades to no locking at all;
      * it is crash-safe. SQLite's locks are OS file locks underneath, so a
        killed process releases them when the kernel closes its handle. A
        lock-row-in-a-table scheme would instead strand the lock forever.

    Database-wide is the right granularity here precisely because the thing it
    guards — the git index — is itself global.
    """
    con = sqlite3.connect(LOCK_DB, timeout=timeout)
    try:
        con.execute("BEGIN IMMEDIATE")
        yield
    finally:
        con.rollback()          # release without writing; nothing to persist
        con.close()


@contextlib.contextmanager
def _creation_lock(channel: str | int | None):
    """Serialise session creation for ONE channel.

    Without it, two cold calls on the same channel each open their own Codex
    session and race to write the state file — last writer wins and the loser's
    conversation is orphaned. Measured before the fix: two concurrent cold sends
    produced two session ids and the survivor recalled only one prompt.

    Scoped to creation, and per channel: concurrent `codex exec resume` on an
    already-pinned session was tested safe (three parallel turns, all recalled),
    and two different channels have no reason to block each other.
    """
    with _flock(SESSIONS / f"{_key(channel)}.lock"):
        yield


def reset(channel: str | int | None = DEFAULT_CHANNEL) -> str | None:
    """Forget one channel's sessions, every user's. Returns an id that was dropped."""
    old = session_id(channel)
    _state_path(channel).unlink(missing_ok=True)
    for f in sorted(SESSIONS.glob(f"{_key(channel)}-*.json")) if SESSIONS.exists() else []:
        old = old or _load(f.stem).get("session_id")
        f.unlink(missing_ok=True)
    return old


def reset_all() -> int:
    """Forget every channel's session. Returns how many were dropped."""
    n = 0
    for f in sorted(SESSIONS.glob("*.json")) if SESSIONS.exists() else []:
        f.unlink(missing_ok=True)
        n += 1
    LEGACY_STATE.unlink(missing_ok=True)
    return n


# ---------- logging ----------

def _oneline(text: str) -> str:
    """Collapse to a single log line, keeping newlines visible as \\n."""
    return (text or "").replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "")



# Single plain-text log: prompts, replies, and everything bot.py did — argv,
# session reuse, sync decisions, exit codes, codex stderr. One line per event so it
# stays greppable; prompt/reply newlines are escaped rather than wrapped.
DEBUG = bool(os.environ.get("MTG_BOT_DEBUG"))
_log_obj: logging.Logger | None = None


def log() -> logging.Logger:
    """Lazily configured logger writing `logs/<utc-date>.log`.

    Configured per-process: bot.py is invoked once per request and exits, so the
    handler opens in append mode, writes, and closes with the process. Safe for
    concurrent invocations because each line is a single small append.
    """
    global _log_obj
    if _log_obj is not None:
        return _log_obj

    lg = logging.getLogger("mtgbot")
    lg.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    lg.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s",
                            datefmt="%Y-%m-%dT%H:%M:%S%z")
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        fh = logging.FileHandler(LOG_DIR / f"{day}.log", encoding="utf-8")
        fh.setFormatter(fmt)
        lg.addHandler(fh)
    except OSError as exc:
        print(f"warning: debug log unavailable: {exc}", file=sys.stderr)
    if DEBUG:                                  # mirror to stderr when debugging
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        lg.addHandler(sh)
    if not lg.handlers:
        lg.addHandler(logging.NullHandler())
    _log_obj = lg
    return lg


# ---------- turns ----------

# Fallback only. Tools record themselves through toollog, which writes to the
# cache database the sandbox can reach; this regex recovers a call from codex's
# captured output if that failed. It is lossy — codex does not echo every tool's
# stderr — which is exactly why it is no longer the primary source.
TOOL_LINE = re.compile(r"\[mtg-tool\]\s*(.+)")


# Auto-commit deck changes after each turn. Set MTG_BOT_NO_PUSH=1 to disable.
#
# This runs in bot.py — the trusted PARENT, outside the sandbox — deliberately.
# The alternative was a git repo inside public/ so the session could commit its
# own work, and that was rejected: `.git/` is currently unwritable from the
# sandbox, which is the only thing stopping the agent from publishing to the
# internet under the owner's GitHub identity. (Measured: `git push` itself
# already works from inside and authenticates via osxkeychain — it simply has
# nothing to push, because `git add`/`commit` hit
# ".git/index.lock: Operation not permitted". Handing it a writable .git would
# join those two halves.) Doing it here gets the same outcome — deck links live
# immediately instead of 404ing until a human pushes — while every commit stays
# attributable to a bot turn rather than to the model's discretion.
AUTOPUSH = not os.environ.get("MTG_BOT_NO_PUSH")

# Catalog builds also recheck every exported TTS image with the remote host.
# Conditional GETs save bandwidth, but thousands of URLs still take minutes;
# leave room for both those checks and new card-thumbnail downloads.
SITE_TIMEOUT = int(os.environ.get("MTG_SITE_TIMEOUT", "600"))


def _git(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, timeout=timeout)


def _build_site() -> str | None:
    """Regenerate the published catalog. Returns its path relative to REPO, ready
    to hand to `git add`, or None if the build failed.

    A subprocess rather than an import, for two reasons: a timeout is available
    (a new deck can need a few dozen card images, and a stalled CDN must not hold
    a Discord reply open), and a crash in the generator cannot take down the bot.

    Runs OUTSIDE the codex sandbox, in this process's own environment — which is
    the point. `docs/` sits outside the workspace precisely so the model cannot
    write the published site directly; only a completed bot turn can.
    """
    site = workspace.site_dir()
    try:
        r = subprocess.run([sys.executable, str(REPO / "scripts" / "common" / "build_site.py"),
                            "--quiet"],
                           capture_output=True, text=True, timeout=SITE_TIMEOUT)
    except subprocess.SubprocessError as exc:
        log().warning("site: build did not finish (%s)", type(exc).__name__)
        return None
    if r.returncode:
        log().warning("site: build failed rc=%d: %s", r.returncode,
                      (r.stderr or r.stdout).strip()[:300])
        return None
    if r.stderr.strip():                       # unavailable images, say
        log().info("site: %s", r.stderr.strip()[:300])
    log().info("site: rebuilt %s", site.name)
    return str(site.relative_to(REPO))


class Busy(RuntimeError):
    """Raised when a model turn is already in flight."""


def _claim_bot() -> sqlite3.Connection:
    """Take the whole-bot lock WITHOUT waiting. Raises Busy if another turn holds it.

    Per-channel locks only stopped one channel racing itself. This is bot-wide,
    because the expensive things a turn does are global: one Codex process at a
    high reasoning effort, the shared Scryfall cache, the git index, and a `git
    push`. Two turns at once contend on all four.

    Non-blocking on purpose. Queueing would leave a Discord user staring at
    nothing for the length of someone else's turn — minutes — with no idea why;
    a refusal they can retry is the kinder failure. `timeout=0` is what makes
    BEGIN IMMEDIATE fail instantly rather than wait.

    The lock is the SQLite transaction itself, so it cannot leak: if this process
    dies the connection closes and the lock is gone, with no stale file to clean.
    """
    con = sqlite3.connect(BUSY_DB, timeout=0)
    try:
        con.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as exc:
        con.close()
        raise Busy from exc
    return con


def _release_bot(con: sqlite3.Connection) -> None:
    try:
        con.rollback()
    finally:
        con.close()


def _autopush(chan: str, source: Path | None = None, what: str = "Deck") -> None:
    """Commit and push decklist changes (or, for sleever, `source` = tts/sleeves/).
    Never raises — a git failure must not lose the user's reply, which has already
    been produced by this point."""
    if not AUTOPUSH:
        return
    try:
        # Serialise: two channels replying at once would otherwise race on the
        # git index, and git errors rather than waiting.
        with _dblock():
            # Scope to the deck workspace only. A bare `git add -A` would sweep
            # up whatever else is in flight in the repo — someone editing
            # scripts/ in another window, say — into a commit attributed to a
            # Discord turn.
            rel = str((source or WORKSPACE).relative_to(REPO))
            if not _git("status", "--porcelain", "--", rel).stdout.strip():
                return                                  # nothing changed
            site = _build_site()
            maps = [
                str((workspace.frontend_dir() / "deck-tiers.json").relative_to(REPO)),
                str((workspace.frontend_dir() / "deck-themes.json").relative_to(REPO)),
            ] if source is None else []
            paths = [rel, *([site] if site else []), *maps]
            add = _git("add", "--", *paths)
            if add.returncode:
                log().warning("autopush: git add failed: %s", add.stderr.strip()[:200])
                return

            msg = f"{what} update via Discord ({chan})"
            # `--` PATHS is what actually bounds the commit. Without it, `git
            # commit` records the WHOLE index, so anything a human had staged in
            # another window — a half-finished script — would be swept into a
            # commit attributed to a Discord turn and pushed. Scoping the `git
            # add` above does not prevent that; only this does. Untracked files
            # still land, because the add above makes them known to the index.
            commit = _git("commit", "-m", msg, "--", *paths)
            if commit.returncode:
                log().warning("autopush: git commit failed: %s",
                              commit.stderr.strip()[:200])
                return
            log().info("autopush: committed %s changes (%s)", what.lower(), chan)

            if not _git("remote").stdout.strip():
                log().info("autopush: no remote configured; committed only")
                return
            push = _git("push", "origin", "HEAD", timeout=180)
            if push.returncode:
                # Diverged history, offline, revoked token — all recoverable by
                # hand later. The commit is already safe locally.
                log().warning("autopush: push failed (commit kept): %s",
                              push.stderr.strip()[:200])
            else:
                log().info("autopush: pushed to origin")
    except Exception as exc:                            # never break a reply
        log().warning("autopush: skipped (%s: %s)", type(exc).__name__, exc)


def _finish(chan: str, owner: str, folder: Path, answer: str,
            combined: str, started: float) -> str:
    """Everything that happens after ANY model turn, in one place.

    Previously the tool-usage log lived only on the fresh-session path, so resume
    turns — the overwhelmingly common case — recorded nothing.
    """
    _log_tool_usage(chan, combined, started)
    # The sandbox cannot write the catalog maps, so the reply's `Categories:` and
    # `Tier:` lines are saved here, before autopush rebuilds the site with them.
    # The maps key decks `<owner>/<Deck>`; the session only ever wrote `owner`'s.
    try:
        touched = deckplacement.touched_stems(folder, started)
        for note in deckplacement.save(answer, touched, workspace.frontend_dir(), owner):
            log().info("PLACEMENT [%s] %s", chan, note)
    except Exception as exc:                # never let bookkeeping eat the reply
        log().warning("PLACEMENT [%s] skipped (%s: %s)", chan, type(exc).__name__, exc)
    _autopush(chan)
    # Expand [[card:Name]] tags into card images. Model replies ONLY -- the
    # deterministic commands return text a user pastes into a deck importer, and
    # a URL in there is something they have to strip back out.
    try:
        answer = postprocess.expand(answer)
    except Exception as exc:                # never let a picture eat the reply
        log().warning("postprocess: skipped (%s: %s)", type(exc).__name__, exc)
    log().info("REPLY  [%s/model] %d chars %dms", chan, len(answer),
               int((time.time() - started) * 1000))
    log().debug("REPLY-BODY %s", _oneline(answer))
    return answer


def _log_tool_usage(chan: str, combined: str, started: float) -> None:
    """Record which repo tools the session ran this turn.

    Asks toollog for the calls in this turn's window; how it stores them is its
    business. Scraping codex's output is kept only as a fallback for the case
    where the log itself was unavailable — it is lossy, which is why it is no
    longer the primary source.
    """
    seen = [c.command for c in toollog.since(started, chan)]
    if not seen:
        seen = [m.strip() for m in TOOL_LINE.findall(combined or "")]
    for line in seen:
        log().info("TOOL   [%s] %s", chan, line)
    if not seen:
        # Worth flagging: a deck change with no tool call means it skipped
        # validation, which AGENTS.md requires.
        log().info("TOOL   [%s] (none)", chan)


def _turn(folder: Path, message: str, sid: str | None, chan: str) -> harness.Turn:
    """One model turn on the configured harness, in `folder`, resuming `sid` if given.

    The deck folder and the shared card cache are the only places it may write; the
    harness enforces that its own way (see harness.py).
    """
    log().debug("turn: %s in %s (resume=%s)", HARNESS.describe(), folder, sid)
    t0 = time.time()
    turn = HARNESS.run(folder, message, sid, chan=chan, timeout=TIMEOUT, writable=[CACHE_DIR])
    if turn.note:
        log().warning("[%s] %s", chan, turn.note)
    log().debug("%s turn in %dms, %d chars of output", HARNESS.name,
                int((time.time() - t0) * 1000), len(turn.output))
    if turn.answer == "(no output)":
        log().warning("%s produced no final message", HARNESS.name)
    return turn


def _usage(discord: bool = False, *, is_image: bool = False) -> str:
    """The harness's allowance line, or "" when it has none to report."""
    try:
        return HARNESS.usage(discord=discord, is_image=is_image)
    except Exception as exc:                 # a footer must never cost the reply
        log().warning("usage: skipped (%s: %s)", type(exc).__name__, exc)
        return ""


def send(message: str, username: str,
         channel: str | int | None = DEFAULT_CHANNEL, *, discord: bool = False) -> str:
    """Send one message to `channel`'s pinned session and return Codex's reply.

    Each Discord channel (or thread) gets its own long-lived Codex session, so
    separate conversations keep separate context. `username` is the Discord
    username, which picks the folder the session works in and so owns whatever
    it builds. Opens a session if none is pinned. Instructions arrive via
    AGENTS.md, not a turn.
    """
    if not message.strip():
        raise ValueError("empty message")
    username = username.strip()
    if not username:
        raise ValueError("empty Discord username")

    started = time.time()
    chan = _key(channel)
    # Full prompt, newlines escaped so one request stays one greppable line.
    log().info("PROMPT [%s/%s] %s", chan, _oneline(username), _oneline(message))

    if message.strip().lower() in usage.USAGE_COMMANDS:
        return _usage(discord) or usage.HEADER + "\nUnavailable right now."

    def with_usage(reply: str) -> str:
        footer = _usage(discord)
        return reply + ("\n\n" + footer if footer else "")

    # Deterministic commands short-circuit the model: a decklist has to be
    # byte-exact to import cleanly, and listing files needs no inference.
    canned = commands.handle(message, username)
    if canned is not None:
        reply = "\n".join(canned)
        log().info("REPLY  [%s/command] %d msg(s) %d chars %dms",
                   chan, len(canned), len(reply), int((time.time() - started) * 1000))
        log().debug("REPLY-BODY %s", _oneline(reply))
        return reply

    owner = workspace.owner_name(username)
    if owner is None:
        log().info("REFUSED [%s] username %r cannot have a deck folder", chan, username)
        return ("I can't build decks for this Discord username: it has characters a "
                "deck folder cannot use, or it matches one of the site's own folders.")
    folder = workspace.owner_dir(owner)
    conv = f"{chan}-{owner}"            # this user's conversation in this channel

    # One model turn at a time, bot-wide. Taken AFTER the deterministic commands
    # above so /deck-print and /deck-list keep answering while a build runs —
    # they only read files and cost nothing.
    try:
        busy = _claim_bot()
    except Busy:
        log().info("BUSY   [%s] refused; already busy", chan)
        return with_usage(BUSY_REPLY)

    folder.mkdir(parents=True, exist_ok=True)
    # Redeploy AGENTS.md 0444 into the user's folder before the harness reads it.
    changed, status = build_agents.build(folder, owner)
    log().log(logging.INFO if changed else logging.DEBUG, "agents.md: %s", status)

    sid = session_id(conv)
    try:
        if sid:
            log().info("[%s] resuming session %s (%s)", chan, sid, HARNESS.describe())
            turn = _turn(folder, message, sid, chan)
            return with_usage(_finish(chan, owner, folder, turn.answer, turn.output, started))

        # No session pinned yet. Take the lock, then re-check: a concurrent call
        # may have created and pinned one while we waited, in which case resume it
        # instead of opening a second, orphaned session.
        with _creation_lock(conv):
            sid = session_id(conv)
            if sid:
                log().info("[%s] another process pinned %s while waiting; resuming it",
                           chan, sid)
                turn = _turn(folder, message, sid, chan)
                return with_usage(_finish(chan, owner, folder, turn.answer, turn.output, started))

            log().info("[%s] no pinned session; opening a new one (%s)", chan, HARNESS.describe())
            turn = _turn(folder, message, None, chan)
            if turn.session_id:
                _save(conv, {"session_id": turn.session_id, "harness": HARNESS.name,
                             "model": MODEL, "effort": EFFORT})
                log().info("[%s] pinned new session %s", chan, turn.session_id)
            else:
                # Session ran but could not be pinned, so the next call would start
                # a new one and lose this conversation's context. Surface it.
                print("warning: the harness reported no session id; session not pinned",
                      file=sys.stderr)
                log().warning("no session id from %s; next call will start over", HARNESS.name)
        # Same tail as the two resume paths above — a fresh session is where a
        # deck is most likely to be CREATED, so skipping this skipped autopush
        # exactly when it mattered most.
        return with_usage(_finish(chan, owner, folder, turn.answer, turn.output, started))
    except Exception as exc:                       # log the failure, then re-raise
        log().error("FAILED [%s] after %dms: %s: %s", chan,
                    int((time.time() - started) * 1000),
                    exc.__class__.__name__, _oneline(str(exc))[:300])
        raise
    finally:
        _release_bot(busy)


def send_sleever(message: str, username: str, channel: str | int | None = DEFAULT_CHANNEL,
                 *, refs: list[str] | None = None, discord: bool = False) -> str:
    """One sleever request: paint a sleeve on the configured harness, then install,
    attach and publish it (see sleever.py). Shares the builder's bot-wide lock, so
    the two never run at once."""
    if not message.strip():
        raise ValueError("empty message")
    username = username.strip()
    started = time.time()
    chan = _key(channel)
    log().info("PROMPT [%s/%s] sleever: %s (%d ref(s))", chan, _oneline(username),
               _oneline(message), len(refs or []))

    if message.strip().lower() in usage.USAGE_COMMANDS:
        return _usage(discord, is_image=True) or usage.HEADER + "\nUnavailable right now."

    def with_usage(reply: str) -> str:
        footer = _usage(discord, is_image=True)
        return reply + ("\n\n" + footer if footer else "")

    owner = workspace.owner_name(username)
    if owner is None:
        log().info("REFUSED [%s] sleever: username %r cannot have a folder", chan, username)
        return "sleever can't make sleeves for this Discord username."
    if not HARNESS.images:
        log().info("SLEEVER [%s] the harness has no image tool", chan)
        return with_usage(sleever.UNAVAILABLE)

    if HARNESS.name == "agy":
        exhausted, resets_iso, resets_at = usage.is_image_quota_exhausted(getattr(HARNESS, "home", None))
        if exhausted:
            log().info("SLEEVER [%s] gemini-3.1-flash-image quota exhausted; using secondary image gen workaround", chan)
            when_str = f"<t:{int(resets_at)}:R>" if discord else (
                datetime.fromtimestamp(resets_at, timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if resets_at else "later"
            )
            try:
                busy = _claim_bot()
            except Busy:
                log().info("BUSY   [%s] refused; already busy", chan)
                return with_usage(BUSY_REPLY)
            conv = f"{chan}-{owner}-sleever"
            try:
                folder = sleever.prepare(owner)
                notes = sleever.fetch_refs(refs or [], folder / "refs")
                for note in notes:
                    log().info("SLEEVER [%s] %s", chan, note)
                state = _load(conv)
                local_refs = sorted([p for p in (folder / "refs").iterdir() if p.is_file()])
                inferred = sleever.infer_sleeve_name(message)
                if inferred != "Sleeves":
                    sleeve_name = inferred
                    prev_sleeve = state.get("sleeve") if sleever.slugify(inferred) == state.get("sleeve") else None
                elif refs:
                    sleeve_name = "Sleeves"
                    prev_sleeve = None
                else:
                    sleeve_name = state.get("sleeve") or "Sleeves"
                    prev_sleeve = state.get("sleeve")
                sleeve_prompt = sleever.sleeve_prompt_for_generator(message, has_refs=bool(local_refs))
                out_png = folder / "sleeve.png"
                sleever.generate_secondary_image(sleeve_prompt, out_png, refs=local_refs, timeout=TIMEOUT)
                answer = f"Made **{sleeve_name}** sleeves.\nSleeve: {sleeve_name}"
                reply, slug = sleever.publish(folder, answer, owner, prev_sleeve, started, secondary=True)
                if slug:
                    state["sleeve"] = slug
                    log().info("SLEEVER [%s] installed tts/sleeves/%s.jpg via secondary generator", chan, slug)
                    _autopush(chan, sleever.SLEEVES_DIR, "Sleeves")
                if state:
                    _save(conv, state)
                log().info("REPLY  [%s/sleever] %d chars %dms (secondary generator)", chan, len(reply),
                           int((time.time() - started) * 1000))
                return with_usage(reply)
            except Exception as exc:
                log().error("FAILED [%s] sleever secondary generator after %dms: %s: %s", chan,
                            int((time.time() - started) * 1000), exc.__class__.__name__, _oneline(str(exc))[:300])
                msg = (f"sleever can't make pictures right now: quota on gemini-3.1-flash-image has been exhausted "
                       f"(resets {when_str}). Secondary image generation also failed: {exc}")
                return with_usage(msg)
            finally:
                _release_bot(busy)
    try:
        busy = _claim_bot()
    except Busy:
        log().info("BUSY   [%s] refused; already busy", chan)
        return with_usage(BUSY_REPLY)
    conv = f"{chan}-{owner}-sleever"
    try:
        folder = sleever.prepare(owner)
        notes = sleever.fetch_refs(refs or [], folder / "refs")
        for note in notes:
            log().info("SLEEVER [%s] %s", chan, note)
        state = _load(conv)
        sid = session_id(conv)
        prompt = message
        if notes:
            prompt += "\n\n(Note from the bot: " + "; ".join(notes) + ".)"
        turn = HARNESS.run(folder, prompt, sid, chan=chan, timeout=TIMEOUT, writable=[])
        if turn.session_id and turn.session_id != sid:
            state = {**state, "session_id": turn.session_id, "harness": HARNESS.name,
                     "model": MODEL, "effort": EFFORT}
            log().info("[%s] pinned new sleever session %s", chan, turn.session_id)
        reply, slug = sleever.publish(folder, turn.answer, owner, state.get("sleeve"), started)
        if slug:
            state["sleeve"] = slug
            log().info("SLEEVER [%s] installed tts/sleeves/%s.jpg", chan, slug)
            _autopush(chan, sleever.SLEEVES_DIR, "Sleeves")
        else:
            log().warning("SLEEVER [%s] no picture this turn", chan)
            if HARNESS.name == "agy":
                exhausted, resets_iso, resets_at = usage.is_image_quota_exhausted(getattr(HARNESS, "home", None))
                if exhausted:
                    when_str = f"<t:{int(resets_at)}:R>" if discord else (
                        datetime.fromtimestamp(resets_at, timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if resets_at else "later"
                    )
                    log().info("SLEEVER [%s] quota exhausted during turn; falling back to secondary generator", chan)
                    try:
                        local_refs = sorted([p for p in (folder / "refs").iterdir() if p.is_file()])
                        inferred = sleever.infer_sleeve_name(message)
                        sleeve_name = sleever.sleeve_name(turn.answer)
                        if not sleeve_name:
                            if inferred != "Sleeves":
                                sleeve_name = inferred
                            elif refs:
                                sleeve_name = "Sleeves"
                            else:
                                sleeve_name = state.get("sleeve") or "Sleeves"
                        prev_sleeve = state.get("sleeve") if (not refs and sleever.slugify(sleeve_name) == state.get("sleeve")) else None
                        sleeve_prompt = sleever.sleeve_prompt_for_generator(message, has_refs=bool(local_refs))
                        out_png = folder / "sleeve.png"
                        sleever.generate_secondary_image(sleeve_prompt, out_png, refs=local_refs, timeout=TIMEOUT)
                        answer = f"Made **{sleeve_name}** sleeves.\nSleeve: {sleeve_name}"
                        reply, slug = sleever.publish(folder, answer, owner, prev_sleeve, started, secondary=True)
                        if slug:
                            state["sleeve"] = slug
                            log().info("SLEEVER [%s] installed tts/sleeves/%s.jpg via secondary generator", chan, slug)
                            _autopush(chan, sleever.SLEEVES_DIR, "Sleeves")
                    except Exception as exc:
                        log().error("SLEEVER [%s] secondary generator also failed: %s", chan, exc)
                        reply = (f"sleever can't make pictures right now: quota on gemini-3.1-flash-image has been exhausted "
                                 f"(resets {when_str}). Secondary image generation also failed: {exc}")
        if state:
            _save(conv, state)
        log().info("REPLY  [%s/sleever] %d chars %dms", chan, len(reply),
                   int((time.time() - started) * 1000))
        log().debug("REPLY-BODY %s", _oneline(reply))
        return with_usage(reply)
    except Exception as exc:
        log().error("FAILED [%s] sleever after %dms: %s: %s", chan,
                    int((time.time() - started) * 1000),
                    exc.__class__.__name__, _oneline(str(exc))[:300])
        raise
    finally:
        _release_bot(busy)


# ---------- cli ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Talk to the pinned deck-builder session.")
    ap.add_argument("message", nargs="?", help="message to send")
    ap.add_argument("-c", "--channel", default=DEFAULT_CHANNEL,
                    help=f"channel/thread id (default: {DEFAULT_CHANNEL})")
    ap.add_argument("-u", "--user",
                    help="Discord username sending the request (required with a message)")
    ap.add_argument("--reset", action="store_true",
                    help="drop this channel's pinned session")
    ap.add_argument("--reset-all", action="store_true",
                    help="drop every channel's pinned session")
    ap.add_argument("--status", action="store_true", help="show all pinned sessions")
    ap.add_argument("--usage", action="store_true", help="show the harness's remaining allowance without a model turn")
    ap.add_argument("--discord", action="store_true", help="format usage reset times for Discord")
    ap.add_argument("--sleever", action="store_true",
                    help="make sleeves (card backs) instead of talking to the deck builder")
    ap.add_argument("--ref", action="append", default=[], metavar="URL",
                    help="sleever: a reference picture to download (repeatable)")
    ap.add_argument("--tail", type=int, nargs="?", const=20, metavar="N",
                    help="print the last N log lines (default 20)")
    args = ap.parse_args()

    if args.usage:
        print(_usage(args.discord) or usage.HEADER + "\nUnavailable right now.")
        return 0

    if args.reset_all:
        n = reset_all()
        log().info("cleared all sessions (%d)", n)
        print(f"cleared {n} session(s)")
        if not args.message:
            return 0

    if args.reset:
        old = reset(args.channel)
        log().info("[%s] session cleared (was %s)", _key(args.channel), old or "none")
        print(f"session cleared for channel {_key(args.channel)}")
        if not args.message:
            return 0

    if args.status:
        print(f"decks     : {WORKSPACE}/<user>/  (each session writes only its own)")
        print(f"cache     : {CACHE_DIR}  (writable by the session)")
        print(f"sessions  : {SESSIONS}")
        print(f"harness   : {HARNESS.describe()}")
        rows = channels()
        if not rows:
            print("\n(no pinned sessions yet — the next send starts one)")
            return 0
        print(f"\n{'channel':<24} {'session':<38} harness / model / effort")
        for name, st in rows:
            print(f"{name:<24} {st.get('session_id','?'):<38} "
                  f"{st.get('harness','codex')} / {st.get('model','?')} / {st.get('effort','?')}")
        return 0

    if args.tail is not None:
        files = sorted(LOG_DIR.glob("*.log"))
        if not files:
            print(f"no logs yet in {LOG_DIR}")
            return 0
        lines = [l for f in files for l in f.read_text().splitlines() if l.strip()]
        print("\n".join(lines[-args.tail:]))
        return 0

    if not args.message:
        ap.error("give a message, or use --usage / --status / --reset / --reset-all / --tail")
    if not args.user:
        ap.error("--user is required when sending a message")

    try:
        if args.sleever:
            print(send_sleever(args.message, args.user, channel=args.channel,
                               refs=args.ref, discord=args.discord))
        else:
            print(send(args.message, args.user, channel=args.channel, discord=args.discord))
    except harness.QuotaExhausted as exc:
        # One neutral line the Discord app recognises (deckBuilder.ts quotaError): no
        # model or harness name, whichever ran out. The details go to the owner's log.
        log().warning("QUOTA  %s %s: %s", HARNESS.name, MODEL, str(exc)[-500:])
        when = usage.exhausted_reset(_usage(args.discord))
        print("deck builder usage limit reached" + (f"; try again at {when}." if when else "."),
              file=sys.stderr)
        return 1
    except (harness.HarnessError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        footer = _usage(args.discord)
        if footer:
            print(footer, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
