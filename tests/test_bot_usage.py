from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))
import usage


def snapshot(used=80):
    return {"rateLimits": {"limitId": "codex", "primary": {
        "usedPercent": used, "windowDurationMins": 300, "resetsAt": 1791528082,
    }, "secondary": {"usedPercent": 41, "windowDurationMins": 10080}}}


class FormatTests(unittest.TestCase):
    def test_account_windows_and_discord_resets(self):
        text = usage.format_limits(snapshot(), "test-model", discord=True)
        self.assertIn("test-model", text)
        self.assertIn("shared account", text)
        self.assertIn("5h: 20% left (resets <t:1791528082:R>)", text)
        self.assertIn("weekly: 59% left", text)
        self.assertIn("2026-10-09 06:41 UTC", usage.format_limits(snapshot(), "test"))

    def test_multiple_buckets_do_not_duplicate_legacy(self):
        data = snapshot()
        data["rateLimitsByLimitId"] = {
            "codex": data["rateLimits"],
            "other": {"limitName": "Other model", "primary": {"usedPercent": 25}},
        }
        text = usage.format_limits(data, "test")
        self.assertEqual(text.count("shared account"), 1)
        self.assertIn("Other model — primary: 75% left", text)

    def test_unknown_or_exhausted_usage_is_not_fabricated(self):
        for used in (None, "80", float("nan"), True, -1):
            with self.subTest(used=used):
                self.assertIn("5h: unavailable", usage.format_limits(snapshot(used), "test"))
        self.assertIn("5h: 0% left", usage.format_limits(snapshot(130), "test"))
        self.assertIn("Unavailable", usage.format_limits({}, "test"))

    def test_credit_only_and_blocked_accounts(self):
        data = {"ordinaryUsageAllowed": False, "rateLimits": {
            "credits": {"hasCredits": True, "balance": "12.50"},
        }}
        text = usage.format_limits(data, "test")
        self.assertIn("credits: 12.50", text)
        self.assertIn("currently blocked", text)
        self.assertNotIn("%", text)

    def test_failure_is_safe_and_never_claims_zero_remaining(self):
        with patch.object(usage, "read_limits", side_effect=OSError("secret from subprocess")):
            text = usage.report("codex", "test")
        self.assertIn("Unavailable", text)
        self.assertNotIn("secret", text)
        self.assertNotIn("0%", text)


class ProtocolTests(unittest.TestCase):
    def fake_codex(self, directory: str, body: str) -> Path:
        script = Path(directory) / "codex"
        script.write_text(f"#!{sys.executable}\n" + body)
        script.chmod(0o755)
        return script

    def test_handshake_notification_and_partial_reads_without_a_model_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = Path(tmp) / "calls.json"
            script = self.fake_codex(tmp, f'''
import json, sys, time
assert sys.argv[1:] == ['app-server', '--listen', 'stdio://']
init = json.loads(sys.stdin.readline())
assert init['method'] == 'initialize'
print(json.dumps({{'id': init['id'], 'result': {{}}}}), flush=True)
ready = json.loads(sys.stdin.readline())
query = json.loads(sys.stdin.readline())
assert ready['method'] == 'initialized'
assert query['method'] == 'account/rateLimits/read'
with open({str(calls)!r}, 'w') as f:
    json.dump([init['method'], ready['method'], query['method']], f)
reply = json.dumps({{'id': query['id'], 'result': {snapshot()!r}}}) + '\\n'
sys.stdout.write('{{"method":"notice"}}\\n' + reply[:20]); sys.stdout.flush()
time.sleep(0.01)
sys.stdout.write(reply[20:]); sys.stdout.flush()
time.sleep(30)
''')
            self.assertEqual(usage.read_limits(str(script), timeout=2), snapshot())
            self.assertEqual(json.loads(calls.read_text()),
                             ["initialize", "initialized", "account/rateLimits/read"])

    def test_timeout_reaps_the_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "pid"
            script = self.fake_codex(tmp, f"import os, time\nopen({str(pidfile)!r}, 'w').write(str(os.getpid()))\ntime.sleep(30)\n")
            started = time.monotonic()
            with self.assertRaisesRegex(usage.UsageUnavailable, "timed out"):
                usage.read_limits(str(script), timeout=0.3)
            self.assertLess(time.monotonic() - started, 2)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pidfile.read_text()), 0)

    def test_rpc_errors_and_malformed_output_are_unavailable(self):
        for line in ('{"id":1,"error":{"message":"private account detail"}}', 'not-json'):
            with self.subTest(line=line), tempfile.TemporaryDirectory() as tmp:
                script = self.fake_codex(tmp, f"import sys, time\nsys.stdin.readline()\nprint({line!r}, flush=True)\ntime.sleep(30)\n")
                text = usage.report(str(script), "test")
                self.assertIn("Unavailable", text)
                self.assertNotIn("private account detail", text)


class BuilderTests(unittest.TestCase):
    def setUp(self):
        import bot
        self.bot = bot
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(bot, "log", return_value=Mock()))
        self.report = self.stack.enter_context(patch.object(bot.usage, "report", return_value="USAGE"))

    def test_usage_command_bypasses_the_busy_lock_and_model(self):
        with patch.object(self.bot, "_claim_bot") as claim, patch.object(self.bot, "_run") as run:
            for message in usage.USAGE_COMMANDS:
                self.assertEqual(self.bot.send(message.upper(), "zzwang"), "USAGE")
            claim.assert_not_called()
            run.assert_not_called()

    def test_busy_reply_has_usage(self):
        with patch.object(self.bot, "_claim_bot", side_effect=self.bot.Busy):
            self.assertEqual(self.bot.send("build a deck", "zzwang"), self.bot.BUSY_REPLY + "\n\nUSAGE")

    def test_exact_deck_commands_remain_importable(self):
        with patch.object(self.bot.commands, "handle", return_value=["1 Sol Ring\n1 Island\n"]):
            self.assertEqual(self.bot.send("!deck test", "zzwang"), "1 Sol Ring\n1 Island\n")
        self.report.assert_not_called()

    def test_fresh_and_resumed_replies_have_one_footer(self):
        bot = self.bot
        for sid in (None, "11111111-1111-1111-1111-111111111111"):
            with self.subTest(sid=sid), contextlib.ExitStack() as stack:
                for name, value in {
                    "_claim_bot": Mock(), "_release_bot": None,
                    "session_id": sid,
                    "_run": ("answer", "session id: 11111111-1111-1111-1111-111111111111"),
                    "_finish": "answer",
                }.items():
                    stack.enter_context(patch.object(bot, name, return_value=value))
                stack.enter_context(patch.object(bot.build_agents, "build", return_value=(False, "ok")))
                stack.enter_context(patch.object(bot, "_creation_lock", return_value=contextlib.nullcontext()))
                tmp = stack.enter_context(tempfile.TemporaryDirectory())
                stack.enter_context(patch.object(bot, "SESSIONS", Path(tmp)))
                stack.enter_context(patch.dict(os.environ, {"MTG_DECKS": tmp}))
                self.assertEqual(bot.send("build a deck", "zzwang", discord=True), "answer\n\nUSAGE")
                # The session runs in the asker's own folder, which it creates.
                self.assertTrue((Path(tmp) / "zzwang").is_dir())
        self.assertEqual(self.report.call_count, 2)
        self.assertTrue(self.report.call_args.kwargs["discord"])

    def test_a_username_that_cannot_have_a_folder_never_reaches_the_model(self):
        with patch.object(self.bot, "_claim_bot") as claim, patch.object(self.bot, "_run") as run:
            for name in ("../zzwang", "img", "Bracket3", "a/b"):
                with self.subTest(name=name):
                    self.assertIn("can't build decks", self.bot.send("build a deck", name))
            claim.assert_not_called()
            run.assert_not_called()

    def test_cli_usage_needs_no_username(self):
        with patch.object(sys, "argv", ["bot.py", "--usage"]), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(self.bot.main(), 0)
        self.assertEqual(output.getvalue(), "USAGE\n")


if __name__ == "__main__":
    unittest.main()
