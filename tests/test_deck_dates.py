"""A deck's dates: when it was first added, and the last change to its list or
guide, by anyone, following it through moves."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
import _paths  # noqa: F401  (scripts/<area>/ on sys.path)

import build_site

DAY = 86400
T0 = 1_790_000_000                      # an arbitrary fixed moment


class Repo:
    """A throwaway git repo with public/ and private/ deck trees."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name).resolve()
        self.git("init", "-q")
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()

    def git(self, *args, when: int = T0):
        env = {**os.environ, "GIT_AUTHOR_DATE": f"@{when} +0000",
               "GIT_COMMITTER_DATE": f"@{when} +0000", "GIT_AUTHOR_NAME": "t",
               "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "-C", str(self.path), *args], check=True,
                       capture_output=True, env=env)

    def write(self, rel: str, text: str) -> Path:
        path = self.path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def commit(self, when: int):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "x", when=when)

    def history(self):
        return build_site.deck_history(self.path, ["public", "private"])

    def dates(self):
        return self.history()[1]

    def added(self, deck: Path) -> int:
        return self.history()[0].get(deck.resolve(), 0)


class ModificationDateTests(unittest.TestCase):
    def test_a_committed_edit_dates_the_deck(self):
        with Repo() as r:
            deck = r.write("public/Bracket3/A-Deck.txt", "1 A\n")
            r.commit(T0)
            r.write("public/Bracket3/A-Deck.txt", "1 A\n1 B\n")
            r.commit(T0 + 2 * DAY)
            self.assertEqual(build_site.modified_at(deck, r.dates()), T0 + 2 * DAY)

    def test_adding_a_deck_is_not_an_edit(self):
        # Covers the commit that first tracked private/: it added 18 decks at
        # once and must not mark them all as edited that day.
        with Repo() as r:
            deck = r.write("private/Bracket3/P-Deck.txt", "1 P\n")
            r.commit(T0)
            self.assertEqual(build_site.modified_at(deck, r.dates()), 0)

    def test_a_guide_edit_is_an_edit_to_the_deck(self):
        with Repo() as r:
            deck = r.write("public/Bracket3/A-Deck.txt", "1 A\n")
            r.write("public/Bracket3/A-Deck.guide", "old\n")
            r.commit(T0)
            r.write("public/Bracket3/A-Deck.guide", "new\n")
            r.commit(T0 + DAY)
            self.assertEqual(build_site.modified_at(deck, r.dates()), T0 + DAY)

    def test_an_uncommitted_edit_counts_from_the_files_own_time(self):
        # bot.py builds before it commits, so the page it publishes must
        # already carry the edit.
        with Repo() as r:
            deck = r.write("public/Bracket3/A-Deck.txt", "1 A\n")
            r.commit(T0)
            r.write("public/Bracket3/A-Deck.txt", "1 A\n1 B\n")
            os.utime(deck, (T0 + 3 * DAY, T0 + 3 * DAY))
            self.assertEqual(build_site.modified_at(deck, r.dates()), T0 + 3 * DAY)

    def test_newest_commit_wins(self):
        with Repo() as r:
            deck = r.write("public/Bracket3/A-Deck.txt", "1 A\n")
            r.commit(T0)
            for i, day in enumerate((1, 5, 3), 2):
                r.write("public/Bracket3/A-Deck.txt", "1 A\n" * i)
                r.commit(T0 + day * DAY)
            # Commit order, not timestamp order: the LAST commit is the latest edit.
            self.assertEqual(build_site.modified_at(deck, r.dates()), T0 + 3 * DAY)


class MovedDeckTests(unittest.TestCase):
    """Every deck moved into an owner folder on 2026-10-18; none may look new."""

    def test_a_pure_move_keeps_both_dates(self):
        with Repo() as r:
            r.write("public/Bracket3/A-Deck.txt", "1 A\n")
            r.commit(T0)
            r.write("public/Bracket3/A-Deck.txt", "1 A\n1 B\n")
            r.commit(T0 + DAY)
            (r.path / "public/alice/Bracket3").mkdir(parents=True)
            r.git("mv", "public/Bracket3/A-Deck.txt", "public/alice/Bracket3/A-Deck.txt")
            moved = r.path / "public/alice/Bracket3/A-Deck.txt"
            # Staged, not yet committed: the build before the commit...
            self.assertEqual((r.added(moved), build_site.modified_at(moved, r.dates())),
                             (T0, T0 + DAY))
            r.commit(T0 + 9 * DAY)
            # ...dates it exactly as the build after it.
            self.assertEqual((r.added(moved), build_site.modified_at(moved, r.dates())),
                             (T0, T0 + DAY))

    def test_a_move_from_private_keeps_its_dates_too(self):
        with Repo() as r:
            r.write("private/Bracket3/P-Deck.txt", "1 P\n")
            r.commit(T0)
            (r.path / "public/zzwang/Bracket3").mkdir(parents=True)
            r.git("mv", "private/Bracket3/P-Deck.txt", "public/zzwang/Bracket3/P-Deck.txt")
            r.commit(T0 + DAY)
            moved = r.path / "public/zzwang/Bracket3/P-Deck.txt"
            self.assertEqual((r.added(moved), build_site.modified_at(moved, r.dates())),
                             (T0, 0))

    def test_a_move_with_edits_is_an_edit(self):
        with Repo() as r:
            r.write("public/Bracket3/A-Deck.txt", "\n".join(f"1 Card {i}" for i in range(20)))
            r.commit(T0)
            (r.path / "public/alice/Bracket3").mkdir(parents=True)
            r.git("mv", "public/Bracket3/A-Deck.txt", "public/alice/Bracket3/A-Deck.txt")
            r.write("public/alice/Bracket3/A-Deck.txt",
                    "\n".join(f"1 Card {i}" for i in range(19)) + "\n1 New Card")
            r.commit(T0 + 2 * DAY)
            moved = r.path / "public/alice/Bracket3/A-Deck.txt"
            self.assertEqual(build_site.modified_at(moved, r.dates()), T0 + 2 * DAY)

    def test_added_is_the_earlier_of_git_and_the_files_own_birth(self):
        with Repo() as r:
            deck = r.write("public/alice/Bracket3/A-Deck.txt", "1 A\n")
            r.commit(T0)
            birth = int(deck.stat().st_birthtime)
            # Git says T0 (in the past); the file was born now: git wins.
            self.assertEqual(build_site.created_at(deck, r.history()[0]), T0)
            # A deck drafted before its first commit: its birth wins.
            later = {deck.resolve(): birth + DAY}
            self.assertEqual(build_site.created_at(deck, later), birth)


class UpdatedChipTests(unittest.TestCase):
    def info(self, created: int, modified: int):
        d = object.__new__(build_site.DeckInfo)
        d.created = created
        d.modified = modified if modified >= created + build_site.UPDATE_GAP else 0
        d.modified_label = build_site._utc_label(d.modified)
        return d

    def test_shown_for_a_later_edit_with_its_time_in_its_own_element(self):
        chip = build_site.updated_chip(self.info(T0, T0 + DAY))
        self.assertIn(f'updated <span data-ts="{T0 + DAY}">', chip)

    def test_hidden_while_the_deck_is_still_being_built(self):
        self.assertEqual(build_site.updated_chip(self.info(T0, T0 + 600)), "")
        self.assertEqual(build_site.updated_chip(self.info(T0, 0)), "")


if __name__ == "__main__":
    unittest.main()
