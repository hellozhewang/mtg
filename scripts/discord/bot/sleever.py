"""sleever: make a sleeve (a custom card back) for the Cactuar table from a Discord message.

    sleever make me sailor moon sleeves          (+ optional image uploads or links)

bot.py runs the turn on the same harness as the builder (whichever model the owner has
picked), in a per-user staging folder: scripts/discord/bot/.sleever/<owner>/. The model only paints. It
saves one picture there and ends its reply with `Sleeve: <Name>`. Everything after that is
this module's, so it behaves the same whatever model made the picture:

  * crop to a Magic card's 63:88 around the centre, resize to 745 x 1040, save as JPEG
    under 500 KB (macOS `sips`);
  * name it `<slug>.jpg` in tts/sleeves/, never overwriting another user's sleeve or one
    of the hand-made ones (ownership is kept privately in scripts/discord/bot/.sleever/owners.json);
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
REPO = HERE.parents[2]
SLEEVES_DIR = REPO / "tts" / "sleeves"
STAGING = HERE / ".sleever"                      # gitignored; one folder per user
OWNERS = STAGING / "owners.json"                 # slug -> Discord owner, for overwrites

WIDTH, HEIGHT = 745, 1040                        # docs/development/tts-sleeves-guide.md "Image specs"
MAX_BYTES = 500_000
IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".webp")
RESERVED = {"standard"}                          # Magic's own back, always listed first

MAX_REFS = 6                                     # uploads the bot downloads per message
REF_TIMEOUT = 20
# No size limit on a reference. One over either of these is re-encoded as a JPEG at
# most REF_SIDE pixels on its longest side, so the model gets a picture it can read;
# so is any format other than PNG, JPEG and WebP (HEIC from a phone, AVIF, GIF...).
REF_SIDE = 4096
REF_PLAIN_BYTES = 12_000_000

SLEEVE_LINE = re.compile(r"^\s*Sleeve:\s*(.+?)\s*$", re.M | re.I)
ATTACH = "[[attach:{}]]"                         # deckBuilder.ts swaps this for the file

UNAVAILABLE = "sleever can't make pictures right now. Try again later."
NO_PICTURE = ("sleever didn't come up with a picture that time. Try again, maybe with "
              "a bit more detail about what you want on the sleeves.")

SLEEVE_CONTENT_RULE = (
    "Do not create or revise sleeves related to Donald Trump, including his likeness, "
    "name, slogans, campaign imagery (including MAGA), or Trump-themed memes or symbols. "
    "This applies to supportive, critical, satirical, and indirect depictions, including "
    "requests based on reference images. If the request or references require "
    "Trump-related artwork, briefly decline without generating an image or a Sleeve: line."
)

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

1. **When you generate (see step 2), use your built-in image generation tool.** Make
   one finished picture per request.
   Never use the ChatGPT website, browser automation, or a paid image API. For Codex,
   use the built-in `image_gen` tool and copy its selected output into this folder. If
   image generation fails due to a quota limit or capacity limit (especially on
   `gemini-3.1-flash-image`), state clearly that image quota on
   `gemini-3.1-flash-image` has been exhausted and give the reset time if known.
   If you have no way to make pictures at all, reply `I can't make pictures right now.`
   and stop.
2. **An attached picture is the sleeve.** Pictures the user attached are in `refs/`
   (ref-1.png, ref-2.jpg, ...). By default, use the picture itself, unchanged:
   do not generate anything, just copy it into place, e.g.
   `cp refs/ref-1.png sleeve.png` (keep its extension; with several, use the one
   the user means, else the first). The bot crops it around the centre and sizes
   it, so a picture that is not portrait or has a border is still used as it is.
   The owner rule in step 4 still applies to it.
   **Only generate** when the user says the picture is a reference or inspiration,
   or asks for changes to it ("in this style", "make her a wizard", "add a
   background", "darker"). Then look at every picture and make one in that spirit.
   Pictures from the user's previous message, if any, are in `refs/earlier/`. Use
   them only when the user refers back to them ("the picture I attached"); then the
   same rule applies. With no picture, generate as usual. If the message has links, you may
   download them into `refs/` or look the subject up on the web; a linked picture
   follows the same rule as an attached one.
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
   **Exception — owner rule:** @CONTENT_RULE@
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
""".replace("@CONTENT_RULE@", SLEEVE_CONTENT_RULE)


class SleeveError(RuntimeError):
    """The picture could not be turned into a sleeve."""


# ---------- staging ----------

def folder(owner: str) -> Path:
    return STAGING / owner


def prepare(owner: str, fresh: bool = True) -> Path:
    """The user's staging folder with fresh instructions (0444) and refs/ ready for
    this message's pictures. `fresh` (the message has pictures) empties refs/;
    otherwise the last message's pictures move to refs/earlier/, where the model
    uses them only when the user refers back to them."""
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
    if fresh:
        shutil.rmtree(refs, ignore_errors=True)
    else:
        current = [p for p in refs.glob("ref-*") if p.is_file()] if refs.is_dir() else []
        if current:
            earlier = refs / "earlier"
            shutil.rmtree(earlier, ignore_errors=True)
            earlier.mkdir(parents=True)
            for p in current:
                p.rename(earlier / p.name)
    refs.mkdir(exist_ok=True)
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


def _readable(part: Path, out: Path) -> bool:
    """Re-encode `part` as a JPEG at `out`, no bigger than REF_SIDE; False if it is
    not a picture macOS can read."""
    try:
        w, h = _size(part)
        _sips("-s", "format", "jpeg", *(["-Z", str(REF_SIDE)] if max(w, h) > REF_SIDE else []),
              str(part), "--out", str(out))
    except (SleeveError, subprocess.SubprocessError, OSError):
        return False
    return out.is_file()


def fetch_refs(urls: list[str], dest: Path) -> list[str]:
    """Download the user's uploads into `dest`. Returns notes on any that were skipped.

    Runs outside the sandbox, so it is strict: https only, and the bytes must be a
    picture whatever the server claims. Any size is fine (see REF_SIDE).
    """
    notes: list[str] = []
    n = 0
    for url in urls[:MAX_REFS]:
        if not url.lower().startswith("https://"):
            notes.append(f"skipped a non-https reference: {url[:80]}")
            continue
        part = dest / f"ref-{n + 1}.part"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mtg-sleever/1"})
            with urllib.request.urlopen(req, timeout=REF_TIMEOUT) as r, part.open("wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
        except Exception as exc:
            part.unlink(missing_ok=True)
            notes.append(f"could not download a reference ({type(exc).__name__})")
            continue
        with part.open("rb") as f:
            kind = _sniff(f.read(16))
        plain = kind in (".png", ".jpg", ".webp") and part.stat().st_size <= REF_PLAIN_BYTES
        out = dest / f"ref-{n + 1}{kind if plain else '.jpg'}"
        if plain:
            part.rename(out)
        elif not _readable(part, out):
            notes.append("skipped a reference that is not a picture")
        part.unlink(missing_ok=True)
        if out.is_file():
            n += 1
    if len(urls) > MAX_REFS:
        notes.append(f"used the first {MAX_REFS} references only")
    return notes


def latest_picture(f: Path, since: float) -> Path | None:
    """The newest picture the model saved in its folder this turn (refs/ excluded)."""
    found = [p for p in f.iterdir()
             if p.is_file() and p.suffix.lower() in IMAGE_TYPES and p.stat().st_mtime >= since]
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


def forget_removed(f: Path, previous: str | None) -> bool:
    """True when `previous` is no longer on the table (the owner removed it). Its picture
    leaves the staging folder too, so nothing of it steers the next request."""
    if not previous or _existing(previous):
        return False
    for old in f.glob("sleeve.*"):
        old.unlink(missing_ok=True)
    return True


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
    if name is None:
        return (body or NO_PICTURE), None
    if picture is None:
        return NO_PICTURE, None
    slug = choose_slug(name, owner, previous)
    dest = SLEEVES_DIR / f"{slug}.jpg"
    finish(picture, dest)
    record_owner(slug, owner)
    label = slug.replace("-", " ").replace("_", " ").title()
    desc_line = body or f"Made **{label}** sleeves."
    lines = [desc_line,
             f"In the table it's **Sleeves: {label}** in the Cactuar deck browser, a few "
             f"minutes from now: open the browser (or press **Refresh** if it's open), then "
             f"pick it before loading a deck.",
             ATTACH.format(dest)]
    return "\n\n".join(lines), slug

