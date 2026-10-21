"""The Tabletop Simulator objects a table spawns, held to what rikrassen's importer
builds for the same cards (its server's reply for Sol Ring, Delver of Secrets and
Elspeth, Sun's Champion, captured 2026-10-16)."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_site
import ttsdecks


def img(name: str) -> dict:
    return {"large": f"https://cards.example/large/{name}.jpg", "normal": f"https://cards.example/n/{name}.jpg"}


SOL = {"id": "sol", "name": "Sol Ring", "type_line": "Artifact", "cmc": 1.0,
       "oracle_text": "{T}: Add {C}{C}.", "image_uris": img("sol"), "color_identity": [],
       "legalities": {"commander": "legal"}}
DELVER = {"id": "delver", "name": "Delver of Secrets // Insectile Aberration", "cmc": 1.0,
          "type_line": "Creature — Human Wizard // Creature — Human Insect", "layout": "transform",
          "color_identity": ["U"], "legalities": {"commander": "legal"},
          "card_faces": [
              {"name": "Delver of Secrets", "type_line": "Creature — Human Wizard", "power": "1",
               "toughness": "1", "image_uris": img("delver-front"),
               "oracle_text": "At the beginning of your upkeep, look at the top card of your library. You may reveal that card. If an instant or sorcery card is revealed this way, transform this creature."},
              {"name": "Insectile Aberration", "type_line": "Creature — Human Insect", "power": "3",
               "toughness": "2", "oracle_text": "Flying", "image_uris": img("delver-back")}]}
ELSPETH = {"id": "elspeth", "name": "Elspeth, Sun's Champion", "cmc": 6.0, "loyalty": "4",
           "type_line": "Legendary Planeswalker — Elspeth", "image_uris": img("elspeth"),
           "color_identity": ["W"], "legalities": {"commander": "legal"},
           "oracle_text": "+1: Create three 1/1 white Soldier creature tokens.\n−3: Destroy all creatures with power 4 or greater.\n−7: You get an emblem with \"Creatures you control get +2/+2 and have flying.\"",
           "all_parts": [
               {"id": "elspeth", "component": "combo_piece", "type_line": "Legendary Planeswalker — Elspeth"},
               {"id": "emblem", "component": "combo_piece", "type_line": "Emblem — Elspeth"},
               {"id": "soldier", "component": "token", "type_line": "Token Creature — Soldier"},
               {"id": "checklist", "component": "combo_piece", "type_line": "Card"}]}
SOLDIER = {"id": "soldier", "name": "Soldier", "type_line": "Token Creature — Soldier", "cmc": 0,
           "oracle_text": "", "power": "1", "toughness": "1", "image_uris": img("soldier")}
SOLDIER_REPRINT = {**SOLDIER, "id": "soldier-2", "image_uris": img("soldier-2")}
EMBLEM = {"id": "emblem", "name": "Elspeth, Sun's Champion Emblem", "type_line": "Emblem — Elspeth",
          "cmc": 0, "oracle_text": "Creatures you control get +2/+2 and have flying.",
          "image_uris": img("emblem")}


class ImporterFormatTests(unittest.TestCase):
    """Nickname and Description exactly as the importer writes them."""

    def nick_desc(self, card):
        return [(f["nickname"], f["description"]) for f in ttsdecks.faces(card)]

    def test_noncreature(self):
        self.assertEqual(self.nick_desc(SOL), [("Sol Ring\nArtifact 1CMC", "{T}: Add {C}{C}.")])

    def test_double_faced_creature(self):
        self.assertEqual(self.nick_desc(DELVER), [
            ("Delver of Secrets\nCreature — Human Wizard 1CMC",
             DELVER["card_faces"][0]["oracle_text"] + "\n[b]1/1[/b]"),
            ("Insectile Aberration\nCreature — Human Insect 1CMC", "Flying\n[b]3/2[/b]")])

    def test_planeswalker_shows_loyalty(self):
        (nick, desc), = self.nick_desc(ELSPETH)
        self.assertEqual(nick, "Elspeth, Sun's Champion\nLegendary Planeswalker — Elspeth 6CMC")
        self.assertTrue(desc.endswith("\n[b]4[/b]"))

    def test_token_with_no_text(self):
        self.assertEqual(self.nick_desc(SOLDIER), [("Soldier\nToken Creature — Soldier 0CMC", "\n[b]1/1[/b]")])

    def test_image_size_fallback_and_non_scryfall_images(self):
        path = "front/4/e/4e4b6e22-93b2-4896-bba5-0ceaa5d8ea3c"
        expected = f"https://img.klrmngr.com/display/{path}.webp"
        for size in ("large", "normal"):
            with self.subTest(size=size):
                self.assertEqual(ttsdecks._image({size: f"https://cards.scryfall.io/{size}/{path}.jpg?1783926791"}), expected)
        custom = "https://cards.example/custom.jpg?version=2"
        self.assertEqual(ttsdecks._image({"large": custom}), custom)
        self.assertEqual(ttsdecks._image(None), "")


class ObjectTests(unittest.TestCase):
    def test_a_double_faced_card_flips_to_its_back_as_state_two(self):
        sheets = ttsdecks.Sheets()
        card = ttsdecks.card_object(DELVER, sheets)
        self.assertNotIn("CustomDeck", card)                 # the pile lists fronts
        back = card["States"]["2"]
        self.assertEqual(back["Nickname"].split("\n")[0], "Insectile Aberration")
        (k, sheet), = back["CustomDeck"].items()             # a back carries its own
        self.assertEqual(back["CardID"], int(k) * 100)
        self.assertEqual(sheet["FaceURL"], img("delver-back")["large"])

    def test_a_pile_lists_each_picture_once(self):
        sheets = ttsdecks.Sheets()
        cards = [ttsdecks.card_object(SOL, sheets)] * 3 + [ttsdecks.card_object(ELSPETH, sheets)]
        p = ttsdecks.pile("Test", cards, sheets)
        self.assertEqual(p["Name"], "DeckCustom")
        self.assertEqual(len(p["ContainedObjects"]), 4)
        self.assertEqual(p["DeckIDs"], [100, 100, 100, 200])
        self.assertEqual(sorted(p["CustomDeck"]), ["1", "2"])
        self.assertEqual(p["CustomDeck"]["1"]["BackURL"], ttsdecks.CARD_BACK)

    def test_a_single_card_is_not_a_pile_and_keeps_its_picture(self):
        sheets = ttsdecks.Sheets()
        p = ttsdecks.pile("Tokens", [ttsdecks.card_object(SOLDIER, sheets)], sheets)
        self.assertEqual(p["Name"], "Card")
        self.assertEqual(p["CustomDeck"]["1"]["FaceURL"], img("soldier")["large"])

    def test_tokens_and_emblems_but_not_the_card_itself_or_its_checklist(self):
        self.assertEqual(ttsdecks.token_ids([ELSPETH]), ["emblem", "soldier"])
        self.assertEqual(ttsdecks.distinct_tokens([SOLDIER, SOLDIER_REPRINT, EMBLEM]), [SOLDIER, EMBLEM])


class SleeveTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        original = ttsdecks.SLEEVES_DIR
        ttsdecks.SLEEVES_DIR = self.dir
        self.addCleanup(setattr, ttsdecks, "SLEEVES_DIR", original)

    def test_standard_first_then_the_folder_by_name(self):
        (self.dir / "zebra_stripes.png").write_bytes(b"png")
        (self.dir / "cactuar.jpg").write_bytes(b"jpg")
        (self.dir / "notes.txt").write_text("not a picture")
        self.assertEqual(ttsdecks.sleeves(), [
            {"id": "standard", "label": "Standard", "url": ttsdecks.CARD_BACK,
             "thumb_url": ttsdecks.CARD_BACK_THUMB},
            {"id": "cactuar", "label": "Cactuar", "file": "sleeves/cactuar.jpg?v=f8146b6c"},
            {"id": "zebra_stripes", "label": "Zebra Stripes", "file": "sleeves/zebra_stripes.png?v=8f8cbb7d"},
        ])

    def test_sleeves_are_published_and_listed(self):
        (self.dir / "cactuar.jpg").write_bytes(b"jpg-bytes")
        out = ttsdecks.files([], Path("/site"), None)
        self.assertEqual(out[Path("/site/tts/sleeves/cactuar.jpg")], b"jpg-bytes")
        index = json.loads(out[Path("/site/tts/decks.json")])
        self.assertEqual([b["id"] for b in index["sleeves"]], ["standard", "cactuar"])

    def test_the_readme_is_published_but_is_not_a_sleeve(self):
        (self.dir / "README.md").write_text("# Sleeves")
        out = ttsdecks.files([], Path("/site"), None)
        self.assertEqual(out[Path("/site/tts/sleeves/README.md")], "# Sleeves")
        self.assertEqual([b["id"] for b in ttsdecks.sleeves()], ["standard"])

    def test_no_folder_means_only_the_standard_back(self):
        ttsdecks.SLEEVES_DIR = self.dir / "missing"
        self.assertEqual([b["id"] for b in ttsdecks.sleeves()], ["standard"])

    @unittest.skipUnless(ttsdecks.SIPS.exists(), "macOS sips only")
    def test_real_pictures_get_a_small_published_thumbnail(self):
        cache = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        original = ttsdecks.THUMB_CACHE
        ttsdecks.THUMB_CACHE = Path(cache.name)
        self.addCleanup(setattr, ttsdecks, "THUMB_CACHE", original)
        (self.dir / "cactuar.jpg").write_bytes((ROOT / "tts" / "sleeves" / "cactuar.jpg").read_bytes())
        entry = ttsdecks.sleeves()[1]
        self.assertRegex(entry["thumb"], r"^sleeves/thumbs/cactuar\.jpg\?v=[0-9a-f]{8}$")
        out = ttsdecks.files([], Path("/site"), None)
        thumb = out[Path("/site/tts/sleeves/thumbs/cactuar.jpg")]
        self.assertTrue(thumb.startswith(b"\xff\xd8\xff"))
        self.assertLess(len(thumb), 40_000)
        self.assertEqual(ttsdecks.files([], Path("/site"), None)[Path("/site/tts/sleeves/thumbs/cactuar.jpg")], thumb)

    def test_announcer_clips_are_published(self):
        out = ttsdecks.files([], Path("/site"), None)
        for name in ("slow-5min.wav", "slow-10min.wav"):
            self.assertTrue(out[Path("/site/tts/sounds") / name].startswith(b"RIFF"), name)
        self.assertNotIn(Path("/site/tts/sounds/make_announcer.py"), out)

    def test_the_repo_ships_the_cactuar_sleeve(self):
        self.assertTrue((ROOT / "tts" / "sleeves" / "cactuar.jpg").is_file())


class TournamentTests(unittest.TestCase):
    def test_pool_keeps_file_order_and_skips_missing_decks_with_a_warning(self):
        from types import SimpleNamespace
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        f = Path(tmp.name) / "tournament.json"
        f.write_text(json.dumps({"decks": ["b/Two", "gone/Deck", "a/One", "b/Two"]}))
        original = ttsdecks.TOURNAMENT_FILE
        ttsdecks.TOURNAMENT_FILE = f
        self.addCleanup(setattr, ttsdecks, "TOURNAMENT_FILE", original)
        decks = [SimpleNamespace(key="a/One"), SimpleNamespace(key="b/Two")]
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(ttsdecks.tournament(decks), ["b/Two", "a/One"])
        self.assertIn("gone/Deck", err.getvalue())
        self.assertEqual(ttsdecks.tournament_keys(), {"b/Two", "gone/Deck", "a/One"})

    def test_the_repo_pool_is_24_distinct_bracket_3_decks_in_the_catalog(self):
        index = json.loads((ROOT / "docs" / "tts" / "decks.json").read_text())
        listed = json.loads(ttsdecks.TOURNAMENT_FILE.read_text())["decks"]
        self.assertEqual(len(listed), 24)
        self.assertEqual(len(set(listed)), 24)
        decks = {d["id"]: d for d in index["decks"]}
        for key in listed:
            self.assertIn(key, decks)
            self.assertEqual(decks[key]["bracket"], "Bracket3", key)
        self.assertEqual(index["tournament"], listed)

    def test_the_catalog_tags_every_tournament_deck(self):
        html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('class="theme-tag tournament"'), 24)
        page = (ROOT / "docs" / "zzwang" / "Bracket3" / "Baral-Control.html").read_text(encoding="utf-8")
        self.assertIn('class="chip tournament"', page)
        other = (ROOT / "docs" / "zzwang" / "Bracket5" / "Kinnan-Combo.html").read_text(encoding="utf-8")
        self.assertNotIn('class="chip tournament"', other)


class DeckFileTests(unittest.TestCase):
    def test_preview_keeps_pinned_faces_partner_order_and_guide_sections(self):
        from types import SimpleNamespace
        d = SimpleNamespace(key="alice/Pair", stem="Pair", commanders=["Elspeth", "Delver"],
                            cards={"Elspeth": ELSPETH, "Delver": DELVER},
                            guide=[("Plan & win", [("Sol Ring + Other", "Make mana."), ("", "Read this prose.")])])
        preview = json.loads(ttsdecks.preview_file(d))
        self.assertEqual(preview["id"], d.key)
        self.assertEqual([c["name"] for c in preview["commanders"]], d.commanders)
        self.assertEqual(preview["commanders"][1]["faces"][1]["FaceURL"], img("delver-back")["large"])
        self.assertEqual(preview["guide"][0], {"title": "Plan & win", "rows": [
            {"name": "Sol Ring + Other", "text": "Make mana."}, {"name": "", "text": "Read this prose."}]})
        self.assertNotIn("ContainedObjects", preview)

    def test_preview_publication_and_content_hash_follow_guide_changes(self):
        d = self.deck_info("1 Sol Ring\n99 Plains\n", {"Sol Ring": SOL, "Plains": SOL})
        d.guide = [("Plan", [("Sol Ring", "Add mana.")])]
        entry = ttsdecks.index_entry(d, "alice/Bracket3/Test.ndjson")
        self.assertTrue(entry["guide"])
        self.assertRegex(entry["preview"], r"^alice/Bracket3/Test\.preview\.json\?v=[a-f0-9]{12}$")
        d.guide[0][1][0] = ("Sol Ring", "Changed guide.")
        self.assertNotEqual(entry["preview"], ttsdecks.index_entry(d, "alice/Bracket3/Test.ndjson")["preview"])
        out = ttsdecks.files([d], Path("/site"), None)
        path = Path("/site/tts") / Path(d.href).with_suffix(".preview.json")
        self.assertEqual(json.loads(out[path])["guide"][0]["rows"][0]["text"], "Changed guide.")

    def deck_info(self, text: str, pool: dict):
        class Query:
            def cards(self, names):
                return {n: pool[n] for n in names if n in pool}, []

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        path = root / "alice" / "Bracket3" / "Elspeth-Tokens.txt"
        path.parent.mkdir(parents=True)
        path.write_text(text)
        return build_site.DeckInfo(path, root, Query(),
                                   theme_assignments={"alice/Elspeth-Tokens": ["gowide", "goblins"]},
                                   tier_assignments={"alice/Elspeth-Tokens": "B"})

    def test_header_library_commander_tokens(self):
        pool = {"Elspeth, Sun's Champion": {**ELSPETH, "type_line": "Legendary Planeswalker — Elspeth"},
                "Sol Ring": SOL, "Plains": {**SOL, "id": "plains", "name": "Plains",
                                            "type_line": "Basic Land — Plains", "cmc": 0,
                                            "oracle_text": "", "image_uris": img("plains")}}
        d = self.deck_info("1 Elspeth, Sun's Champion\n1 Sol Ring\n98 Plains\n", pool)
        lines = ttsdecks.deck_file(d, {"emblem": EMBLEM, "soldier": SOLDIER}).splitlines()
        header, library, commander, tokens = map(json.loads, lines)
        self.assertEqual(header, {"v": 1, "name": "Elspeth-Tokens", "commanders": 1, "tokens": True})
        self.assertEqual(len(library["ContainedObjects"]), 99)          # the commander is apart
        self.assertEqual(len(library["CustomDeck"]), 2)                  # 98 Plains share a sheet
        self.assertEqual(commander["Nickname"].split("\n")[0], "Elspeth, Sun's Champion")
        self.assertEqual([c["Nickname"].split("\n")[0] for c in tokens["ContainedObjects"]],
                         ["Elspeth, Sun's Champion Emblem", "Soldier"])

    def test_the_published_index_has_no_local_only_category(self):
        pool = {"Sol Ring": {**SOL, "type_line": "Legendary Artifact"}, "Plains": SOL}
        d = self.deck_info("1 Sol Ring\n99 Plains\n", pool)
        entry = ttsdecks.index_entry(d, "alice/Bracket3/Elspeth-Tokens.ndjson")
        self.assertEqual(entry["themes"], ["gowide"])
        self.assertEqual((entry["id"], entry["owner"], entry["tier"]), ("alice/Elspeth-Tokens", "alice", "B"))
        self.assertNotIn("goblins", json.dumps(ttsdecks.index([d], {d.key: "x"})))

    def test_all_card_faces_use_the_tts_image_cache(self):
        # Real Scryfall URL shapes, including the scan-version query that the
        # old fixtures omitted. Direct requests from UnityPlayer get HTTP 400.
        def image(name, face="front"):
            return {"large": f"https://cards.scryfall.io/large/{face}/a/b/{name}.jpg?1783926791"}

        commander = {**ELSPETH, "image_uris": image("commander")}
        sol = {**SOL, "image_uris": image("library")}
        delver = {**DELVER, "card_faces": [
            {**DELVER["card_faces"][0], "image_uris": image("delver")},
            {**DELVER["card_faces"][1], "image_uris": image("delver", "back")},
        ]}
        soldier = {**SOLDIER, "image_uris": image("token")}
        d = self.deck_info("1 Elspeth, Sun's Champion\n98 Sol Ring\n1 Delver of Secrets // Insectile Aberration\n",
                           {c["name"]: c for c in (commander, sol, delver)})
        text = ttsdecks.deck_file(d, {"soldier": soldier})
        self.assertNotIn("cards.scryfall.io", text)
        _, library, leader, token = map(json.loads, text.splitlines())
        expected = "https://img.klrmngr.com/display/"
        self.assertEqual(library["CustomDeck"]["1"]["FaceURL"], expected + "front/a/b/library.webp")
        back = library["ContainedObjects"][-1]["States"]["2"]
        self.assertEqual(next(iter(back["CustomDeck"].values()))["FaceURL"], expected + "back/a/b/delver.webp")
        self.assertEqual(leader["CustomDeck"]["1"]["FaceURL"], expected + "front/a/b/commander.webp")
        self.assertEqual(token["CustomDeck"]["2"]["FaceURL"], expected + "front/a/b/token.webp")
        self.assertEqual(commander["image_uris"], image("commander"))  # catalog keeps its original URL


if __name__ == "__main__":
    unittest.main()
