"""Tiny template loader for the `frontend/` folder.

Markup, CSS and JS live in `frontend/` as real files rather than as strings
inside build_site.py: an editor can syntax-highlight and lint them there, and a
design change never means touching Python. build_site.py supplies data; this
module supplies plumbing; neither knows the other's job.

Two mechanisms, both deliberately minimal — no dependency, no expression
language, no logic in the markup:

  {{TOKEN}}         replaced by a value. Uppercase, so it never collides with
                    real markup, and substitution is SINGLE-PASS, so a card
                    named "{{X}}" could not inject a token.

  <template data-part="name">…</template>
                    a repeatable fragment. Extracted out of the page and
                    available as `.part("name")`, so the markup for one deck tile
                    lives next to the page that repeats it instead of being an
                    f-string in Python.

Extraction takes the blank line that separates a `<template>` from whatever comes
before it, not just the template itself. Without that, every part defined in a
file left one blank line behind in the rendered page, so ADDING a part — a change
that alters no output — rewrote the tail of all 23 deck pages. Generated files are
diffed and committed here; a template edit should move only what it means to move.

Nothing here escapes anything. Escaping is the caller's decision because the
caller knows which values are text (a card name) and which are already markup (a
rendered list of tiles) — a template engine guessing that is how you get either
double-escaped apostrophes in `Urza's Saga` or an injection.
"""
from __future__ import annotations

import re
from pathlib import Path

TOKEN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
PART = re.compile(
    r'\n?[ \t]*<template\s+data-part="([a-z0-9-]+)"\s*>(.*?)</template>[ \t]*\n?',
    re.DOTALL)


class TemplateError(RuntimeError):
    pass


class Template:
    def __init__(self, text: str, name: str = "<inline>"):
        self.name = name
        self.parts: dict[str, Template] = {}

        def take(m: re.Match) -> str:
            self.parts[m.group(1)] = Template(m.group(2).strip("\n"),
                                              f"{name}#{m.group(1)}")
            return ""

        self.text = PART.sub(take, text)

    def part(self, name: str) -> Template:
        if name not in self.parts:
            raise TemplateError(
                f"{self.name}: no part {name!r} (have: {sorted(self.parts) or 'none'})")
        return self.parts[name]

    def render(self, **values: object) -> str:
        """Fill every {{TOKEN}}. An unknown or unsupplied token is an error, not
        a silent blank — a typo either way should fail the build, not ship a page
        with a hole in it."""
        def sub(m: re.Match) -> str:
            key = m.group(1)
            if key not in values:
                raise TemplateError(
                    f"{self.name}: {{{{{key}}}}} has no value "
                    f"(given: {', '.join(sorted(values)) or 'nothing'})")
            return str(values[key])
        out = TOKEN.sub(sub, self.text)
        unused = set(values) - set(TOKEN.findall(self.text))
        if unused:
            raise TemplateError(f"{self.name}: unused values {sorted(unused)}")
        return out

    def repeat(self, rows: list[dict]) -> str:
        return "".join(self.render(**row) for row in rows)


def load(directory: Path) -> dict[str, Template]:
    """Every .html in `directory`, keyed by stem. Assets (.css/.js) are copied
    verbatim by the caller and never parsed — a CSS rule can legally contain
    braces that are none of this module's business."""
    out: dict[str, Template] = {}
    for path in sorted(directory.glob("*.html")):
        out[path.stem] = Template(path.read_text(encoding="utf-8"), path.name)
    if not out:
        raise TemplateError(f"no templates found in {directory}")
    return out
