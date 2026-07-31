#!/usr/bin/env python3
"""Generate the static deck catalog that GitHub Pages publishes.

    ./build_site.py                  # rebuild docs/ from public/  -- PUBLISHED
    ./build_site.py --private        # public + private -> private-docs/, local only
    ./build_site.py --check          # exit 1 if docs/ is stale; write nothing
    ./build_site.py --out /tmp/site  # build elsewhere to look before publishing

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
import frontend
import toollog
import workspace
from cardlib import CardQuery, ImageQuery, SymbolQuery, local_name
# Same policy as the validator, imported rather than restated: a bracket cap or a
# land count that disagreed with `validate_deck.py` would make the site lie.
from validate_deck import gc_cap, land_counts

REPO_FALLBACK = "https://github.com/hellozhewang/mtg"

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
SECTION_ORDER = ["Creatures", "Planeswalkers", "Instants", "Sorceries",
                 "Artifacts", "Enchantments", "Battles", "Lands", "Other"]

COLOUR_NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}
MANA_TOKEN = re.compile(r"\{[^}]+\}")


# ---------- card helpers ----------

def category(card: dict) -> str:
    front = (card.get("type_line") or "").split(" // ")[0]
    for token, label in CATEGORIES:
        if token in front:
            return label
    return "Other"


def art_sets(card: dict) -> list[dict]:
    """The `image_uris` dicts for a card: one, or one per face on a DFC."""
    if card.get("image_uris"):
        return [card["image_uris"]]
    return [f["image_uris"] for f in card.get("card_faces") or [] if f.get("image_uris")]


def e(text: object) -> str:
    return html.escape(str(text), quote=True)


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
                 private: bool = False):
        self.path = path
        self.private = private
        self.rel = path.resolve().relative_to(root)
        self.bracket = self.rel.parent.as_posix()
        self.label = bracket_label(self.bracket)
        self.stem = path.stem
        # Private decks get their own URL prefix because the two collections DO
        # collide -- GrandArbiter-Prison exists in both, as different lists. They
        # still share a bracket section in the UI; only the path is separated.
        self.href = ("private/" if private else "") + \
            self.rel.with_suffix(".html").as_posix()
        # From the href, not from `rel`: the private prefix adds a level, and
        # getting this wrong points every asset link one directory too high.
        self.depth = self.href.count("/")
        self.deck = deckfile.parse(path)
        self.cards, self.missing = q.cards(self.deck.names)
        self.raw = path.read_text(encoding="utf-8")

        cmd = self.cards.get(self.deck.commander)
        self.commander = self.deck.commander
        self.colours = list((cmd or {}).get("color_identity") or [])
        arts = art_sets(cmd or {})
        self.art_url = arts[0].get(ART, "") if arts else ""

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
        for entry in self.deck.entries:
            card = self.cards.get(entry.name, {})
            buckets.setdefault(category(card), []).append((entry.count, entry.name, card))
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
            LABEL=f"{e(d.stem)} — {e(d.commander)}"
                  + (" (private)" if d.private else "")))
    if bracket is not None:
        groups.append(layout.part("picker-group").render(
            BRACKET=e(bracket_label(bracket)), OPTIONS="".join(opts)))
    return "".join(groups)


def render_index(tpl: dict[str, frontend.Template], decks: list[DeckInfo],
                 repo: str, mana: Mana) -> str:
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
        art = (f'<img class="art" src="img/{e(local_name(d.art_url))}" alt=""'
               f' loading="lazy" decoding="async" width="626" height="457">'
               if d.art_url else '<span class="art-blank"></span>')
        tiles.append(index.part("tile").render(
            HREF=e(d.href), ART=art, NAME=e(d.stem), COMMANDER=e(d.commander),
            TAG=index.part("tag").render() if d.private else "",
            PIPS=mana.pips(d.colours, ""), TOTAL=d.total, LANDS=d.lands,
            MV=f"{d.avg_mv:.2f}",
            GC=f"{len(d.gcs)}/{d.cap}" if d.cap is not None else str(len(d.gcs))))
    if bracket is not None:
        flush()

    return layout.render(
        TITLE="Commander decks", UP="", REPO=e(repo),
        DESCRIPTION=f"{len(decks)} Magic: the Gathering Commander decklists.",
        PICKER=picker(layout, decks, None, ""),
        MAIN=index.render(COUNT=len(decks), SECTIONS="".join(sections)))


def render_deck(tpl: dict[str, frontend.Template], d: DeckInfo,
                decks: list[DeckInfo], repo: str, mana: Mana) -> str:
    page, layout = tpl["deck"], tpl["layout"]
    up = "../" * d.depth
    blob = f"{repo}/blob/main/public/{d.rel.as_posix()}"
    raw = (repo.replace("https://github.com/", "https://raw.githubusercontent.com/")
           + f"/main/public/{d.rel.as_posix()}")

    # A private deck is not on GitHub, so linking to it would 404. Omit both.
    links = "" if d.private else page.part("links").render(RAW=e(raw), BLOB=e(blob))
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
                        f' data-thumb="{up}img/{e(local_name(uris[0][THUMB]))}"')
                if len(uris) > 1:
                    data += f' data-back="{e(uris[1].get(FULL, ""))}"'
            rendered.append(page.part("card").render(
                CLASS="card cmdr" if cardname == d.commander else "card",
                NAME=e(cardname), DATA=data, QTY=count,
                GCFLAG='<span class="gcflag" title="Game Changer">GC</span>'
                       if card.get("game_changer") else "",
                COST=mana.render(card.get("mana_cost") or "", up)))
        sections.append(page.part("section").render(
            NAME=e(name), N=sum(c for c, _, _ in rows), CARDS="".join(rendered)))

    return layout.render(
        TITLE=f"{d.stem} — {d.commander}", UP=up, REPO=e(repo),
        DESCRIPTION=f"{e(d.commander)} — {d.total}-card Commander deck, "
                    f"{d.label}, {d.gc_label} Game Changers.",
        PICKER=picker(layout, decks, d, up),
        MAIN=page.render(
            NAME=e(d.stem), PIPS=mana.pips(d.colours, up), COMMANDER=e(d.commander),
            BRACKET=e(d.label), TAG=page.part("tag").render() if d.private else "",
            LINKS=links, TOTAL=d.total,
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
            SECTIONS="".join(sections)))


# ---------- driver ----------

def repo_url() -> str:
    """Derive the GitHub URL from the git remote, so a moved repo stays linked.

    Local config only — no network, so it is safe inside a bot turn and gives the
    same answer every run for a given checkout.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(workspace.deck_root().parent),
             "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=10)
        url = out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        url = ""
    if not url:
        return REPO_FALLBACK
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url[len("git@github.com:"):]
    return url[:-4] if url.endswith(".git") else url


def collect_images(decks: list[DeckInfo], img: ImageQuery,
                   out_dir: Path) -> dict[Path, bytes]:
    """Fetch every committed image once, deduplicated across decks.

    Deduplication is the point: 14 decks share 818 distinct cards, and the same
    Sol Ring thumbnail must not be downloaded, stored or committed 14 times.
    """
    wanted: dict[str, Path] = {}
    for d in decks:
        if d.art_url:
            wanted[d.art_url] = out_dir / "img" / local_name(d.art_url)
        for card in d.cards.values():
            for uris in art_sets(card):
                if url := uris.get(THUMB):
                    wanted[url] = out_dir / "img" / local_name(url)

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


def refuse_if_publishable(out_dir: Path) -> None:
    """Abort if private decks would be written somewhere git can see.

    The failure this prevents is one command away — `--private --out docs` — and
    it is silent: the pages would look right, and `bot.py` would push them on the
    next Discord turn without anyone deciding to. So the check is on the OUTPUT,
    not on the flag, and it asks git rather than pattern-matching a path: whatever
    `.gitignore` currently says is the real answer.
    """
    if out_dir == workspace.site_dir():
        raise SystemExit(f"refusing --private into the published tree: {out_dir}")
    try:
        r = subprocess.run(["git", "-C", str(workspace.deck_root().parent),
                            "check-ignore", "-q", str(out_dir)],
                           capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return                      # no git here: the equality check above stands
    if r.returncode == 1:           # 0 = ignored, 1 = NOT ignored, 128 = not a repo
        raise SystemExit(
            f"refusing --private into a tracked directory: {out_dir}\n"
            f"private decklists must not be committable — add it to .gitignore first")


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


def plan(sources: list[tuple[Path, bool]], out_dir: Path, repo: str,
         q: CardQuery, img: ImageQuery, sym: SymbolQuery) -> dict[Path, str | bytes]:
    """Every file the site consists of, as {path: content}. Nothing written yet.

    `sources` is [(deck root, is_private)]. Both collections share one set of
    bracket sections -- a private deck is marked, not segregated -- so they are
    merged and sorted together here rather than rendered as separate groups.

    Building the whole thing in memory first is what makes `--check` possible and
    what lets sync() write only real differences.
    """
    tpl = frontend.load(workspace.frontend_dir())
    fdir = workspace.frontend_dir()
    decks = sorted(
        (DeckInfo(p, root, q, private)
         for root, private in sources for p in deckfile.discover([root])),
        # `private` is in the key, not just for grouping: the two collections can
        # hold the same filename, and without it the sort order of a colliding
        # pair would be arbitrary -- which breaks byte-determinism.
        key=lambda d: (d.bracket, d.stem.lower(), d.private))
    mana = Mana(sym.uris())

    files: dict[Path, str | bytes] = {
        out_dir / "index.html": render_index(tpl, decks, repo, mana),
        out_dir / "style.css": (fdir / "style.css").read_text(encoding="utf-8"),
        out_dir / "app.js": (fdir / "app.js").read_text(encoding="utf-8"),
        out_dir / ".nojekyll": "",
    }
    for d in decks:
        files[out_dir / d.href] = render_deck(tpl, d, decks, repo, mana)
    files.update(collect_images(decks, img, out_dir))
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


def sync(files: dict[Path, str | bytes], out_dir: Path) -> tuple[int, int]:
    """Write what changed, delete what no longer belongs. Returns (written, removed).

    Writing only on difference is what keeps `git status` quiet between real deck
    edits; pruning is what stops a renamed deck leaving a stale page live forever.
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


def main() -> int:
    toollog.record()
    ap = argparse.ArgumentParser(description="Build the static deck catalog.")
    ap.add_argument("--out", type=Path,
                    help="output directory (default: docs/, or private-docs/ with --private)")
    ap.add_argument("--private", action="store_true",
                    help="include private/ decks too, marked (private), and build "
                         "to private-docs/ -- gitignored, never published")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the site is stale; write nothing")
    ap.add_argument("--quiet", action="store_true", help="only report problems")
    args = ap.parse_args()

    sources = [(workspace.deck_root(), False)]
    if args.private:
        sources.append((workspace.private_root(), True))
    default_out = workspace.private_site_dir() if args.private else workspace.site_dir()
    out_dir = args.out.expanduser().resolve() if args.out else default_out
    if args.private:
        refuse_if_publishable(out_dir)
    q = CardQuery(db_path=workspace.cache_db())
    img = ImageQuery(db_path=workspace.cache_db())
    sym = SymbolQuery(db_path=workspace.cache_db())
    files = plan(sources, out_dir, repo_url(), q, img, sym)

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
        pages = sum(1 for p in files if p.suffix == ".html")
        mb = sum(len(b) for b in files.values() if isinstance(b, bytes)) / 1048576
        print(f"{pages - 1} decks -> {out_dir}  "
              f"({written} written, {removed} removed, {len(files)} files, "
              f"{mb:.1f} MB images)")
        print(f"# {q.counters()}   {img.counters()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
