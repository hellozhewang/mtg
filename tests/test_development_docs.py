"""Authored docs must survive site pruning and alternate-output builds."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site
import release_tts
import workspace


class DevelopmentDocsTests(unittest.TestCase):
    def test_authored_docs_survive_in_place_sync_but_orphans_do_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            source = site / "development"
            source.mkdir()
            (source / "guide.md").write_text("# Guide\n")
            (site / "obsolete.html").write_text("old")
            with patch.object(build_site, "DEVELOPMENT_DOCS", source):
                files = build_site.development_docs(site)
                self.assertEqual(build_site.sync(files, site), (0, 1))
                self.assertEqual(build_site.sync(files, site), (0, 0))
            self.assertEqual((source / "guide.md").read_text(), "# Guide\n")
            self.assertFalse((site / "obsolete.html").exists())

    def test_alternate_output_copies_nested_docs_from_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source, out = base / "source", base / "out"
            (source / "nested").mkdir(parents=True)
            (source / "nested" / "guide.md").write_text("# Guide\n")
            with patch.object(build_site, "DEVELOPMENT_DOCS", source):
                files = build_site.development_docs(out)
                build_site.sync(files, out)
            self.assertEqual((out / "development/nested/guide.md").read_text(), "# Guide\n")
            self.assertTrue((source / "nested/guide.md").exists())

    def test_site_plan_includes_authored_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source, root, out = base / "authored", base / "public", base / "site"
            source.mkdir(); root.mkdir()
            (source / "guide.md").write_text("# Kept\n")
            symbols = Mock(); symbols.uris.return_value = {}
            with patch.object(build_site, "DEVELOPMENT_DOCS", source):
                files = build_site.plan(root, out, "test", None, Mock(), symbols)
            self.assertEqual(files[out / "development/guide.md"], "# Kept\n")

    def test_release_uses_moved_changelog_and_namespace_is_reserved(self):
        self.assertEqual(release_tts.CHANGELOG, ROOT / "docs/development/tts-changelog.md")
        self.assertGreaterEqual(release_tts.current_version(release_tts.CHANGELOG.read_text()), 61)
        self.assertIsNone(workspace.owner_name("development"))
        self.assertEqual(release_tts.WIP, ROOT / "tts/WIP.md")


if __name__ == "__main__":
    unittest.main()
