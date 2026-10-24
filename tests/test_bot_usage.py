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
import _paths  # noqa: F401  (scripts/<area>/ on sys.path)
import usage


def snapshot(used=80):
    return {"rateLimits": {"limitId": "codex", "primary": {
        "usedPercent": used, "windowDurationMins": 300, "resetsAt": 1791528082,
    }, "secondary": {"usedPercent": 41, "windowDurationMins": 10080}}}


class FormatTests(unittest.TestCase):
    def test_account_windows_and_discord_resets(self):
        text = usage.format_limits(snapshot(), "test-model", discord=True)
        self.assertNotIn("test-model", text)          # players never see the model
        self.assertNotIn("Codex", text)
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
        self.assertEqual(len(text.splitlines()), 3)    # header + one line per bucket, no duplicate
        self.assertIn("primary: 75% left", text)
        self.assertNotIn("Other model", text)

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


AGY_USAGE = {"groups": [
    {"name": "Gemini Models", "buckets": [
        {"window": "weekly", "remaining_fraction": 0.9661, "reset_time": "2026-10-26T01:01:47Z"},
        {"window": "5h", "remaining_fraction": 0.9346, "reset_time": "2026-10-19T15:06:08Z"}]},
    {"name": "Claude and GPT models", "buckets": [
        {"window": "weekly", "remaining_fraction": 1, "reset_time": "2026-10-26T10:48:08Z"},
        {"window": "5h", "remaining_fraction": 1, "reset_time": "2026-10-19T15:48:08Z"}]},
    {"name": "Gemini 4 Argon", "buckets": [
        {"window": "weekly", "remaining_fraction": 0.6785, "reset_time": "2026-10-26T00:47:19Z"}]}]}


class AgyUsageTests(unittest.TestCase):
    def test_the_footer_matches_the_codex_shape_for_the_models_group(self):
        text = usage.format_agy(AGY_USAGE, "gemini-3.8-flash-high")
        self.assertEqual(text, "Usage remaining\n"
                               "5h: 93% left (resets 2026-10-19 15:06 UTC) · "
                               "weekly: 97% left (resets 2026-10-26 01:01 UTC)")

    def test_each_model_reads_its_own_group(self):
        self.assertEqual(usage.format_agy(AGY_USAGE, "gemini-4-argon-high").splitlines()[1],
                         "weekly: 68% left (resets 2026-10-26 00:47 UTC)")
        self.assertIn("5h: 100% left", usage.format_agy(AGY_USAGE, "claude-opus-5-5-high"))
        self.assertIn("5h: 93% left", usage.format_agy(AGY_USAGE, "gemini-3.8-flash-high"))
        self.assertEqual(len(usage.format_agy(AGY_USAGE, "mystery").splitlines()), 2)  # one group

    def test_no_model_harness_or_vendor_is_named(self):
        for model in ("gemini-3.8-flash-high", "gemini-4-argon-high", "claude-opus-5-5-high"):
            text = usage.format_agy(AGY_USAGE, model, discord=True)
            for word in ("gemini", "argon", "claude", "gpt", "codex", "antigravity", "agy", model):
                self.assertNotIn(word, text.lower(), (model, word))

    def test_discord_gets_relative_timestamps(self):
        self.assertIn("(resets <t:1792422368:R>)", usage.format_agy(AGY_USAGE, "gemini-3.8-flash-high", discord=True))

    def test_reads_the_usage_panel_from_agy_and_never_invents_a_quota(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "agy"
            reply = {"conversation_id": "", "status": "SUCCESS", "response": "table",
                     "command": {"name": "usage", "data": AGY_USAGE}}
            fake.write_text(f"#!/usr/bin/env python3\nimport sys, os\nassert sys.argv[1:] == ['--print=/usage', '--output-format', 'json']\n"
                            f"assert os.environ['HOME'] == {tmp!r}\nprint({json.dumps(json.dumps(reply))})\n")
            fake.chmod(0o755)
            self.assertIn("5h: 93% left", usage.agy_report(str(fake), tmp, "gemini-3.8-flash-high"))
            fake.write_text("#!/bin/sh\necho not-json\n")
            self.assertIn("Unavailable", usage.agy_report(str(fake), tmp, "gemini-3.8-flash-high"))


class BuilderTests(unittest.TestCase):
    def setUp(self):
        import bot
        self.bot = bot
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(bot, "log", return_value=Mock()))
        self.report = self.stack.enter_context(patch.object(bot.HARNESS, "usage", return_value="USAGE"))

    def test_usage_command_bypasses_the_busy_lock_and_model(self):
        with patch.object(self.bot, "_claim_bot") as claim, patch.object(self.bot, "_turn") as run:
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
                    "_turn": bot.harness.Turn("answer", "11111111-1111-1111-1111-111111111111", ""),
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
        with patch.object(self.bot, "_claim_bot") as claim, patch.object(self.bot, "_turn") as run:
            for name in ("../zzwang", "img", "Bracket3", "a/b"):
                with self.subTest(name=name):
                    self.assertIn("can't build decks", self.bot.send("build a deck", name))
            claim.assert_not_called()
            run.assert_not_called()

    def test_a_harness_without_usage_adds_no_footer(self):
        bot = self.bot
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(bot.HARNESS, "usage", return_value=""))
            stack.enter_context(patch.object(bot, "_claim_bot", side_effect=bot.Busy))
            self.assertEqual(bot.send("build a deck", "zzwang"), bot.BUSY_REPLY)
            self.assertEqual(bot.send("usage", "zzwang"), "Usage remaining\nUnavailable right now.")

    def test_a_new_session_is_pinned_with_its_harness_and_model(self):
        bot = self.bot
        with contextlib.ExitStack() as stack:
            for name, value in {"_claim_bot": Mock(), "_release_bot": None, "_finish": "answer",
                                "_turn": bot.harness.Turn("answer", "conv-1", "")}.items():
                stack.enter_context(patch.object(bot, name, return_value=value))
            stack.enter_context(patch.object(bot.build_agents, "build", return_value=(False, "ok")))
            stack.enter_context(patch.object(bot, "_creation_lock", return_value=contextlib.nullcontext()))
            tmp = stack.enter_context(tempfile.TemporaryDirectory())
            stack.enter_context(patch.object(bot, "SESSIONS", Path(tmp)))
            stack.enter_context(patch.dict(os.environ, {"MTG_DECKS": tmp}))
            bot.send("build a deck", "zzwang")
            saved = json.loads(next(Path(tmp).glob("*.json")).read_text())
            self.assertEqual((saved["session_id"], saved["harness"], saved["model"]),
                             ("conv-1", bot.HARNESS.name, bot.MODEL))
            # Another harness's session (or one saved before harnesses: Codex's) is not resumed.
            key = next(Path(tmp).glob("*.json")).stem
            self.assertEqual(bot.session_id(key), "conv-1")
            other = {**saved, "harness": "elsewhere"}
            (Path(tmp) / f"{key}.json").write_text(json.dumps(other))
            self.assertIsNone(bot.session_id(key))
            legacy = {k: v for k, v in saved.items() if k != "harness"}
            (Path(tmp) / f"{key}.json").write_text(json.dumps(legacy))
            if bot.HARNESS.name != "codex":
                self.assertIsNone(bot.session_id(key))

    def test_running_out_of_allowance_is_one_neutral_line(self):
        footer = ("Usage remaining\n5h: 40% left (resets <t:1792422368:R>) · "
                  "weekly: 0% left (resets <t:1792976507:R>)")
        argv = ["bot.py", "--discord", "--user", "zzwang", "--", "build a deck"]
        quota = self.bot.harness.QuotaExhausted("You have exhausted your quota on this model. (gemini)")
        with patch.object(sys, "argv", argv), patch.object(self.bot, "send", side_effect=quota), \
                patch.object(self.bot.HARNESS, "usage", return_value=footer), \
                contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.bot.main(), 1)
        # The spent weekly window decides when to come back, not the 5-hour one.
        self.assertEqual(err.getvalue(), "deck builder usage limit reached; try again at <t:1792976507:R>.\n")
        for leak in ("gemini", "agy", "codex", self.bot.MODEL):
            self.assertNotIn(leak.lower(), err.getvalue().lower())

    def test_cli_usage_needs_no_username(self):
        with patch.object(sys, "argv", ["bot.py", "--usage"]), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(self.bot.main(), 0)
        self.assertEqual(output.getvalue(), "USAGE\n")


class GeminiImageQuotaTests(unittest.TestCase):
    def test_parse_image_quota_error(self):
        sample = """
        error generating image: failed to generate content: 429 Too Many Requests, body: {
          "error": {
            "code": 429,
            "message": "You have exhausted your capacity on this model.",
            "status": "RESOURCE_EXHAUSTED",
            "details": [
              {
                "metadata": {
                  "model": "gemini-3.1-flash-image",
                  "quotaResetTimeStamp": "2026-10-26T02:59:39Z"
                }
              }
            ]
          }
        }
        """
        info = usage.parse_image_quota_error(sample)
        self.assertIsNotNone(info)
        self.assertEqual(info["model"], "gemini-3.1-flash-image")
        self.assertEqual(info["resets_iso"], "2026-10-26T02:59:39Z")
        self.assertEqual(info["resets_at"], 1792983579.0)

        # None on unrelated errors
        self.assertIsNone(usage.parse_image_quota_error("random error text"))
        self.assertIsNone(usage.parse_image_quota_error("gemini-3.8-flash-high RESOURCE_EXHAUSTED"))

    def test_record_read_and_exhausted_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            # No record yet
            self.assertEqual(usage.is_image_quota_exhausted(home), (False, None, None))
            self.assertEqual(usage.format_image_quota(home), "Image (gemini-3.1-flash-image): available")

            # Active exhaustion in future
            future = time.time() + 3600
            usage.record_image_quota(home, {
                "model": "gemini-3.1-flash-image",
                "resets_at": future,
                "resets_iso": "2026-10-26T02:59:39Z",
            })
            exhausted, resets_iso, resets_at = usage.is_image_quota_exhausted(home)
            self.assertTrue(exhausted)
            self.assertEqual(resets_at, future)
            self.assertEqual(resets_iso, "2026-10-26T02:59:39Z")

            # Formatting
            text_plain = usage.format_image_quota(home, discord=False)
            self.assertIn("Image (gemini-3.1-flash-image): 0% left (resets ", text_plain)
            text_discord = usage.format_image_quota(home, discord=True)
            self.assertIn(f"<t:{int(future)}:R>", text_discord)

            # Expired exhaustion in past
            past = time.time() - 100
            usage.record_image_quota(home, {
                "model": "gemini-3.1-flash-image",
                "resets_at": past,
                "resets_iso": "2026-10-20T00:00:00Z",
            })
            self.assertEqual(usage.is_image_quota_exhausted(home), (False, None, None))
            self.assertEqual(usage.format_image_quota(home), "Image (gemini-3.1-flash-image): available")

    def test_format_agy_includes_image_when_is_image_is_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            future = 1792983579.0
            usage.record_image_quota(home, {
                "model": "gemini-3.1-flash-image",
                "resets_at": future,
                "resets_iso": "2026-10-26T02:59:39Z",
            })
            # When is_image=False: no image line
            text_builder = usage.format_agy(AGY_USAGE, "gemini-3.8-flash-high", image_home=home, is_image=False)
            self.assertNotIn("gemini-3.1-flash-image", text_builder)

            # When is_image=True: has image line
            text_sleever = usage.format_agy(AGY_USAGE, "gemini-3.8-flash-high", image_home=home, is_image=True, discord=True)
            self.assertIn("Image (gemini-3.1-flash-image): 0% left (resets <t:1792983579:R>)", text_sleever)
            self.assertIn("5h: 93% left", text_sleever)

    def test_check_session_image_quota_distinguishes_turns_in_same_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            conv_id = "test-conv-123"
            brain = home / ".gemini" / "antigravity-cli" / "brain" / conv_id
            logs_dir = brain / ".system_generated" / "logs"
            subagents_dir = brain / ".system_generated" / "subagents"
            logs_dir.mkdir(parents=True)
            subagents_dir.mkdir(parents=True)

            future = time.time() + 3600
            future_iso = "2026-10-26T02:59:39Z"

            # Create subagent 1 transcript (old turn: success)
            sa1_id = "subagent-1"
            sa1_log = home / ".gemini" / "antigravity-cli" / "brain" / sa1_id / ".system_generated" / "logs"
            sa1_log.mkdir(parents=True)
            (sa1_log / "transcript.jsonl").write_text('{"step_index": 1, "type": "GENERIC", "content": "saved sleeve"}\n')
            (subagents_dir / f"{sa1_id}.json").write_text(json.dumps({
                "conversationId": sa1_id,
                "spawnStepIndex": 5,
            }))

            # Create subagent 2 transcript (turn 2: quota error)
            sa2_id = "subagent-2"
            sa2_log = home / ".gemini" / "antigravity-cli" / "brain" / sa2_id / ".system_generated" / "logs"
            sa2_log.mkdir(parents=True)
            sa2_error = f'{{"model": "gemini-3.1-flash-image", "status": "RESOURCE_EXHAUSTED", "quotaResetTimeStamp": "{future_iso}"}}'
            (sa2_log / "transcript.jsonl").write_text(json.dumps({"step_index": 2, "error": sa2_error}) + "\n")
            (subagents_dir / f"{sa2_id}.json").write_text(json.dumps({
                "conversationId": sa2_id,
                "spawnStepIndex": 25,
            }))

            # Session transcript has:
            # - Request 1 at step 0
            # - Request 2 at step 20 (where subagent 2 spawned)
            transcript = logs_dir / "transcript.jsonl"
            transcript.write_text(
                json.dumps({"step_index": 0, "type": "USER_INPUT", "content": "prompt 1"}) + "\n" +
                json.dumps({"step_index": 5, "type": "PLANNER_RESPONSE"}) + "\n" +
                json.dumps({"step_index": 20, "type": "USER_INPUT", "content": "prompt 2"}) + "\n" +
                json.dumps({"step_index": 25, "type": "PLANNER_RESPONSE"}) + "\n"
            )

            # Turn 2: checks current request (starts at step 20) -> finds subagent 2 quota error
            info = usage.check_session_image_quota(home, conv_id)
            self.assertIsNotNone(info)
            self.assertEqual(info["model"], "gemini-3.1-flash-image")
            self.assertEqual(info["resets_iso"], future_iso)

            # Turn 3: user sends a new prompt at step 40
            transcript.write_text(
                transcript.read_text() +
                json.dumps({"step_index": 40, "type": "USER_INPUT", "content": "prompt 3"}) + "\n"
            )
            # Now last USER_INPUT is step 40; subagent 2 (spawnStepIndex 25) belongs to prior turn
            info_turn3 = usage.check_session_image_quota(home, conv_id)
            self.assertIsNone(info_turn3)


class SleeverImageQuotaTests(unittest.TestCase):
    def test_send_sleever_uses_secondary_workaround_when_image_quota_is_exhausted(self):
        import bot
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            future = 1792983579.0
            usage.record_image_quota(home, {
                "model": "gemini-3.1-flash-image",
                "resets_at": future,
                "resets_iso": "2026-10-26T02:59:39Z",
            })
            with patch.object(bot.HARNESS, "home", home), \
                 patch.object(bot.HARNESS, "name", "agy"), \
                 patch.object(bot.HARNESS, "images", True), \
                 patch.object(bot, "_claim_bot"), \
                 patch.object(bot, "_autopush"), \
                 patch.object(bot.HARNESS, "run") as mock_run, \
                 patch.object(bot.sleever, "generate_secondary_image") as mock_gen, \
                 patch.object(bot.sleever, "publish", return_value=("Made **Sleeves** sleeves.\n\n*(Using secondary image gen workaround)*", "sleeves")), \
                 patch.object(bot.HARNESS, "usage", return_value="Image (gemini-3.1-flash-image): 0% left"):
                reply = bot.send_sleever("make me sleeves", "zzwang", discord=True)
                # Primary model harness is NOT called
                mock_run.assert_not_called()
                # Secondary generator is called
                mock_gen.assert_called_once()
                self.assertIn("secondary image gen workaround", reply)
                self.assertIn("Image (gemini-3.1-flash-image): 0% left", reply)

    def test_send_sleever_fails_with_quota_when_secondary_also_fails(self):
        import bot
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            future = 1792983579.0
            usage.record_image_quota(home, {
                "model": "gemini-3.1-flash-image",
                "resets_at": future,
                "resets_iso": "2026-10-26T02:59:39Z",
            })
            with patch.object(bot.HARNESS, "home", home), \
                 patch.object(bot.HARNESS, "name", "agy"), \
                 patch.object(bot.HARNESS, "images", True), \
                 patch.object(bot, "_claim_bot"), \
                 patch.object(bot.HARNESS, "run") as mock_run, \
                 patch.object(bot.sleever, "generate_secondary_image", side_effect=RuntimeError("browser closed")), \
                 patch.object(bot.HARNESS, "usage", return_value="Image (gemini-3.1-flash-image): 0% left"):
                reply = bot.send_sleever("make me sleeves", "zzwang", discord=True)
                mock_run.assert_not_called()
                self.assertIn("quota on gemini-3.1-flash-image has been exhausted", reply)
                self.assertIn("<t:1792983579:R>", reply)
                self.assertIn("Secondary image generation also failed: browser closed", reply)
                self.assertIn("Image (gemini-3.1-flash-image): 0% left", reply)


if __name__ == "__main__":
    unittest.main()
