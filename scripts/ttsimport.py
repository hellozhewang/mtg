"""Ask Tabletop Simulator's deck importer whether it can load a decklist.

    ./ttsimport.py Bracket3/Marchesa-Crew.txt      # what would a player get?

The table these decks are played on embeds rikrassen's MTG Deck/Draft/Cube
Importer. It builds a deck by POSTing the pasted list to its backend and spawning
the JSON that streams back, so sending the same request tells us exactly what a
player would get: which lines it could not find, how many cards arrive, and which
printing each one is. `validate_deck.py` calls `check()` for every deck.

What the importer does with a line, measured against the server (2026-10-12):
  * `1 Sol Ring (CMM) 410` loads that printing; `1 Sol Ring (CMM)` and
    `1 [CMM] Sol Ring` pick the set. Set codes are case-insensitive.
  * The leading quantity is required. Without it the whole line is taken as the
    card name and reported as "failed to find card".
  * A set or number that does not match the card is NOT an error. The card loads
    in some other printing, which is why callers compare `Result.faces` with the
    printing they asked for instead of trusting an empty error list.

This is somebody's free service. Results are cached by the exact text sent, so an
unchanged deck is never sent twice, and uncached requests are spaced out.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workspace

BASE_URL = "https://importer.rikrassen.com"
# The importer's own client refuses to talk to a backend on another version and
# re-downloads itself, so ask the backend which one it is and fall back to this.
CLIENT_VERSION = "v0.11.0"
USER_AGENT = "mtg-deck-tools/1.0 (deck import check; github.com/hellozhewang/mtg)"
TIMEOUT = 90
POLITE_DELAY = 1.5                       # seconds between uncached requests
CACHE_DAYS = 30
CACHE_MAX = 600
# Bump when `parse` changes what it reads out of a reply, so results computed by
# the old reading are fetched again instead of trusted.
PARSER_VERSION = 2

# Where the importer lays the cards out. Any seated player's hand works; the
# values only position the spawned objects, which we never spawn.
HAND = {
    "position": {"x": 0, "y": 3, "z": -20}, "rotation": {"x": 0, "y": 0, "z": 0},
    "scale": {"x": 20, "y": 5, "z": 5}, "forward": {"x": 0, "y": 0, "z": 1},
    "right": {"x": 1, "y": 0, "z": 0}, "up": {"x": 0, "y": 1, "z": 0},
}


class ImporterUnavailable(RuntimeError):
    """The backend could not be reached or did not answer usefully. Not a verdict
    on the deck: callers report it and carry on."""


@dataclass
class Result:
    errors: list[str] = field(default_factory=list)     # the importer's own messages
    count: int = 0                                       # cards returned, tokens excluded
    tokens: int = 0
    # Card name -> Scryfall ids of the printings it loaded (one per copy's face).
    faces: dict[str, list[str]] = field(default_factory=dict)
    cached: bool = False

    def printing_of(self, name: str) -> list[str]:
        """Ids loaded for `name`. The importer names a double-faced card by both
        faces, the decklist by its front."""
        if name in self.faces:
            return self.faces[name]
        return next((ids for full, ids in self.faces.items()
                     if full.split(" // ")[0] == name.split(" // ")[0]), [])


def _face_id(url: str) -> str:
    """The Scryfall id inside an image URL such as .../front/4/6/46ca0b66-....webp"""
    return url.rsplit("/", 1)[-1].split(".", 1)[0]


def parse(text: str) -> Result:
    """Read the newline-delimited JSON the backend streams back.

    The reply is the deck, then whatever the deck makes: a pile nicknamed
    "Tokens", or a single loose Card when there is exactly one token or meld
    result (Tabletop Simulator has no one-card pile). Only the deck is counted.
    A one-card list has no pile at all, so its first object is the deck.
    """
    result = Result()
    objects = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if "error" in obj and "Name" not in obj:
            result.errors.append(str(obj["error"]))
        else:
            objects.append(obj)
    deck = next((o for o in objects if o.get("Nickname") == "Deck" and o.get("ContainedObjects")),
                objects[0] if objects else None)
    for obj in objects:
        cards = obj.get("ContainedObjects") or [obj]
        if obj is not deck:
            result.tokens += len(cards)
            continue
        sheets = {int(k): v.get("FaceURL", "") for k, v in (obj.get("CustomDeck") or {}).items()}
        for card in cards:
            own = card.get("CustomDeck") or {}
            url = next(iter(own.values())).get("FaceURL", "") if own \
                else sheets.get(int(card.get("CardID", 0)) // 100, "")
            name = (card.get("Nickname") or "").split("\n", 1)[0]
            result.faces.setdefault(name, []).append(_face_id(url))
            result.count += 1
    return result


def _request(url: str, body: bytes | None, headers: dict[str, str]) -> str:
    req = urllib.request.Request(url, data=body, method="POST" if body else "GET",
                                 headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        # 400 is the importer rejecting the list ("invalid deck format: ..."), which
        # is a verdict. Anything else is the service having a bad day.
        if exc.code == 400 and '"error"' in text:
            return text
        raise ImporterUnavailable(f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ImporterUnavailable(str(getattr(exc, "reason", exc))) from exc


_version: str | None = None


def client_version() -> str:
    global _version
    if _version is None:
        try:
            _version = _request(f"{BASE_URL}/version", None, {}).strip() or CLIENT_VERSION
        except ImporterUnavailable:
            _version = CLIENT_VERSION
    return _version


def fetch(deck_text: str) -> Result:
    """Send one decklist, exactly as a player would paste it."""
    body = json.dumps({"url": "", "data": deck_text, "hand": HAND,
                       "useStates": True, "preferOriginalPrinting": False}).encode()
    text = _request(f"{BASE_URL}/build", body, {
        "Accept": "application/x-ndjson", "Content-Type": "application/json",
        "X-Client-Version": client_version(), "Accept-Language": "en"})
    try:
        return parse(text)
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
        raise ImporterUnavailable(f"unreadable response ({type(exc).__name__})") from exc


# ---------- cache ----------

def _cache_path() -> Path:
    return workspace.cache_dir() / "tts-import.json"


def _load_cache() -> dict:
    try:
        return json.loads(_cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict) -> None:
    """Best effort: the Discord builder's sandbox mounts the cache read-only."""
    if len(cache) > CACHE_MAX:
        for key in sorted(cache, key=lambda k: cache[k].get("at", 0))[:len(cache) - CACHE_MAX]:
            del cache[key]
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(cache), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


_last_request = 0.0


def check(deck_text: str, use_cache: bool = True) -> Result:
    """`fetch`, remembered by the exact text sent."""
    global _last_request
    key = hashlib.sha256(deck_text.encode("utf-8")).hexdigest()
    cache = _load_cache() if use_cache else {}
    hit = cache.get(key)
    if hit and hit.get("v") == PARSER_VERSION \
            and time.time() - hit.get("at", 0) < CACHE_DAYS * 86400:
        return Result(**hit["result"], cached=True)
    wait = POLITE_DELAY - (time.time() - _last_request)
    if _last_request and wait > 0:
        time.sleep(wait)
    try:
        result = fetch(deck_text)
    finally:
        _last_request = time.time()
    if use_cache:
        cache = _load_cache()                  # another process may have written since
        data = asdict(result)
        data.pop("cached")
        cache[key] = {"at": time.time(), "v": PARSER_VERSION, "result": data}
        _save_cache(cache)
    return result


def main() -> int:
    import deckfile
    paths = deckfile.discover([Path(p) for p in sys.argv[1:]]) if len(sys.argv) > 1 else []
    if not paths:
        sys.exit(__doc__.split("\n\n")[1])
    bad = 0
    for path in paths:
        deck = deckfile.parse(path)
        try:
            result = check(path.read_text(encoding="utf-8"))
        except ImporterUnavailable as exc:
            print(f"??    {path.name}: importer unavailable ({exc})")
            continue
        ok = not result.errors and result.count == deck.total
        bad += not ok
        print(f"{'OK  ' if ok else 'FAIL'}  {path.name}: {result.count}/{deck.total} cards, "
              f"{result.tokens} tokens{' (cached)' if result.cached else ''}")
        for err in result.errors:
            print(f"      !! {err}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
