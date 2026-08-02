"""Persistent metadata about deck files.

Unlike `.cache/cards.db`, this database is trusted provenance written by the bot
parent outside the Codex sandbox. It is intentionally small and separate: card
objects and images are disposable caches, while the Discord user who created a
deck must survive cache clears and must not be editable by the model whose work
is being attributed.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS deck_authors (
    deck          TEXT PRIMARY KEY,
    author        TEXT NOT NULL,
    attributed_at REAL NOT NULL
);
"""


class DeckAuthorStore:
    """SQLite-backed mapping of workspace-relative deck path to Discord user."""

    def __init__(self, path: Path, timeout: float = 10.0):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, timeout=timeout)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout = 10000")
        self.conn.executescript(SCHEMA)

    def set(self, deck: str, author: str) -> None:
        """Attribute `deck` to `author`, replacing stale data for that path."""
        deck = deck.strip()
        author = author.strip()
        if not deck:
            raise ValueError("deck path cannot be empty")
        if not author:
            raise ValueError("deck author cannot be empty")
        self.conn.execute(
            "INSERT INTO deck_authors(deck,author,attributed_at) VALUES(?,?,?) "
            "ON CONFLICT(deck) DO UPDATE SET author=excluded.author, "
            "attributed_at=excluded.attributed_at",
            (deck, author, time.time()),
        )
        self.conn.commit()

    def get(self, deck: str) -> str | None:
        row = self.conn.execute(
            "SELECT author FROM deck_authors WHERE deck = ?", (deck,)
        ).fetchone()
        return row["author"] if row else None

    def all(self) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT deck, author FROM deck_authors ORDER BY deck"
        ).fetchall()
        return {row["deck"]: row["author"] for row in rows}

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> DeckAuthorStore:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
