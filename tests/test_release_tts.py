"""scripts/tabletop/release_tts.py: version numbers and patch notes (the PC side is not run here)."""
from __future__ import annotations

import sys
import json
import tempfile
import unittest
from unittest.mock import patch, Mock
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _paths  # noqa: F401  (scripts/<area>/ on sys.path)

import release_tts

LOG = "# Cactuar table\n\nIntro.\n\n## v28 — 2026-10-19 (test build)\n- Louder.\n\n## v3–v10 — 2026-10-18\n- Old.\n"


class ChangelogTests(unittest.TestCase):
    def test_the_current_version_is_the_highest_entry(self):
        self.assertEqual(release_tts.current_version(LOG), 28)
        self.assertGreaterEqual(release_tts.current_version(release_tts.CHANGELOG.read_text()), 29)

    def test_a_new_entry_goes_above_the_newest(self):
        out = release_tts.add_entry(LOG, 29, ["Sleeves menu", " ", "Louder clips"], "abc1234", "2026-10-20")
        self.assertIn("Intro.\n\n## v29 — 2026-10-20 (commit abc1234)\n- Sleeves menu\n- Louder clips\n\n## v28", out)
        self.assertEqual(release_tts.current_version(out), 29)

    def test_the_pc_details_are_not_in_the_repo(self):
        text = (ROOT / "scripts" / "tabletop" / "release_tts.py").read_text()
        self.assertNotRegex(text, r"\d+\.\d+\.\d+\.\d+")
        self.assertNotIn("cloak", text)


class WorkshopTests(unittest.TestCase):
    def test_task_uses_existing_interactive_token_without_policy_changes(self):
        xml = release_tts.workshop_task_xml("S-1-5-test", r"C:\folder & files")
        root = ET.fromstring(xml)
        ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
        self.assertEqual(root.find(".//t:LogonType", ns).text, "InteractiveToken")
        self.assertEqual(root.find(".//t:RunLevel", ns).text, "LeastPrivilege")
        self.assertIsNone(root.find("t:Triggers", ns))
        args = root.find(".//t:Arguments", ns).text
        self.assertIn(r'-File "C:\folder & files\tts_workshop.ps1"', args)
        self.assertNotIn("ExecutionPolicy", args)
        self.assertNotIn("EncodedCommand", args)

    def test_success_requires_steam_confirmation_for_the_requested_item(self):
        result = {"ok": True, "eresult": 1, "item": "123", "needs_legal_agreement": False}
        release_tts.validate_workshop_result(result, "123")
        for change in ({"ok": False}, {"eresult": 15}, {"item": "456"}, {"needs_legal_agreement": True}):
            with self.subTest(change=change), self.assertRaises(SystemExit):
                release_tts.validate_workshop_result(result | change, "123")

    def test_upload_rejects_blocking_policy_before_staging_or_launching(self):
        pc = Mock()
        pc.powershell.return_value = json.dumps({"policy": "Restricted"})
        with self.assertRaises(SystemExit):
            release_tts.workshop_upload(pc, Path("unused"), Path("unused"), "123", "note")
        pc.shell.assert_not_called()
        pc.write.assert_not_called()

    def test_temporary_task_is_removed_when_steam_reports_failure(self):
        pc = Mock(workshop_dir="/mnt/c/upload", steam_dll=r"C:\tts\steam_api64.dll")
        pc.powershell.return_value = json.dumps({"policy": "RemoteSigned", "user": "PC/user",
                                                "desktopUser": "PC/user", "steam": [{"SessionId": 1}],
                                                "sid": "S-1-5-test"})
        def shell(command, **kwargs):
            if command.startswith("if [ -f"):
                return json.dumps({"ok": False, "eresult": 15, "item": "123", "message": "access denied"})
            return ""
        pc.shell.side_effect = shell
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "save.json").write_text('{"SaveName":"v32"}')
            (folder / "thumb.png").write_bytes(b"preview")
            with patch.object(release_tts, "REPO", folder):
                (folder / "scripts" / "tabletop").mkdir(parents=True)
                (folder / "scripts/tabletop/tts_workshop.ps1").write_text("# stub")
                with self.assertRaises(SystemExit):
                    release_tts.workshop_upload(pc, folder / "save.json", folder / "thumb.png", "123", "note")
        commands = [call.args[0] for call in pc.shell.call_args_list]
        self.assertTrue(any(c.startswith("schtasks.exe /Run") for c in commands))
        self.assertTrue(commands[-1].startswith("schtasks.exe /Delete"))
        task_data = next(c.args[1] for c in pc.write.call_args_list if c.args[0].endswith("/task.xml"))
        self.assertTrue(task_data.startswith((b"\xff\xfe", b"\xfe\xff")))
        ET.fromstring(task_data)  # schtasks needs a matching UTF-16 declaration and BOM

    def test_workshop_only_uploads_delivered_bytes_without_building_or_advancing_version(self):
        save = json.dumps({"SaveName": "MTG 6 player Cactuar Ver_v32", "LuaScript": "-- Pages"}).encode()
        pc = Mock(workshop_id="123", saves="/mnt/c/Saves")
        pc.read.side_effect = [save, b"png"]
        with tempfile.TemporaryDirectory() as tmp:
            config, changelog = Path(tmp) / "config", Path(tmp) / "log"
            config.write_text("{}")
            original = "## v32 — 2026-10-19\n- Fix refresh.\n"
            changelog.write_text(original)
            captured = {}
            def record_upload(pc_arg, save_arg, thumb_arg, item_arg, note_arg):
                captured.update(save=save_arg.read_bytes(), preview=thumb_arg.read_bytes(),
                                item=item_arg, note=note_arg)
            with patch.object(release_tts, "CONFIG", config), patch.object(release_tts, "CHANGELOG", changelog), \
                 patch.object(release_tts, "PC", return_value=pc), \
                 patch.object(release_tts, "check_published", return_value="abc1234"), \
                 patch.object(release_tts, "build") as build, \
                 patch.object(release_tts, "workshop_upload", side_effect=record_upload), \
                 patch.object(sys, "argv", ["release_tts.py", "--workshop-only"]):
                self.assertEqual(release_tts.main(), 0)
                build.assert_not_called()
                self.assertEqual(captured, {"save": save, "preview": b"png", "item": "123", "note": "v32: Fix refresh."})
            self.assertEqual(changelog.read_text(), original)
            pc.write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
