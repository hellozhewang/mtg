#!/usr/bin/env python3
"""Ask Codex for a second opinion on the decks in this folder.

    ./ask_codex.py "your question"                 # auto-picks best model + highest effort
    ./ask_codex.py "question" -o answer.md         # also save the final answer
    ./ask_codex.py --list                          # show every model + its effort tiers
    ./ask_codex.py "q" --model gpt-5.6-luna --effort low
    ./ask_codex.py --refresh "question"            # force a models-cache refresh first
    echo "long prompt" | ./ask_codex.py            # prompt from stdin

Model and reasoning effort are resolved DYNAMICALLY from ~/.codex/models_cache.json
on every run, so this keeps working when OpenAI ships a new tier -- nothing is
hardcoded. Selection rule: lowest `priority` among visibility=="list" models, then
the last (highest) entry in that model's `supported_reasoning_levels`.

Two Codex CLI gotchas this encodes so you don't rediscover them:
  * `--search` is a TOP-LEVEL flag and is REJECTED by `codex exec`. Web search on
    exec must be enabled with `-c tools.web_search=true`.
  * `-a/--ask-for-approval` is likewise top-level only; exec is already
    non-interactive and reports `approval: never` on its own.

Web search is always on: bans, the Game Changers list, and bracket rules change
over time, so an answer from stale training data is worse than useless.
Runs read-only -- Codex can read the decklists but cannot modify them.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workspace

CACHE = Path.home() / ".codex" / "models_cache.json"
HERE = workspace.deck_root()   # codex's working root == the writable workspace
FALLBACK = ("gpt-5.6-sol", "max")


def load_models() -> list[dict]:
    try:
        return json.loads(CACHE.read_text())["models"]
    except Exception as exc:                       # missing, corrupt, or schema drift
        print(f"warning: could not read {CACHE}: {exc}", file=sys.stderr)
        return []


def efforts_of(model: dict) -> list[str]:
    return [lv["effort"] for lv in (model.get("supported_reasoning_levels") or [])]


def resolve(models: list[dict]) -> tuple[str, str]:
    """Best available (model_slug, highest_effort)."""
    usable = [m for m in models if m.get("visibility") == "list" and m.get("slug")]
    if not usable:
        return FALLBACK
    best = min(usable, key=lambda m: m.get("priority", 9999))
    levels = efforts_of(best)
    return best["slug"], (levels[-1] if levels else "high")


def refresh_cache() -> None:
    """Cheapest possible call; running codex at all rewrites models_cache.json."""
    print("refreshing models cache...", file=sys.stderr)
    subprocess.run(
        ["codex", "exec", "--skip-git-repo-check", "-s", "read-only", "-C", str(HERE),
         "-m", "gpt-5.6-luna", "-c", 'model_reasoning_effort="low"', "ok"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    )


def show_list(models: list[dict]) -> None:
    try:
        fetched = json.loads(CACHE.read_text()).get("fetched_at")
        print(f"cache fetched_at: {fetched}\n")
    except Exception:
        pass
    for m in sorted(models, key=lambda m: m.get("priority", 9999)):
        star = " <-- auto" if m["slug"] == resolve(models)[0] else ""
        print(f"{m['slug']:<18} prio={m.get('priority'):<3} vis={m.get('visibility'):<5} "
              f"search={m.get('supports_search_tool')} efforts={efforts_of(m)}{star}")
        print(f"{'':<18} {m.get('description', '')}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Ask Codex for a second opinion (read-only, web search on).")
    ap.add_argument("prompt", nargs="?", help="question; omit to read from stdin")
    ap.add_argument("-o", "--out", default="/tmp/codex-answer.md",
                    help="write the final answer here (default: %(default)s)")
    ap.add_argument("--model", help="override auto-detected model")
    ap.add_argument("--effort", help="override auto-detected reasoning effort")
    ap.add_argument("--refresh", action="store_true", help="refresh models cache first")
    ap.add_argument("--list", action="store_true", help="list models and exit")
    args = ap.parse_args()

    if args.refresh:
        refresh_cache()

    models = load_models()

    if args.list:
        show_list(models)
        return 0

    prompt = args.prompt if args.prompt is not None else sys.stdin.read().strip()
    if not prompt:
        ap.error("no prompt given (pass an argument or pipe one in)")

    auto_model, auto_effort = resolve(models)
    model = args.model or auto_model
    effort = args.effort or auto_effort

    # Warn instead of failing if an override isn't supported by that model.
    chosen = next((m for m in models if m.get("slug") == model), None)
    if chosen and effort not in efforts_of(chosen):
        print(f"warning: {model} lists efforts {efforts_of(chosen)}, not {effort!r}",
              file=sys.stderr)

    print(f">>> model={model}  effort={effort}  web_search=on  sandbox=read-only\n")

    cmd = [
        "codex", "exec",
        "--skip-git-repo-check",          # this folder is not a git repo
        "-s", "read-only",                # Codex may read decklists, never write
        "-C", str(HERE),
        "-m", model,
        "-c", f'model_reasoning_effort="{effort}"',
        "-c", "tools.web_search=true",    # NOT --search; that is top-level only
        "-o", args.out,
        prompt,
    ]
    proc = subprocess.run(cmd, stdin=subprocess.DEVNULL)
    if proc.returncode != 0:
        print(f"codex exited {proc.returncode}", file=sys.stderr)
        return proc.returncode

    out = Path(args.out)
    if out.exists():
        print(f"\n{'=' * 19} answer -> {out} {'=' * 19}")
        print(out.read_text().rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
