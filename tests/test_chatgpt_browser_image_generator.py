"""Check stale-image, failed-download and overwrite protection without browser calls."""
import importlib.util
import itertools
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib


SPEC = importlib.util.spec_from_file_location(
    "chatgpt_image_generator",
    Path(__file__).resolve().parents[1] / "scripts/chatgpt-browser-image-generator.py",
)
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


def png():
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data +
                struct.pack(">I", zlib.crc32(kind + data)))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


class ImageGeneratorTests(unittest.TestCase):
    def test_hidden_download_controls_are_not_clicked(self):
        browser = generator.Browser("test")
        with patch.object(browser, "snapshot", return_value={
            "snapshot": '- button "Download" [ref=e2]',
            "refs": {"e1": {"role": "button", "name": "Download"},
                     "e2": {"role": "button", "name": "Download"}},
        }):
            self.assertEqual(browser.ref("button", "Download"), "@e2")

    def test_old_image_cannot_mask_a_new_refusal(self):
        class RefusedBrowser:
            def state(self):
                return {"busy": False, "turns": [
                    {"id": "old", "images": [{"ready": True}]},
                    {"id": "new", "images": [], "text": "Image limit reached."},
                ]}
        with patch.object(generator.time, "monotonic", side_effect=[1, 2, 3, 9, 10, 11]), \
                patch.object(generator.time, "sleep"):
            with self.assertRaisesRegex(generator.GenerationError, "Image limit reached"):
                generator.wait_for_image(RefusedBrowser(), {"old"}, 20)

    def test_latest_failed_turn_does_not_select_history(self):
        state = {"turns": [
            {"id": "old", "images": [{"ready": True}]},
            {"id": "new", "images": []},
        ]}
        self.assertEqual(generator.select_turn(state, {"old"})["id"], "new")
        self.assertIsNone(generator.select_turn(state, {"old", "new"}))

    def test_png_integrity_and_dimensions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "image.png"
            path.write_bytes(png())
            info = generator.png_info(path)
            self.assertEqual((info["width"], info["height"]), (1, 1))
            path.write_bytes(png()[:-12])
            with self.assertRaisesRegex(generator.GenerationError, "incomplete"):
                generator.png_info(path)

    def test_html_download_never_becomes_output(self):
        class BadDownload:
            def ref(self, *args, **kwargs):
                return "@download"

            def run(self, command, *args, **kwargs):
                if command == "download":
                    Path(args[1]).write_text("<html>Please sign in</html>")
                return {}
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "image.png"
            with self.assertRaisesRegex(generator.GenerationError, "not an original PNG"):
                generator.download_turn(BadDownload(),
                                        {"id": "new", "images": [{"ready": True}]}, output)
            self.assertFalse(output.exists())

    def test_existing_output_is_rejected_before_any_browser_call(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "existing.png"
            output.write_bytes(b"keep this")
            with patch.object(generator, "Browser") as browser, \
                    patch("sys.stderr"):
                with self.assertRaises(SystemExit):
                    generator.main(["--prompt", "a dog", "--out", str(output)])
            browser.assert_not_called()
            self.assertEqual(output.read_bytes(), b"keep this")

    def test_output_created_during_download_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "image.png"

            class ConcurrentDownload:
                def ref(self, *args, **kwargs):
                    return "@download"

                def run(self, command, *args, **kwargs):
                    if command == "download":
                        Path(args[1]).write_bytes(png())
                        output.write_bytes(b"another writer")
                    return {}

            with self.assertRaisesRegex(generator.GenerationError, "Output already exists"):
                generator.download_turn(ConcurrentDownload(),
                                        {"id": "new", "images": [{"ready": True}]}, output)
            self.assertEqual(output.read_bytes(), b"another writer")

    def test_lost_download_ack_retries_download_only(self):
        class LostAckBrowser:
            downloads = 0
            commands = []

            def ref(self, *args, **kwargs):
                return "@download"

            def run(self, command, *args, **kwargs):
                self.commands.append(command)
                if command == "download":
                    self.downloads += 1
                    if self.downloads == 1:
                        raise generator.GenerationError("no response came back")
                    Path(args[1]).write_bytes(png())
                return {}

        with tempfile.TemporaryDirectory() as folder:
            browser = LostAckBrowser()
            with patch.object(generator.time, "monotonic", side_effect=itertools.count()), \
                    patch.object(generator.time, "sleep"):
                generator.download_turn(browser, {"id": "new", "images": [{"ready": True}]},
                                        Path(folder) / "image.png")
            self.assertEqual(browser.downloads, 2)
            self.assertEqual(browser.commands, ["click", "wait", "download", "download"])

    def test_completed_download_survives_lost_ack_without_retry(self):
        class CompletedBrowser:
            downloads = 0

            def ref(self, *args, **kwargs):
                return "@download"

            def run(self, command, *args, **kwargs):
                if command == "download":
                    self.downloads += 1
                    Path(args[1]).write_bytes(png())
                    raise generator.GenerationError("no response came back")
                return {}

        with tempfile.TemporaryDirectory() as folder:
            browser = CompletedBrowser()
            output = Path(folder) / "image.png"
            generator.download_turn(browser, {"id": "new", "images": [{"ready": True}]}, output)
            self.assertEqual(browser.downloads, 1)
            self.assertEqual(output.read_bytes(), png())


if __name__ == "__main__":
    unittest.main()
