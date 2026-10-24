#!/usr/bin/env python3
"""Build the next Cactuar table version and deliver it to the owner's TTS Saves folder.

Every delivered/test build gets the next vN, never an unnumbered Preview name.
The owner separately selects which version to publish to Steam; do not use any
Workshop upload option without that explicit release instruction.

    python3 scripts/tabletop/release_tts.py --notes "Sleeves menu" --notes "Louder announcer"
    python3 scripts/tabletop/release_tts.py --dry-run          # build locally, deliver nothing
    python3 scripts/tabletop/release_tts.py --current          # print the version we're at

What it does, in order:

1. Reads the latest version from docs/development/tts-changelog.md; the new one is the next number.
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
6. With --workshop, updates the Steam Workshop item too (see "Workshop" below).
7. Copies tts/WIP.md and docs/development/tts-changelog.md to the PC Desktop, and adds the new
   version's entry to docs/development/tts-changelog.md. Commit and push that file afterwards.

Workshop: TTS uses Steam's legacy RemoteStorage API, not SteamCMD's UGC uploader.
A temporary, least-privileged interactive task runs tts_workshop.ps1 in the owner's
logged-in Windows session, using TTS's steam_api64.dll and the running Steam client.
No passwords or execution-policy changes. --workshop-only uploads the current
delivered save without rebuilding it or incrementing the version.

Where the PC is comes from tts/deploy.local.json (gitignored; see INTERNALS.md):

    {"ssh": "user@host", "tts_dir": "/mnt/c/.../Tabletop Simulator",
     "desktop": "/mnt/c/.../Desktop", "workshop_id": "3822623414"}
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
import time
import urllib.request
import uuid
from xml.sax.saxutils import escape
from datetime import date
from io import BytesIO
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHANGELOG = REPO / "docs" / "development" / "tts-changelog.md"
WIP = REPO / "tts" / "WIP.md"
CONFIG = REPO / "tts" / "deploy.local.json"
NAME = "MTG 6 player Cactuar Ver_v{}"
BASE_WORKSHOP = "Mods/Workshop/2293586471.json"
PAGES = "https://hellozhewang.github.io/mtg/tts/"
TILE = "tts/cactuar-tile.jpg"
VERSION_RE = re.compile(r"^## v(\d+)\b", re.M)
TTS_APP = 286160


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


def entry_notes(text: str, version: int) -> list[str]:
    """The bullet lines of version `version`'s changelog entry."""
    m = re.search(rf"^## v{version}\b.*?\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return [l[2:].strip() for l in (m.group(1) if m else "").splitlines() if l.startswith("- ")]


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
    dirty = git("status", "--porcelain", "--", "tts", "scripts/tabletop/build_tts_table.py")
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
        self.workshop_id = config.get("workshop_id")
        self.workshop_dir = config.get("workshop_dir", "/mnt/c/cactuar-workshop")
        self.steam_dll = config.get("steam_dll")
        self.saves = f"{self.tts_dir}/Saves"

    def shell(self, script: str, data: bytes = b"", timeout: int = 300) -> str:
        """Run `script` in the PC's shell, which reads its commands from stdin (an
        argument would arrive as one word). `script` is one line; `data` follows it,
        for a command on that line to read, and `exit` is on the same line so the
        shell never reads `data` as commands."""
        payload = f"{script.strip()}; exit\n".encode() + data
        return run("ssh", "-T", "-o", "ConnectTimeout=10", self.ssh, input=payload, timeout=timeout).decode()

    def powershell(self, script: str) -> str:
        return self.shell("powershell.exe -NoLogo -NoProfile -NonInteractive -Command "
                          + shlex.quote("$ErrorActionPreference='Stop'; " + script)
                          + " < /dev/null", timeout=30).lstrip("\ufeff").strip()

    def read(self, path: str) -> bytes:
        return run("ssh", "-T", "-o", "ConnectTimeout=10", self.ssh,
                   input=f"cat {shlex.quote(path)}; exit\n".encode(), timeout=300)

    def write(self, path: str, data: bytes) -> None:
        self.shell(f"head -c {len(data)} > {shlex.quote(path)}", data)
        remote = self.shell(f"sha256sum {shlex.quote(path)}").split()[0]
        if remote != hashlib.sha256(data).hexdigest():
            fail(f"checksum mismatch after copying {path}")


def windows_path(path: str) -> str:
    match = re.fullmatch(r"/mnt/([a-z])/(.+)", path)
    if not match:
        raise ValueError(f"expected a WSL Windows-drive path: {path!r}")
    return match[1].upper() + ":\\" + match[2].replace("/", "\\")


def ps_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def workshop_task_xml(sid: str, folder: str) -> str:
    """On-demand only; runs as the already logged-in user, never elevated."""
    args = (f'-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden '
            f'-File "{folder}\\tts_workshop.ps1" -Config "{folder}\\config.json"')
    return f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Principals><Principal id="Owner"><UserId>{escape(sid)}</UserId>
    <LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel>
  </Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT12M</ExecutionTimeLimit></Settings>
  <Actions Context="Owner"><Exec><Command>powershell.exe</Command>
    <Arguments>{escape(args)}</Arguments><WorkingDirectory>{escape(folder)}</WorkingDirectory>
  </Exec></Actions>
</Task>
'''


def validate_workshop_result(result: dict, item: str) -> None:
    if (result.get("ok") is not True or result.get("eresult") != 1
            or str(result.get("item")) != item or result.get("needs_legal_agreement")):
        fail(f"Workshop upload wasn't confirmed: {result.get('message', result)}")


def workshop_upload(pc: PC, save: Path, thumb: Path, item: str, note: str) -> None:
    """Upload through Steam's legacy API in a temporary interactive task."""
    if not re.fullmatch(r"[1-9]\d*", item):
        fail(f"not a Workshop item id: {item!r}")
    from tts_bson import encode
    # Read-only preflight: refuse a policy that would block this script. Never
    # bypass it, alter policy, or ask for an elevated/password-bearing task.
    status = json.loads(pc.powershell(
        "[pscustomobject]@{policy=\"$(Get-ExecutionPolicy)\"; "
        "sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value; "
        "user=[Security.Principal.WindowsIdentity]::GetCurrent().Name; "
        "desktopUser=(Get-CimInstance Win32_ComputerSystem).UserName; "
        "steam=@(Get-Process steam -ErrorAction SilentlyContinue | Select-Object Id,SessionId)"
        "} | ConvertTo-Json -Depth 4"))
    if status["policy"] not in ("RemoteSigned", "Unrestricted", "Bypass"):
        fail(f"Windows policy {status['policy']} doesn't permit the local uploader; policy left unchanged")
    if not status["desktopUser"] or status["desktopUser"].lower() != status["user"].lower() or not status["steam"]:
        fail("Steam must be running in the SSH user's logged-in Windows desktop session")
    dll_script = (
        "$p=Get-Process 'Tabletop Simulator' -ErrorAction SilentlyContinue | Select-Object -First 1; "
        "$roots=@(); if ($p) {$roots += Split-Path $p.Path}; "
        "$steam=(Get-ItemProperty 'HKCU:\\Software\\Valve\\Steam').SteamPath; "
        "$libs=@($steam); $vdf=Join-Path $steam 'steamapps/libraryfolders.vdf'; "
        "if (Test-Path $vdf) {foreach ($m in [regex]::Matches((Get-Content -Raw $vdf), "
        "'\"path\"\\s+\"([^\"]+)\"')) {$libs += $m.Groups[1].Value.Replace('\\\\','\\')}}; "
        "foreach ($lib in $libs) {$roots += Join-Path $lib 'steamapps/common/Tabletop Simulator'}; "
        "$dll=$roots | ForEach-Object {Join-Path $_ 'Tabletop Simulator_Data/Plugins/x86_64/steam_api64.dll'} "
        "| Where-Object {Test-Path $_} | Select-Object -First 1; if (-not $dll) {throw 'TTS steam_api64.dll not found'}; $dll")
    dll = pc.steam_dll or pc.powershell(dll_script)
    run_id = uuid.uuid4().hex
    folder = f"{pc.workshop_dir}/{run_id}"
    folder_win = windows_path(folder)
    task = f"CactuarWorkshop-{run_id}"
    result_path = f"{folder}/result.json"
    pc.shell("mkdir -p " + shlex.quote(folder))
    payload = encode(json.loads(save.read_text(encoding="utf-8")))
    config = {"dll": dll, "item": item, "file": folder_win + "\\WorkshopUpload",
              "preview": folder_win + "\\preview.png", "note": note,
              "result": folder_win + "\\result.json"}
    for filename, blob in (("WorkshopUpload", payload), ("preview.png", thumb.read_bytes()),
                           ("tts_workshop.ps1", (REPO / "scripts/tabletop/tts_workshop.ps1").read_bytes()),
                           ("config.json", json.dumps(config, ensure_ascii=False).encode()),
                           ("task.xml", workshop_task_xml(status["sid"], folder_win).encode("utf-16"))):
        pc.write(f"{folder}/{filename}", blob)
    print(f"Workshop payload staged and checksummed: {folder}", flush=True)
    pc.powershell(
        "$tokens=$null; $errors=$null; "
        f"[void][Management.Automation.Language.Parser]::ParseFile({ps_string(folder_win + '/tts_workshop.ps1')}, "
        "[ref]$tokens, [ref]$errors); if ($errors.Count) {throw ($errors -join '; ')}")
    created = False
    try:
        pc.shell("schtasks.exe /Create /TN " + shlex.quote(task)
                 + " /XML " + shlex.quote(folder_win + "\\task.xml") + " < /dev/null")
        created = True
        pc.shell("schtasks.exe /Run /TN " + shlex.quote(task) + " < /dev/null")
        print(f"Uploading Workshop item {item} in the logged-in session (temporary task).", flush=True)
        deadline, next_report = time.monotonic() + 660, time.monotonic() + 30
        while time.monotonic() < deadline:
            raw = pc.shell(f"if [ -f {shlex.quote(result_path)} ]; then cat {shlex.quote(result_path)}; fi",
                           timeout=30).lstrip("\ufeff").strip()
            if raw:
                # Keep the server's verdict locally even if the task is removed.
                cache = REPO / ".cache/workshop"
                cache.mkdir(parents=True, exist_ok=True)
                (cache / f"{item}-{run_id}-result.json").write_text(raw)
                verdict = json.loads(raw)
                validate_workshop_result(verdict, item)
                print(f"Workshop item {item} updated: Steam EResult 1; account {verdict.get('steam_id')}", flush=True)
                return
            if time.monotonic() >= next_report:
                state = json.loads(pc.powershell(
                    f"$t=Get-ScheduledTask -TaskName {ps_string(task)}; "
                    "$i=$t | Get-ScheduledTaskInfo; "
                    "[pscustomobject]@{state=\"$($t.State)\"; result=$i.LastTaskResult} | ConvertTo-Json"))
                if state["state"] != "Running":
                    fail(f"Workshop task stopped without a result: {state}; inspect {folder_win}")
                print("Waiting for Steam's Workshop result...", flush=True)
                next_report = time.monotonic() + 30
            time.sleep(2)
        fail(f"Workshop upload timed out; inspect {folder_win}")
    finally:
        if created:
            pc.shell("schtasks.exe /Delete /TN " + shlex.quote(task) + " /F < /dev/null")
            print("Temporary Workshop task removed.", flush=True)


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
    for rel, blob in head_files(["tts", "scripts", "docs/tts/card-colors.json"]).items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_bytes(blob)
    base_file = out_dir / "base.json"
    base_file.write_bytes(base)
    save = out_dir / f"{name}.json"
    run(sys.executable, str(src / "scripts" / "tabletop" / "build_tts_table.py"), str(base_file),
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
    ap.add_argument("--workshop", action="store_true",
                    help="also update the Steam Workshop item (workshop_id in the config)")
    ap.add_argument("--workshop-only", action="store_true",
                    help="upload the CURRENT delivered save; no rebuild or new version")
    ap.add_argument("--workshop-test", metavar="ITEM_ID",
                    help="upload HEAD's build to a throwaway Workshop item; no version, no Saves")
    args = ap.parse_args()
    if sum(bool(v) for v in (args.workshop, args.workshop_only, args.workshop_test)) > 1:
        ap.error("choose only one Workshop mode")
    if args.workshop_only and (args.dry_run or args.base or args.skip_publish_check):
        ap.error("--workshop-only uses the delivered save and requires publication checks")

    text = CHANGELOG.read_text(encoding="utf-8")
    current = current_version(text)
    if args.current:
        print(f"v{current}")
        return 0
    version = args.version or (current if args.workshop_only else current + 1)
    if args.workshop_only:
        args.notes = args.notes or entry_notes(text, version)
    elif version <= current and not args.dry_run:
        fail(f"v{version} isn't newer than v{current}")
    name = NAME.format(version)
    if args.workshop_test:
        name, args.notes = f"Cactuar Workshop test ({version - 1})", args.notes or ["Workshop upload test"]
    if not args.notes and not args.dry_run:
        fail("say what changed: --notes \"...\" (repeatable)")

    commit = check_published(args.skip_publish_check or args.dry_run)
    pc = None
    if not (args.dry_run and args.base):
        try:
            pc = PC(json.loads(CONFIG.read_text(encoding="utf-8")))
        except FileNotFoundError:
            fail(f"no {CONFIG.relative_to(REPO)}: see INTERNALS.md for the PC's details")
    if args.workshop_only:
        if not pc.workshop_id:
            fail(f"{CONFIG.name} has no workshop_id")
        with tempfile.TemporaryDirectory() as tmp:
            save, thumb = (Path(tmp) / f"{name}{suffix}" for suffix in (".json", ".png"))
            for path in (save, thumb):
                path.write_bytes(pc.read(f"{pc.saves}/{path.name}"))
            delivered = json.loads(save.read_text(encoding="utf-8"))
            if delivered.get("SaveName") != name or re.search(r'soundBase\s*=\s*"', delivered.get("LuaScript", "")):
                fail("delivered save has the wrong version or a LAN audio override")
            print(f"Uploading the existing delivered {name}; no rebuild or version increment.", flush=True)
            workshop_upload(pc, save, thumb, pc.workshop_id, f"v{version}: " + "; ".join(args.notes))
        return 0
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
        if args.workshop_test:
            workshop_upload(pc, save, thumb, args.workshop_test, "; ".join(args.notes))
            print("test upload only: nothing delivered to Saves, no version recorded")
            return 0
        for f in (save, thumb):
            pc.write(f"{pc.saves}/{f.name}", f.read_bytes())
        print(f"delivered to Saves, checksums match")
        for old in remove_old(pc, name):
            print(f"removed {old}")
        if args.workshop:
            if not pc.workshop_id:
                fail(f"{CONFIG.name} has no workshop_id")
            workshop_upload(pc, save, thumb, pc.workshop_id, f"v{version}: " + "; ".join(args.notes))
            args.notes = [*args.notes, f"Workshop item {pc.workshop_id} updated."]

    CHANGELOG.write_text(add_entry(text, version, args.notes, commit, date.today().isoformat()),
                         encoding="utf-8")
    for local, remote in ((WIP, "Cactuar table WIP.md"), (CHANGELOG, "Cactuar table CHANGELOG.md")):
        pc.write(f"{pc.desktop}/{remote}", local.read_bytes())
    print(f"v{version} recorded in {CHANGELOG.relative_to(REPO)}; WIP and changelog copied to the Desktop.")
    print("Next: commit and push docs/development/tts-changelog.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
