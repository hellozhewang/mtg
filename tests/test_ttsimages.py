"""The catalog must not publish TTS objects whose images fail Unity GETs."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr
import http.client
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_site
import ttsimages


def png():
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\0\xff\0\0")) + chunk(b"IEND", b""))


def export(*objects, commanders=1):
    return "\n".join(json.dumps(obj) for obj in [
        {"commanders": commanders, "tokens": len(objects) > commanders + 1}, *objects])


def sheet(front="https://example.org/front.webp", back="https://example.org/back.jpg"):
    return {"CustomDeck": {"1": {"FaceURL": front, "BackURL": back}}}


class Response(io.BytesIO):
    status = 200

    def __init__(self, body=None, **headers):
        body = png() if body is None else body
        super().__init__(body)
        self.headers = {"Content-Type": "image/png", "Content-Length": str(len(body)), **headers}


class URLTests(unittest.TestCase):
    def test_collect_exact_urls_from_every_export_role_and_nested_states(self):
        files = {Path("decks.json"): "ignored", Path("alice/Test.ndjson"): export(
            {**sheet(), "ContainedObjects": [{"States": {"2": sheet("https://example.org/flip.webp")}}]},
            sheet("https://example.org/first.webp"), sheet("https://example.org/second.webp"),
            sheet("https://example.org/token.webp"), commanders=2).encode()}
        uses = ttsimages.image_urls(files)
        self.assertEqual(len(uses), 6)
        self.assertIn("alice/Test.ndjson: commander 1 (FaceURL)", uses["https://example.org/first.webp"])
        self.assertIn("alice/Test.ndjson: commander 2 (FaceURL)", uses["https://example.org/second.webp"])
        self.assertIn("alice/Test.ndjson: tokens (FaceURL)", uses["https://example.org/token.webp"])
        self.assertIn("alice/Test.ndjson: library (FaceURL)", uses["https://example.org/flip.webp"])
        self.assertEqual(len(uses["https://example.org/back.jpg"]), 4)

    def test_get_uses_unity_user_agent_and_validates_bytes(self):
        opener = Mock(return_value=Response(ETag='"version1"'))
        metadata, unchanged = ttsimages.check_url("https://example.org/image", opener=opener)
        request = opener.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("User-agent"), ttsimages.USER_AGENT)
        self.assertEqual(metadata["format"], "png")
        self.assertEqual(metadata["size"], len(png()))
        self.assertEqual(metadata["etag"], '"version1"')
        self.assertFalse(unchanged)

    def test_rejects_error_pages_and_incomplete_images_even_with_http_200(self):
        cases = [
            Response(b'{"error":"generic_user_agent"}', **{"Content-Type": "application/json"}),
            Response(b"<html>blocked</html>", **{"Content-Type": "text/html"}),
            Response(b"not an image"), Response(png()[:-5]),
            Response(**{"Content-Length": "9999"}),
        ]
        for response in cases:
            with self.subTest(headers=response.headers), self.assertRaises(ttsimages.ImageError):
                ttsimages.check_url("https://example.org/image", opener=lambda *a, **k: response)

    def test_http_and_network_failures_are_actionable(self):
        for error in [urllib.error.HTTPError("https://example.org", 400, "Bad", {}, io.BytesIO()),
                      urllib.error.HTTPError("https://example.org", 404, "Missing", {}, io.BytesIO()),
                      urllib.error.URLError("unreachable"), TimeoutError("timed out"),
                      http.client.IncompleteRead(b"partial", 100)]:
            with self.subTest(error=error), self.assertRaises(ttsimages.ImageError):
                ttsimages.check_url("https://example.org/image", opener=Mock(side_effect=error))

    def test_missing_and_malformed_urls_fail(self):
        for url in ("", "not-a-url"):
            with self.subTest(url=url), self.assertRaises(ttsimages.ImageError):
                ttsimages.check_url(url)

    def test_304_requires_previously_verified_bytes_and_a_conditional_request(self):
        valid = {"format": "png", "size": len(png()), "etag": '"version1"'}
        for previous in (None, {"etag": '"version1"'}, {"format": "png", "size": 100}, valid):
            opener = Mock(side_effect=urllib.error.HTTPError("https://example.org", 304, "Not modified", {}, io.BytesIO()))
            with self.subTest(previous=previous):
                if previous == valid:
                    metadata, unchanged = ttsimages.check_url("https://example.org/image", previous, opener)
                    self.assertTrue(unchanged)
                    self.assertEqual(metadata, valid)
                    self.assertEqual(opener.call_args.args[0].get_header("If-none-match"), '"version1"')
                else:
                    with self.assertRaises(ttsimages.ImageError):
                        ttsimages.check_url("https://example.org/image", previous, opener)

    def test_modified_since_fallback_and_changed_response_revalidation(self):
        previous = {"format": "png", "size": len(png()), "modified": "Wed, 01 Jan 2025 00:00:00 GMT"}
        opener = Mock(return_value=Response())
        _, unchanged = ttsimages.check_url("https://example.org/image", previous, opener)
        self.assertFalse(unchanged)
        self.assertEqual(opener.call_args.args[0].get_header("If-modified-since"), previous["modified"])
        with self.assertRaises(ttsimages.ImageError):
            ttsimages.check_url("https://example.org/image", previous,
                                Mock(return_value=Response(b"broken replacement")))

    def test_supported_format_signatures_and_webp_container_boundary(self):
        # A complete, decodable one-pixel WebP fixture.
        import base64
        webp = base64.b64decode("UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA")
        self.assertEqual(ttsimages.image_format(webp), "webp")
        self.assertEqual(ttsimages.image_format(png()), "png")
        self.assertEqual(ttsimages.image_format(b"\xff\xd8\xff\xe0data\xff\xd9"), "jpeg")
        for bad in (webp[:-1], png()[:-1], b"\xff\xd8\xff\xe0truncated"):
            with self.subTest(bad=bad), self.assertRaises(ttsimages.ImageError):
                ttsimages.image_format(bad)


class BuildValidationTests(unittest.TestCase):
    def test_deduplicates_but_rechecks_on_next_build(self):
        files = {Path("a.ndjson"): export(sheet(), sheet()), Path("b.ndjson"): export(sheet(), sheet())}
        proof = {"format": "png", "size": len(png()), "etag": '"v1"'}
        with tempfile.TemporaryDirectory() as tmp:
            checker = Mock(return_value=(proof, False))
            report = ttsimages.validate(files, Path(tmp) / "cache.db", checker=checker, recheck_days=0)
            self.assertEqual(checker.call_count, 2)
            self.assertEqual((report.checked, report.downloaded, report.unchanged), (2, 2, 0))
            self.assertTrue(all(call.args[1] is None for call in checker.call_args_list))
            checker.reset_mock()
            checker.return_value = proof, True
            report = ttsimages.validate(files, Path(tmp) / "cache.db", checker=checker, recheck_days=0)
            self.assertEqual(checker.call_count, 2)
            self.assertTrue(all(call.args[1]["etag"] == proof["etag"] for call in checker.call_args_list))
            self.assertEqual((report.checked, report.downloaded, report.unchanged), (2, 0, 2))

    def test_recent_checks_skip_the_network_until_they_expire(self):
        files = {Path("a.ndjson"): export(sheet(), sheet())}
        proof = {"format": "webp", "size": 10, "etag": '"v1"'}
        day = 86400
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cache.db"
            checker = Mock(return_value=(proof, False))
            ttsimages.validate(files, db, checker=checker, recheck_days=7, now=1000 * day)
            self.assertEqual(checker.call_count, 2)                       # new: downloaded
            checker.reset_mock()
            report = ttsimages.validate(files, db, checker=checker, recheck_days=7, now=1006 * day)
            self.assertEqual(checker.call_count, 0)                       # 6 days: trusted
            self.assertEqual((report.checked, report.cached), (2, 2))
            checker.return_value = proof, True
            report = ttsimages.validate(files, db, checker=checker, recheck_days=7, now=1008 * day)
            self.assertEqual(checker.call_count, 2)                       # 8 days: rechecked
            self.assertEqual((report.checked, report.unchanged, report.cached), (2, 2, 0))
            checker.reset_mock()
            ttsimages.validate(files, db, checker=checker, recheck_days=7, now=1009 * day)
            self.assertEqual(checker.call_count, 0)                       # the recheck renewed it

    def test_a_new_url_is_always_checked_even_beside_cached_ones(self):
        proof = {"format": "webp", "size": 10}
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cache.db"
            checker = Mock(return_value=(proof, False))
            ttsimages.validate({Path("a.ndjson"): export(sheet())}, db, checker=checker, now=100)
            checker.reset_mock()
            new = sheet(front="https://example.org/new.webp")
            ttsimages.validate({Path("a.ndjson"): export(sheet(), new)}, db, checker=checker, now=200)
            self.assertEqual([c.args[0] for c in checker.call_args_list], ["https://example.org/new.webp"])

    def test_failed_urls_are_not_cached_and_include_deck_and_role(self):
        files = {Path("owner/Bad.ndjson"): export(sheet(), sheet("https://example.org/missing"))}
        proof = {"format": "png", "size": len(png())}
        def check(url, previous):
            if url.endswith("/missing"):
                self.assertIsNone(previous)
                raise ttsimages.ImageError("HTTP 404")
            return proof, False
        with tempfile.TemporaryDirectory() as tmp:
            for _ in range(2):
                with self.assertRaises(ttsimages.ValidationError) as caught:
                    ttsimages.validate(files, Path(tmp) / "cache.db", checker=check)
                self.assertIn("HTTP 404: https://example.org/missing", str(caught.exception))
                self.assertIn("owner/Bad.ndjson: commander 1", str(caught.exception))

    def test_normal_and_check_builds_fail_before_any_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "docs"
            out.mkdir()
            existing = out / "index.html"
            existing.write_text("previous catalog")
            for flags in ([], ["--check"]):
                with self.subTest(flags=flags), ExitStack() as stack:
                    stack.enter_context(patch.object(sys, "argv", ["build_site.py", "--quiet", *flags]))
                    stack.enter_context(patch.object(build_site.toollog, "record"))
                    stack.enter_context(patch.object(build_site.workspace, "site_dir", return_value=out))
                    for name in ("CardQuery", "ImageQuery", "SymbolQuery"):
                        stack.enter_context(patch.object(build_site, name))
                    stack.enter_context(patch.object(build_site, "plan", return_value={existing: "new catalog"}))
                    error = ttsimages.ValidationError({"bad": "HTTP 404"}, {"bad": {"owner/deck"}})
                    validate = stack.enter_context(patch.object(ttsimages, "validate", side_effect=error))
                    sync = stack.enter_context(patch.object(build_site, "sync"))
                    stderr = stack.enter_context(redirect_stderr(io.StringIO()))
                    self.assertEqual(build_site.main(), 1)
                    validate.assert_called_once()
                    sync.assert_not_called()
                    self.assertEqual(existing.read_text(), "previous catalog")
                    self.assertIn("HTTP 404", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
