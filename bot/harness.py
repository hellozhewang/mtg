"""The agent harness the deck builder runs on, behind one small interface.

A harness is the CLI that hosts the model: it reads AGENTS.md in the deck folder, runs
tools, keeps the conversation, and returns a reply. The bot needs four things from it:

    turn = harness.run(folder, message, session_id, chan=..., timeout=..., writable=[...])
    turn.answer       the reply text
    turn.session_id   the conversation to resume next time (the harness stores it)
    turn.output       everything it printed, for the log

and `harness.usage(discord=...)`, an allowance line for the reply footer, or "" when
the harness has none to report.

Pick one with MTG_BOT_HARNESS (default `agy`) and its model with MTG_BOT_MODEL (default:
the harness's own). Changing either starts every Discord conversation afresh once: a
session id belongs to the harness and model that made it (see bot.session_id).

    codex  OpenAI Codex CLI. Confines itself (`-s workspace-write -C <folder>`).
    agy    Google Antigravity CLI: Gemini, Claude, GPT-OSS. Runs in turbo
           (`--dangerously-skip-permissions`: no prompts, which a headless turn cannot
           answer anyway) inside an OS sandbox (bot/sandbox.py) that the kernel enforces.
           Its own home folder (bot/.harness/agy/) keeps the bot's settings, sign-in and
           conversations apart from the owner's own Antigravity setup.

Adding a harness: subclass Harness, implement `run` (and `usage` if it has one), and
register it in HARNESSES.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import sandbox

HERE = Path(__file__).resolve().parent

# Directories whose programs the builder's shell may find by bare name. Standard
# system paths only: python3, git, bash/zsh, cat, grep, sed, awk, diff and curl live
# here. Deliberately absent: the homebrew prefix, where `claude`, the `codex` npm shim,
# `gh` and `npx` are installed. A speed bump for Codex; for sandboxed harnesses the
# profile's exec denials are the wall.
EXEC_ALLOWED_DIRS = ("/usr/bin", "/bin", "/usr/sbin", "/sbin", "/usr/libexec")


class HarnessError(RuntimeError):
    """The harness failed to produce a turn."""


class QuotaExhausted(HarnessError):
    """The model's allowance ran out. Reported to players without naming the model."""


# How each harness words running out of allowance. Matched exactly enough not to fire
# on a user's prompt that merely mentions quotas (the output can carry the transcript).
QUOTA_RE = re.compile(r"hit your usage limit|insufficient_quota|exhausted your quota|"
                      r"RESOURCE_EXHAUSTED|quota (?:has been )?exceeded", re.I)


@dataclass
class Turn:
    answer: str
    session_id: str | None
    output: str


class Harness:
    name = "base"
    default_model = ""
    default_effort: str | None = None
    label = ""

    def __init__(self, model: str | None = None, effort: str | None = None):
        self.model = model or self.default_model
        self.effort = effort if effort is not None else self.default_effort

    def run(self, folder: Path, message: str, session_id: str | None, *,
            chan: str, timeout: int, writable: list[Path]) -> Turn:
        raise NotImplementedError

    def usage(self, *, discord: bool = False) -> str:
        return ""

    def describe(self) -> str:
        effort = f" effort={self.effort}" if self.effort else ""
        return f"{self.name} model={self.model}{effort}"

    @staticmethod
    def _env(chan: str, **extra: str) -> dict:
        # MTG_TOOL_CHANNEL tags each tool record so the drain after this turn takes
        # only its own lines (scripts/toollog.py).
        return {**os.environ, "PATH": ":".join(EXEC_ALLOWED_DIRS), "MTG_TOOL_CHANNEL": chan, **extra}


# ---------- Codex ----------

def _native_codex(shim: str) -> str | None:
    """The compiled binary the npm `codex` shim spawns, so node never needs to be on
    the builder's PATH (node lives in the homebrew prefix next to `claude`)."""
    try:
        pkg_root = Path(os.path.realpath(shim)).parent.parent   # .../@openai/codex
        for entry in (pkg_root / "node_modules" / "@openai").iterdir():
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
        pass
    return None


class CodexHarness(Harness):
    """`codex exec`, confined by its own sandbox. Not wrapped in ours: Codex applies a
    Seatbelt profile per tool call, and macOS refuses a nested sandbox_apply."""
    name = "codex"
    default_model = "gpt-6-astra"
    default_effort = "high"
    label = "Codex"
    SESSION_RE = re.compile(r"session id:\s*([0-9a-fA-F-]{32,40})")

    def __init__(self, model: str | None = None, effort: str | None = None):
        super().__init__(model, effort)
        shim = shutil.which("codex")
        if shim is None:
            raise HarnessError("codex not found on PATH")
        native = _native_codex(shim)
        if native:
            self.exe, self.path = native, ":".join(EXEC_ALLOWED_DIRS)
        else:
            node = shutil.which("node")
            if node is None:
                raise HarnessError("node not found on PATH (required by the codex shim)")
            # Expose node alone through a one-link directory, not the homebrew prefix.
            bin_dir = HERE / ".sandbox-bin"
            bin_dir.mkdir(exist_ok=True)
            link = bin_dir / "node"
            if not link.is_symlink() or os.path.realpath(link) != os.path.realpath(node):
                link.unlink(missing_ok=True)
                link.symlink_to(node)
            self.exe, self.path = shim, ":".join((str(bin_dir),) + EXEC_ALLOWED_DIRS)

    def args(self, folder: Path, message: str, session_id: str | None,
             out_file: Path, writable: list[Path]) -> list[str]:
        args = [self.exe, "exec", "--skip-git-repo-check",
                "-s", "workspace-write", "-C", str(folder)]
        for path in writable:
            args += ["--add-dir", str(path)]
        args += ["-m", self.model,
                 "-c", f'model_reasoning_effort="{self.effort}"',
                 "-c", "tools.web_search=true",
                 # workspace-write blocks the network, which breaks find_cards.py.
                 "-c", "sandbox_workspace_write.network_access=true",
                 "-o", str(out_file)]
        # `--` stops a message that starts with a dash being read as a flag.
        return args + (["resume", session_id, "--", message] if session_id else ["--", message])

    def run(self, folder, message, session_id, *, chan, timeout, writable):
        out_file = HERE / f".reply-{int(time.time() * 1000)}-{os.getpid()}.txt"
        try:
            proc = subprocess.run(self.args(folder, message, session_id, out_file, writable),
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  timeout=timeout, env={**self._env(chan), "PATH": self.path})
            output = (proc.stdout or "") + (proc.stderr or "")
            if proc.returncode != 0:
                if QUOTA_RE.search(output[-4000:]):
                    raise QuotaExhausted(output[-2000:])
                raise HarnessError(f"codex exited {proc.returncode}\n{output[-2000:]}")
            answer = out_file.read_text().strip() if out_file.exists() else ""
        finally:
            out_file.unlink(missing_ok=True)
        found = self.SESSION_RE.search(output)
        return Turn(answer or "(no output)", session_id or (found.group(1) if found else None), output)

    def usage(self, *, discord: bool = False) -> str:
        import usage                                    # Codex's allowance RPC
        return usage.report(self.exe, self.model, discord=discord)


# ---------- Antigravity (agy) ----------

class AgyHarness(Harness):
    """`agy --print`, headless, in turbo, inside bot/sandbox.py's profile."""
    name = "agy"
    default_model = "gemini-3.8-flash-high"
    default_effort = None              # the model id carries the thinking level
    label = "Antigravity"

    # The owner's own Antigravity sign-in, copied into the bot's home when newer.
    SIGN_IN = (Path(".gemini") / "antigravity-cli" / "antigravity-oauth-token",
               Path(".gemini") / "jetski-standalone-oauth-token")

    def __init__(self, model: str | None = None, effort: str | None = None,
                 home: Path | None = None, exe: str | None = None):
        super().__init__(model, effort)
        self.exe = exe or os.environ.get("MTG_AGY_BIN") or shutil.which("agy") \
            or str(Path.home() / ".gemini" / "bin" / "agy")
        if not Path(self.exe).is_file():
            raise HarnessError(f"agy not found ({self.exe})")
        self.home = home or HERE / ".harness" / "agy"

    def prepare(self, workspace_root: Path) -> None:
        """The bot's own Antigravity home: sign-in, trusted workspace, turbo preset."""
        cli = self.home / ".gemini" / "antigravity-cli"
        config = self.home / ".gemini" / "config"
        cli.mkdir(parents=True, exist_ok=True)
        config.mkdir(parents=True, exist_ok=True)
        for rel in self.SIGN_IN:
            src, dst = Path.home() / rel, self.home / rel
            if src.is_file() and (not dst.is_file() or src.stat().st_mtime > dst.stat().st_mtime):
                shutil.copy2(src, dst)
                dst.chmod(0o600)
        settings = cli / "settings.json"
        data = json.loads(settings.read_text()) if settings.is_file() else {}
        data["trustedWorkspaces"] = [str(workspace_root)]
        settings.write_text(json.dumps(data, indent=1) + "\n")
        cfg = config / "config.json"
        data = json.loads(cfg.read_text()) if cfg.is_file() else {}
        data.setdefault("userSettings", {})["permissionPreset"] = "AGENT_PERMISSION_PRESET_TURBO"
        cfg.write_text(json.dumps(data, indent=1) + "\n")

    def args(self, message: str, session_id: str | None, timeout: int) -> list[str]:
        # --model on every run: only the owner picks the model (MTG_BOT_MODEL), so
        # nothing saved in agy's settings can change it. --disable-slash-commands: a
        # Discord message starting with "/" ("/model …", "/usage") is the user's
        # words for the builder, never an agy command.
        args = [self.exe, "--model", self.model, "--dangerously-skip-permissions",
                "--disable-slash-commands",
                "--output-format", "json", "--print-timeout", f"{timeout}s"]
        if self.effort:
            args += ["--effort", self.effort]
        if session_id:
            args += ["--conversation", session_id]
        # One argument: `-p <msg>` would read a message starting with "-" as a flag.
        return args + [f"--print={message}"]

    def profile(self, folder: Path, writable: list[Path]) -> str:
        return sandbox.profile([folder, *writable, self.home])

    @staticmethod
    def parse(stdout: str) -> dict:
        """The JSON result: the last stdout line that is one."""
        for line in reversed((stdout or "").splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict) and "conversation_id" in data:
                    return data
        raise HarnessError("agy printed no JSON result")

    def run(self, folder, message, session_id, *, chan, timeout, writable):
        self.prepare(folder.parent)
        argv = sandbox.wrap(self.args(message, session_id, timeout), self.profile(folder, writable))
        proc = subprocess.run(argv, cwd=folder, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=timeout + 30,
                              env=self._env(chan, HOME=str(self.home)))
        output = (proc.stdout or "") + (proc.stderr or "")
        if QUOTA_RE.search(proc.stderr or "") or (proc.returncode != 0 and QUOTA_RE.search(output[-4000:])):
            raise QuotaExhausted(output[-2000:])
        if proc.returncode != 0:
            raise HarnessError(f"agy exited {proc.returncode}\n{output[-2000:]}")
        data = self.parse(proc.stdout)
        if data.get("status") != "SUCCESS":
            if QUOTA_RE.search(json.dumps(data)):
                raise QuotaExhausted(output[-2000:])
            raise HarnessError(f"agy status {data.get('status')}\n{output[-2000:]}")
        answer = (data.get("response") or "").strip()
        return Turn(answer or "(no output)", data.get("conversation_id") or session_id, output)

    def usage(self, *, discord: bool = False) -> str:
        """agy's own /usage panel, as data, for the quota group this model draws from."""
        import usage
        self.prepare(Path(os.environ.get("MTG_DECKS") or HERE.parent / "public"))
        return usage.agy_report(self.exe, str(self.home), self.model, discord=discord)


HARNESSES = {"codex": CodexHarness, "agy": AgyHarness}
DEFAULT = "agy"


def from_env() -> Harness:
    """The harness MTG_BOT_HARNESS names, with MTG_BOT_MODEL / MTG_BOT_EFFORT."""
    name = os.environ.get("MTG_BOT_HARNESS", DEFAULT).strip().lower()
    if name not in HARNESSES:
        raise HarnessError(f"unknown MTG_BOT_HARNESS {name!r}; one of {', '.join(HARNESSES)}")
    return HARNESSES[name](os.environ.get("MTG_BOT_MODEL") or None,
                           os.environ.get("MTG_BOT_EFFORT") or None)
