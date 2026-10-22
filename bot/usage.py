"""Read the builder harness's allowance without starting a model turn.

Codex: https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt
Only initialize + account/rateLimits/read are sent. Credentials stay in Codex.

Antigravity (agy): `agy --print=/usage --output-format json`, its own usage panel as
data: groups of models that share a weekly and a 5-hour limit, each bucket with the
fraction remaining and the reset time. No model turn is run.
"""
from __future__ import annotations

import json
import math
import re
import os
import selectors
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


USAGE_COMMANDS = {"usage", "!usage", "/builder-usage", "!builder-usage"}
TIMEOUT = 8.0


class UsageUnavailable(RuntimeError):
    pass


def read_limits(codex: str, *, timeout: float = TIMEOUT) -> dict:
    """Use a short-lived stdio RPC connection with a deadline and bounded reads."""
    deadline = time.monotonic() + timeout
    proc = subprocess.Popen(
        [codex, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        bufsize=0, start_new_session=True,
    )
    pending = b""
    received = 0

    def send(message: dict) -> None:
        proc.stdin.write((json.dumps(message) + "\n").encode())
        proc.stdin.flush()

    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)

            def response(request_id: int) -> dict:
                nonlocal pending, received
                while time.monotonic() < deadline:
                    if b"\n" not in pending:
                        if not selector.select(max(0, deadline - time.monotonic())):
                            break
                        chunk = os.read(proc.stdout.fileno(), 65536)
                        if not chunk:
                            raise UsageUnavailable("usage lookup ended early")
                        received += len(chunk)
                        if received > 1_000_000:
                            raise UsageUnavailable("unexpected usage response")
                        pending += chunk
                        continue
                    line, pending = pending.split(b"\n", 1)
                    message = json.loads(line)
                    if not isinstance(message, dict) or message.get("id") != request_id:
                        continue  # notifications are not our RPC response
                    if "error" in message:
                        # Never forward an upstream error containing account/auth details.
                        raise UsageUnavailable("the allowance could not be read")
                    result = message.get("result")
                    if not isinstance(result, dict):
                        raise UsageUnavailable("unexpected usage response")
                    return result
                raise UsageUnavailable("usage lookup timed out")

            send({"id": 1, "method": "initialize", "params": {
                "clientInfo": {"name": "mtg_usage", "version": "1.0"},
            }})
            response(1)
            send({"method": "initialized", "params": {}})
            send({"id": 2, "method": "account/rateLimits/read"})
            return response(2)
    finally:
        # Reap the server on success, timeout and malformed responses alike. A
        # process group also covers any helper the app server started on boot.
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        proc.stdin.close()
        proc.stdout.close()


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _window(window: dict, name: str, discord: bool) -> str:
    minutes = window.get("windowDurationMins")
    if _number(minutes) and minutes > 0:
        if minutes == 10080:
            name = "weekly"
        elif minutes % 60 == 0:
            name = f"{minutes / 60:g}h"
        else:
            name = f"{minutes:g}m"
    used = window.get("usedPercent")
    remaining = f"{max(0, min(100, 100 - used)):g}% left" if _number(used) and used >= 0 else "unavailable"
    text = f"{name}: {remaining}"
    resets = window.get("resetsAt")
    if _number(resets) and resets > 0:
        try:
            when = datetime.fromtimestamp(resets, timezone.utc)
            reset = f"<t:{int(resets)}:R>" if discord else when.strftime("%Y-%m-%d %H:%M UTC")
            text += f" (resets {reset})"
        except (ValueError, OverflowError, OSError):
            pass
    return text


# What players see names no model, harness or vendor: the owner alone picks those,
# and the builder is just "the builder" to everyone else.
HEADER = "Usage remaining"


def format_limits(result: dict, model: str, *, discord: bool = False) -> str:
    """Codex's account buckets, unlabelled: a model name is not a separate quota."""
    header = HEADER
    buckets = result.get("rateLimitsByLimitId")
    buckets = dict(buckets) if isinstance(buckets, dict) else {}
    legacy = result.get("rateLimits")
    if isinstance(legacy, dict):
        key = legacy.get("limitId") or "codex"
        if not isinstance(buckets.get(key), dict):
            buckets[key] = legacy
    lines = []
    for key, bucket in buckets.items():
        if not isinstance(bucket, dict):
            continue
        parts = [_window(bucket[name], name, discord) for name in ("primary", "secondary")
                 if isinstance(bucket.get(name), dict)]
        credits = bucket.get("credits")
        if isinstance(credits, dict):
            if credits.get("unlimited") is True:
                parts.append("credits: unlimited")
            elif credits.get("hasCredits") is True and credits.get("balance") is not None:
                parts.append(f"credits: {credits['balance']}")
        if parts:
            lines.append(" · ".join(parts))
    if result.get("ordinaryUsageAllowed") is False:
        lines.append("Usage is currently blocked.")
    return header + "\n" + ("\n".join(lines) if lines else "Unavailable: no allowance windows were returned.")


def report(codex: str, model: str, *, discord: bool = False) -> str:
    """Usage failure must never discard a deckbuilding reply or invent a quota."""
    try:
        return format_limits(read_limits(codex), model, discord=discord)
    except (UsageUnavailable, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, UsageUnavailable) else "could not read usage"
        return f"{HEADER}\nUnavailable: {reason}."


# ---------- Antigravity (agy) ----------

AGY_WINDOWS = {"5h": 0, "weekly": 1}      # 5-hour first, then weekly, as Codex shows them
IMAGE_MODEL = "gemini-3.1-flash-image"
IMAGE_QUOTA_FILE = "image_quota.json"


def parse_image_quota_error(text: str) -> dict | None:
    """Extract gemini-3.1-flash-image 429 quota exhaustion info from log/error text."""
    if IMAGE_MODEL not in text or ("QUOTA_EXHAUSTED" not in text and "RESOURCE_EXHAUSTED" not in text):
        return None
    ts_match = re.search(r'quotaResetTimeStamp(?:\\["\'])?\s*:\s*\\["\']?([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z?)', text)
    if not ts_match:
        ts_match = re.search(r'["\']quotaResetTimeStamp["\']\s*:\s*["\']([^"\']+)["\']', text)
    resets_iso = ts_match.group(1) if ts_match else None
    resets_at = None
    if resets_iso:
        try:
            resets_at = datetime.fromisoformat(resets_iso.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
        except ValueError:
            pass
    return {
        "model": IMAGE_MODEL,
        "resets_iso": resets_iso,
        "resets_at": resets_at,
    }


def check_session_image_quota(home: Path | str | None, conv_id: str | None) -> dict | None:
    """Directly inspect this specific turn's brain and subagents for image quota errors."""
    if not home or not conv_id:
        return None
    brain_dir = Path(home) / ".gemini" / "antigravity-cli" / "brain" / conv_id
    if not brain_dir.is_dir():
        return None
    # 1. Check parent session messages from subagents
    msgs_dir = brain_dir / ".system_generated" / "messages"
    if msgs_dir.is_dir():
        for msg_file in sorted(msgs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
            try:
                info = parse_image_quota_error(msg_file.read_text(encoding="utf-8", errors="replace"))
                if info and info.get("resets_at"):
                    return info
            except Exception:
                continue
    # 2. Check parent session transcript
    parent_log = brain_dir / ".system_generated" / "logs" / "transcript.jsonl"
    if parent_log.is_file():
        try:
            info = parse_image_quota_error(parent_log.read_text(encoding="utf-8", errors="replace"))
            if info and info.get("resets_at"):
                return info
        except Exception:
            pass
    # 3. Check subagents spawned in this session
    subagents_dir = brain_dir / ".system_generated" / "subagents"
    if subagents_dir.is_dir():
        for sa_meta in subagents_dir.glob("*.json"):
            try:
                sa_data = json.loads(sa_meta.read_text(encoding="utf-8"))
                sa_id = sa_data.get("conversationId")
                if sa_id:
                    sa_log = Path(home) / ".gemini" / "antigravity-cli" / "brain" / sa_id / ".system_generated" / "logs" / "transcript.jsonl"
                    if sa_log.is_file():
                        info = parse_image_quota_error(sa_log.read_text(encoding="utf-8", errors="replace"))
                        if info and info.get("resets_at"):
                            return info
            except Exception:
                continue
    return None


def scan_recent_image_quota(home: Path | str) -> dict | None:
    """Scan the newest log files in home for gemini-3.1-flash-image quota errors."""
    log_dir = Path(home) / ".gemini" / "antigravity-cli" / "log"
    if not log_dir.is_dir():
        return None
    log_files = sorted(log_dir.glob("cli-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for log_path in log_files[:10]:
        try:
            size = log_path.stat().st_size
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                if size > 100_000:
                    f.seek(size - 100_000)
                chunk = f.read()
            info = parse_image_quota_error(chunk)
            if info:
                return info
        except Exception:
            continue
    return None


def read_image_quota(home: Path | str | None) -> dict | None:
    """Read cached image quota state, or scan recent logs if not cached yet."""
    if not home:
        return None
    quota_path = Path(home) / IMAGE_QUOTA_FILE
    if quota_path.is_file():
        try:
            data = json.loads(quota_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("model") == IMAGE_MODEL:
                return data
        except (OSError, ValueError):
            pass
    info = scan_recent_image_quota(home)
    if info and info.get("resets_at") and info["resets_at"] > time.time():
        record_image_quota(home, info)
        return info
    return None


def record_image_quota(home: Path | str | None, info: dict) -> None:
    """Cache the image quota state to image_quota.json."""
    if not home:
        return
    quota_path = Path(home) / IMAGE_QUOTA_FILE
    try:
        quota_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": info.get("model", IMAGE_MODEL),
            "resets_iso": info.get("resets_iso"),
            "resets_at": info.get("resets_at"),
            "updated_at": time.time(),
        }
        quota_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def is_image_quota_exhausted(home: Path | str | None) -> tuple[bool, str | None, float | None]:
    """Check if gemini-3.1-flash-image quota is currently exhausted.
    Returns (exhausted, resets_iso, resets_at)."""
    info = read_image_quota(home)
    if info and _number(info.get("resets_at")):
        resets_at = float(info["resets_at"])
        if resets_at > time.time():
            return True, info.get("resets_iso"), resets_at
    return False, None, None


def format_image_quota(home: Path | str | None, *, discord: bool = False) -> str:
    """Image quota line for Sleever on Gemini."""
    exhausted, resets_iso, resets_at = is_image_quota_exhausted(home)
    if exhausted and resets_at:
        try:
            when = datetime.fromtimestamp(resets_at, timezone.utc)
            reset_str = f"<t:{int(resets_at)}:R>" if discord else when.strftime("%Y-%m-%d %H:%M UTC")
            return f"Image ({IMAGE_MODEL}): 0% left (resets {reset_str})"
        except (ValueError, OverflowError, OSError):
            pass
        return f"Image ({IMAGE_MODEL}): 0% left"
    return f"Image ({IMAGE_MODEL}): available"


def read_agy(exe: str, home: str, *, timeout: float = 20.0) -> dict:
    """agy's /usage data. Run with the bot's own agy home, which holds its sign-in."""
    try:
        proc = subprocess.run([exe, "--print=/usage", "--output-format", "json"],
                              capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, "HOME": home}, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as exc:
        raise UsageUnavailable("usage lookup timed out") from exc
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            command = data.get("command") if isinstance(data, dict) else None
            if isinstance(command, dict) and isinstance(command.get("data"), dict):
                return command["data"]
    raise UsageUnavailable("no usage data was returned")


def _agy_group(groups: list, model: str) -> list:
    """The quota group the model draws from: a group named for the model (Argon), else
    Claude/GPT for those, else the Gemini group; the first group if none matches."""
    words = model.lower()
    named = [g for g in groups if isinstance(g, dict) and any(
        w in str(g.get("name", "")).lower() for w in ("argon",) if w in words)]
    if named:
        return named
    if words.startswith(("claude", "gpt")):
        wanted = "claude"
    elif words.startswith("gemini"):
        wanted = "gemini models"
    else:
        wanted = None
    match = [g for g in groups if isinstance(g, dict) and wanted and wanted in str(g.get("name", "")).lower()]
    return match or [g for g in groups if isinstance(g, dict)][:1]


def _agy_bucket(bucket: dict, discord: bool) -> str:
    window = str(bucket.get("window") or bucket.get("name") or "limit")
    fraction = bucket.get("remaining_fraction")
    remaining = f"{max(0, min(100, round(fraction * 100)))}% left" if _number(fraction) else "unavailable"
    text = f"{window}: {remaining}"
    reset = bucket.get("reset_time")
    if isinstance(reset, str) and reset:
        try:
            when = datetime.fromisoformat(reset.replace("Z", "+00:00")).astimezone(timezone.utc)
            text += " (resets " + (f"<t:{int(when.timestamp())}:R>" if discord
                                   else when.strftime("%Y-%m-%d %H:%M UTC")) + ")"
        except ValueError:
            pass
    return text


def format_agy(data: dict, model: str, *, discord: bool = False,
               image_home: str | Path | None = None, is_image: bool = False) -> str:
    """The same shape as the Codex footer, for the group the model draws from, with
    no group or model name (players don't see which model runs). When is_image is True,
    includes gemini-3.1-flash-image quota line."""
    lines = []
    if is_image and image_home:
        img_line = format_image_quota(image_home, discord=discord)
        if img_line:
            lines.append(img_line)
    for group in _agy_group(data.get("groups") or [], model):
        buckets = [b for b in group.get("buckets") or [] if isinstance(b, dict)]
        buckets.sort(key=lambda b: AGY_WINDOWS.get(str(b.get("window")), 9))
        parts = [_agy_bucket(b, discord) for b in buckets]
        if parts:
            lines.append(" · ".join(parts))
    return HEADER + "\n" + ("\n".join(lines) if lines else "Unavailable: no limits were returned.")


def exhausted_reset(text: str) -> str | None:
    """When the emptiest window in a footer resets, for "try again at": a spent weekly
    window outlasts the 5-hour one, so the lowest "N% left" decides."""
    found = re.findall(r"(\d+(?:\.\d+)?)% left \(resets ([^)]+)\)", text or "")
    return min(found, key=lambda f: float(f[0]))[1] if found else None


def agy_report(exe: str, home: str, model: str, *, discord: bool = False, is_image: bool = False) -> str:
    """Usage failure must never discard a deckbuilding reply or invent a quota."""
    try:
        return format_agy(read_agy(exe, home), model, discord=discord, image_home=home, is_image=is_image)
    except (UsageUnavailable, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, UsageUnavailable) else "could not read usage"
        lines = []
        if is_image and home:
            img_line = format_image_quota(home, discord=discord)
            if img_line:
                lines.append(img_line)
        lines.append(f"Unavailable: {reason}.")
        return HEADER + "\n" + "\n".join(lines)
