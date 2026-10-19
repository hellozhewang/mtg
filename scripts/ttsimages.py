"""Check the exact image URLs in TTS exports before publishing them.

A new URL is downloaded with TTS's UnityPlayer User-Agent and its bytes checked.
A URL verified within RECHECK_DAYS (default 7) is trusted without contacting the
host: rechecking all ~4,300 on every build hammered the community's image server
until it reset connections. An older verification is renewed with a conditional
GET (HTTP 304 via the stored ETag/Last-Modified). Set MTG_TTS_IMAGE_RECHECK_DAYS=0
to check everything now. Only successful checks are stored, separately from
Scryfall's card metadata and thumbnail bytes.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import http.client
import json
import os
from pathlib import Path
import struct
import time
import urllib.error
import urllib.request

from cardlib.db import PageStore

USER_AGENT = "UnityPlayer/2019.4.40f1 (UnityWebRequest/1.0, libcurl/7.80.0-DEV)"
TIMEOUT = 15
WORKERS = 4
MAX_BYTES = 16 * 1024 * 1024
CACHE_PREFIX = "tts:image-check:v1:"
RECHECK_DAYS = float(os.environ.get("MTG_TTS_IMAGE_RECHECK_DAYS", "7"))


class ImageError(ValueError):
    pass


class ValidationError(ValueError):
    def __init__(self, failures: dict[str, str], uses: dict[str, set[str]]):
        self.failures = failures
        lines = [f"TTS image validation failed: {len(failures)}/{len(uses)} unique URLs"]
        for url, reason in sorted(failures.items())[:30]:
            locations = sorted(uses[url])
            where = ", ".join(locations[:3])
            if len(locations) > 3:
                where += f" (+{len(locations) - 3} more)"
            lines.extend([f"  {reason}: {url}", f"    {where}"])
        if len(failures) > 30:
            lines.append(f"  ... {len(failures) - 30} more failed URLs")
        super().__init__("\n".join(lines))


@dataclass
class Report:
    checked: int = 0
    downloaded: int = 0
    unchanged: int = 0
    cached: int = 0           # verified recently: no request made

    def __str__(self):
        return (f"TTS images: {self.checked} unique URLs verified "
                f"({self.downloaded} downloaded, {self.unchanged} unchanged, "
                f"{self.cached} recently verified)")


def _verified(metadata: dict | None) -> bool:
    return bool(metadata) and metadata.get("format") in ("jpeg", "png", "webp") \
        and metadata.get("size", 0) > 0


def image_urls(files: dict[Path, str | bytes]) -> dict[str, set[str]]:
    """All exported faces and backs, including nested double-faced states.

    Inspect the actual spawn JSON, rather than reconstructing URLs from card
    metadata: it is the exact printing and URL the players will receive.
    """
    uses: dict[str, set[str]] = {}

    def walk(obj, location):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ("FaceURL", "BackURL"):
                    uses.setdefault(value or "", set()).add(f"{location} ({key})")
                else:
                    walk(value, location)
        elif isinstance(obj, list):
            for value in obj:
                walk(value, location)

    for path, body in sorted(files.items()):
        if path.suffix != ".ndjson":
            continue
        lines = (body.decode("utf-8") if isinstance(body, bytes) else body).splitlines()
        header = json.loads(lines[0])
        for i, line in enumerate(lines[1:]):
            role = ("library" if i == 0 else f"commander {i}"
                    if i <= header["commanders"] else "tokens")
            walk(json.loads(line), f"{path}: {role}")
    return uses


def image_format(body: bytes) -> str:
    """Recognise supported image bytes and reject empty/truncated/error bodies.

    This checks file signatures and container boundaries, not full pixel decoding.
    It catches the JSON/HTML HTTP responses TTS misreports as unknown formats.
    """
    if len(body) >= 4 and body.startswith(b"\xff\xd8\xff") and body.endswith(b"\xff\xd9"):
        return "jpeg"
    if (len(body) >= 45 and body.startswith(b"\x89PNG\r\n\x1a\n")
            and body[12:16] == b"IHDR" and body[-12:] == b"\0\0\0\0IEND\xaeB`\x82"
            and all(struct.unpack(">II", body[16:24]))):
        return "png"
    if (len(body) >= 30 and body[:4] == b"RIFF" and body[8:12] == b"WEBP"
            and struct.unpack("<I", body[4:8])[0] + 8 == len(body)
            and body[12:16] in (b"VP8 ", b"VP8L", b"VP8X")):
        return "webp"
    raise ImageError("response is not a complete JPEG, PNG or WebP image")


def check_url(url: str, previous: dict | None = None, opener=None) -> tuple[dict, bool]:
    """Return verified cache metadata and whether a validated image was unchanged."""
    if not url:
        raise ImageError("missing image URL")
    previous = previous or {}
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    verified = previous.get("format") in ("jpeg", "png", "webp") and previous.get("size", 0) > 0
    if verified:
        if previous.get("etag"):
            headers["If-None-Match"] = previous["etag"]
        elif previous.get("modified"):
            headers["If-Modified-Since"] = previous["modified"]
    try:
        request = urllib.request.Request(url, headers=headers)
        with (opener or urllib.request.urlopen)(request, timeout=TIMEOUT) as response:
            if response.status != 200:
                raise ImageError(f"unexpected HTTP {response.status}")
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if mime and mime not in ("image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"):
                raise ImageError(f"unexpected content type {mime}")
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ImageError("image exceeds 16 MiB")
            length = response.headers.get("Content-Length")
            if length is not None and int(length) != len(body):
                raise ImageError("incomplete image download")
            kind = image_format(body)
            return {"etag": response.headers.get("ETag"),
                    "modified": response.headers.get("Last-Modified"),
                    "format": kind, "size": len(body)}, False
    except urllib.error.HTTPError as exc:
        try:
            if exc.code == 304 and verified and (headers.get("If-None-Match") or headers.get("If-Modified-Since")):
                return previous, True
            raise ImageError(f"HTTP {exc.code}") from exc
        finally:
            exc.close()
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, ValueError) as exc:
        if isinstance(exc, ImageError):
            raise
        raise ImageError(str(exc)) from exc


def validate(files: dict[Path, str | bytes], db_path: Path, progress=None,
             checker=None, recheck_days: float | None = None, now: float | None = None) -> Report:
    """Validate every unique URL; fail before publication if any image fails.

    URLs verified within `recheck_days` are trusted without a request. SQLite is
    used only on the caller thread. Successful checks are committed as they
    finish, so an interrupted cold build resumes where it stopped.
    """
    uses = image_urls(files)
    store = PageStore(db_path, ttl_hours=24 * 365)
    report, failures = Report(), {}
    now = time.time() if now is None else now
    window = (RECHECK_DAYS if recheck_days is None else recheck_days) * 86400
    previous = {url: store.get(CACHE_PREFIX + url) for url in uses}
    fresh = {url for url, meta in previous.items()
             if _verified(meta) and now - (meta.get("checked_at") or 0) < window}
    report.cached = report.checked = len(fresh)

    def check(url):
        try:
            return (checker or check_url)(url, previous[url])
        finally:
            time.sleep(0.05)  # limit load on the community's image service

    try:
        if progress:
            progress(report, len(uses))
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            pending = {pool.submit(check, url): url for url in sorted(uses) if url not in fresh}
            for future in as_completed(pending):
                url = pending[future]
                try:
                    metadata, unchanged = future.result()
                    store.put(CACHE_PREFIX + url, {**metadata, "checked_at": now})
                    report.unchanged += unchanged
                    report.downloaded += not unchanged
                except ImageError as exc:
                    failures[url] = str(exc)
                report.checked += 1
                if progress and (report.checked % 250 == 0 or report.checked == len(uses)):
                    progress(report, len(uses))
    finally:
        store.conn.close()
    if failures:
        raise ValidationError(failures, uses)
    return report
