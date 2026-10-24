"""A macOS Seatbelt profile around a deck-builder harness process.

Harnesses that cannot confine themselves (or whose own permission prompts would end a
headless turn) run under `sandbox-exec` with a profile built here. The kernel enforces
it on the harness and every process it starts, so it holds whatever the model tries:

  * writes: only the asking user's deck folder, the shared card cache, the harness's
    own state folder, temp space and terminal devices. A write anywhere else fails
    with "Operation not permitted", which the model sees and works around; the turn
    and its reply go on.
  * reads: everything (the builder reads other users' decks and ../../scripts), except
    credential stores: SSH and GPG keys, cloud and GitHub tokens, the other agent CLIs'
    sign-ins and the owner's own harness config.
  * exec: other agent CLIs (`claude`, `codex`, `gh`, `npx`) are denied by path, which,
    unlike a curated PATH, absolute paths cannot get around.
  * network: allowed. The builder searches Scryfall and the web.

Measured on 2026-10-19 with `agy` and Gemini 3.8 Flash: writes inside succeeded,
writes and shell writes outside failed, a protected file could not be read, and the
model reported each and finished its reply.

Codex is NOT wrapped: it applies its own Seatbelt profile per tool call, and macOS
refuses a nested sandbox_apply, so an outer profile breaks every Codex tool call.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
HOME = Path.home()

# Credential stores the builder never needs to read.
SECRETS = (
    HOME / ".ssh", HOME / ".gnupg", HOME / ".aws", HOME / ".azure", HOME / ".kube",
    HOME / ".docker", HOME / ".netrc", HOME / ".git-credentials", HOME / ".config" / "gh",
    HOME / ".codex", HOME / ".claude", HOME / ".claude.json",
    HOME / ".gemini" / "antigravity-cli", HOME / ".gemini" / "config",
    HOME / ".gemini" / "jetski-standalone-oauth-token", HOME / ".gemini" / "antigravity",
    HOME / "Library" / "Keychains",
)

# Other agent CLIs and publishing tools the builder must not start.
NO_EXEC_NAMES = ("claude", "codex", "gh", "npx")

# Always writable: temp space and the terminal devices a shell needs (a PTY needs
# /dev/ptmx, without which every command fails "failed to create PTY").
SYSTEM_WRITABLE = (Path("/private/var/folders"), Path("/private/tmp"))
DEVICES = ('(literal "/dev/null")', '(literal "/dev/zero")', '(literal "/dev/dtracehelper")',
           '(literal "/dev/ptmx")', '(regex #"^/dev/tty")', '(regex #"^/dev/fd/")')


def _q(path: Path | str) -> str:
    """A path as a Seatbelt string literal."""
    text = str(path)
    if '"' in text or "\\" in text or "\n" in text:
        raise ValueError(f"unsafe path for a sandbox profile: {text!r}")
    return f'"{text}"'


def _real(path: Path) -> Path:
    """Seatbelt matches resolved paths (/tmp is /private/tmp)."""
    try:
        return Path(os.path.realpath(path))
    except OSError:
        return path


def no_exec_paths(names: tuple[str, ...] = NO_EXEC_NAMES) -> list[Path]:
    """Where each named CLI is installed, symlink and target both."""
    out: list[Path] = []
    for name in names:
        found = shutil.which(name)
        if found:
            for p in (Path(found), _real(Path(found))):
                if p not in out:
                    out.append(p)
    return out


def profile(writable: list[Path], unreadable: tuple[Path, ...] = SECRETS,
            no_exec: list[Path] | None = None) -> str:
    """The profile text: allow by default, then confine writes, reads and execs."""
    writes = [_real(p) for p in writable] + [_real(p) for p in SYSTEM_WRITABLE]
    lines = [
        "(version 1)",
        "(allow default)",
        "(deny file-write*)",
        "(allow file-write*",
        *(f"  (subpath {_q(p)})" for p in writes),
        *(f"  {d}" for d in DEVICES),
        ")",
    ]
    reads = [_real(p) for p in unreadable]
    if reads:
        lines += ["(deny file-read*", *(f"  (subpath {_q(p)})" for p in reads), ")"]
    execs = no_exec_paths() if no_exec is None else no_exec
    if execs:
        lines += ["(deny process-exec", *(f"  (literal {_q(p)})" for p in execs), ")"]
    return "\n".join(lines) + "\n"


def wrap(argv: list[str], profile_text: str) -> list[str]:
    """`argv` run under the profile."""
    return [SANDBOX_EXEC, "-p", profile_text, *argv]
