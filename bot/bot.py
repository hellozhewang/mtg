#!/usr/bin/env python3
"""Persistent Codex session for the Discord bot to talk to.

    from bot import send, reset, session_id
    reply = send("Which Game Changers is Zur-Voltron running?")

Or from a shell, for testing:

    ./bot.py "swap Moat out of Zur-Voltron for something legal"
    ./bot.py --reset            # start a fresh session
    ./bot.py --status

One long-lived Codex session is pinned PER CHANNEL. State lives in
`.sessions/<channel>.json`; the first call for a channel records its session UUID
and every later call uses `codex exec resume <uuid>`, so each Discord channel or
thread keeps its own conversation context. Pass the channel id:

    reply = send("...", channel=message.channel.id)

Omitting it uses the "cli" channel, which is what the command line uses.

Operating instructions: edit the AGENTS_MD string in `scripts/build_agents.py`,
which deploys it to `public/AGENTS.md` as mode 0444 before every send, because
codex auto-injects AGENTS.md only from its working directory — under an
`# AGENTS.md instructions for <dir>` / `<INSTRUCTIONS>` header, on every invocation
including resumes. So the rules cost no turn, apply to fresh sessions, and take
effect mid-conversation when edited. The source lives outside `-C public` so the
session cannot alter it.

After each model turn, decklist changes under `public/` are committed and pushed
automatically — see `_autopush`. Detection is scoped to that directory only; when
something there did change, `docs/` (the published catalog) is regenerated from
it and staged in the same commit, so the site never lags the decks.

Codex has no flag to name a session, so the UUID is scraped from the startup
banner (`session id: <uuid>`) and persisted here. Note `codex exec resume` filters
by cwd, so every invocation must run from the same directory — hence the fixed
`-C WORKSPACE`.

Sandbox: `-s workspace-write -C <public/>` confines writes to the deck workspace.
`../scripts`, `../private`, `../logs`, and the docs are readable and runnable but
not writable. The cache lives at `<repo>/.cache`, outside the workspace, so it is
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
import shutil
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


HERE = Path(__file__).resolve().parent               # bot/ — OUTSIDE the workspace
REPO = HERE.parent

# The AGENTS.md generator lives in scripts/ (outside the writable root) so the
# session cannot edit the thing that writes its own instructions.
sys.path.insert(0, str(REPO / "scripts"))
import build_agents
import workspace

import commands

# Ask workspace.py; do NOT derive these from __file__. bot/ sits outside the tree
# it drives, so `HERE.parent` is the repo root — using it as the workspace would
# silently hand the Codex session write access to scripts/, private/ and logs/.
WORKSPACE = workspace.deck_root()                    # public/ — the writable root
CACHE_DIR = workspace.cache_dir()                    # outside WORKSPACE; needs --add-dir
SESSIONS = HERE / ".sessions"                        # one JSON per Discord channel
LEGACY_STATE = HERE / ".session.json"                # pre-per-channel; migrated on load
LOG_DIR = REPO / "logs"                              # one text log per UTC day

# Channel key used when nothing is supplied — CLI testing, mostly. Discord passes
# the channel or thread id so each conversation gets its own Codex session.
DEFAULT_CHANNEL = "cli"

MODEL = os.environ.get("MTG_BOT_MODEL", "gpt-5.6-sol")
# Discord users are waiting on this, so default below the ceiling. `ultra`/`max`
# can push a single turn into minutes.
EFFORT = os.environ.get("MTG_BOT_EFFORT", "high")
TIMEOUT = int(os.environ.get("MTG_BOT_TIMEOUT", "600"))

# ---------- exec lockdown ----------
#
# AGENTS.md tells the session never to invoke another LLM/agent CLI. That is
# advisory; this is the enforcement. `claude` is installed on this machine, on
# the PATH a naive subprocess would inherit whole, and runs as the same OS user
# with the same working ~/.claude credentials — so "don't" is not sufficient.
#
# This is a curated PATH, and it is the WEAK form of this control: it blocks
# bare command names (`claude`) but NOT absolute paths (`/opt/homebrew/bin/claude`).
#
# The sibling discord-bot project does this properly in src/infra/execSandbox.ts,
# wrapping codex in a macOS Seatbelt profile that denies `process-exec` at the
# kernel level, which absolute paths cannot bypass. That was tried here and does
# NOT work for this workspace. Measured, not assumed:
#
#   codex applies its OWN Seatbelt profile per shell tool-call, and macOS denies
#   a nested sandbox_apply. Under an outer sandbox-exec wrapper, codex starts and
#   answers fine, but every tool call fails with:
#       "sandbox-exec: sandbox_apply: Operation not permitted"
#   Confirmed on BOTH -s read-only and -s workspace-write, so it is not a
#   workspace-write quirk.
#
# That is exactly why it works over there and not here: that project locks down
# its CHAT backend, which must never run a shell command at all. This workspace
# is the privileged agent — running python3/grep/diff IS its job — so wrapping it
# in Seatbelt would break the tools rather than protect them.
#
# codex does expose a native `execpolicy` .rules mechanism (see `--ignore-rules`)
# which would not conflict, being inside codex rather than wrapped around it. It
# is undocumented in --help and its parser is unstable, so it is not used here.
# That is the thing to revisit if this ever needs to be a real boundary.

CODEX_BIN = shutil.which("codex")
if CODEX_BIN is None:
    raise RuntimeError("codex not found on PATH")
_NODE_BIN = shutil.which("node")
if _NODE_BIN is None:
    raise RuntimeError("node not found on PATH (required by codex)")

# Directories whose contents the session may exec. Standard system paths only:
# python3, git, bash/zsh, cat, grep, sed, awk, diff, curl all live here. What is
# deliberately absent is the homebrew prefix — which is where `claude`, the
# `codex` npm shim, `gh` and `npx` are installed.
EXEC_ALLOWED_DIRS = ("/usr/bin", "/bin", "/usr/sbin", "/sbin", "/usr/libexec")


def _native_codex(shim: str) -> str | None:
    """Find the compiled binary the npm `codex` shim spawns internally.

    Worth the trouble because the shim is a `#!/usr/bin/env node` script that
    execs the native binary as a child — two extra execs (node, then the binary)
    that the seatbelt allowlist would otherwise have to name, one of which lives
    in the homebrew prefix we are trying not to open up. Going straight to the
    native binary keeps the allowlist to system directories plus one path.

    Reads the installed package layout rather than hardcoding a platform triple,
    so a codex upgrade keeping the same structure needs no change here.
    """
    try:
        pkg_root = Path(os.path.realpath(shim)).parent.parent   # .../@openai/codex
        scope = pkg_root / "node_modules" / "@openai"
        for entry in scope.iterdir():
            if not entry.name.startswith("codex-"):
                continue
            vendor = entry / "vendor"
            if not vendor.is_dir():
                continue
            for triple in vendor.iterdir():
                candidate = triple / "bin" / "codex"
                if candidate.is_file():
                    return str(candidate)
    except OSError:
        pass                                    # caller logs and degrades
    return None


def _build_sandbox() -> tuple[str, str]:
    """Returns (exec_path, PATH) for launching codex.

    NOTE: no sandbox-exec wrapper, deliberately. See the module doc above — a
    Seatbelt wrapper is incompatible with a codex session that runs commands.
    """
    native = _native_codex(CODEX_BIN)
    if native:
        # Exec the compiled binary, not the npm `#!/usr/bin/env node` shim. That
        # removes node from the picture entirely, which matters here: node lives
        # in the homebrew prefix alongside `claude`, so the shim would force
        # either that whole directory onto PATH or a symlink workaround.
        return native, ":".join(EXEC_ALLOWED_DIRS)

    # Shim fallback: needs node, which is NOT in EXEC_ALLOWED_DIRS. Expose it
    # via a directory containing only that one symlink rather than adding the
    # homebrew prefix, which would also re-expose `claude`.
    sandbox_bin = HERE / ".sandbox-bin"
    sandbox_bin.mkdir(exist_ok=True)
    link = sandbox_bin / "node"
    if not link.is_symlink() or os.path.realpath(link) != os.path.realpath(_NODE_BIN):
        link.unlink(missing_ok=True)
        link.symlink_to(_NODE_BIN)
    print("WARNING [exec-sandbox] could not resolve the native codex binary; "
          "falling back to the npm shim and exposing node.", file=sys.stderr)
    return CODEX_BIN, ":".join((str(sandbox_bin),) + EXEC_ALLOWED_DIRS)


SANDBOX_EXEC_PATH, SANDBOX_PATH = _build_sandbox()

SESSION_RE = re.compile(r"session id:\s*([0-9a-fA-F-]{32,40})")


class CodexError(RuntimeError):
    pass


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
    return _load(channel).get("session_id")


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


# Global mutex, held only briefly. Lives in bot/ and NOT in .cache/cards.db,
# deliberately: the cache is handed to the sandbox via --add-dir, so a lock kept
# there would be one the sandboxed session could take, hold or corrupt.
LOCK_DB = HERE / ".locks.db"
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
    """Forget one channel's session. Returns the id that was dropped."""
    old = session_id(channel)
    _state_path(channel).unlink(missing_ok=True)
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


# ---------- codex invocation ----------

def _base_args() -> list[str]:
    return [
        SANDBOX_EXEC_PATH, "exec",     # absolute; see the exec lockdown block
        "--skip-git-repo-check",       # this tree is not a git repo
        "-s", "workspace-write",       # writes confined to -C, plus --add-dir
        "-C", str(WORKSPACE),
        "--add-dir", str(CACHE_DIR),   # let the tools write the Scryfall cache
        "-m", MODEL,
        "-c", f'model_reasoning_effort="{EFFORT}"',
        "-c", "tools.web_search=true",  # NOT --search; that flag is top-level only
        # workspace-write blocks network by default, which breaks find_cards.py
        # (Scryfall) with a DNS error rather than a permission error. This grants
        # egress; it is what makes live card search work at all.
        "-c", "sandbox_workspace_write.network_access=true",
    ]


# Emitted on stderr by scripts/toollog.py. The sandbox blocks the tools from
# writing logs/ themselves (deliberately — that is what stops the session
# rewriting its own history), so they announce on stderr, codex captures it, and
# we re-log it here from OUTSIDE the sandbox where it cannot be forged.
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

# Generous, because the first build after a NEW deck downloads a card image for
# each card it introduced. Steady state is a fraction of a second — every image
# is already in the SQLite cache — so this ceiling is for the cold case only.
SITE_TIMEOUT = int(os.environ.get("MTG_SITE_TIMEOUT", "180"))


def _git(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, timeout=timeout)


def _build_site() -> str | None:
    """Regenerate the published catalog. Returns its path relative to REPO, for
    staging, or None if the build failed.

    A subprocess rather than an import, for two reasons: a timeout is available
    (a new deck can need a few dozen card images, and a stalled CDN must not hold
    a Discord reply open), and a crash in the generator cannot take down the bot.

    Runs OUTSIDE the codex sandbox, in this process's own environment — which is
    the point. `docs/` sits outside the workspace precisely so the model cannot
    write the published site directly; only a completed bot turn can.
    """
    site = workspace.site_dir()
    try:
        r = subprocess.run([sys.executable, str(REPO / "scripts" / "build_site.py"),
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


def _autopush(chan: str) -> None:
    """Commit and push decklist changes. Never raises — a git failure must not
    lose the user's reply, which has already been produced by this point."""
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
            rel = str(WORKSPACE.relative_to(REPO))
            if not _git("status", "--porcelain", "--", rel).stdout.strip():
                return                                  # no deck changed
            site = _build_site()
            paths = [rel, *([site] if site else [])]     # public/ and docs/, nothing else
            add = _git("add", "--", *paths)
            if add.returncode:
                log().warning("autopush: git add failed: %s", add.stderr.strip()[:200])
                return
            msg = f"Deck update via Discord ({chan})"
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
            log().info("autopush: committed deck changes (%s)", chan)

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


def _finish(chan: str, answer: str, combined: str, started: float) -> str:
    """Everything that happens after ANY model turn, in one place.

    Previously the tool-usage log lived only on the fresh-session path, so resume
    turns — the overwhelmingly common case — recorded nothing.
    """
    _log_tool_usage(chan, combined)
    _autopush(chan)
    log().info("REPLY  [%s/model] %d chars %dms", chan, len(answer),
               int((time.time() - started) * 1000))
    log().debug("REPLY-BODY %s", _oneline(answer))
    return answer


def _log_tool_usage(chan: str, combined: str) -> None:
    """Record which repo tools the session actually ran this turn."""
    seen = TOOL_LINE.findall(combined or "")
    for line in seen:
        log().info("TOOL   [%s] %s", chan, line.strip())
    if not seen:
        # Worth flagging: a deck change with no tool call means it skipped
        # validation, which AGENTS.md requires.
        log().info("TOOL   [%s] (none)", chan)


def _run(args: list[str], out_file: Path) -> tuple[str, str]:
    """Run codex, returning (final_message, combined_output)."""
    log().debug("exec: %s", " ".join(args))
    t0 = time.time()
    # SANDBOX_PATH restricts what the codex PROCESS sees as its own PATH, hence
    # what any shell tool-call it makes internally can find — args[0] is already
    # an absolute path (CODEX_BIN), so this does not affect launching codex itself.
    env = {**os.environ, "PATH": SANDBOX_PATH}
    proc = subprocess.run(
        args, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=TIMEOUT, env=env,
    )
    ms = int((time.time() - t0) * 1000)
    combined = (proc.stdout or "") + (proc.stderr or "")
    log().debug("codex rc=%s in %dms, %d chars of output",
                proc.returncode, ms, len(combined))
    if proc.returncode != 0:
        log().error("codex rc=%s; stderr tail: %s",
                    proc.returncode, (proc.stderr or "")[-400:].replace("\n", " "))
        raise CodexError(f"codex exited {proc.returncode}\n{combined[-2000:]}")
    answer = out_file.read_text().strip() if out_file.exists() else ""
    if not answer:
        log().warning("codex produced no final message (-o file empty or missing)")
    return answer or "(no output)", combined


def send(message: str, channel: str | int | None = DEFAULT_CHANNEL) -> str:
    """Send one message to `channel`'s pinned session and return Codex's reply.

    Each Discord channel (or thread) gets its own long-lived Codex session, so
    separate conversations keep separate context. Pass the channel/thread id.
    Opens a session if none is pinned. Instructions arrive via AGENTS.md, not a turn.
    """
    if not message.strip():
        raise ValueError("empty message")

    started = time.time()
    chan = _key(channel)
    # Full prompt, newlines escaped so one request stays one greppable line.
    log().info("PROMPT [%s] %s", chan, _oneline(message))

    # Deterministic commands short-circuit the model: a decklist has to be
    # byte-exact to import cleanly, and listing files needs no inference.
    canned = commands.handle(message)
    if canned is not None:
        reply = "\n".join(canned)
        log().info("REPLY  [%s/command] %d msg(s) %d chars %dms",
                   chan, len(canned), len(reply), int((time.time() - started) * 1000))
        log().debug("REPLY-BODY %s", _oneline(reply))
        return reply

    changed, status = build_agents.build()  # redeploy AGENTS.md 0444 before codex reads
    log().log(logging.INFO if changed else logging.DEBUG, "agents.md: %s", status)

    # pid in the name: two calls in the same millisecond would otherwise collide
    out_file = HERE / f".reply-{int(time.time() * 1000)}-{os.getpid()}.txt"
    sid = session_id(channel)
    try:
        if sid:
            log().info("[%s] resuming session %s (model=%s effort=%s)",
                       chan, sid, MODEL, EFFORT)
            args = _base_args() + ["-o", str(out_file), "resume", sid, message]
            answer, combined = _run(args, out_file)
            return _finish(chan, answer, combined, started)

        # No session pinned yet. Take the lock, then re-check: a concurrent call
        # may have created and pinned one while we waited, in which case resume it
        # instead of opening a second, orphaned session.
        with _creation_lock(channel):
            sid = session_id(channel)
            if sid:
                log().info("[%s] another process pinned %s while waiting; resuming it",
                           chan, sid)
                args = _base_args() + ["-o", str(out_file), "resume", sid, message]
                answer, combined = _run(args, out_file)
                return _finish(chan, answer, combined, started)

            log().info("[%s] no pinned session; opening a new one (model=%s effort=%s)",
                       chan, MODEL, EFFORT)
            args = _base_args() + ["-o", str(out_file), message]
            answer, combined = _run(args, out_file)

            found = SESSION_RE.search(combined)
            if found:
                _save(channel, {"session_id": found.group(1),
                                "model": MODEL, "effort": EFFORT})
                log().info("[%s] pinned new session %s", chan, found.group(1))
            else:
                # Session ran but could not be pinned, so the next call would start
                # a new one and lose this conversation's context. Surface it.
                print("warning: could not parse session id from codex output; "
                      "session not pinned", file=sys.stderr)
                log().warning("could not parse session id; next call will start over")
        # Same tail as the two resume paths above — a fresh session is where a
        # deck is most likely to be CREATED, so skipping this skipped autopush
        # exactly when it mattered most.
        return _finish(chan, answer, combined, started)
    except Exception as exc:                       # log the failure, then re-raise
        log().error("FAILED [%s] after %dms: %s: %s", chan,
                    int((time.time() - started) * 1000),
                    exc.__class__.__name__, _oneline(str(exc))[:300])
        raise
    finally:
        out_file.unlink(missing_ok=True)


# ---------- cli ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Talk to the pinned Codex deck session.")
    ap.add_argument("message", nargs="?", help="message to send")
    ap.add_argument("-c", "--channel", default=DEFAULT_CHANNEL,
                    help=f"channel/thread id (default: {DEFAULT_CHANNEL})")
    ap.add_argument("--reset", action="store_true",
                    help="drop this channel's pinned session")
    ap.add_argument("--reset-all", action="store_true",
                    help="drop every channel's pinned session")
    ap.add_argument("--status", action="store_true", help="show all pinned sessions")
    ap.add_argument("--tail", type=int, nargs="?", const=20, metavar="N",
                    help="print the last N log lines (default 20)")
    args = ap.parse_args()

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
        print(f"workspace : {WORKSPACE}")
        print(f"cache     : {CACHE_DIR}  (granted via --add-dir)")
        print(f"sessions  : {SESSIONS}")
        print(f"defaults  : model={MODEL} effort={EFFORT}")
        rows = channels()
        if not rows:
            print("\n(no pinned sessions yet — the next send starts one)")
            return 0
        print(f"\n{'channel':<24} {'session':<38} model / effort")
        for name, st in rows:
            print(f"{name:<24} {st.get('session_id','?'):<38} "
                  f"{st.get('model','?')} / {st.get('effort','?')}")
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
        ap.error("give a message, or use --status / --reset / --reset-all / --tail")

    try:
        print(send(args.message, channel=args.channel))
    except (CodexError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
