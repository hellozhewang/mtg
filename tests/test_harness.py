"""The builder's harnesses (scripts/discord/bot/harness.py) and the OS sandbox around them (scripts/discord/bot/sandbox.py).

The sandbox tests run the real macOS `sandbox-exec`: the profile is the only thing
keeping a turbo-mode agent inside the asker's deck folder, so it is tested by trying
to escape it, not by reading it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import _paths  # noqa: F401  (scripts/<area>/ on sys.path)

import harness
import sandbox

DARWIN = sys.platform == "darwin" and Path(sandbox.SANDBOX_EXEC).exists()


def fake_agy(folder: Path, reply: dict | None = None, exit_code: int = 0) -> Path:
    """An executable standing in for agy: records its argv, cwd and HOME, prints `reply`."""
    script = folder / "agy"
    record = folder / "record.json"
    reply = reply if reply is not None else {"conversation_id": "conv-9", "status": "SUCCESS",
                                              "response": "built it\n"}
    script.write_text(f"""#!/usr/bin/env python3
import json, os, sys
json.dump({{"argv": sys.argv[1:], "cwd": os.getcwd(), "home": os.environ.get("HOME"),
           "path": os.environ.get("PATH"), "chan": os.environ.get("MTG_TOOL_CHANNEL")}},
          open({str(record)!r}, "w"))
print("some progress line")
print({json.dumps(json.dumps(reply))})
sys.exit({exit_code})
""")
    script.chmod(0o755)
    return script


class AgyArgsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.h = harness.AgyHarness(exe=str(fake_agy(self.dir)), home=self.dir / "home")

    def test_turbo_json_and_a_dash_message_as_one_argument(self):
        args = self.h.args("- give me the list", None, 600)
        self.assertIn("--dangerously-skip-permissions", args)
        self.assertIn("--disable-slash-commands", args)     # "/model …" from Discord is just text
        self.assertEqual(args[args.index("--model") + 1], "gemini-3.8-flash-high")
        self.assertEqual(args[args.index("--output-format") + 1], "json")
        self.assertEqual(args[-1], "--print=- give me the list")
        self.assertNotIn("--conversation", args)

    def test_resume_names_the_conversation(self):
        args = self.h.args("next", "conv-1", 600)
        self.assertEqual(args[args.index("--conversation") + 1], "conv-1")

    def test_parse_takes_the_json_result_among_other_output(self):
        data = harness.AgyHarness.parse('starting\n{"oops"\n{"conversation_id":"c","status":"SUCCESS"}\n')
        self.assertEqual(data["conversation_id"], "c")
        with self.assertRaises(harness.HarnessError):
            harness.AgyHarness.parse("no json here\n")

    def test_prepare_copies_a_newer_sign_in_and_sets_turbo(self):
        real = self.dir / "realhome"
        token = real / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"
        token.parent.mkdir(parents=True)
        token.write_text("TOKEN-1")
        with patch.object(harness.Path, "home", return_value=real):
            self.h.prepare(self.dir / "public")
            copied = self.h.home / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"
            self.assertEqual(copied.read_text(), "TOKEN-1")
            self.assertEqual(oct(copied.stat().st_mode & 0o777), "0o600")
            token.write_text("TOKEN-2")
            os.utime(token, (copied.stat().st_mtime + 10,) * 2)
            self.h.prepare(self.dir / "public")
            self.assertEqual(copied.read_text(), "TOKEN-2")
        settings = json.loads((self.h.home / ".gemini" / "antigravity-cli" / "settings.json").read_text())
        self.assertEqual(settings["trustedWorkspaces"], [str(self.dir / "public")])
        config = json.loads((self.h.home / ".gemini" / "config" / "config.json").read_text())
        self.assertEqual(config["userSettings"]["permissionPreset"], "AGENT_PERMISSION_PRESET_TURBO")


@unittest.skipUnless(DARWIN, "macOS sandbox-exec only")
class AgyRunTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name).resolve()
        self.folder = self.dir / "public" / "zzwang"
        self.folder.mkdir(parents=True)

    def make(self, **kw) -> harness.AgyHarness:
        return harness.AgyHarness(exe=str(fake_agy(self.dir, **kw)), home=self.dir / "home")

    def test_a_turn_runs_in_the_folder_under_its_own_home_and_returns_the_reply(self):
        h = self.make()
        with patch.object(harness.Path, "home", return_value=self.dir / "nohome"):
            turn = h.run(self.folder, "build a deck", None, chan="c1", timeout=60, writable=[])
        self.assertEqual((turn.answer, turn.session_id), ("built it", "conv-9"))
        record = json.loads((self.dir / "record.json").read_text())
        self.assertEqual(Path(record["cwd"]).resolve(), self.folder)
        self.assertEqual(record["home"], str(self.dir / "home"))
        self.assertEqual(record["chan"], "c1")
        self.assertNotIn("homebrew", record["path"])
        self.assertIn("--print=build a deck", record["argv"])

    def test_failure_status_and_exit_codes_raise(self):
        with patch.object(harness.Path, "home", return_value=self.dir / "nohome"):
            with self.assertRaisesRegex(harness.HarnessError, "status ERROR"):
                self.make(reply={"conversation_id": "x", "status": "ERROR"}).run(
                    self.folder, "hi", None, chan="c", timeout=60, writable=[])
            with self.assertRaisesRegex(harness.HarnessError, "exited 3"):
                self.make(exit_code=3).run(self.folder, "hi", None, chan="c", timeout=60, writable=[])

    def test_an_exhausted_allowance_is_its_own_error(self):
        with patch.object(harness.Path, "home", return_value=self.dir / "nohome"):
            with self.assertRaises(harness.QuotaExhausted):
                self.make(reply={"conversation_id": "x", "status": "ERROR",
                                 "error": "You have exhausted your quota on this model."}).run(
                    self.folder, "hi", None, chan="c", timeout=60, writable=[])

    def test_quota_words_in_a_users_prompt_are_not_an_exhausted_allowance(self):
        self.assertIsNone(harness.QUOTA_RE.search("build me a deck, I have a quota of 3 game changers"))
        for line in ("ERROR: You\u2019ve hit your usage limit. Upgrade to Pro", "insufficient_quota",
                     "You have exhausted your quota on this model.", "429 RESOURCE_EXHAUSTED"):
            self.assertTrue(harness.QUOTA_RE.search(line), line)

    def test_an_empty_reply_is_no_output_and_the_session_is_kept(self):
        h = self.make(reply={"conversation_id": "conv-2", "status": "SUCCESS", "response": ""})
        with patch.object(harness.Path, "home", return_value=self.dir / "nohome"):
            turn = h.run(self.folder, "hi", "conv-2", chan="c", timeout=60, writable=[])
        self.assertEqual((turn.answer, turn.session_id), ("(no output)", "conv-2"))


@unittest.skipUnless(DARWIN, "macOS sandbox-exec only")
class SandboxTests(unittest.TestCase):
    """Escape attempts under the real profile. Temp space is writable by design, so the
    'outside' and 'secret' places live under the repo, not in a temp dir."""

    def setUp(self):
        self.probe = ROOT / "tests" / ".sandbox-probe"
        shutil.rmtree(self.probe, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.probe, True)
        self.inside = self.probe / "inside"
        self.outside = self.probe / "outside"
        self.secret = self.probe / "secret"
        for d in (self.inside, self.outside, self.secret):
            d.mkdir(parents=True)
        (self.secret / "key.txt").write_text("TOPSECRET")
        self.profile = sandbox.profile([self.inside], unreadable=(self.secret,),
                                       no_exec=[Path("/usr/bin/whoami")])

    def sh(self, command: str) -> subprocess.CompletedProcess:
        return subprocess.run(sandbox.wrap(["/bin/sh", "-c", command], self.profile),
                              capture_output=True, text=True, timeout=30)

    def test_writes_only_inside(self):
        self.assertEqual(self.sh(f"echo ok > {self.inside}/a.txt").returncode, 0)
        self.assertEqual((self.inside / "a.txt").read_text(), "ok\n")
        bad = self.sh(f"echo no > {self.outside}/b.txt")
        self.assertNotEqual(bad.returncode, 0)
        self.assertFalse((self.outside / "b.txt").exists())
        self.assertIn("not permitted", bad.stderr.lower())

    def test_the_repo_itself_is_read_only(self):
        self.assertNotEqual(self.sh(f"echo x >> {ROOT}/README.md").returncode, 0)
        self.assertEqual(self.sh(f"head -c 10 {ROOT}/README.md").returncode, 0)

    def test_secrets_cannot_be_read(self):
        out = self.sh(f"cat {self.secret}/key.txt")
        self.assertNotEqual(out.returncode, 0)
        self.assertNotIn("TOPSECRET", out.stdout)

    def test_named_programs_cannot_be_started(self):
        self.assertNotEqual(self.sh("/usr/bin/whoami").returncode, 0)
        self.assertEqual(self.sh("/usr/bin/true").returncode, 0)

    def test_shells_get_a_terminal_and_temp_space(self):
        self.assertEqual(self.sh("mktemp").returncode, 0)

    def test_the_default_profile_covers_ssh_and_agent_clis(self):
        text = sandbox.profile([self.inside])
        self.assertIn(str(Path.home() / ".ssh"), text)
        self.assertIn('(literal "/dev/ptmx")', text)
        for name in ("claude", "codex"):
            found = shutil.which(name)
            if found:
                self.assertIn(found, text)

    def test_unsafe_paths_are_refused(self):
        with self.assertRaises(ValueError):
            sandbox.profile([Path('/tmp/x") (allow file-write*')])


class SelectionTests(unittest.TestCase):
    def test_env_picks_the_harness_and_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = fake_agy(Path(tmp))
            env = {"MTG_BOT_HARNESS": "agy", "MTG_BOT_MODEL": "claude-opus-5-5-high", "MTG_AGY_BIN": str(exe)}
            with patch.dict(os.environ, env):
                h = harness.from_env()
            self.assertEqual((h.name, h.model), ("agy", "claude-opus-5-5-high"))

    def test_unknown_harness_is_an_error(self):
        with patch.dict(os.environ, {"MTG_BOT_HARNESS": "nope"}):
            with self.assertRaises(harness.HarnessError):
                harness.from_env()

    @unittest.skipUnless(shutil.which("codex"), "codex not installed")
    def test_codex_args_resume_and_confine(self):
        h = harness.CodexHarness()
        args = h.args(Path("/d/public/zz"), "- list", "sess-1", Path("/tmp/out.txt"), [Path("/d/.cache")])
        self.assertEqual(args[args.index("-C") + 1], "/d/public/zz")
        self.assertEqual(args[args.index("--add-dir") + 1], "/d/.cache")
        self.assertEqual(args[-4:], ["resume", "sess-1", "--", "- list"])


if __name__ == "__main__":
    unittest.main()
