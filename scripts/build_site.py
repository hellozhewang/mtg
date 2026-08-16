#!/usr/bin/env python3
"""Generate the static deck catalog that GitHub Pages publishes.

    ./build_site.py                  # rebuild docs/, and docs/private/ if private/ has decks
    ./build_site.py --check          # exit 1 if docs/ is stale; write nothing
    ./build_site.py --out /tmp/site  # build elsewhere to look before publishing

TWO OUTPUTS, AND ONLY ONE OF THEM IS PUBLIC.

    docs/         public/ only.        Committed, and served by GitHub Pages.
    docs/private/   public/ + private/.  Gitignored, so Pages never sees it.

No flag. Drop a deck in `private/` and the next build picks it up; the folder is
gitignored, so nothing about it can reach GitHub. That is the whole mechanism:
Pages serves the COMMITTED contents of `docs/`, so a directory git never records
cannot be served, even sitting inside the published tree.

Why two indexes rather than one catalog with private decks marked in it: the
published `docs/index.html` lists and links every deck it knows about. A single
index containing private decks would put their names on the web and link to pages
that 404 there — so the private view gets its own index alongside the public one.
It lives inside `docs/` so both resolve `style.css` and `img/` the same relative
way, and the public build never depends on whether `private/` exists.

Two consequences worth knowing before editing this file:

  * the public build must never prune `docs/private/` — it walks its whole output
    directory deleting anything it did not generate, and the local site is exactly
    that. Hence `sync(keep=...)`, and the same exclusion in `--check`;
  * a private deck's pages carry NO GitHub links. `raw.githubusercontent.com` for
    a file that was never pushed is a 404 dressed up as a working button.

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
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deckfile
from deckmeta import DeckAuthorStore
import frontend
import toollog
import workspace
from cardlib import CardQuery, ImageQuery, SymbolQuery, local_name
# Same policy as the validator, imported rather than restated: a bracket cap or a
# land count that disagreed with `validate_deck.py` would make the site lie.
from validate_deck import gc_cap, land_counts

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

# Byline for decks under private/. They are hand-built rather than written by a
# Discord turn, so DeckAuthorStore has no row for them and the tile would carry no
# author at all; this is the one place a name is stated rather than recorded.
PRIVATE_AUTHOR = "zzwang-private"

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
    """
    return local_name(card.get("oracle_id") or card.get("id") or "unknown",
                      face, size, url)


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
    """`Bracket3` -> `Bracket 3`, `Bracket3.5` -> `Bracket 3.5`.

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
                 authors: dict[str, str], private: bool = False):
        self.path = path
        self.rel = path.resolve().relative_to(root)
        self.private = private
        # DeckAuthorStore is keyed on the path relative to the deck root, so
        # `private/Bracket3/Foo.txt` and `public/Bracket3/Foo.txt` produce the SAME
        # key — a private deck would otherwise inherit the byline of an unrelated
        # public deck that happens to share a name. Private decks are hand-built
        # anyway, so they never have a row of their own; skip the lookup entirely.
        self.author = PRIVATE_AUTHOR if private else authors.get(self.rel.as_posix())
        # Grouping is by BRACKET, not by which tree the file came from, so a
        # private Bracket 3 deck sits with the public ones and is told apart by a
        # badge. That is the ask: a marker on the tile, not a section of its own.
        # `Unsorted` covers a file dropped straight into private/ with no bracket
        # folder — rel.parent is then `.`, which would title a section ".".
        self.bracket = self.rel.parent.as_posix()
        if self.bracket == ".":
            self.bracket = "Unsorted"
        self.label = bracket_label(self.bracket)
        self.stem = path.stem
        # Private pages live under their own path segment so a private deck and a
        # public one with the same bracket and name cannot resolve to one file and
        # silently overwrite each other in the output.
        self.href = ("private/" if private else "") + \
            self.rel.with_suffix(".html").as_posix()
        self.depth = self.href.count("/")
        self.deck = deckfile.parse(path)
        self.cards, self.missing = q.cards(self.deck.names)
        self.raw = path.read_text(encoding="utf-8")

        cmd = self.cards.get(self.deck.commander)
        self.commander = self.deck.commander
        self.colours = list((cmd or {}).get("color_identity") or [])
        arts = art_sets(cmd or {})
        self.art_url = arts[0].get(ART, "") if arts else ""
        self.art_card = cmd or {}

        self.lands, self.flex = land_counts(self.deck, self.cards)
        self.cap = gc_cap(path, None)
        self.gcs = sorted(n for n in self.deck.names
                          if self.cards.get(n, {}).get("game_changer"))
        nonland = [c for c in self.cards.values()
                   if "Land" not in (c.get("type_line") or "").split(" // ")[0]]
        self.avg_mv = sum(c.get("cmc", 0) for c in nonland) / len(nonland) if nonland else 0.0

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
            # Line 1 is the commander by format definition -- keyed on position,
            # not on a name match, so a deck that (illegally) repeats the name
            # cannot pull a second card into the Commander section.
            bucket = "Commander" if i == 0 else category(card)
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
            # A <select> option renders no markup, so the badge the tiles get has
            # to be plain text here.
            LABEL=f"{e(d.stem)} — {e(d.commander)}"
                  + (" (private)" if d.private else "")))
    if bracket is not None:
        groups.append(layout.part("picker-group").render(
            BRACKET=e(bracket_label(bracket)), OPTIONS="".join(opts)))
    return "".join(groups)


def render_index(tpl: dict[str, frontend.Template], decks: list[DeckInfo],
                 repo: str, mana: Mana,
                 available_images: set[str] | None = None) -> str:
    index, layout = tpl["index"], tpl["layout"]
    sections, bracket, tiles = [], None, []

    def flush() -> None:
        sections.append(index.part("section").render(
            BRACKET=e(bracket_label(bracket)), N=len(tiles), TILES="".join(tiles)))

    for d in decks:
        if d.bracket != bracket:
            if bracket is not None:
                flush()
            bracket, tiles = d.bracket, []
        art_name = image_file(d.art_card, 0, ART, d.art_url) if d.art_url else ""
        # A transient CDN failure must not leave a dangling <img> in the
        # published catalog. `None` preserves the standalone renderer's old
        # behavior; production passes the filenames fetched for this build.
        has_art = bool(art_name and
                       (available_images is None or art_name in available_images))
        art = (f'<img class="art" src="img/{e(art_name)}" alt=""'
               f' loading="lazy" decoding="async" width="626" height="457">'
               if has_art else '<span class="art-blank"></span>')
        tiles.append(index.part("tile").render(
            HREF=e(d.href), ART=art, NAME=e(d.stem), COMMANDER=e(d.commander),
            TAG=index.part("tag").render() if d.private else "",
            AUTHOR=(f'        <span class="tile-author">by {e(d.author)}</span>\n'
                    if d.author else ""),
            # The existing free-text filter reads data-search, so including the
            # author makes a username a first-class filter with no second state.
            # "private" goes in as a word, which makes the search box a filter for
            # unpublished decks with no extra control to build.
            SEARCH=e(" ".join(x for x in
                              (d.stem, d.commander, d.label, d.author,
                               "private" if d.private else "") if x)),
            PIPS=mana.pips(d.colours, ""), TOTAL=d.total, LANDS=d.lands,
            MV=f"{d.avg_mv:.2f}",
            GC=f"{len(d.gcs)}/{d.cap}" if d.cap is not None else str(len(d.gcs))))
    if bracket is not None:
        flush()

    return mirror_tips(layout.render(
        TITLE="Commander decks", UP="", REPO=e(repo),
        DESCRIPTION=f"{len(decks)} Magic: the Gathering Commander decklists.",
        PICKER=picker(layout, decks, None, ""),
        MAIN=index.render(COUNT=len(decks), SECTIONS="".join(sections))))


def render_deck(tpl: dict[str, frontend.Template], d: DeckInfo,
                decks: list[DeckInfo], repo: str, mana: Mana) -> str:
    page, layout = tpl["deck"], tpl["layout"]
    up = "../" * d.depth
    # No GitHub links for a private deck: the file was never pushed, so both URLs
    # would 404 — a broken button is worse than an absent one. Copy and Plain-text
    # still work, because those read the decklist embedded in the page.
    if d.private:
        links = page.part("private-note").render()
    else:
        links = page.part("links").render(
            RAW=e(repo.replace("https://github.com/",
                               "https://raw.githubusercontent.com/")
                  + f"/main/public/{d.rel.as_posix()}"),
            BLOB=e(f"{repo}/blob/main/public/{d.rel.as_posix()}"))

    gclist = page.part("gclist").render(NAMES="".join(
        page.part("gcname").render(NAME=e(n)) for n in d.gcs)) if d.gcs else ""
    warn = page.part("warn").render(
        NAMES=e(", ".join(sorted(d.missing)))) if d.missing else ""

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
                CLASS="card cmdr" if cardname == d.commander else "card",
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
            TAG=page.part("tag").render() if d.private else "", LINKS=links,
            LANDS=f"{d.lands}" + (f" +{d.flex}" if d.flex else ""),
            # A modal DFC like Malakir Rebirth is `Instant // Land`: playable as a
            # tapped land but not a mana source you can plan around, so it is
            # counted apart from the real lands rather than inflating them.
            LANDNOTE=(f"{d.lands} lands, plus {d.flex} modal double-faced "
                      f"card{'s' if d.flex > 1 else ''} playable as a land"
                      if d.flex else f"{d.lands} lands"),
            MV=f"{d.avg_mv:.2f}", GC=e(d.gc_label),
            GCLIST=gclist, WARN=warn, CURVE=bars,
            RAWLIST=e(d.raw),
            SECTIONS="".join(sections))))


# ---------- driver ----------



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
         img: ImageQuery, sym: SymbolQuery,
         private_root: Path | None = None) -> dict[Path, str | bytes]:
    """Every file the site consists of, as {path: content}. Nothing written yet.

    Building the whole thing in memory first is what makes `--check` possible and
    what lets sync() write only real differences.

    `private_root` adds a second tree of decks, badged and linked but never
    published. It defaults to None so the published build cannot include them by
    forgetting a flag — the unsafe case has to be asked for explicitly.
    """
    tpl = frontend.load(workspace.frontend_dir())
    fdir = workspace.frontend_dir()
    with DeckAuthorStore(workspace.deck_metadata_db()) as store:
        authors = store.all()
    found = [(p, root, False) for p in deckfile.discover([root])]
    if private_root and private_root.is_dir():
        # ONLY the bracket folders, not the whole tree. private/ is a personal
        # scratch directory as well as a deck directory — notes, tool inputs and
        # anything else live alongside the decks — and `discover()` would happily
        # turn every .txt in there into a "deck". It did: four showcards input
        # files rendered as decklists, one of them a 51-card "commander".
        # The bracket folder is what marks a file as a deck, here and in gc_cap().
        found += [(p, private_root, True)
                  for p in deckfile.discover(sorted(private_root.glob("Bracket*")))]
    decks = sorted((DeckInfo(p, base, q, authors, private=priv)
                    for p, base, priv in found),
                   # Private and public interleave inside a bracket rather than
                   # sorting apart, so a deck sits where you would look for it.
                   key=lambda d: (d.bracket, d.stem.lower(), d.private))
    mana = Mana(sym.uris())
    image_files = collect_images(decks, img, out_dir)
    available_images = {path.name for path in image_files}

    files: dict[Path, str | bytes] = {
        out_dir / "index.html": render_index(
            tpl, decks, repo, mana, available_images
        ),
        out_dir / "style.css": (fdir / "style.css").read_text(encoding="utf-8"),
        out_dir / "app.js": (fdir / "app.js").read_text(encoding="utf-8"),
        out_dir / ".nojekyll": "",
    }
    for d in decks:
        files[out_dir / d.href] = render_deck(tpl, d, decks, repo, mana)
    files.update(image_files)
    files.update(collect_symbols(mana, sym, out_dir))   # after render: needs .used
    return files


def _same(path: Path, body: str | bytes) -> bool:
    if not path.exists():
        return False
    if isinstance(body, bytes):
        return path.read_bytes() == body
    try:
        return path.read_text(encoding="utf-8") == body
    except UnicodeDecodeError:
        return False


def _under(path: Path, parent: Path | None) -> bool:
    """Is `path` inside `parent`? False when there is no parent to be inside of."""
    return parent is not None and parent in path.parents


def sync(files: dict[Path, str | bytes], out_dir: Path,
         keep: Path | None = None) -> tuple[int, int]:
    """Write what changed, delete what no longer belongs. Returns (written, removed).

    Writing only on difference is what keeps `git status` quiet between real deck
    edits; pruning is what stops a renamed deck leaving a stale page live forever.

    **Pruning is confined to `out_dir`. It never touches the database.** Deleting a
    deck removes its page and any card image no longer used by another deck, but
    every cached card, page and image row stays. That is what makes deletion cheap
    to undo: restoring the .txt and rebuilding costs zero downloads, because the
    bytes were never thrown away. Measured — remove a deck, rebuild, restore,
    rebuild: `images 937 hit / 0 miss, 0 downloads`.

    `keep` is a subtree pruning skips. The local catalog is generated INTO the
    published one (docs/private/), so without this the public build would delete it
    wholesale on the next Discord message — every file under there is, correctly,
    something this build did not produce.
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
            if keep is not None and (path == keep or _under(path, keep)):
                continue
            if path.is_file() and path not in files:
                path.unlink()
                removed += 1
            elif path.is_dir() and not any(path.iterdir()):
                path.rmdir()
    return written, removed


def report(files: dict[Path, str | bytes], out_dir: Path,
           written: int, removed: int) -> None:
    """One line per output tree. Both builds print the same shape."""
    pages = sum(1 for p in files if p.suffix == ".html")
    mb = sum(len(b) for b in files.values() if isinstance(b, bytes)) / 1048576
    print(f"{pages - 1} decks -> {out_dir}  "
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
    # The local catalog is a subdirectory of whatever we are building, so it
    # follows --out. The published build must leave it alone.
    private_site = out_dir / workspace.PRIVATE_SITE_NAME
    keep = private_site
    private_root = workspace.private_dir()
    # Same rule as plan(): bracket folders only. These two scans must agree, or
    # the build reports a deck count it did not render.
    private_decks = (deckfile.discover(sorted(private_root.glob("Bracket*")))
                     if private_root.is_dir() else [])
    q = CardQuery(db_path=workspace.cache_db())
    img = ImageQuery(db_path=workspace.cache_db())
    sym = SymbolQuery(db_path=workspace.cache_db())
    # The published site is built from public/ ALONE, unconditionally. Nothing
    # about what is on GitHub should vary with what happens to be in private/.
    files = plan(root, out_dir, workspace.repo_url(), q, img, sym)

    if args.check:
        stale = [p for p, body in files.items() if not _same(p, body)]
        orphan = [p for p in out_dir.rglob("*")
                  if p.is_file() and p not in files
                  and not _under(p, keep)] if out_dir.exists() else []
        for p in sorted(stale):
            print(f"stale:  {p}")
        for p in sorted(orphan):
            print(f"orphan: {p}")
        if stale or orphan:
            return 1
        if not args.quiet:
            print(f"{out_dir} is up to date ({len(files)} files)")
        return 0

    written, removed = sync(files, out_dir, keep=keep)
    if img.failed:
        print(f"warning: {len(img.failed)} image(s) unavailable, "
              f"first: {img.failed[0]}", file=sys.stderr)
    if not args.quiet:
        report(files, out_dir, written, removed)

    # The local catalog, only when there is something private to show. No flag:
    # the folder being present IS the request, and the folder being gitignored is
    # what keeps the result off the web.
    if private_decks:
        pfiles = plan(root, private_site, workspace.repo_url(), q, img, sym,
                      private_root=private_root)
        pwritten, premoved = sync(pfiles, private_site)
        if not args.quiet:
            print(f"+ {len(private_decks)} private deck(s) from {private_root}")
            report(pfiles, private_site, pwritten, premoved)
    elif not args.quiet and private_site.exists():
        # private/ emptied but the local catalog is still on disk, listing decks
        # that are gone. Say so; deleting someone's local tree unasked is worse.
        print(f"note: {private_site} still exists but private/ has no decks — "
              f"remove it by hand if you are done with it")

    if not args.quiet:
        print(f"# {q.counters()}   {img.counters()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
