"""Read the signed-in Codex account's allowance without starting a model turn.

Protocol: https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt
Only initialize + account/rateLimits/read are sent. Credentials stay in Codex.
"""
from __future__ import annotations

import json
import math
import os
import selectors
import signal
import subprocess
import time
from datetime import datetime, timezone


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
                            raise UsageUnavailable("Codex exited before reporting usage")
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
                        raise UsageUnavailable("Codex could not read the account allowance")
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


def format_limits(result: dict, model: str, *, discord: bool = False) -> str:
    """Label account buckets honestly; a model name is not a separate quota."""
    header = f"Usage remaining · {model}"
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
            label = "Codex (shared account)" if key == "codex" else bucket.get("limitName") or key
            lines.append(f"{label} — " + " · ".join(parts))
    if result.get("ordinaryUsageAllowed") is False:
        lines.append("Codex reports that account usage is currently blocked.")
    return header + "\n" + ("\n".join(lines) if lines else "Unavailable: Codex returned no allowance windows.")


def report(codex: str, model: str, *, discord: bool = False) -> str:
    """Usage failure must never discard a deckbuilding reply or invent a quota."""
    try:
        return format_limits(read_limits(codex), model, discord=discord)
    except (UsageUnavailable, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, UsageUnavailable) else "could not read Codex usage"
        return f"Usage remaining · {model}\nUnavailable: {reason}."
