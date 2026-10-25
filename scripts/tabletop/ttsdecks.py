"""Tabletop Simulator objects for every deck, so a table can spawn one in a click.

build_site.py calls `files()` and publishes what it returns under docs/tts/:

    tts/decks.json                          the index a table's deck browser lists
    tts/<owner>/<Bracket>/<Deck>.ndjson     one deck, ready to spawn
    tts/<owner>/<Bracket>/<Deck>.preview.json  readable commander faces and structured guide
    tts/cactuar-tile.jpg                    the picture on the table's Cactuar tiles
    tts/sleeves/<name>.jpg                  sleeves (card backs) a player can pick, from the repo's tts/sleeves/
    tts/sleeves/thumbs/<name>.jpg           146 x 204 previews of them for the Sleeves menu
    tts/sounds/<name>.wav                   the slow-turn announcer's clips, from the repo's tts/sounds/
    tts/table/<name>.png                    the table's decals (stack panel, trigger labels), from tts/table/

A deck file is one JSON value per line:

    {"v": 1, "name": "Giada-Angels", "commanders": 1, "tokens": true}    header
    <the library pile>
    <commander>                  one line per commander: one, or two for partners
    <the tokens>                 a pile, or a single card; absent when none

The table decodes only the header. Every other line goes to `spawnObjectJSON`
exactly as written: decoding objects into Lua tables and encoding them again would
turn CustomDeck's numeric keys ("1", "2") into an array, and the cards would lose
their pictures. One object per line, rather than strings inside one JSON value,
also saves the escaping on every quote.

The objects match what rikrassen's importer builds (measured against its server,
2026-10-16), so the table's own scripts treat our cards like any imported card:
each card is a one-card sheet, listed once in the pile's CustomDeck; its Nickname is `Name\\nType line NCMC`, its
Description the rules text with `[b]P/T[/b]` or `[b]loyalty[/b]` after it; a
double-faced card keeps its back as state 2. Pictures use the same image cache as
the importer: Scryfall rejects TTS's default UnityPlayer User-Agent. Pinned
printings are used as the catalog shows them, and the commanders and tokens are
separate objects so the table can put each in its own zone.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

_SCRIPTS = next(p for p in Path(__file__).resolve().parents if p.name == "scripts")
sys.path[:0] = [d for d in (str(_SCRIPTS / s) for s in ("common", "tabletop", "discord", "discord/bot"))
                if d not in sys.path]          # scripts/ is split by area; module names stay flat

import decktiers
import deckthemes
import deckguide

TILE_IMAGE = Path(__file__).resolve().parents[2] / "tts" / "cactuar-tile.jpg"
# Every picture here is a sleeve (card back) players can choose in the table's browser.
# Adding one needs only a catalog build and a push: the menu lists decks.json's "sleeves".
SLEEVES_DIR = TILE_IMAGE.parent / "sleeves"
SLEEVE_TYPES = (".jpg", ".jpeg", ".png")
# Small previews for the table's Sleeves grid. Every player's table downloads all of
# them when the deck list loads, so they are tiny. Made with macOS `sips`; elsewhere
# the menu shows names only. Cached by the source picture's hash, so a rebuild writes
# byte-identical files.
THUMB_W, THUMB_H = 146, 204
THUMB_CACHE = TILE_IMAGE.parent.parent / ".cache" / "sleeve-thumbs"
SIPS = Path("/usr/bin/sips")
# Clips the table plays through Tabletop Simulator's music player (cactuar_turns.lua).
SOUNDS_DIR = TILE_IMAGE.parent / "sounds"
# The tournament pool the browser's Tournament mode offers (curated by hand).
TOURNAMENT_FILE = TILE_IMAGE.parent / "tournament.json"
SOUND_TYPES = (".wav", ".mp3", ".ogg")
# Decal pictures cactuar_lines.lua lays on the table (make_table_art.py renders them).
TABLE_ART_DIR = TILE_IMAGE.parent / "table"

# Scryfall's standard Magic card back, and its small size for the Sleeves grid.
CARD_BACK = "https://backs.scryfall.io/large/0/a/0aeebaf5-8c7d-4636-9e82-8c27447861f7.jpg"
CARD_BACK_THUMB = CARD_BACK.replace("/large/", "/small/")
IMAGE_SIZES = ("large", "normal")       # first one present wins
IMAGE_BASE = "https://img.klrmngr.com"
TRANSFORM = {"posX": 0, "posY": 0, "posZ": 0, "rotX": 0, "rotY": 180, "rotZ": 0,
             "scaleX": 1, "scaleY": 1, "scaleZ": 1}
INDEX_VERSION = 1

# Mirrors the --tier-* colours in frontend/style.css, so a tier reads the same on
# the table as in the catalog. GOD's gradient is represented by its first stop.
TIER_COLOURS = {"GOD": "#ffe58a", "SS": "#ff5c8a", "S": "#ff7f7f", "A": "#ffbf7f",
                "B": "#ffdf7f", "C": "#f2f28a", "D": "#bfef8f", "TRASH": "#8d93a3"}


# ---------- one card ----------

def _image(uris: dict | None) -> str:
    uris = uris or {}
    url = next((uris[s] for s in IMAGE_SIZES if uris.get(s)), "")
    parts = urlsplit(url)
    if parts.hostname != "cards.scryfall.io":
        return url
    # Same printing UUID and front/back face, on the importer's image cache.
    # Its display images are WebP; Scryfall's size and scan-version query do
    # not apply. This covers commanders, tokens and double-faced backs too.
    face = PurePosixPath(parts.path.split("/", 2)[2]).with_suffix(".webp")
    return f"{IMAGE_BASE}/display/{face}"


def _cmc(card: dict) -> str:
    value = card.get("cmc") or 0
    return f"{value:g}"


def _stats(face: dict) -> str:
    if face.get("power") is not None and face.get("toughness") is not None:
        return f"{face['power']}/{face['toughness']}"
    return face.get("loyalty") or face.get("defense") or ""


def _face(name: str, type_line: str, cmc: str, oracle: str, stats: str, image: str) -> dict:
    return {"nickname": f"{name}\n{type_line} {cmc}CMC",
            "description": oracle + (f"\n[b]{stats}[/b]" if stats else ""),
            "image": image}


def faces(card: dict) -> list[dict]:
    """The card as one face, or two when its sides have separate pictures.

    Split, adventure and flip cards print both halves on one picture, so they are
    one face carrying both halves' text. Transforming and modal double-faced cards
    have a picture per side: those become a front and a flip-to back.
    """
    halves = card.get("card_faces") or []
    cmc = _cmc(card)
    if len(halves) >= 2 and all(h.get("image_uris") for h in halves[:2]):
        return [_face(h.get("name", ""), h.get("type_line", ""), cmc,
                      h.get("oracle_text") or "", _stats(h), _image(h["image_uris"]))
                for h in halves[:2]]
    oracle = card.get("oracle_text")
    if oracle is None:
        oracle = "\n//\n".join(h.get("oracle_text") or "" for h in halves)
    stats = _stats(card) or next((_stats(h) for h in halves if _stats(h)), "")
    return [_face(card.get("name", ""), card.get("type_line", ""), cmc, oracle, stats,
                  _image(card.get("image_uris")))]


class Sheets:
    """One single-card sheet per distinct picture. Thirty Swamps share one sheet,
    so a pile's CustomDeck stays as small as the number of different pictures."""

    def __init__(self):
        self.ids: dict[str, int] = {}
        self.images: dict[int, str] = {}

    def key(self, image: str) -> int:
        if image not in self.ids:
            self.ids[image] = len(self.ids) + 1
            self.images[self.ids[image]] = image
        return self.ids[image]

    @staticmethod
    def sheet(image: str) -> dict:
        return {"FaceURL": image, "BackURL": CARD_BACK, "NumWidth": 1, "NumHeight": 1,
                "BackIsHidden": True, "UniqueBack": False, "Type": 0}


def card_object(card: dict, sheets: Sheets) -> dict:
    """One Tabletop Simulator card, with its back face as state 2 when it has one.

    The front carries no CustomDeck of its own: `pile` lists every front's sheet
    once, as the importer does, and gives a lone card its sheet back. A back face
    always carries its own, since the pile's list covers fronts only."""
    front, *back = faces(card)

    def obj(face: dict, own_sheet: bool) -> dict:
        k = sheets.key(face["image"])
        out = {"Name": "Card", "Nickname": face["nickname"], "Description": face["description"],
               "CardID": k * 100, "Transform": dict(TRANSFORM), "HideWhenFaceDown": True}
        if own_sheet:
            out["CustomDeck"] = {str(k): Sheets.sheet(face["image"])}
        return out

    out = obj(front, own_sheet=False)
    if back:
        out["States"] = {"2": obj(back[0], own_sheet=True)}
    return out


def pile(name: str, cards: list[dict], sheets: Sheets) -> dict:
    """A deck of `cards`, or the card itself when there is only one: Tabletop
    Simulator has no one-card deck."""
    fronts = {c["CardID"] // 100 for c in cards}
    custom = {str(k): Sheets.sheet(sheets.images[k]) for k in sorted(fronts)}
    if len(cards) == 1:
        return {**cards[0], "CustomDeck": custom}
    return {"Name": "DeckCustom", "Nickname": name, "Transform": dict(TRANSFORM),
            "DeckIDs": [c["CardID"] for c in cards], "CustomDeck": custom,
            "ContainedObjects": cards, "HideWhenFaceDown": True}


# ---------- tokens ----------

def token_ids(cards: list[dict]) -> list[str]:
    """Scryfall ids of what the deck's cards make: tokens and emblems.

    `all_parts` also lists the card itself, its meld partner and the set's
    checklist card, so only the `token` component and emblems are taken. (Scryfall
    files Elspeth's emblem as a combo piece, which is why emblems are matched by
    type.)"""
    ids: list[str] = []
    for card in cards:
        own = card.get("id")
        for part in card.get("all_parts") or []:
            if part.get("id") == own:
                continue
            if part.get("component") == "token" or "Emblem" in (part.get("type_line") or ""):
                ids.append(part["id"])
    return list(dict.fromkeys(ids))


def distinct_tokens(tokens: list[dict]) -> list[dict]:
    """One of each token: printings of the same 1/1 Soldier collapse into one."""
    seen, out = set(), []
    for t in tokens:
        key = (t.get("name"), t.get("type_line"), t.get("oracle_text"), _stats(t))
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


# ---------- one deck, and the index ----------

def deck_file(d, tokens: dict[str, dict]) -> str:
    """The spawnable objects for DeckInfo `d`: header, library, commanders, tokens."""
    library_sheets, side_sheets = Sheets(), Sheets()
    leaders = set(d.commanders)
    library = []
    for entry in d.deck.entries:
        if entry.name in leaders or entry.name not in d.cards:
            continue
        library += [card_object(d.cards[entry.name], library_sheets)] * entry.count
    commanders = [pile(n, [card_object(d.cards[n], side_sheets)], side_sheets)
                  for n in d.commanders if n in d.cards]
    made = distinct_tokens([tokens[i] for i in token_ids([d.cards[n] for n in d.deck.names
                                                          if n in d.cards]) if i in tokens])
    token_objs = [card_object(t, side_sheets) for t in made]
    header = {"v": INDEX_VERSION, "name": d.stem, "commanders": len(commanders),
              "tokens": bool(token_objs)}
    lines = [header, pile(d.stem, library, library_sheets), *commanders]
    if token_objs:
        lines.append(pile("Tokens", token_objs, side_sheets))
    return "".join(json.dumps(o, ensure_ascii=False, separators=(",", ":")) + "\n" for o in lines)


def index_entry(d, path: str) -> dict:
    themes = deckthemes.visible(d.themes, local=False)
    tier = decktiers.visible(d.tier, local=False)
    return {"id": d.key, "name": d.stem, "owner": d.author, "commander": d.commander,
            "bracket": d.bracket, "bracketLabel": d.label, "tier": tier or "",
            "themes": list(themes), "colors": "".join(d.colours), "gc": len(d.gcs),
            "cap": d.cap, "mv": round(d.avg_mv, 2), "lands": d.lands,
            "added": d.created, "updated": d.modified, "file": path,
            "preview": preview_path(path) + "?v=" + hashlib.sha256(preview_file(d).encode()).hexdigest()[:12],
            "guide": bool(d.guide), "commanders": commander_preview(d),
            "commander_text": commander_text_path(path) + "?v=" + hashlib.sha256(commander_text_file(d).encode()).hexdigest()[:12]}


def preview_path(deck_path: str) -> str:
    return str(PurePosixPath(deck_path).with_suffix(".preview.json"))


def commander_text_path(deck_path: str) -> str:
    return str(PurePosixPath(deck_path).with_suffix(".commander.jsonl"))


def commander_text_file(d) -> str:
    """Small text-only records, fetched on selection rather than in the main index."""
    commanders = []
    for name in d.commanders:
        card = d.cards.get(name)
        if not card:
            continue
        text_faces = []
        for face in card.get("card_faces") or [card]:
            text_faces.append({key: face.get(key) or "" for key in
                               ("name", "mana_cost", "type_line", "oracle_text", "power", "toughness", "loyalty", "defense")})
        commanders.append({"name": name, "mv": card.get("cmc", 0), "faces": text_faces})
    return "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                   for record in ({"v": 1, "id": d.key, "count": len(commanders)}, *commanders))


def commander_preview(d) -> list[dict]:
    """Pinned faces in the catalog: selecting a deck needs no metadata request."""
    commanders = []
    for name in d.commanders:
        card = d.cards.get(name)
        if card:
            commanders.append({"name": name, "faces": [
                {"name": face["nickname"].split("\n", 1)[0], "FaceURL": face["image"]}
                for face in faces(card)]})
    return commanders


def preview_file(d) -> str:
    """Lazy-loaded illustrated guide, retaining commanders for older table builds."""
    commanders = commander_preview(d)
    guide = []
    for title, rows in d.guide:
        section = {"title": title, "rows": []}
        for name, text in rows:
            pictures = []
            for joiner, piece in deckguide.pieces(name) if name else []:
                card = d.cards.get(piece)
                pictures.append({"name": card.get("name", piece) if card else piece,
                                 "joiner": joiner, "faces": [
                                     {"name": face["nickname"].split("\n", 1)[0], "FaceURL": face["image"]}
                                     for face in faces(card)] if card else []})
            section["rows"].append({"name": name, "text": text, "cards": pictures})
        guide.append(section)
    return json.dumps({"v": 1, "id": d.key, "name": d.stem,
                       "commanders": commanders, "guide": guide}, ensure_ascii=False,
                      separators=(",", ":")) + "\n"


def sleeve_files() -> list[Path]:
    if not SLEEVES_DIR.is_dir():
        return []
    return sorted(p for p in SLEEVES_DIR.iterdir() if p.suffix.lower() in SLEEVE_TYPES)


def sleeve_thumb(p: Path) -> bytes | None:
    """A THUMB_W x THUMB_H JPEG of sleeve `p`, or None where it can't be made."""
    data = p.read_bytes()
    cached = THUMB_CACHE / f"{hashlib.sha256(data).hexdigest()[:16]}.jpg"
    if cached.is_file():
        return cached.read_bytes()
    if not SIPS.exists():
        return None
    THUMB_CACHE.mkdir(parents=True, exist_ok=True)
    tmp = cached.with_suffix(".tmp.jpg")
    r = subprocess.run([str(SIPS), "-z", str(THUMB_H), str(THUMB_W), "-s", "format", "jpeg",
                        "-s", "formatOptions", "80", str(p), "--out", str(tmp)],
                       capture_output=True, timeout=60)
    if r.returncode or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        return None
    tmp.replace(cached)
    return cached.read_bytes()


def sleeves() -> list[dict]:
    """The sleeves a player can pick: Magic's own back first, then tts/sleeves/ by name.
    `url` is absolute; `file` is relative to decks.json (with a content hash so TTS
    fetches updated art instead of serving a stale cached image for the same name)."""
    out = [{"id": "standard", "label": "Standard", "url": CARD_BACK, "thumb_url": CARD_BACK_THUMB}]
    for p in sleeve_files():
        label = p.stem.replace("-", " ").replace("_", " ").title()
        v = hashlib.sha256(p.read_bytes()).hexdigest()[:8]
        entry = {"id": p.stem, "label": label, "file": f"sleeves/{p.name}?v={v}"}
        if sleeve_thumb(p) is not None:
            entry["thumb"] = f"sleeves/thumbs/{p.stem}.jpg?v={v}"
        out.append(entry)
    return out


def tournament_keys() -> set[str]:
    """Deck ids tts/tournament.json lists; the catalog tags these decks."""
    if not TOURNAMENT_FILE.is_file():
        return set()
    return set(json.loads(TOURNAMENT_FILE.read_text(encoding="utf-8")).get("decks", []))


def tournament(decks: list) -> list[str]:
    """The curated tournament pool, as deck ids, in the file's order. A listed deck the
    catalog doesn't have (renamed or deleted) is left out with a warning, rather than
    failing every build."""
    if not TOURNAMENT_FILE.is_file():
        return []
    wanted = json.loads(TOURNAMENT_FILE.read_text(encoding="utf-8")).get("decks", [])
    have = {d.key for d in decks}
    for key in wanted:
        if key not in have:
            print(f"warning: {TOURNAMENT_FILE.name} lists {key}, which isn't in the catalog",
                  file=sys.stderr)
    return [k for k in dict.fromkeys(wanted) if k in have]


def index(decks: list, paths: dict[str, str]) -> dict:
    return {
        "v": INDEX_VERSION,
        "tiers": [{"id": k, "label": t.label, "title": t.title, "color": TIER_COLOURS.get(k, "#cccccc")}
                  for k, t in decktiers.TIERS.items() if not t.local_only],
        "themes": [{"id": k, "label": t.label} for k, t in deckthemes.THEMES.items()
                   if not t.local_only],
        "sleeves": sleeves(),
        "tournament": tournament(decks),
        "decks": [index_entry(d, paths[d.key]) for d in decks],
    }


def catalog_file(data: dict) -> str:
    """Same catalog metadata as decks.json, split into small frame-decodable records."""
    header = {key: value for key, value in data.items() if key != "decks"}
    header["count"] = len(data["decks"])
    return "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                   for record in (header, *data["decks"]))


def files(decks: list, out_dir: Path, q) -> dict[Path, str | bytes]:
    """Every docs/tts/ file for `decks` (build_site.DeckInfo objects)."""
    wanted = token_ids([c for d in decks for n in d.deck.names
                        if (c := d.cards.get(n)) is not None])
    try:
        tokens = q.by_ids(wanted) if wanted else {}
    except Exception:                       # tokens are a convenience: build without them
        tokens = {}
    root = out_dir / "tts"
    out: dict[Path, str | bytes] = {root / TILE_IMAGE.name: TILE_IMAGE.read_bytes()}
    for p in sleeve_files():
        out[root / "sleeves" / p.name] = p.read_bytes()
        thumb = sleeve_thumb(p)
        if thumb is not None:
            out[root / "sleeves" / "thumbs" / f"{p.stem}.jpg"] = thumb
    if SOUNDS_DIR.is_dir():
        for p in sorted(SOUNDS_DIR.iterdir()):
            if p.suffix.lower() in SOUND_TYPES:
                out[root / "sounds" / p.name] = p.read_bytes()
    if TABLE_ART_DIR.is_dir():
        for p in sorted(TABLE_ART_DIR.glob("*.png")):
            out[root / "table" / p.name] = p.read_bytes()
    paths: dict[str, str] = {}
    for d in decks:
        rel = Path(d.href).with_suffix(".ndjson").as_posix()   # <owner>/<Bracket>/<Deck>.ndjson
        paths[d.key] = rel
        out[root / rel] = deck_file(d, tokens)
        out[root / preview_path(rel)] = preview_file(d)
        out[root / commander_text_path(rel)] = commander_text_file(d)
    data = index(decks, paths)
    out[root / "decks.json"] = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
    out[root / "catalog.jsonl"] = catalog_file(data)
    return out
