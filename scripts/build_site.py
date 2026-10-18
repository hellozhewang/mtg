#!/usr/bin/env python3
"""Generate the static deck catalog that GitHub Pages publishes.

    ./build_site.py                  # rebuild docs/ from public/
    ./build_site.py --check          # exit 1 if docs/ is stale; write nothing
    ./build_site.py --out /tmp/site  # build elsewhere to look before publishing

EVERY DECK IS PUBLISHED, from one folder per owner: public/<user>/<Bracket>/.
A deck's page mirrors its file (`docs/<user>/<Bracket>/<Deck>.html`), so two
owners can each have a deck of the same name. The folder is the byline.

One file is NOT published: docs/index.local.html, the owner's copy of the index
with local-only categories and tiers (Goblins). It is gitignored, and the LAN
server (start_private_server.py) serves it as its home page.

Decks lived in public/<Bracket>/ and private/<Bracket>/ until 2026-10-18; every
old page path now holds a redirect (frontend/redirects.json), so links already
shared in Discord keep working.

Data comes from here, markup comes from `frontend/`:

    frontend/layout.html   page shell + the deck menu carried on every page
    frontend/index.html    the catalog
    frontend/deck.html     one deck
    frontend/style.css     copied to docs/ verbatim
    frontend/app.js        hover preview, lightbox, gallery toggle, copy button

    docs/index.html        <- generated
    docs/<Bracket>/<Deck>.html
    docs/img/*.webp        <- card thumbnails, see below
    docs/mana/*.svg        <- the real Magic mana symbols, from Scryfall
    docs/.nojekyll         serve the files as-is instead of running Jekyll

IMAGE HOSTING IS A SPLIT, and the reason is repo size. 818 unique cards across
the decks is 7.7 MB at thumbnail size but 78 MB at readable size, and git keeps
every version of a binary forever. So:

  * thumbnails (`thumb`, ~9 KB) are committed under docs/img/ and used for the
    gallery grid and catalog tiles — same-origin, instant, no external requests
    for the page as it first appears;
  * the readable image behind a hover or a click is loaded from
    `cards.scryfall.io` on demand, costing the repo nothing.

Either way **the bytes are cached in SQLite** (cardlib.ImageQuery), so deleting
docs/ and rebuilding from scratch downloads nothing. Image URLs are
content-addressed, so that cache never expires — see ImageStore.

THE OUTPUT MUST BE DETERMINISTIC. bot.py regenerates this after every model turn
and commits whatever changed, so anything varying run to run — a build timestamp,
an unsorted iteration, a random id — would mean an empty commit on every Discord
message. Hence: everything sorted, and no clock is read in here.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
from datetime import datetime, timezone
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deckfile
import deckguide
import deckthemes
import decktiers
import frontend
import toollog
import workspace
from cardlib import CardQuery, ImageQuery, ScryfallError, SymbolQuery, local_name
# Same policy as the validator, imported rather than restated: a bracket cap or a
# land count or mana average that disagreed with the validator would mislead.
from validate_deck import average_mana_value, commanders, gc_cap, land_counts

THUMB = "thumb"        # webp, 146x204, ~9 KB — committed
FULL = "normal"        # jpg, 488x680, ~96 KB — hotlinked
ART = "art"            # webp, landscape crop — committed, catalog tiles only

# Front-face type decides the section. The order is precedence, not display:
# "Artifact Creature" must land in Creatures, and Land is tested first *on the
# front face only* so an MDFC's land back face cannot drag it out of Instants.
CATEGORIES = [
    ("Land", "Lands"),
    ("Creature", "Creatures"),
    ("Planeswalker", "Planeswalkers"),
    ("Battle", "Battles"),
    ("Instant", "Instants"),
    ("Sorcery", "Sorceries"),
    ("Enchantment", "Enchantments"),
    ("Artifact", "Artifacts"),
]
# Commander first, and as its own section rather than a highlighted row inside
# Creatures: it is the one card always available, so it is the first thing anyone
# reading a list wants to see, and it is not really part of the creature count.
SECTION_ORDER = ["Commander", "Creatures", "Planeswalkers", "Instants",
                 "Sorceries", "Artifacts", "Enchantments", "Battles",
                 "Lands", "Other"]

COLOUR_NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}
MANA_TOKEN = re.compile(r"\{[^}]+\}")
TIP_ATTR = re.compile(r'data-tip="([^"]*)"')


# ---------- card helpers ----------

def category(card: dict) -> str:
    front = (card.get("type_line") or "").split(" // ")[0]
    for token, label in CATEGORIES:
        if token in front:
            return label
    return "Other"


def mana_cost(card: dict) -> str:
    """Front-face mana cost.

    A transforming double-faced card has NO top-level `mana_cost` — the cost sits
    on each face — so reading only the top level renders Serah Farron and friends
    as though they were free.
    """
    if card.get("mana_cost"):
        return card["mana_cost"]
    faces = card.get("card_faces") or []
    return (faces[0].get("mana_cost") if faces else "") or ""


def image_file(card: dict, face: int, size: str, url: str) -> str:
    """Committed filename for one of a card's images.

    Oracle id identifies the card across printings; `id` is the per-printing
    fallback for the rare object that has no oracle id (art series, tokens).

    A printing a decklist pins (see pinned_art) is the exception: it is filed
    under that printing's own id. It has to be, because another deck shows the
    same card in its default art and both pictures must exist; and it can be,
    because a pin names one fixed printing, so the name cannot drift the way a
    cached "whatever Scryfall returned" printing does.
    """
    return local_name(card.get(PINNED) or card.get("oracle_id") or card.get("id")
                      or "unknown", face, size, url)


PINNED = "pinned_printing_id"

# The owner's local index; see plan(). Must stay in .gitignore.
LOCAL_INDEX = "index.local.html"


def pinned_art(deck: deckfile.Deck, cards: dict[str, dict], q: CardQuery) -> dict[str, dict]:
    """Show the art of each printing a list pins, e.g. `1 Sol Ring (SLD) 249`.

    Returns `cards` with a COPY of each pinned card carrying that printing's
    pictures. Only the pictures change: rules text, cost and legality stay the
    card's own, and the shared card object other decks render is untouched.

    A pin that does not resolve or that names another card is left in default
    art, as is every pin if Scryfall cannot be reached. Reporting a bad pin is
    validate_deck.py's job; a cosmetic lookup must not fail a site build.
    """
    pins = {name: p for name, p in deck.printings.items() if p.number and name in cards}
    if not pins:
        return cards
    try:
        found = q.printings([(p.set, p.number) for p in pins.values()])
    except ScryfallError as exc:
        print(f"warning: pinned art not loaded for {deck.path.name} ({exc})", file=sys.stderr)
        return cards
    out = dict(cards)
    for name, p in pins.items():
        card, hit = cards[name], found.get((p.set, p.number))
        ours = {card.get("oracle_id")} | {f.get("oracle_id") for f in card.get("card_faces") or []}
        if not hit or not (ours - {None}) & set(hit["oracle_ids"]):
            continue
        if hit["id"] == card.get("id"):
            # The pin IS the printing we already show. Leave the shared object
            # alone: collect_images keeps one file per image URL, so filing the
            # same picture under a second name would leave one of them unwritten.
            continue
        shown = {**card, PINNED: hit["id"]}
        if hit["image_uris"]:
            shown["image_uris"] = hit["image_uris"]
        elif len(hit["face_images"]) == len(card.get("card_faces") or []):
            shown.pop("image_uris", None)
            shown["card_faces"] = [{**f, "image_uris": uris}
                                   for f, uris in zip(card["card_faces"], hit["face_images"])]
        else:
            continue
        out[name] = shown
    return out


def art_sets(card: dict) -> list[dict]:
    """The `image_uris` dicts for a card: one, or one per face on a DFC."""
    if card.get("image_uris"):
        return [card["image_uris"]]
    return [f["image_uris"] for f in card.get("card_faces") or [] if f.get("image_uris")]


def e(text: object) -> str:
    return html.escape(str(text), quote=True)


def mirror_tips(page: str) -> str:
    """Give every `data-tip` a matching `aria-label`.

    The tooltip itself is CSS `::after` content, which screen readers do not
    reliably announce — so the accessible name has to be a real attribute. Done
    here rather than in the templates so each sentence exists once instead of
    twice, where the two copies would drift.
    """
    return TIP_ATTR.sub(lambda m: f'{m.group(0)} aria-label="{m.group(1)}"', page)


def bracket_label(folder: str) -> str:
    """`Bracket3` -> `Bracket 3`, `Bracket4` -> `Bracket 4`.

    Display only. The folder name itself is the bracket's identity — it drives the
    Game Changer cap in validate_deck.py and the published URL — so it is never
    the thing that gets rewritten.
    """
    return re.sub(r"(?<=[A-Za-z])(?=\d)", " ", folder)


class Mana:
    """Renders `{W}{W}` as the real Magic symbols.

    Holds the symbol -> SVG-filename map and hands back <img> tags. Files land in
    docs/mana/ and are committed: 25 symbols cover every deck here and they total
    about 40 KB, so the argument that keeps card scans on Scryfall's CDN does not
    apply — these are small, reused hundreds of times per page, and better served
    same-origin.
    """

    def __init__(self, uris: dict[str, str]):
        self.uris = uris
        self.used: dict[str, str] = {}          # url -> filename, for collect()

    def _file(self, url: str) -> str:
        name = Path(urlsplit(url).path).name
        self.used[url] = name
        return name

    def render(self, cost: str, up: str) -> str:
        out = []
        for token in MANA_TOKEN.findall(cost or ""):
            url = self.uris.get(token)
            if url:
                out.append(f'<img class="ms" src="{up}mana/{e(self._file(url))}"'
                           f' alt="{e(token)}" width="15" height="15">')
            else:                               # unknown symbol: show the text
                out.append(f'<span class="ms-text">{e(token)}</span>')
        return "".join(out)

    def pips(self, colours: list[str], up: str) -> str:
        """A deck's colour identity, as the five mana symbols."""
        tokens = [f"{{{c}}}" for c in sorted(colours, key="WUBRG".index)] or ["{C}"]
        out = []
        for token in tokens:
            title = COLOUR_NAMES.get(token[1], "Colourless")
            url = self.uris.get(token)
            if url:
                out.append(f'<img class="pip" src="{up}mana/{e(self._file(url))}"'
                           f' alt="{e(title)}" title="{e(title)}"'
                           f' width="19" height="19">')
            else:
                out.append(f'<span class="ms-text">{e(token)}</span>')
        return "".join(out)


# ---------- model ----------

class DeckInfo:
    """One decklist, resolved against Scryfall and ready to render."""

    def __init__(self, path: Path, root: Path, q: CardQuery,
                 created: int = 0, modified: int = 0,
                 theme_assignments: dict[str, tuple[str, ...]] | None = None,
                 tier_assignments: dict[str, str] | None = None):
        self.path = path
        self.created = created
        # Date AND time, so decks added the same day still read in order. Written
        # in UTC so the build is the same on every machine; app.js rewrites it in
        # each visitor's own timezone. Git records the time for every deck, so
        # none needs a guessed 00:00.
        self.created_label = _utc_label(created)
        # Shown only for a real later edit. Finishing a new deck rewrites it for
        # minutes after it first appears, and "updated" five minutes after "added"
        # says nothing.
        self.modified = modified if modified >= created + UPDATE_GAP else 0
        self.modified_label = _utc_label(self.modified)
        # `<owner>/<Bracket>/<Deck>.txt`. The folder IS the owner: the builder
        # writes only in the folder of whoever asked, so no other record is needed.
        self.rel = path.resolve().relative_to(root)
        self.author = self.rel.parts[0]
        # Grouping is by BRACKET across every owner's decks.
        self.bracket = self.rel.parent.name
        self.label = bracket_label(self.bracket)
        self.stem = path.stem
        # Maps are keyed `<owner>/<Deck>`: two owners may each have a Giada-Angels.
        self.key = f"{self.author}/{self.stem}"
        self.themes = deckthemes.classify(self.key, theme_assignments or {})
        # None until someone places the deck; the catalog shows it as Unrated.
        self.tier = decktiers.classify(self.key, tier_assignments or {})
        # The page mirrors the file's place: `<owner>/<Bracket>/<Deck>.html`.
        self.href = self.rel.with_suffix(".html").as_posix()
        self.depth = self.href.count("/")
        self.deck = deckfile.parse(path)
        self.cards, self.missing = q.cards(self.deck.names)
        self.cards = pinned_art(self.deck, self.cards, q)
        self.raw = path.read_text(encoding="utf-8")
        self.guide = deckguide.load(path)
        # A guide may name a card the deck does not run — a card it beat, or one
        # you would side toward. Resolve those too or their rows render imageless.
        extra = [n for n in deckguide.card_names(self.guide) if n not in self.cards]
        if extra:
            found, _missing = q.cards(extra)
            self.cards = {**self.cards, **found}

        # One commander, or a partner pair on lines 1 and 2 (validate_deck rules).
        # The pair's names read together; line 1 supplies the art and preview.
        self.commanders = commanders(self.deck, self.cards)
        self.commander = " & ".join(self.commanders)
        cmd = self.cards.get(self.deck.commander)
        self.colours = sorted({c for name in self.commanders
                               for c in self.cards.get(name, {}).get("color_identity") or []},
                              key="WUBRG".index)
        arts = art_sets(cmd or {})
        self.art_url = arts[0].get(ART, "") if arts else ""
        self.art_card = cmd or {}

        self.lands, self.flex = land_counts(self.deck, self.cards)
        self.cap = gc_cap(path, None)
        self.gcs = sorted(n for n in self.deck.names
                          if self.cards.get(n, {}).get("game_changer"))
        self.avg_mv = average_mana_value(self.deck, self.cards)

    @property
    def total(self) -> int:
        return self.deck.total

    @property
    def gc_label(self) -> str:
        return f"{len(self.gcs)}/{self.cap}" if self.cap is not None \
            else f"{len(self.gcs)} (uncapped)"

    def sections(self) -> list[tuple[str, list[tuple[int, str, dict]]]]:
        """Entries bucketed by card type, each bucket sorted by cost then name."""
        buckets: dict[str, list] = {}
        for i, entry in enumerate(self.deck.entries):
            card = self.cards.get(entry.name, {})
            # Line 1 is the commander by format definition, and line 2 too when it
            # is a legal partner -- keyed on position, not on a name match, so a
            # deck that (illegally) repeats a name cannot pull a third card in.
            bucket = "Commander" if i < len(self.commanders) else category(card)
            buckets.setdefault(bucket, []).append((entry.count, entry.name, card))
        for rows in buckets.values():
            rows.sort(key=lambda r: (r[2].get("cmc", 0) or 0, r[1].lower()))
        return [(name, buckets[name]) for name in SECTION_ORDER if name in buckets]

    def curve(self) -> list[tuple[str, int]]:
        """Nonland mana curve, 0..6 then 7+. Counts copies, so `16 Swamp` stays
        out rather than flattening the graph into a spike at zero."""
        counts = [0] * 8
        for entry in self.deck.entries:
            card = self.cards.get(entry.name)
            if not card or "Land" in (card.get("type_line") or "").split(" // ")[0]:
                continue
            counts[min(int(card.get("cmc", 0) or 0), 7)] += entry.count
        return [(str(i) if i < 7 else "7+", n) for i, n in enumerate(counts)]


# ---------- rendering ----------

def picker(layout: frontend.Template, decks: list[DeckInfo],
           current: DeckInfo | None, up: str) -> str:
    groups, bracket, opts = [], None, []
    for d in decks:
        if d.bracket != bracket:
            if bracket is not None:
                groups.append(layout.part("picker-group").render(
                    BRACKET=e(bracket_label(bracket)), OPTIONS="".join(opts)))
            bracket, opts = d.bracket, []
        opts.append(layout.part("picker-option").render(
            HREF=up + e(d.href),
            SELECTED=" selected" if current is d else "",
            # Owners can share a deck name, so each option says whose it is.
            LABEL=f"{e(d.stem)} — {e(d.commander)} · {e(d.author)}"))
    if bracket is not None:
        groups.append(layout.part("picker-group").render(
            BRACKET=e(bracket_label(bracket)), OPTIONS="".join(opts)))
    return "".join(groups)


def render_index(tpl: dict[str, frontend.Template], decks: list[DeckInfo],
                 repo: str, mana: Mana,
                 available_images: set[str] | None = None,
                 local: bool = False) -> str:
    """The catalog index. `local` renders the owner's copy (index.local.html),
    the only one that shows local-only categories such as Goblins."""
    index, layout = tpl["index"], tpl["layout"]
    grouped: dict[str, set[str]] = {}
    by_bracket: dict[str, list[str]] = {}
    # Local-only categories MIRROR decks that already sit in a canonical one:
    # theme -> bracket -> copies of the tiles, rendered here and never moved.
    mirrors: dict[str, dict[str, list[str]]] = {}
    active_themes = set()

    for d in decks:
        shown = deckthemes.visible(d.themes, local)
        grouped.setdefault(shown[0], set()).add(d.bracket)
        active_themes.update(shown)
        art_name = image_file(d.art_card, 0, ART, d.art_url) if d.art_url else ""
        # A transient CDN failure must not leave a dangling <img> in the
        # published catalog. `None` preserves the standalone renderer's old
        # behavior; production passes the filenames fetched for this build.
        has_art = bool(art_name and
                       (available_images is None or art_name in available_images))
        art = (f'<img class="art" src="img/{e(art_name)}" alt=""'
               f' loading="lazy" decoding="async" width="626" height="457">'
               if has_art else '<span class="art-blank"></span>')
        # Use the commander's full front face, not the cropped catalog art.
        # URLs in data attributes load only on hover; the local thumbnail is
        # a fallback when the readable CDN image cannot be reached.
        faces = art_sets(d.art_card)
        front = faces[0] if faces else {}
        preview = ""
        if front.get(FULL):
            preview = f' data-name="{e(d.commanders[0])}" data-img="{e(front[FULL])}"'
            thumb_name = (image_file(d.art_card, 0, THUMB, front[THUMB])
                          if front.get(THUMB) else "")
            if thumb_name and (available_images is None or thumb_name in available_images):
                preview += f' data-thumb="img/{e(thumb_name)}"'
        tier = decktiers.visible(d.tier, local)
        tile = index.part("tile").render(
            HREF=e(d.href), ART=art, NAME=e(d.stem), COMMANDER=e(d.commander),
            PREVIEW=preview,
            BRACKET_ID=e(d.bracket), TIER=e(tier or decktiers.UNRATED_ID),
            TIER_BADGE=tier_badge(index, tier),
            THEMES=e(" ".join(shown)),
            THEME_TAGS="".join(index.part("theme-tag").render(
                LABEL=e(deckthemes.THEMES[t].label),
                CLASS=" local" if deckthemes.THEMES[t].local_only else "")
                for t in shown),
            AUTHOR=(f'        <span class="tile-author">by {e(d.author)}</span>\n'
                    if d.author else ""),
            # The existing free-text filter reads data-search, so including the
            # author makes a username a first-class filter with no second state.
            CREATED=(f'<span class="chip date" data-ts="{d.created}" data-tip="When this '
                     f'deck was first added to the collection, in your local time.">'
                     f'{e(d.created_label)} UTC</span>'
                     if d.created_label else ""),
            UPDATED=updated_chip(d),
            # The date joins data-search too, so typing "2026-08" in the box
            # filters the catalog to that month at no extra cost.
            SEARCH=e(" ".join(x for x in
                              (d.stem, d.commander, d.label, d.author,
                               d.created_label, d.modified_label,
                               deckthemes.search_text(shown),
                               d.art_card.get("type_line", ""),
                               # Last, so the folded `stier` token cannot run
                               # into a following word and match the wrong tier.
                               decktiers.search_text(tier)) if x)),
            PIPS=mana.pips(d.colours, ""), TOTAL=d.total, LANDS=d.lands,
            MV=f"{d.avg_mv:.2f}",
            GC=f"{len(d.gcs)}/{d.cap}" if d.cap is not None else str(len(d.gcs)))
        by_bracket.setdefault(d.bracket, []).append(tile)
        for t in shown:
            if deckthemes.THEMES[t].local_only:
                # A second link to the same deck. `mirror` keeps the script from
                # moving it and keeps it out of the deck count.
                mirrors.setdefault(t, {}).setdefault(d.bracket, []).append(
                    tile.replace('<a class="tile"', '<a class="tile mirror"', 1))
    sections = []
    for key, theme in deckthemes.THEMES.items():
        if theme.local_only:
            if key not in mirrors:
                continue
            brackets = [index.part("bracket").render(
                BRACKET=e(bracket_label(bracket)), BRACKET_ID=e(bracket),
                TILES="".join(tiles)) for bracket, tiles in sorted(mirrors[key].items())]
        elif key in grouped:
            brackets = [index.part("bracket").render(
                BRACKET=e(bracket_label(bracket)), BRACKET_ID=e(bracket),
                TILES="") for bracket in sorted(grouped[key])]
        else:
            continue
        sections.append(index.part("strategy").render(
            THEME=e(key), LABEL=e(theme.label), DESCRIPTION=e(theme.description),
            # Local-only categories are badged so they never pass for public ones.
            LOCAL=index.part("category-local").render() if theme.local_only else "",
            BRACKETS="".join(brackets)))
    options = "".join(index.part("theme-option").render(
        VALUE=e(key), LABEL=e(theme.label + (" (local)" if theme.local_only else "")))
        for key, theme in deckthemes.THEMES.items() if key in active_themes)
    brackets = "".join(index.part("list-bracket").render(
        BRACKET=e(bracket_label(bracket)), BRACKET_ID=e(bracket),
        TILES="".join(tiles)) for bracket, tiles in sorted(by_bracket.items()))
    # Tiers view: empty destinations, strongest first, Unrated last. The script
    # moves the same tiles in, as it does for Categories.
    present = {decktiers.visible(d.tier, local) or decktiers.UNRATED_ID for d in decks}
    tiers = "".join(index.part("tier").render(
        TIER=e(key), LABEL=e(t.label), TITLE=e(t.title), DESCRIPTION=e(t.description))
        for key, t in [*decktiers.TIERS.items(), (decktiers.UNRATED_ID, decktiers.UNRATED)]
        if key in present)

    return mirror_tips(layout.render(
        TITLE="Commander decks", UP="", REPO=e(repo),
        DESCRIPTION=f"{len(decks)} Magic: the Gathering Commander decklists.",
        PICKER=picker(layout, decks, None, ""),
        MAIN=index.render(COUNT=len(decks), OPTIONS=options,
                          BRACKETS=brackets, CATEGORIES="".join(sections),
                          TIERS=tiers)))


def updated_chip(d: DeckInfo) -> str:
    """`updated <date>`, for a deck edited after it was first added. The date sits
    in its own element because app.js rewrites a [data-ts] element's whole text
    in the visitor's timezone, which would otherwise erase the word."""
    if not d.modified_label:
        return ""
    return (f'<span class="chip date" data-tip="When this deck\'s list or guide last '
            f'changed, in your local time.">updated <span data-ts="{d.modified}">'
            f'{e(d.modified_label)} UTC</span></span>')


def tier_badge(tpl: frontend.Template, tier: str | None) -> str:
    """The coloured tier mark used on tiles and the deck header."""
    t = decktiers.info(tier)
    return tpl.part("tier-badge").render(
        TIER=e(tier or decktiers.UNRATED_ID), LABEL=e(t.label),
        TIP=e(f"{t.title}. {t.description}"))


def render_guide(page: frontend.Template, d: "DeckInfo",
                 mana: "Mana", up: str) -> tuple[str, str]:
    """(guide article, guide button). Empty strings when the deck has no guide.

    Returning the button alongside the article keeps the two from drifting: a
    page can never show a Guide tab with nothing behind it, or a guide nobody can
    reach.
    """
    if not d.guide:
        return "", ""
    out = []
    for title, rows in d.guide:
        body = []
        for name, note in rows:
            if not name:
                body.append(page.part("guide-prose").render(TEXT=e(note)))
                continue
            parts = deckguide.pieces(name)
            if len(parts) > 1:
                body.append(render_guide_combo(page, d, parts, note, up))
                continue
            card = d.cards.get(name, {})
            img, data = guide_media(card, name, up)
            body.append(page.part("guide-card").render(
                NAME=e(card.get("name", name)), DATA=data, IMG=img,
                COST=mana.render(mana_cost(card), up), NOTE=e(note)))
        if title:
            out.append(page.part("guide-section").render(
                TITLE=page.part("guide-title").render(TEXT=e(title)), ROWS="".join(body)))
        else:
            out.append(page.part("guide-intro").render(ROWS="".join(body)))
    return (page.part("guide").render(SECTIONS="".join(out)),
            page.part("guidebtn").render())


def render_guide_combo(page: frontend.Template, d: "DeckInfo",
                       parts: list[tuple[str, str]], note: str, up: str) -> str:
    """A guide row naming several cards: `A + B` (a combo) or `A -> B` (a tutor
    or sequencing line). Each card is its own zoomable piece — the lightbox looks
    for the nearest element carrying data-img, so a click opens the card under
    the pointer rather than the first card of the row."""
    pics, names = [], []
    for joiner, name in parts:
        card = d.cards.get(name, {})
        shown = card.get("name", name)
        if joiner:
            sign = "→" if joiner == "->" else "+"
            pics.append(page.part("guide-join").render(SIGN=sign))
            names.append(f" {sign} ")
        img, data = guide_media(card, name, up)
        pics.append(page.part("guide-piece").render(NAME=e(shown), DATA=data, IMG=img))
        names.append(shown)
    return page.part("guide-combo").render(
        PIECES="".join(pics), NAMES=e("".join(names)), NOTE=e(note))


def guide_media(card: dict, name: str, up: str) -> tuple[str, str]:
    """(thumbnail <img>, data-* attributes) for one card in a guide row."""
    uris = art_sets(card)
    data = img = ""
    if uris:
        thumb = f"{up}img/{e(image_file(card, 0, THUMB, uris[0][THUMB]))}"
        # Small by choice: the guide is prose you read, and the card is
        # there to identify what the sentence is about, not to be read
        # itself. Click zooms it to full size via the lightbox below.
        #
        # LOCAL THUMB ONLY, no srcset. An earlier version offered the
        # 488px `normal` as a second candidate so a 2x display would get
        # a sharp 88px image — but at DPR 2 the browser needs 176px, so
        # it rejected the 146px thumb and fetched the 488px one from
        # cards.scryfall.io for EVERY row, on page load. That is ~50
        # hotlinked images per guide, and on any machine that cannot
        # reach that host the whole guide renders as broken-image icons.
        # It also contradicts the hosting split at the top of this file:
        # external images are for hover and click, not first paint.
        # 146px into an 88px box is mildly soft at 2x; that is the trade.
        img = (f'<img class="gthumb" src="{thumb}" alt="{e(name)}"'
               f' loading="lazy" decoding="async" width="88" height="123">')
        # Same data-* the list view uses, so the existing hover preview
        # and lightbox work here with no extra JavaScript.
        data = f' data-img="{e(uris[0].get(FULL, ""))}"'
        if len(uris) > 1:
            data += f' data-back="{e(uris[1].get(FULL, ""))}"'
    return img, data


def render_deck(tpl: dict[str, frontend.Template], d: DeckInfo,
                decks: list[DeckInfo], repo: str, mana: Mana) -> str:
    page, layout = tpl["deck"], tpl["layout"]
    up = "../" * d.depth
    source = f"public/{d.rel.as_posix()}"
    links = page.part("links").render(
        RAW=e(repo.replace("https://github.com/", "https://raw.githubusercontent.com/")
              + f"/main/{source}"),
        BLOB=e(f"{repo}/blob/main/{source}"))

    gclist = page.part("gclist").render(NAMES="".join(
        page.part("gcname").render(NAME=e(n)) for n in d.gcs)) if d.gcs else ""
    warn = page.part("warn").render(
        NAMES=e(", ".join(sorted(d.missing)))) if d.missing else ""

    guide_html, guide_btn = render_guide(page, d, mana, up)

    peak = max((n for _, n in d.curve()), default=0) or 1
    bars = "".join(page.part("bar").render(
        N=n, MV=label, PCT=round(100 * n / peak), LABEL=n or "")
        for label, n in d.curve())

    sections = []
    for name, rows in d.sections():
        rendered = []
        for count, cardname, card in rows:
            uris = art_sets(card)
            data = ""
            if uris:
                data = (f' data-img="{e(uris[0].get(FULL, ""))}"'
                        f' data-thumb="{up}img/'
                        f'{e(image_file(card, 0, THUMB, uris[0][THUMB]))}"')
                if len(uris) > 1:
                    data += f' data-back="{e(uris[1].get(FULL, ""))}"'
            rendered.append(page.part("card").render(
                CLASS="card cmdr" if cardname in d.commanders else "card",
                NAME=e(cardname), DATA=data, QTY=count,
                GCFLAG='<span class="gcflag" data-tip="Game Changer — on '
                       'Wizards\' list of the format\'s most powerful cards">GC</span>'
                       if card.get("game_changer") else "",
                COST=mana.render(mana_cost(card), up)))
        sections.append(page.part("section").render(
            NAME=e(name), N=sum(c for c, _, _ in rows), CARDS="".join(rendered)))

    return mirror_tips(layout.render(
        TITLE=f"{d.stem} — {d.commander}", UP=up, REPO=e(repo),
        DESCRIPTION=f"{e(d.commander)} — {d.total}-card Commander deck, "
                    f"{d.label}, {d.gc_label} Game Changers.",
        PICKER=picker(layout, decks, d, up),
        MAIN=page.render(
            NAME=e(d.stem), PIPS=mana.pips(d.colours, up), COMMANDER=e(d.commander),
            BRACKET=e(d.label), TOTAL=d.total,
            # Deck pages are shared by the published site and the local index,
            # so they show only a tier that is not local-only.
            TIER=tier_badge(page, tier) if (tier := decktiers.visible(d.tier, False)) else "",
            LINKS=links,
            DATES=(f'<span class="chip date" data-tip="When this deck was first added '
                   f'to the collection, in your local time.">added <span data-ts="{d.created}">'
                   f'{e(d.created_label)} UTC</span></span>' if d.created_label else "")
                  + updated_chip(d),
            LANDS=f"{d.lands}" + (f" +{d.flex}" if d.flex else ""),
            # A modal DFC like Malakir Rebirth is `Instant // Land`: playable as a
            # tapped land but not a mana source you can plan around, so it is
            # counted apart from the real lands rather than inflating them.
            LANDNOTE=(f"{d.lands} lands, plus {d.flex} modal double-faced "
                      f"card{'s' if d.flex > 1 else ''} playable as a land"
                      if d.flex else f"{d.lands} lands"),
            MV=f"{d.avg_mv:.2f}", GC=e(d.gc_label),
            GUIDE=guide_html, GUIDEBTN=guide_btn,
            GCLIST=gclist, WARN=warn, CURVE=bars,
            RAWLIST=e(d.raw),
            SECTIONS="".join(sections))))


# ---------- driver ----------




def deck_history(checkout: Path, trees: list[str]) -> tuple[dict[Path, int], dict[Path, int]]:
    """(first added, last changed) for every deck file git knows, as unix times.

    One `git log` over the deck trees, oldest commit first, following renames, so
    a deck keeps its history when it moves: every deck moved into an owner folder
    on 2026-10-18, and before that the owner's decks moved out of private/.

      * added: the first commit that added the file. A deck deleted and added
        back (Krenko) keeps its FIRST add, the date it was actually created.
      * changed: the last commit that changed its content. A pure move (R100)
        is not a change; a move with edits is. The add is not a change either:
        that is the creation date's business.

    Then what is not committed yet, from `git status`: a staged move maps the
    old path's history onto the new one, so a build made just before committing
    a move dates every deck exactly as the build after it will; and a file with
    uncommitted edits takes its own modification time, because bot.py builds
    BEFORE it commits a turn's decks and the page it publishes must already
    carry the edit. That mtime is the one deliberate exception to determinism:
    once committed, the next build swaps it for the commit's time, minutes later.
    That change rides along with the next real commit; autopush never makes a
    commit for it alone, since it commits only when a deck changed.
    """
    added: dict[str, int] = {}
    changed: dict[str, int] = {}
    try:
        log = subprocess.run(
            ["git", "-C", str(checkout), "log", "--reverse", "-M", "--format=%x01%at",
             "--name-status", "--", *trees],
            capture_output=True, text=True, timeout=30).stdout if trees else ""
        status = subprocess.run(
            ["git", "-C", str(checkout), "status", "--porcelain=v2",
             "--untracked-files=no", "--", *trees],
            capture_output=True, text=True, timeout=30).stdout if trees else ""
    except (OSError, subprocess.SubprocessError):
        log = status = ""

    def moved(old: str, new: str) -> None:
        if old in added:
            added[new] = min(added.pop(old), added.get(new, 2**62))
        if old in changed:
            changed[new] = changed.pop(old)

    stamp = 0
    for line in log.splitlines():
        if line.startswith("\x01"):
            stamp = int(line[1:])
            continue
        code, *paths = line.split("\t")
        if code.startswith("R") and len(paths) == 2:
            moved(*paths)
            if code != "R100":
                changed[paths[1]] = stamp
        elif code == "A" and paths:
            added.setdefault(paths[0], stamp)
        elif code == "M" and paths:
            changed[paths[0]] = stamp

    for line in status.splitlines():
        if line.startswith("2 "):                   # staged move: "2 XY ... R<score> new\told"
            fields, old = line.split("\t", 1)
            parts = fields.split(" ", 9)
            xy, score, path = parts[1], parts[8], parts[9]
            moved(old, path)
            edited = score != "R100" or xy[1] != "."
        elif line.startswith("1 "):                 # "1 XY ... path"
            parts = line.split(" ", 8)
            xy, path = parts[1], parts[8]
            edited = "M" in xy
        else:
            continue
        if edited and (checkout / path).is_file():
            changed[path] = int((checkout / path).stat().st_mtime)

    def absolute(d: dict[str, int]) -> dict[Path, int]:
        return {(checkout / p).resolve(): t for p, t in d.items()}
    return absolute(added), absolute(changed)


def created_at(path: Path, added: dict[Path, int]) -> int:
    """The earlier of git's first add and the file's own birth time.

    Either can be the late one. A deck drafted locally before its first commit was
    born before git saw it, which is true of every deck that once lived in
    private/; a file git rewrote (a fresh clone, a checkout) was born after. The
    published build only ever runs on this machine, where the bot runs, and
    editing a file in place keeps its birth time."""
    st = path.stat()
    birth = int(getattr(st, "st_birthtime", st.st_mtime))
    return min(added.get(path.resolve(), birth), birth)


def modified_at(path: Path, changed: dict[Path, int]) -> int:
    """The later of the decklist's and its guide's last change; a guide edit is
    an edit to the deck."""
    return max(changed.get(path.resolve(), 0),
               changed.get(path.with_suffix(".guide").resolve(), 0))


# An edit this soon after a deck first appeared is part of building it.
UPDATE_GAP = 3600


def _utc_label(stamp: int) -> str:
    return datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m-%d %H:%M") if stamp else ""


def collect_images(decks: list[DeckInfo], img: ImageQuery,
                   out_dir: Path) -> dict[Path, bytes]:
    """Fetch every committed image once, deduplicated across decks.

    Deduplication is the point: 14 decks share 818 distinct cards, and the same
    Sol Ring thumbnail must not be downloaded, stored or committed 14 times.
    """
    wanted: dict[str, Path] = {}
    for d in decks:
        if d.art_url:
            wanted[d.art_url] = (out_dir / "img" /
                                 image_file(d.art_card, 0, ART, d.art_url))
        for card in d.cards.values():
            for face, uris in enumerate(art_sets(card)):
                if url := uris.get(THUMB):
                    wanted[url] = (out_dir / "img" /
                                   image_file(card, face, THUMB, url))

    # Two URLs mapping to one file is a silent data-loss bug — one image simply
    # overwrites the other and the page still validates. It has happened once
    # (see local_name), so it fails the build now rather than shipping.
    if len(set(wanted.values())) != len(wanted):
        seen: dict[Path, str] = {}
        for url, path in sorted(wanted.items()):
            if path in seen:
                raise SystemExit(
                    f"image filename collision: {path.name}\n  {seen[path]}\n  {url}")
            seen[path] = url

    # Commit as we go, not once at the end. A cold build downloads ~830 images
    # and bot.py kills it at SITE_TIMEOUT; with a single commit at the end, a
    # timeout would discard every byte fetched and the next turn would start from
    # zero — the site would never finish building. Committing in batches makes an
    # interrupted build resumable, which is the difference between "slow once" and
    # "never succeeds".
    files: dict[Path, bytes] = {}
    for i, url in enumerate(sorted(wanted), 1):
        if body := img.get(url):
            files[wanted[url]] = body
        if i % 50 == 0:
            img.commit()
    img.commit()
    return files


def collect_symbols(mana: Mana, sym: SymbolQuery, out_dir: Path) -> dict[Path, bytes]:
    """SVGs for the mana symbols the pages actually reference.

    Driven by `mana.used`, populated as the pages rendered, so a symbol no deck
    uses is never downloaded or committed — 25 of Magic's 84, here.
    """
    files: dict[Path, bytes] = {}
    for url, name in sorted(mana.used.items()):
        if body := sym.svg(url):
            files[out_dir / "mana" / name] = body
    sym.commit()
    return files


def plan(root: Path, out_dir: Path, repo: str, q: CardQuery,
         img: ImageQuery, sym: SymbolQuery) -> dict[Path, str | bytes]:
    """Every file the site consists of, as {path: content}. Nothing written yet.

    Building the whole thing in memory first is what makes `--check` possible and
    what lets sync() write only real differences.
    """
    tpl = frontend.load(workspace.frontend_dir())
    fdir = workspace.frontend_dir()
    assignments = deckthemes.load(fdir / "deck-themes.json")
    tiers = decktiers.load(fdir / "deck-tiers.json")
    checkout = root.parent
    # `private` is history only: the owner's decks lived there until 2026-10-18,
    # and following their moves keeps their dates.
    added, changed = deck_history(checkout, [root.name, "private"]
                                  if checkout in root.parents else [])
    decks = sorted((DeckInfo(p, root, q,
                             created=created_at(p, added),
                             modified=modified_at(p, changed),
                             theme_assignments=assignments,
                             tier_assignments=tiers)
                    for p in deckfile.discover_collection(root)),
                   # Bracket order also drives the deck picker. Both index views
                   # preserve newest-first order within each bracket or category
                   # subgroup. Name, then owner, breaks ties deterministically.
                   key=lambda d: (d.bracket, -d.created, d.stem.lower(), d.author))
    # Every deck is meant to have a tier (deck-tiers.md). Say which do not.
    unrated = [d.key for d in decks if not d.tier]
    if unrated:
        print(f"warning: {len(unrated)} deck(s) have no power tier: "
              f"{', '.join(unrated)} — see deck-tiers.md", file=sys.stderr)
    mana = Mana(sym.uris())
    image_files = collect_images(decks, img, out_dir)
    available_images = {path.name for path in image_files}

    files: dict[Path, str | bytes] = {
        out_dir / "index.html": render_index(tpl, decks, repo, mana, available_images),
        # The owner's copy of the index, with local-only categories (Goblins).
        # Gitignored, so Pages never has it; start_private_server.py serves it
        # as the home page of the LAN catalog. Only the index differs: deck
        # pages show no categories, so they are shared with the published site.
        out_dir / LOCAL_INDEX: render_index(tpl, decks, repo, mana, available_images,
                                            local=True),
        out_dir / "style.css": (fdir / "style.css").read_text(encoding="utf-8"),
        out_dir / "app.js": (fdir / "app.js").read_text(encoding="utf-8"),
        out_dir / ".nojekyll": "",
    }
    for d in decks:
        files[out_dir / d.href] = render_deck(tpl, d, decks, repo, mana)
        # The bare list beside each page, so the Random button can fetch ~2 KB
        # ahead of the click instead of a whole deck page.
        files[(out_dir / d.href).with_suffix(".txt")] = d.raw
    files.update(redirect_pages(tpl, decks, out_dir, fdir / "redirects.json", files))
    files.update(image_files)
    files.update(collect_symbols(mana, sym, out_dir))   # after render: needs .used
    return files


def redirect_pages(tpl: dict[str, frontend.Template], decks: list[DeckInfo],
                   out_dir: Path, mapping: Path,
                   taken: dict[Path, str | bytes]) -> dict[Path, str]:
    """A tiny page at each pre-2026-10-18 deck URL that forwards to where the deck
    lives now, so links already shared in Discord keep working.

    Until then a deck's page was `<Bracket>/<Deck>.html` (and the owner's decks
    `private/<Bracket>/<Deck>.html`); `mapping` records where each one went. A
    target that no longer exists (the deck was renamed or deleted since) gets no
    redirect, and an old path is never allowed to shadow a real page."""
    if not mapping.exists():
        return {}
    live = {d.href: d for d in decks}
    pages: dict[Path, str] = {}
    for old, new in sorted(json.loads(mapping.read_text(encoding="utf-8")).items()):
        target = out_dir / old
        if new not in live or target in taken:
            continue
        pages[target] = tpl["redirect"].render(
            NAME=e(live[new].stem), TO=e("../" * old.count("/") + new))
    return pages


def _same(path: Path, body: str | bytes) -> bool:
    if not path.exists():
        return False
    if isinstance(body, bytes):
        return path.read_bytes() == body
    try:
        return path.read_text(encoding="utf-8") == body
    except UnicodeDecodeError:
        return False


def sync(files: dict[Path, str | bytes], out_dir: Path) -> tuple[int, int]:
    """Write what changed, delete what no longer belongs. Returns (written, removed).

    Writing only on difference is what keeps `git status` quiet between real deck
    edits; pruning is what stops a renamed deck leaving a stale page live forever.

    **Pruning is confined to `out_dir`. It never touches the database.** Deleting a
    deck removes its page and any card image no longer used by another deck, but
    every cached card, page and image row stays. That is what makes deletion cheap
    to undo: restoring the .txt and rebuilding costs zero downloads, because the
    bytes were never thrown away. Measured — remove a deck, rebuild, restore,
    rebuild: `images 937 hit / 0 miss, 0 downloads`.
    """
    written = 0
    for path, body in sorted(files.items()):
        if _same(path, body):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(body, bytes):
            path.write_bytes(body)
        else:
            path.write_text(body, encoding="utf-8")
        written += 1

    removed = 0
    if out_dir.exists():
        for path in sorted(out_dir.rglob("*"), reverse=True):
            if path.is_file() and path not in files:
                path.unlink()
                removed += 1
            elif path.is_dir() and not any(path.iterdir()):
                path.rmdir()
    return written, removed


def report(files: dict[Path, str | bytes], out_dir: Path,
           written: int, removed: int) -> None:
    """One line summarising the build."""
    # Each deck page has its bare list beside it; nothing else in docs/ is a .txt.
    decks = sum(1 for p in files if p.suffix == ".txt")
    mb = sum(len(b) for b in files.values() if isinstance(b, bytes)) / 1048576
    print(f"{decks} decks -> {out_dir}  "
          f"({written} written, {removed} removed, {len(files)} files, "
          f"{mb:.1f} MB images)")


def main() -> int:
    toollog.record()
    ap = argparse.ArgumentParser(description="Build the static deck catalog.")
    ap.add_argument("--out", type=Path,
                    help="output directory (default: docs/)")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the published site is stale; write nothing")
    ap.add_argument("--quiet", action="store_true", help="only report problems")
    args = ap.parse_args()

    root = workspace.deck_root()
    out_dir = args.out.expanduser().resolve() if args.out else workspace.site_dir()
    q = CardQuery(db_path=workspace.cache_db())
    img = ImageQuery(db_path=workspace.cache_db())
    sym = SymbolQuery(db_path=workspace.cache_db())
    files = plan(root, out_dir, workspace.repo_url(), q, img, sym)

    if args.check:
        stale = [p for p, body in files.items() if not _same(p, body)]
        orphan = [p for p in out_dir.rglob("*")
                  if p.is_file() and p not in files] if out_dir.exists() else []
        for p in sorted(stale):
            print(f"stale:  {p}")
        for p in sorted(orphan):
            print(f"orphan: {p}")
        if stale or orphan:
            return 1
        if not args.quiet:
            print(f"{out_dir} is up to date ({len(files)} files)")
        return 0

    written, removed = sync(files, out_dir)
    if img.failed:
        print(f"warning: {len(img.failed)} image(s) unavailable, "
              f"first: {img.failed[0]}", file=sys.stderr)
    if not args.quiet:
        report(files, out_dir, written, removed)
        print(f"# {q.counters()}   {img.counters()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
