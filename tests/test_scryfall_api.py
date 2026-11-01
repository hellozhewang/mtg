"""cardlib.api: a 429 or a 5xx from Scryfall is waited out, not fatal."""
from __future__ import annotations

import email.message
import io
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _paths  # noqa: E402,F401  (scripts/<area>/ on sys.path)

from cardlib import api  # noqa: E402


def error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://api.scryfall.com", code, "x", headers, io.BytesIO(b"{}"))


class Ok(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def run(*responses):
    """GET through ScryfallAPI with urlopen answering `responses` in turn; returns
    (result or error, the waits slept beyond the polite delay)."""
    replies = iter(responses)

    def urlopen(_req):
        r = next(replies)
        if isinstance(r, Exception):
            raise r
        return Ok(r)

    slept: list[float] = []
    with patch.object(api.urllib.request, "urlopen", urlopen), \
            patch.object(api.time, "sleep", slept.append):
        client = api.ScryfallAPI(delay=0)
        try:
            got = client._get("/cards/named", {"exact": "Sol Ring"})
        except api.ScryfallError as exc:
            got = exc
    return got, [s for s in slept if s], client.calls


class RetryTests(unittest.TestCase):
    def test_a_rate_limit_waits_then_succeeds(self):
        got, waits, calls = run(error(429), b'{"name": "Sol Ring"}')
        self.assertEqual((got, waits, calls), ({"name": "Sol Ring"}, [api.RATE_LIMIT_WAIT], 2))

    def test_retry_after_is_honoured_and_capped(self):
        self.assertEqual(run(error(429, "5"), b"{}")[1], [5.0])
        self.assertEqual(run(error(429, "600"), b"{}")[1], [api.RATE_LIMIT_WAIT])

    def test_a_server_error_backs_off(self):
        got, waits, _ = run(error(503), error(502), b"{}")
        self.assertEqual((got, waits), ({}, [1, 2]))

    def test_it_gives_up_after_the_retries(self):
        got, waits, calls = run(*[error(429)] * (api.RETRIES + 1))
        self.assertIsInstance(got, api.ScryfallError)
        self.assertEqual((len(waits), calls), (api.RETRIES, api.RETRIES + 1))

    def test_other_errors_are_not_retried(self):
        got, waits, calls = run(error(400))
        self.assertIsInstance(got, api.ScryfallError)
        self.assertEqual((waits, calls), ([], 1))
        self.assertEqual(run(error(404))[0]["data"], [])


if __name__ == "__main__":
    unittest.main()
