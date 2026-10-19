#!/usr/bin/env python3
"""Build the next Cactuar table version and deliver it to the owner's TTS Saves folder.

    python3 scripts/release_tts.py --notes "Sleeves menu" --notes "Louder announcer"
    python3 scripts/release_tts.py --dry-run          # build locally, deliver nothing
    python3 scripts/release_tts.py --current          # print the version we're at

What it does, in order:

1. Reads the latest version from tts/CHANGELOG.md; the new one is the next number.
2. Checks HEAD is pushed and GitHub Pages already serves HEAD's sounds and tile
   picture. The table downloads those from Pages by content-hashed URL, and TTS caches
   by URL: delivering first would let TTS cache the old file under the new name.
3. Builds from HEAD (`git archive`), never from the working tree, so files still being
   edited (a clip someone is re-recording) can't slip into a release.
4. Fetches the base table (Workshop 2293586471) from the PC, builds
   "MTG 6 player Cactuar Ver_vN", and makes the thumbnail from the tile picture.
5. Delivers both to the PC's TTS Saves folder, checks their SHA-256 there, and removes
   the previous Cactuar versions (the owner keeps only the latest). It never touches
   anything else in Saves.
6. Copies tts/WIP.md and tts/CHANGELOG.md to the PC Desktop, and adds the new
   version's entry to tts/CHANGELOG.md. Commit and push that file afterwards.

Where the PC is comes from tts/deploy.local.json (gitignored; see INTERNALS.md):

    {"ssh": "user@host", "tts_dir": "/mnt/c/.../Tabletop Simulator",
     "desktop": "/mnt/c/.../Desktop"}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from datetime import date
from io import BytesIO
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHANGELOG = REPO / "tts" / "CHANGELOG.md"
WIP = REPO / "tts" / "WIP.md"
CONFIG = REPO / "tts" / "deploy.local.json"
NAME = "MTG 6 player Cactuar Ver_v{}"
BASE_WORKSHOP = "Mods/Workshop/2293586471.json"
PAGES = "https://hellozhewang.github.io/mtg/tts/"
TILE = "tts/cactuar-tile.jpg"
VERSION_RE = re.compile(r"^## v(\d+)\b", re.M)


def fail(msg: str) -> None:
    sys.exit(f"release_tts: {msg}")


def run(*args: str, input: bytes | None = None, timeout: int = 300) -> bytes:
    r = subprocess.run(args, input=input, capture_output=True, timeout=timeout)
    if r.returncode:
        fail(f"{' '.join(args[:3])} failed: {r.stderr.decode(errors='replace').strip()[:300]}")
    return r.stdout


def git(*args: str) -> str:
    return run("git", "-C", str(REPO), *args).decode().strip()


# ---------- version and notes ----------

def current_version(text: str) -> int:
    found = [int(v) for v in VERSION_RE.findall(text)]
    if not found:
        fail(f"no '## vN' entry in {CHANGELOG.relative_to(REPO)}")
    return max(found)


def add_entry(text: str, version: int, notes: list[str], commit: str, today: str) -> str:
    """The changelog with a new top entry, placed above the newest existing one."""
    lines = "\n".join(f"- {n.strip()}" for n in notes if n.strip()) or "- (no notes)"
    entry = f"## v{version} — {today} (commit {commit})\n{lines}\n\n"
    first = VERSION_RE.search(text)
    return text[:first.start()] + entry + text[first.start():] if first else text + "\n" + entry


# ---------- checks ----------

def head_files(paths: list[str]) -> dict[str, bytes]:
    """`paths` (files or folders) as they are at HEAD."""
    data = run("git", "-C", str(REPO), "archive", "--format=tar", "HEAD", *paths)
    out = {}
    with tarfile.open(fileobj=BytesIO(data)) as tar:
        for m in tar.getmembers():
            if m.isfile():
                out[m.name] = tar.extractfile(m).read()
    return out


def check_published(skip: bool) -> str:
    """HEAD's short hash, after checking it's pushed and live on Pages."""
    commit = git("rev-parse", "--short", "HEAD")
    if skip:
        return commit
    git("fetch", "-q", "origin")
    if subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", "HEAD", "origin/main"]).returncode:
        fail("HEAD isn't pushed to origin/main yet. Push first: the table reads Pages.")
    wanted = {name: blob for name, blob in head_files(["tts/sounds", TILE]).items()
              if name == TILE or name.endswith((".wav", ".mp3", ".ogg"))}
    for name, blob in sorted(wanted.items()):
        url = PAGES + name.removeprefix("tts/") + f"?release={hashlib.sha256(blob).hexdigest()[:8]}"
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                live = r.read()
        except Exception as exc:
            fail(f"couldn't fetch {url} ({type(exc).__name__}). Pages may still be publishing.")
        if hashlib.sha256(live).digest() != hashlib.sha256(blob).digest():
            fail(f"Pages doesn't serve HEAD's {name} yet. Wait a minute after the push and retry.")
    dirty = git("status", "--porcelain", "--", "tts", "scripts/build_tts_table.py")
    if dirty:
        print("note: uncommitted changes under tts/ are NOT in this build:\n" + dirty)
    return commit


# ---------- the PC ----------

class PC:
    def __init__(self, config: dict):
        try:
            self.ssh, self.tts_dir, self.desktop = config["ssh"], config["tts_dir"], config["desktop"]
        except KeyError as exc:
            fail(f"{CONFIG.name} is missing {exc}")
        self.saves = f"{self.tts_dir}/Saves"

    def shell(self, script: str, data: bytes = b"", timeout: int = 300) -> str:
        """Run `script` in the PC's shell, which reads its commands from stdin (an
        argument would arrive as one word). `script` is one line; `data` follows it,
        for a command on that line to read, and `exit` is on the same line so the
        shell never reads `data` as commands."""
        payload = f"{script.strip()}; exit\n".encode() + data
        return run("ssh", "-T", "-o", "ConnectTimeout=10", self.ssh, input=payload, timeout=timeout).decode()

    def read(self, path: str) -> bytes:
        return run("ssh", "-T", "-o", "ConnectTimeout=10", self.ssh,
                   input=f"cat {shlex.quote(path)}; exit\n".encode(), timeout=300)

    def write(self, path: str, data: bytes) -> None:
        self.shell(f"head -c {len(data)} > {shlex.quote(path)}", data)
        remote = self.shell(f"sha256sum {shlex.quote(path)}").split()[0]
        if remote != hashlib.sha256(data).hexdigest():
            fail(f"checksum mismatch after copying {path}")


def remove_old(pc: PC, keep: str) -> list[str]:
    """Delete earlier Cactuar builds (.json/.png) from Saves; nothing else."""
    listing = pc.shell(f"cd {shlex.quote(pc.saves)} && ls -1").splitlines()
    pattern = re.compile(r"^MTG 6 player Cactuar Ver_v\d+\.(json|png)$")
    old = [f for f in listing if pattern.match(f) and not f.startswith(keep + ".")]
    if old:
        pc.shell(f"cd {shlex.quote(pc.saves)} && rm -f -- " + " ".join(shlex.quote(f) for f in old))
    return old


# ---------- build ----------

def build(base: bytes, name: str, out_dir: Path) -> tuple[Path, Path]:
    """Build `name` from HEAD into `out_dir`; returns (save json, thumbnail png)."""
    src = out_dir / "src"
    src.mkdir()
    for rel, blob in head_files(["tts", "scripts"]).items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_bytes(blob)
    base_file = out_dir / "base.json"
    base_file.write_bytes(base)
    save = out_dir / f"{name}.json"
    run(sys.executable, str(src / "scripts" / "build_tts_table.py"), str(base_file),
        "-o", str(save), "--name", name)
    lua = json.loads(save.read_text(encoding="utf-8"))["LuaScript"]
    if re.search(r'soundBase\s*=\s*"', lua):
        fail("the built table points its clips somewhere other than Pages")
    thumb = out_dir / f"{name}.png"
    run("/usr/bin/sips", "-s", "format", "png", str(src / TILE), "--out", str(thumb))
    return save, thumb


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--notes", action="append", default=[], metavar="TEXT",
                    help="a patch note for this version (repeatable)")
    ap.add_argument("--version", type=int, help="override the version number")
    ap.add_argument("--current", action="store_true", help="print the current version and exit")
    ap.add_argument("--dry-run", action="store_true", help="build into a temp folder only")
    ap.add_argument("--base", type=Path, help="a local copy of the base table (skips the PC fetch)")
    ap.add_argument("--skip-publish-check", action="store_true",
                    help="don't require HEAD to be pushed and live on Pages (test builds only)")
    args = ap.parse_args()

    text = CHANGELOG.read_text(encoding="utf-8")
    current = current_version(text)
    if args.current:
        print(f"v{current}")
        return 0
    version = args.version or current + 1
    if version <= current and not args.dry_run:
        fail(f"v{version} isn't newer than v{current}")
    name = NAME.format(version)
    if not args.notes and not args.dry_run:
        fail("say what changed: --notes \"...\" (repeatable)")

    commit = check_published(args.skip_publish_check or args.dry_run)
    pc = None
    if not (args.dry_run and args.base):
        try:
            pc = PC(json.loads(CONFIG.read_text(encoding="utf-8")))
        except FileNotFoundError:
            fail(f"no {CONFIG.relative_to(REPO)}: see INTERNALS.md for the PC's details")
    base = args.base.read_bytes() if args.base else pc.read(f"{pc.tts_dir}/{BASE_WORKSHOP}")

    with tempfile.TemporaryDirectory() as tmp:
        save, thumb = build(base, name, Path(tmp))
        print(f"built {name} from {commit} ({save.stat().st_size // 1024} KB)")
        if args.dry_run:
            keep = REPO / ".cache" / "release"
            keep.mkdir(parents=True, exist_ok=True)
            for f in (save, thumb):
                (keep / f.name).write_bytes(f.read_bytes())
            print(f"dry run: nothing delivered; files in {keep.relative_to(REPO)}/")
            return 0
        for f in (save, thumb):
            pc.write(f"{pc.saves}/{f.name}", f.read_bytes())
        print(f"delivered to Saves, checksums match")
        for old in remove_old(pc, name):
            print(f"removed {old}")

    CHANGELOG.write_text(add_entry(text, version, args.notes, commit, date.today().isoformat()),
                         encoding="utf-8")
    for local, remote in ((WIP, "Cactuar table WIP.md"), (CHANGELOG, "Cactuar table CHANGELOG.md")):
        pc.write(f"{pc.desktop}/{remote}", local.read_bytes())
    print(f"v{version} recorded in {CHANGELOG.relative_to(REPO)}; WIP and changelog copied to the Desktop.")
    print("Next: commit and push tts/CHANGELOG.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
