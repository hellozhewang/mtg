"""Layer 1 — Scryfall image CDN client.

Pure network, a sibling of api.py rather than part of it, because it talks to a
different host with different rules:

  * Images live on `cards.scryfall.io`, NOT `api.scryfall.com`. The CDN is not
    rate-limited the way the API is, and it returns image bytes, not JSON.
  * **The URLs are content-addressed.** A card image URL ends in the printing's
    UUID plus a `?<version>` query string that changes only when Scryfall
    replaces the scan. So bytes fetched for a given URL are valid forever — which
    is why ImageStore has no TTL, unlike every other cache in this repo.
  * Nothing here fetches a URL out of thin air. Every URL comes from the
    `image_uris` already sitting in a cached card object, so having the card
    costs zero extra API calls to know where its picture is.

Sizes, measured on a real card (Grand Arbiter Augustin IV):

    thumb    webp   146x204     9.4 KB     gallery grid, catalog tiles
    small    jpg    146x204    14.2 KB
    art      webp   crop       42.4 KB     landscape art, for deck tiles
    normal   jpg    488x680    95.6 KB     hover preview and click-to-zoom
    png      png    745x1040  ~700 KB

Those numbers drive the hosting split in build_site.py: 818 unique cards is
7.7 MB at `thumb` but 78 MB at `normal`, and a public git repo keeps every
version forever.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import PurePosixPath
from urllib.parse import urlsplit

# Two CDNs, both Scryfall's: card scans, and the mana-symbol SVGs. Note `.io`,
# NOT `.com` — svgs.scryfall.com does not resolve at all.
HOSTS = ("cards.scryfall.io", "svgs.scryfall.io")
# These serve images, so `Accept: application/json` — required by the API — would
# be actively wrong here. Only the User-Agent carries over.
HEADERS = {"User-Agent": "MtgDeckTuner/1.0", "Accept": "image/*"}
POLITE_DELAY = 0.05            # a CDN, so lighter than api.py's 0.12


class ImageError(RuntimeError):
    pass


FACES = ("front", "back")


def local_name(oracle_id: str, face: int, size: str, url: str) -> str:
    """Stable filename for a card image: `<oracle_id>-<face>-<size>.<ext>`.

    **Keyed on ORACLE ID, not the printing UUID.** A card object in the cache is
    whichever printing Scryfall happened to return, and any search rewrites it —
    `find_cards.py` banks every card a search hits. So a routine ninja search can
    swap Yuriko from one printing to another, which changes the image URL. With
    printing-keyed names that renamed the file, so the site builder wrote a new
    one and pruned the old: unrelated card art churning in git on a turn that
    only added a deck. Measured once: 8 deleted, 44 added, for one new decklist.

    Oracle id is the card's identity across every printing, so the filename now
    holds still. A different printing still changes the BYTES, and git records
    that as a modification — but it stays one stable path per card instead of an
    add/delete pair, and nothing goes stale.

    Face and size stay in the name because each was a real collision: a DFC's two
    faces share one identity, and `thumb` and `art` are both `.webp`.
    """
    ext = PurePosixPath(urlsplit(url).path).suffix or ".jpg"
    return f"{oracle_id}-{FACES[1 if face else 0]}-{size}{ext}"


class ImageAPI:
    """Fetches image bytes. `calls` counts HTTP requests made."""

    def __init__(self, delay: float = POLITE_DELAY):
        self.delay = delay
        self.calls = 0

    def get(self, url: str) -> bytes:
        if urlsplit(url).hostname not in HOSTS:
            # Guardrail, not paranoia: URLs come from card JSON, and this keeps a
            # malformed or hand-edited one from turning the builder into a
            # general-purpose downloader.
            raise ImageError(f"refusing url outside {HOSTS}: {url}")
        req = urllib.request.Request(url, headers=HEADERS)
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            raise ImageError(f"HTTP {e.code} for {url}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ImageError(f"{type(e).__name__} for {url}") from e
        finally:
            time.sleep(self.delay)
