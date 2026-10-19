"""sleever: make a sleeve (a custom card back) for the Cactuar table from a Discord message.

    sleever make me sailor moon sleeves          (+ optional image uploads or links)

bot.py runs the turn on the same harness as the builder (whichever model the owner has
picked), in a per-user staging folder: bot/.sleever/<owner>/. The model only paints. It
saves one picture there and ends its reply with `Sleeve: <Name>`. Everything after that is
this module's, so it behaves the same whatever model made the picture:

  * crop to a Magic card's 63:88 around the centre, resize to 745 x 1040, save as JPEG
    under 500 KB (macOS `sips`);
  * name it `<slug>.jpg` in tts/sleeves/, never overwriting another user's sleeve or one
    of the hand-made ones (ownership is kept privately in bot/.sleever/owners.json);
  * hand the file path back so Discord can attach the picture; bot.py then autopushes
    tts/sleeves/ and docs/, and the table's Sleeves menu lists it after a Refresh.

The model never writes tts/sleeves/ or docs/ itself: the sandbox only lets it write its
staging folder.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SLEEVES_DIR = REPO / "tts" / "sleeves"
STAGING = HERE / ".sleever"                      # gitignored; one folder per user
OWNERS = STAGING / "owners.json"                 # slug -> Discord owner, for overwrites

WIDTH, HEIGHT = 745, 1040                        # tts/sleeves/README.md "Image specs"
MAX_BYTES = 500_000
IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".webp")
RESERVED = {"standard"}                          # Magic's own back, always listed first

MAX_REFS = 6                                     # uploads the bot downloads per message
MAX_REF_BYTES = 12_000_000
REF_TIMEOUT = 20

SLEEVE_LINE = re.compile(r"^\s*Sleeve:\s*(.+?)\s*$", re.M | re.I)
ATTACH = "[[attach:{}]]"                         # deckBuilder.ts swaps this for the file

UNAVAILABLE = "sleever can't make pictures right now. Try again later."
NO_PICTURE = ("sleever didn't come up with a picture that time. Try again, maybe with "
              "a bit more detail about what you want on the sleeves.")

INSTRUCTIONS = """\
# You are sleever

You make **sleeves**: custom card backs for the Cactuar Tabletop Simulator table.
@OWNER@ asked for them in Discord. Players pick sleeves from the table's
**Sleeves** menu, and every card of the next deck they load gets that back.

You only make sleeves. If someone asks for a deck, a card list or anything else,
tell them that's what `builder` is for, and stop.

## Who you are, to the players

Your name is sleever, always in lowercase. Never say which AI model, assistant,
harness or company you are, even if asked, and never let one of those names
appear in a reply. Only the owner chooses the model.

## Making the picture

1. **Use your image generation tool.** Make one finished picture per request. If
   you have no way to make pictures, reply `I can't make pictures right now.`
   and stop.
2. **References.** Any pictures the user attached are in `refs/` (ref-1.png,
   ref-2.jpg, ...). Look at every one and use them as references for character,
   style and colours. If the message has links, you may download them into
   `refs/` or look the subject up on the web. Make an original illustration in
   that spirit: do not copy official artwork, or a reference, as it is.
3. **What makes a good sleeve.** It is the back of every card in the deck, seen
   small and many times over:
   - one strong motif, centred, that reads at thumbnail size; not busy;
   - portrait, 2:3 or taller. It is cropped around the centre to a Magic card's
     63:88, so keep everything important away from the edges (about 8% margin);
   - full-bleed art all the way to every edge: **no border, frame or rounded
     corners**, because Tabletop Simulator rounds the corners itself;
   - **no text, letters, logos or watermarks** unless the user asks for words;
4. **Content: anything goes**, sexual content included, as are characters from
   anime, games and films as fan art.
5. **Save it as `sleeve.png`** (or `.jpg`/`.webp`) in your working directory.
   When revising ("make it darker"), make the new version and save it under the
   same name, replacing the old one.

## Your reply

Short, in this shape:

    Made **<Name>** sleeves: <one sentence on the design>.
    Sleeve: <Name>

- Use `Updated **<Name>** sleeves` for a revision.
- `<Name>` is 1 to 4 words and becomes the label in the Sleeves menu. For a
  revision, keep the same Name unless the user asks to rename it.
- End with the `Sleeve:` line on its own line. The bot reads it, attaches your
  picture and publishes it; players see it in the Sleeves menu a few minutes
  later, after pressing **Refresh** in the deck browser.
- Do not describe files, folders, commands or your tools.

## Your sandbox

You can write only in this folder. Writing anywhere else fails with "operation
not permitted". That is deliberate; do not try to work around it.
"""


class SleeveError(RuntimeError):
    """The picture could not be turned into a sleeve."""


# ---------- staging ----------

def folder(owner: str) -> Path:
    return STAGING / owner


def prepare(owner: str) -> Path:
    """The user's staging folder with fresh instructions (0444) and an empty refs/."""
    f = folder(owner)
    f.mkdir(parents=True, exist_ok=True)
    agents = f / "AGENTS.md"
    text = INSTRUCTIONS.replace("@OWNER@", owner)
    if not agents.exists() or agents.read_text(encoding="utf-8") != text:
        if agents.exists():
            agents.chmod(0o644)
        agents.write_text(text, encoding="utf-8")
    agents.chmod(0o444)
    refs = f / "refs"
    shutil.rmtree(refs, ignore_errors=True)          # only this message's references
    refs.mkdir()
    return f


def _sniff(data: bytes) -> str | None:
    """The image type of `data` by its magic bytes, or None."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    return None


def fetch_refs(urls: list[str], dest: Path) -> list[str]:
    """Download the user's uploads into `dest`. Returns notes on any that were skipped.

    Runs outside the sandbox, so it is strict: https only, a size cap, and the bytes
    must be a picture whatever the server claims.
    """
    notes: list[str] = []
    n = 0
    for url in urls[:MAX_REFS]:
        if not url.lower().startswith("https://"):
            notes.append(f"skipped a non-https reference: {url[:80]}")
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mtg-sleever/1"})
            with urllib.request.urlopen(req, timeout=REF_TIMEOUT) as r:
                data = r.read(MAX_REF_BYTES + 1)
        except Exception as exc:
            notes.append(f"could not download a reference ({type(exc).__name__})")
            continue
        kind = _sniff(data)
        if len(data) > MAX_REF_BYTES or kind is None:
            notes.append("skipped a reference that was too big or not a picture")
            continue
        n += 1
        (dest / f"ref-{n}{kind}").write_bytes(data)
    if len(urls) > MAX_REFS:
        notes.append(f"used the first {MAX_REFS} references only")
    return notes


def latest_picture(f: Path, since: float) -> Path | None:
    """The newest picture the model saved in its folder this turn (refs/ excluded)."""
    found = [p for p in f.iterdir()
             if p.is_file() and p.suffix.lower() in IMAGE_TYPES and p.stat().st_mtime >= since - 1]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


# ---------- naming ----------

def sleeve_name(answer: str) -> str | None:
    found = SLEEVE_LINE.findall(answer or "")
    name = found[-1].strip().strip("*`'\"") if found else ""
    return name[:40] or None


def strip_name_line(answer: str) -> str:
    return SLEEVE_LINE.sub("", answer or "").strip()


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40].strip("-")
    return slug or "sleeves"


def _owners() -> dict[str, str]:
    try:
        return json.loads(OWNERS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _existing(slug: str) -> bool:
    return any((SLEEVES_DIR / f"{slug}{ext}").exists() for ext in (".jpg", ".jpeg", ".png"))


def choose_slug(name: str, owner: str, previous: str | None) -> str:
    """The file name for `name`: this user's own sleeve is replaced, anyone else's never.

    A revision keeps the session's previous sleeve when the name is unchanged (even if
    that one had to become `rainbow-2`). A name that clashes with a sleeve this user
    doesn't own (another user's, or a hand-made one) gets -2, -3, ...
    """
    base = slugify(name)
    if base in RESERVED:
        base = f"{base}-sleeves"
    owners = _owners()
    if previous and owners.get(previous) == owner and \
            (previous == base or re.fullmatch(re.escape(base) + r"-\d+", previous)):
        return previous
    candidate, n = base, 1
    while _existing(candidate) and owners.get(candidate) != owner:
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def record_owner(slug: str, owner: str) -> None:
    owners = _owners()
    owners[slug] = owner
    OWNERS.parent.mkdir(parents=True, exist_ok=True)
    OWNERS.write_text(json.dumps(owners, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ---------- the picture ----------

def _sips(*args: str) -> subprocess.CompletedProcess:
    r = subprocess.run(["/usr/bin/sips", *args], capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise SleeveError(f"sips {' '.join(args[:2])} failed: {(r.stderr or r.stdout).strip()[:200]}")
    return r


def _size(path: Path) -> tuple[int, int]:
    out = _sips("-g", "pixelWidth", "-g", "pixelHeight", str(path)).stdout
    w = re.search(r"pixelWidth:\s*(\d+)", out)
    h = re.search(r"pixelHeight:\s*(\d+)", out)
    if not (w and h):
        raise SleeveError("could not read the picture's size")
    return int(w.group(1)), int(h.group(1))


def finish(src: Path, dest: Path) -> None:
    """Crop `src` to 63:88 around its centre, resize to WIDTH x HEIGHT, save JPEG at `dest`."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work.png"
        _sips("-s", "format", "png", str(src), "--out", str(work))
        w, h = _size(work)
        if w < 300 or h < 400:
            raise SleeveError(f"the picture is too small ({w}x{h})")
        ratio = WIDTH / HEIGHT
        if w / h > ratio:
            cw, ch = round(h * ratio), h                     # too wide: trim the sides
        else:
            cw, ch = w, round(w / ratio)                     # too tall: trim top and bottom
        _sips("--cropToHeightWidth", str(ch), str(cw), str(work))
        _sips("-z", str(HEIGHT), str(WIDTH), str(work))
        out = Path(tmp) / "out.jpg"
        for quality in (88, 80, 72, 64):
            _sips("-s", "format", "jpeg", "-s", "formatOptions", str(quality), str(work), "--out", str(out))
            if out.stat().st_size <= MAX_BYTES:
                break
        if _size(out) != (WIDTH, HEIGHT):
            raise SleeveError(f"resize gave {_size(out)}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, dest)


def publish(f: Path, answer: str, owner: str, previous: str | None, since: float) -> tuple[str, str | None]:
    """After a turn: install the sleeve and return (reply, slug), or the reply alone.

    The reply loses its `Sleeve:` line and gains the attach marker for Discord.
    """
    picture = latest_picture(f, since)
    name = sleeve_name(answer)
    body = strip_name_line(answer)
    if picture is None:
        return (body or NO_PICTURE), None
    if name is None:
        name = previous.replace("-", " ").title() if previous else "Sleeves"
    slug = choose_slug(name, owner, previous)
    dest = SLEEVES_DIR / f"{slug}.jpg"
    finish(picture, dest)
    record_owner(slug, owner)
    label = slug.replace("-", " ").replace("_", " ").title()
    lines = [body or f"Made **{label}** sleeves.",
             f"In the table: open the Cactuar deck browser, press **Refresh**, then pick "
             f"**Sleeves: {label}** before loading a deck. It goes live in a few minutes.",
             ATTACH.format(dest)]
    return "\n\n".join(lines), slug

