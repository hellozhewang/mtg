#!/usr/bin/env python3
"""Refresh only the table's embedded card colors, without rewriting catalog pages.

Normal build_site.py builds this same file alongside the catalog. This focused
command preserves unrelated catalog edits when preparing a table-only release.
"""
from pathlib import Path

import build_site
import deckfile
import ttsdecks
import workspace
from cardlib import CardQuery


def main():
    root = workspace.deck_root()
    q = CardQuery(db_path=workspace.cache_db())
    decks = [build_site.DeckInfo(p, root, q) for p in deckfile.discover_collection(root)]
    cards = [c for d in decks for c in d.cards.values()]
    tokens = q.by_ids(ttsdecks.token_ids(cards))
    target = Path(__file__).resolve().parents[1] / "docs/tts/card-colors.json"
    target.write_text(ttsdecks.music_metadata(cards + list(tokens.values())), encoding="utf-8")
    print(f"Wrote {target.relative_to(target.parents[2])}: {target.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
