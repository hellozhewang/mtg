#!/usr/bin/env python3
"""Ask Codex for a second opinion on the decks in this folder.

    ./ask_codex.py "your question"                 # preferred model + effort, else best available
    ./ask_codex.py "question" -o answer.md         # also save the final answer
    ./ask_codex.py --list                          # show every model + its effort tiers
    ./ask_codex.py "q" --model gpt-5.6-luna --effort low
    ./ask_codex.py --refresh "question"            # force a models-cache refresh first
    echo "long prompt" | ./ask_codex.py            # prompt from stdin

Model and reasoning effort are resolved DYNAMICALLY from ~/.codex/models_cache.json
on every run, so this keeps working when OpenAI ships a new tier -- nothing is
hardcoded beyond one preference. Selection rule: PREFERRED_MODEL if the cache lists it,
otherwise the lowest `priority` among visibility=="list" models; then PREFERRED_EFFORT
if that model supports it, otherwise its last (highest) `supported_reasoning_levels`.

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
FALLBACK = ("gpt-6-astra", "max")
# The owner's choice for deck reviews (2026-10-03). It needs a current Codex CLI:
# 0.153 got "gpt-6.1-sol is not supported when using Codex with a ChatGPT account"
# (misleading — the account is fine) while 0.160 works. If the run fails anyway,
# main() retries once with the best other listed model. xhigh rather than the top
# tier keeps a review inside the time a background run allows.
PREFERRED_MODEL = "gpt-6.1-sol"
PREFERRED_EFFORT = "xhigh"


def load_models() -> list[dict]:
    try:
        return json.loads(CACHE.read_text())["models"]
    except Exception as exc:                       # missing, corrupt, or schema drift
        print(f"warning: could not read {CACHE}: {exc}", file=sys.stderr)
        return []


def efforts_of(model: dict) -> list[str]:
    return [lv["effort"] for lv in (model.get("supported_reasoning_levels") or [])]


def resolve(models: list[dict]) -> tuple[str, str]:
    """(model_slug, effort): PREFERRED when this account offers it, else the best
    available model; PREFERRED_EFFORT when that model supports it, else its highest."""
    usable = [m for m in models if m.get("visibility") == "list" and m.get("slug")]
    if not usable:
        return FALLBACK
    best = (next((m for m in usable if m["slug"] == PREFERRED_MODEL), None)
            or min(usable, key=lambda m: m.get("priority", 9999)))
    levels = efforts_of(best)
    if PREFERRED_EFFORT in levels:
        return best["slug"], PREFERRED_EFFORT
    return best["slug"], (levels[-1] if levels else "high")


def run_codex(model: str, effort: str, out: str, prompt: str) -> int:
    print(f">>> model={model}  effort={effort}  web_search=on  sandbox=read-only\n")
    cmd = [
        "codex", "exec",
        "--skip-git-repo-check",          # this folder is not a git repo
        "-s", "read-only",                # Codex may read decklists, never write
        "-C", str(HERE),
        "-m", model,
        "-c", f'model_reasoning_effort="{effort}"',
        "-c", "tools.web_search=true",    # NOT --search; that is top-level only
        "-o", out,
        prompt,
    ]
    return subprocess.run(cmd, stdin=subprocess.DEVNULL).returncode


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
    if not args.model and auto_model != PREFERRED_MODEL:
        print(f"note: {PREFERRED_MODEL} is not in the models cache; using {auto_model}",
              file=sys.stderr)
    model = args.model or auto_model
    effort = args.effort or auto_effort

    # Warn instead of failing if an override isn't supported by that model.
    chosen = next((m for m in models if m.get("slug") == model), None)
    if chosen and effort not in efforts_of(chosen):
        print(f"warning: {model} lists efforts {efforts_of(chosen)}, not {effort!r}",
              file=sys.stderr)

    code = run_codex(model, effort, args.out, prompt)
    # The models cache is shared with newer Codex clients (the VS Code extension
    # bundles its own), so it can list a model the CLI on PATH is too old to use.
    # When the PREFERRED pick fails, retry once with the best other listed model
    # rather than failing the whole review.
    if code != 0 and not args.model and model == PREFERRED_MODEL:
        others = [m for m in models if m.get("visibility") == "list"
                  and m.get("slug") and m["slug"] != PREFERRED_MODEL]
        retry = (min(others, key=lambda m: m.get("priority", 9999))["slug"]
                 if others else FALLBACK[0])
        levels = efforts_of(next((m for m in others if m["slug"] == retry), {}))
        retry_effort = (args.effort or (PREFERRED_EFFORT if PREFERRED_EFFORT in levels
                                        else (levels[-1] if levels else "high")))
        print(f"note: {model} failed; retrying with {retry}", file=sys.stderr)
        code = run_codex(retry, retry_effort, args.out, prompt)
    if code != 0:
        print(f"codex exited {code}", file=sys.stderr)
        return code

    out = Path(args.out)
    if out.exists():
        print(f"\n{'=' * 19} answer -> {out} {'=' * 19}")
        print(out.read_text().rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
