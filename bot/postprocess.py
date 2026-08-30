"""Message processor: expand card tags in a reply into card images.

    from postprocess import expand
    expand("Here is [[card:Zur the Enchanter]].")

Discord renders a bare image URL as an inline preview, so "show a card" reduces
to "put the right URL on its own line". That is all this module does.

WHY A TAG AND NOT NAME-MATCHING
-------------------------------
The obvious alternative is to scan the reply for anything that looks like a card
name and linkify it. That is wrong here: a deckbuilding reply is *full* of card
names — a 99-card list, a tuning discussion, a bracket explanation — and turning
each into an image would bury the answer under fifty pictures. The model knows
which one card it is actually talking about; the tag is how it says so.

WHERE THE URL COMES FROM
------------------------
`CardStore`, the same Scryfall cache the deck tools and the site builder use. So
this is cache-first and costs no network call on a warm cache, and the URL is
content-addressed, meaning it never expires.

`normal` (488x680), not the committed `thumb` (146x204): a thumbnail is sized for
a grid cell on the catalog page and looks blurry as a Discord embed. The bytes in
`ImageStore` are not used — Discord needs a URL it can fetch, and bot.py replies
are strings, with no attachment channel to hand raw bytes through.

FAILURE IS ALWAYS SILENT-BUT-VISIBLE
------------------------------------
A tag that names a card we cannot resolve becomes the plain name in the text.
A reply is the user's answer; a broken tag must never eat it, and must never
show them `[[card:...]]` either.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts"))

import workspace

# [[card:Name]] — deliberately unlike anything in a decklist or in prose, so a
# reply that merely mentions a card cannot trigger it by accident.
TAG = re.compile(r"\[\[card:\s*([^\]\n]{1,120}?)\s*\]\]", re.I)

SIZE = "normal"          # 488x680; `thumb` is grid-sized and reads as blurry
MAX_IMAGES = 4           # a wall of embeds is worse than none


def _image_url(card: dict) -> str:
    """Front-face image URL. A transforming card keeps its faces one level down."""
    if uris := card.get("image_uris"):
        return uris.get(SIZE, "")
    for face in card.get("card_faces") or []:
        if uris := face.get("image_uris"):
            return uris.get(SIZE, "")
    return ""


def expand(text: str, limit: int = MAX_IMAGES) -> str:
    """Replace [[card:Name]] tags with the plain name, and append the images.

    The name stays INLINE so the sentence still reads as English, and the URLs
    go at the END, each alone on its own line. Substituting the URL in place put
    whatever followed the tag — usually a full stop — on the same line, and
    Discord will not preview a URL that shares a line with other text.

    Unresolvable tags degrade to the bare name and add no URL. Tags past `limit`
    do the same, so a model that tags a whole decklist still replies readably.
    """
    if not text or not TAG.search(text):
        return text
    names = [m.group(1).strip() for m in TAG.finditer(text)]
    try:
        from cardlib import CardQuery
        cards, _ = CardQuery(db_path=workspace.cache_db()).cards(names)
    except Exception:                       # cache missing, schema drift, no net
        return TAG.sub(lambda m: m.group(1).strip(), text)

    urls: list[str] = []                    # ordered, de-duplicated

    def swap(match: re.Match) -> str:
        name = match.group(1).strip()
        card = cards.get(name)
        if card:
            url = _image_url(card)
            if url and url not in urls and len(urls) < limit:
                urls.append(url)
            return card.get("name", name)   # canonical spelling, free of charge
        return name

    body = TAG.sub(swap, text)
    return body if not urls else body.rstrip() + "\n\n" + "\n".join(urls)
