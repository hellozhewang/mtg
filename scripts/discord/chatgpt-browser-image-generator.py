#!/usr/bin/env python3
"""Generate an image through a signed-in ChatGPT browser and download its PNG.

Uses agent-browser and ChatGPT's normal website, subscription limits and checks.
No image API key is used. Authentication stays in agent-browser's local storage.
See docs/development/agent-browser-guide.md for setup and known UI limitations.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse


LOCAL_CONFIG = Path.home() / ".agent-browser" / "image-generation.json"
IMAGE_BUTTON = 'button[data-testid="generated-image-preview"]'

# Support the current UI and conventional conversation-turn markup. Response
# identity matters: an old successful image must never mask a new refusal.
PAGE_STATE = r"""(() => {
  const root = document.querySelector('main') || document;
  let nodes = [...root.querySelectorAll('[data-turn-key]')];
  let attr = 'data-turn-key';
  if (!nodes.length) {
    nodes = [...root.querySelectorAll('article[data-testid^="conversation-turn"]')];
    attr = 'data-testid';
  }
  if (!nodes.length) {
    nodes = [...root.querySelectorAll('[data-message-author-role="assistant"]')];
    attr = 'data-message-id';
  }
  return {
    url: location.href,
    login: [...document.querySelectorAll('button')].some(b =>
      (b.getAttribute('aria-label') || b.innerText).trim() === 'Log in'),
    challenge: !!document.querySelector('iframe[src*="challenges.cloudflare.com"]') ||
      document.title === 'Just a moment...',
    busy: [...root.querySelectorAll('button')].some(b =>
      ['Stop', 'Stop generating', 'Stop streaming'].includes(
        b.getAttribute('aria-label') || b.innerText)),
    draft: [...root.querySelectorAll('[role="textbox"],textarea')]
      .filter(e => e.getAttribute('aria-label') === 'Ask ChatGPT')
      .map(e => e.value || e.innerText || '').join(''),
    turns: nodes.map(n => ({
      id: n.getAttribute(attr),
      text: n.innerText.slice(-1800),
      images: [...n.querySelectorAll('button[data-testid="generated-image-preview"]')]
        .map(b => ({
          ready: !!b.querySelector('img')?.complete &&
            b.querySelector('img').naturalWidth > 0
        })),
    })),
  };
})()"""


class GenerationError(RuntimeError):
    """A failed browser operation or incomplete generation."""


class Browser:
    def __init__(self, session: str, executable: str = "agent-browser"):
        self.command = [executable, "--session", session, "--headed",
                        "--restore", session, "--json"]

    def run(self, *args: str, timeout: float = 45) -> dict:
        try:
            result = subprocess.run(self.command + list(args), capture_output=True,
                                    text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            # Never retry a send automatically: it could already have succeeded.
            raise GenerationError(f"Browser command {args[0]!r} did not complete. "
                                  "Inspect the open chat before retrying.") from exc
        try:
            payload = json.loads(result.stdout)
        except ValueError as exc:
            raise GenerationError(f"Browser command {args[0]!r} returned invalid JSON.") from exc
        if result.returncode or not payload.get("success"):
            error = payload.get("error") or "unknown browser error"
            raise GenerationError(f"Browser command {args[0]!r} failed: {error}")
        return payload.get("data") or {}

    def state(self) -> dict:
        return self.run("eval", PAGE_STATE)["result"]

    def snapshot(self) -> dict:
        return self.run("snapshot", "-i")

    def ref(self, role: str, name: str, *, optional: bool = False) -> str | None:
        snapshot = self.snapshot()
        visible = set(re.findall(r"\[ref=([^\]]+)\]", snapshot.get("snapshot", "")))
        matches = [ref for ref, value in snapshot.get("refs", {}).items()
                   if ref in visible and value.get("role") == role and value.get("name") == name]
        if len(matches) == 1:
            return "@" + matches[0]
        if optional and not matches:
            return None
        raise GenerationError(f"Expected one {role} named {name!r}; found {len(matches)}. "
                              "The ChatGPT layout may have changed.")

    def close_viewer(self) -> None:
        try:
            ref = self.ref("button", "Close viewer", optional=True)
            if ref:
                self.run("click", ref)
                return
        except GenerationError:
            pass
        try:
            self.run("press", "Escape")
        except GenerationError:
            pass
        try:
            self.run("eval", """(() => {
                const btn = document.querySelector(
                    'button[aria-label="Close viewer"], [role="dialog"] button[aria-label*="Close" i], button[aria-label="Close"]'
                );
                if (btn) btn.click();
            })()""")
        except GenerationError:
            pass

    def upload_file(self, path: Path) -> None:
        file_path = str(path.resolve())
        self.run("upload", 'input[type="file"]', file_path)
        name_json = json.dumps(path.name)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            has_attachment = self.run("eval", f"""(() => {{
                const target = {name_json}.toLowerCase();
                const cards = [...document.querySelectorAll('button[aria-label*="Remove" i], img[alt], [aria-label]')];
                return cards.some(c => (c.getAttribute('aria-label') || c.getAttribute('alt') || '').toLowerCase().includes(target));
            }})()""").get("result")
            if has_attachment:
                return
            time.sleep(0.5)


def check_access(state: dict) -> None:
    if state.get("challenge"):
        raise GenerationError("ChatGPT requires human verification. Complete it in the "
                              "visible browser, then run again.")
    if state.get("login"):
        raise GenerationError("Sign in to ChatGPT in the visible browser, then run again. "
                              "The browser session will save the login locally.")


def select_turn(state: dict, before: set[str]) -> dict | None:
    """Select only a turn created after this request, never a historical image."""
    turns = [turn for turn in state.get("turns", [])
             if turn.get("id") and turn["id"] not in before]
    return turns[-1] if turns else None


def wait_for_image(browser: Browser, before: set[str], timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    settled_at = None
    last_report = 0.0
    while time.monotonic() < deadline:
        state = browser.state()
        check_access(state)
        turn = select_turn(state, before)
        if turn and not state.get("busy"):
            if any(image.get("ready") for image in turn.get("images", [])):
                return turn
            if turn.get("images"):
                # A retained response can hydrate before its image bytes load.
                settled_at = None
            else:
                settled_at = settled_at or time.monotonic()
            # Allow the image controls to render after streaming finishes.
            if settled_at is not None and time.monotonic() - settled_at >= 5:
                text = turn.get("text", "").strip()
                raise GenerationError("ChatGPT completed without a downloadable image. "
                                      "No retry was submitted. Response: " + text[-900:])
        else:
            settled_at = None
        if time.monotonic() - last_report >= 30:
            print("Waiting for ChatGPT's new image…", file=sys.stderr, flush=True)
            last_report = time.monotonic()
        time.sleep(2)
    raise GenerationError("Generation timed out. The request may still be running; "
                          "check the chat and use --download-only to recover it. "
                          "No duplicate request was submitted.")


def png_info(path: Path) -> dict:
    with path.open("rb") as stream:
        header = stream.read(33)
        if (len(header) < 33 or header[:8] != b"\x89PNG\r\n\x1a\n" or
                header[8:16] != b"\x00\x00\x00\rIHDR"):
            raise GenerationError("The download is not an original PNG. "
                                  "No output file was installed.")
        width, height = struct.unpack(">II", header[16:24])
        if not width or not height:
            raise GenerationError("The downloaded PNG has invalid dimensions.")
        digest = hashlib.sha256(header)
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        stream.seek(-12, os.SEEK_END)
        if stream.read() != b"\x00\x00\x00\x00IEND\xaeB`\x82":
            raise GenerationError("The downloaded PNG is incomplete; no output was installed.")
    return {"width": width, "height": height, "bytes": path.stat().st_size,
            "sha256": digest.hexdigest()}


def download_turn(browser: Browser, turn: dict, output: Path) -> dict:
    if len(turn.get("images", [])) != 1:
        raise GenerationError("Expected exactly one image in the selected response.")
    # Scope the click to the selected response, not the last image in history.
    turn_id = json.dumps(turn["id"])
    selector = (f'[data-turn-key={turn_id}] {IMAGE_BUTTON}, '
                f'article[data-testid={turn_id}] {IMAGE_BUTTON}, '
                f'[data-message-id={turn_id}] {IMAGE_BUTTON}')
    if hasattr(browser, "close_viewer"):
        browser.close_viewer()
    try:
        browser.run("click", selector)
    except GenerationError:
        # Fall back to scrolling into view and clicking via JS if covered or obstructed
        try:
            browser.run("eval", f"document.querySelector({repr(selector)})?.scrollIntoView({{ block: 'center' }})")
        except GenerationError:
            pass
        browser.run("eval", f"document.querySelector({repr(selector)})?.click()")
    try:
        browser.run("wait", "--fn", """[...document.querySelectorAll('[role="dialog"] img')]
      .some(i => i.complete && i.naturalWidth > 0 &&
                 i.getBoundingClientRect().width > 0 &&
                 /^Generated image/.test(i.alt))""")
        deadline = time.monotonic() + 20
        ref = None
        while time.monotonic() < deadline:
            ref = browser.ref("button", "Download", optional=True)
            if ref:
                break
            time.sleep(0.5)
        if not ref:
            raise GenerationError("Image viewer did not expose a Download button.")
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".chatgpt-download-", dir=output.parent) as tmp:
            for attempt in range(2):
                downloaded = Path(tmp) / f"original-{attempt}.png"
                try:
                    browser.run("download", ref, str(downloaded), timeout=90)
                except GenerationError as exc:
                    # A lost acknowledgement is ambiguous. Recover a completed file
                    # first, then allow ONE retry of only the original-file download.
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        if downloaded.exists():
                            try:
                                png_info(downloaded)
                                break
                            except GenerationError:
                                pass
                        time.sleep(0.5)
                    else:
                        transient = any(message in str(exc) for message in
                                        ("no response came back", "did not complete"))
                        if attempt == 0 and transient:
                            print("Download acknowledgement lost; retrying only the download…",
                                  file=sys.stderr, flush=True)
                            ref = browser.ref("button", "Download")
                            continue
                        raise
                break
            info = png_info(downloaded)
            try:
                # The temp file is on the same filesystem. Linking is atomic and
                # refuses an existing destination even if another writer raced us.
                os.link(downloaded, output)
            except FileExistsError as exc:
                raise GenerationError(f"Output already exists: {output}. Choose another name.") from exc
        return {"path": str(output), **info}
    finally:
        if hasattr(browser, "close_viewer"):
            browser.close_viewer()


def chat_url(value: str) -> str:
    url = urlparse(value)
    if (url.scheme != "https" or url.netloc != "chatgpt.com" or
            url.query or url.fragment or
            (url.path not in ("", "/") and not url.path.startswith("/c/"))):
        raise argparse.ArgumentTypeError("Use https://chatgpt.com/ or a ChatGPT /c/ chat URL.")
    return value


def acquire_lock(session: str):
    key = hashlib.sha256(session.encode()).hexdigest()[:16]
    path = Path.home() / ".agent-browser" / f"image-generator-{key}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.open("a+")
    path.chmod(0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock.close()
        raise GenerationError("Another generator is using this browser session. "
                              "Wait for it to finish.") from exc
    return lock


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--prompt", help="Image description; requests exactly one image")
    source.add_argument("--prompt-file", type=Path, help="UTF-8 image prompt file")
    source.add_argument("--download-only", action="store_true",
                        help="Download the latest completed turn's image without sending")
    parser.add_argument("--ref", action="append", dest="refs", type=Path, default=[],
                        help="Reference image to upload to ChatGPT (can be specified multiple times)")
    parser.add_argument("--out", required=True, type=Path, help="New output PNG path")
    parser.add_argument("--chat-url", type=chat_url,
                        help="Chat URL; defaults to local image-generation.json or New chat")
    parser.add_argument("--session", default="chatgpt-account")
    parser.add_argument("--timeout", type=float, default=600, help="Generation timeout in seconds")
    args = parser.parse_args(argv)
    if not args.download_only and args.prompt is None and args.prompt_file is None:
        parser.error("provide --prompt, --prompt-file, or --download-only")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    output = args.out.expanduser().resolve()
    if output.suffix.lower() != ".png":
        parser.error("--out must end in .png; originals are downloaded without conversion")
    if output.exists():
        parser.error(f"output already exists: {output}; choose a new filename")
    if not shutil.which("agent-browser"):
        parser.error("agent-browser is not installed; see docs/development/agent-browser-guide.md")
    ref_paths = [r.expanduser().resolve() for r in args.refs]
    for r in ref_paths:
        if not r.is_file():
            parser.error(f"reference image does not exist: {r}")
    lock = None
    try:
        prompt = args.prompt_file.read_text(encoding="utf-8") if args.prompt_file else args.prompt
        if not args.download_only and not (prompt or "").strip():
            raise GenerationError("The prompt is empty.")
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=output.parent):
            pass  # Verify output is writable before spending a generation.
        config = json.loads(LOCAL_CONFIG.read_text()) if LOCAL_CONFIG.exists() else {}
        url = chat_url(args.chat_url or config.get("chat_url") or "https://chatgpt.com/")
        lock = acquire_lock(args.session)
        browser = Browser(args.session)
        print("Opening the saved ChatGPT browser session…", file=sys.stderr, flush=True)
        browser.run("open", url)
        browser.close_viewer()
        deadline = time.monotonic() + 30
        while True:
            state = browser.state()
            check_access(state)
            if state.get("busy"):
                raise GenerationError("A response is already generating in this chat. "
                                      "Wait for it to finish before starting another request.")
            composer = browser.ref("textbox", "Ask ChatGPT", optional=True)
            if not composer:
                browser.close_viewer()
                composer = browser.ref("textbox", "Ask ChatGPT", optional=True)
            history_ready = not urlparse(url).path.startswith("/c/") or bool(state.get("turns"))
            if composer and history_ready:
                break
            if time.monotonic() >= deadline:
                raise GenerationError("ChatGPT did not load its composer within 30 seconds.")
            time.sleep(1)
        if args.download_only:
            turns = state.get("turns") or []
            if not turns:
                raise GenerationError("No conversation turns are loaded; open a completed chat first.")
            before = {turn["id"] for turn in turns[:-1] if turn.get("id")}
            turn = wait_for_image(browser, before, min(args.timeout, 30))
        else:
            if state.get("draft", "").strip():
                raise GenerationError("The composer contains an unsent draft. "
                                      "Clear or save it before running this script.")
            if any(not turn.get("id") for turn in state.get("turns", [])):
                raise GenerationError("Cannot identify existing turns safely; UI layout changed.")
            before = {turn["id"] for turn in state.get("turns", []) if turn.get("id")}
            for r in ref_paths:
                print(f"Uploading reference image: {r.name}…", file=sys.stderr, flush=True)
                browser.upload_file(r)
            request = "Generate exactly one image based on this description:\n\n" + prompt
            browser.run("fill", composer, request)
            send = browser.ref("button", "Send")
            browser.run("click", send)
            print("Prompt submitted once. Waiting for the image…", file=sys.stderr, flush=True)
            turn = wait_for_image(browser, before, args.timeout)
        info = download_turn(browser, turn, output)
        info["source"] = "chatgpt-browser"
        print(json.dumps(info, indent=2))
        return 0
    except (GenerationError, OSError, ValueError, argparse.ArgumentTypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if lock is not None:
            lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
