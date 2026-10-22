# Sleeves

> **Drop pictures in the repo's `tts/sleeves/`, not `docs/tts/sleeves/`.** `docs/` is the
> catalog build's output: the build copies the pictures there. Authored development docs live in
> `docs/development/`, which the build explicitly preserves.

Every picture in `tts/sleeves/` is a sleeve (a custom card back) players can choose in the
Cactuar table's deck browser (**Sleeves ▾**, above **Load into my seat**). The choice is per player and
applies to every card of the next deck they load: library, commanders and tokens.

To add one: put the picture in `tts/sleeves/`, run the catalog build and push. No table rebuild or
Workshop upload is needed, because the table reads the list from the published site.

## sleever: sleeves from Discord

Players can also have sleeves made for them. In the deck builder's Discord channels:

    sleever make me sailor moon sleeves
    sleever <pictures attached, or links pasted> a pixel-art version of this cat
    sleever make it darker                      (revises your last one)

sleever paints the picture with whichever model the owner has set for the builder
(`bot/harness.py`; it needs a harness with an image tool). Then `bot/sleever.py`:
- crops it to these specs and saves `<name>.jpg` in `tts/sleeves/`;
- never overwrites a hand-made sleeve or another player's;
- attaches the sleeve to the Discord reply;
- autopushes `tts/sleeves/` and `docs/`, so it shows in the Sleeves menu a few minutes later
  (reopen the browser, or press **Refresh** in an open one).

The model works in `bot/.sleever/<user>/`, which isn't in git. Uploads are downloaded to
`refs/` there. Who made which sleeve is kept in `bot/.sleever/owners.json`.

## Image specs

| | |
|---|---|
| format | `.jpg`, `.jpeg` or `.png`. Nothing else is offered as a sleeve; the documentation lives in `docs/development/`. |
| shape | portrait, a Magic card's 63:88. **745 × 1040** is the reference size. Other shapes are stretched to fit. |
| size | keep it under ~500 KB. JPEG quality 85–90 is plenty; `cactuar.jpg` is about 130 KB. Every player downloads it. |
| corners | fill the whole rectangle: Tabletop Simulator rounds the card's corners itself. Leave about 25 px of border free of anything important. |
| file name | lowercase `a-z`, `0-9`, `-` or `_`, with no spaces (it becomes a URL). It must be unique by name, ignoring the extension. |
| label | the menu shows the file name without its extension, title-cased, with `-` and `_` as spaces: `dragon_fire.png` → "Dragon Fire". |
| reserved | don't name a file `standard.*`. `standard` is the built-in choice, Magic's own back from Scryfall, which is always listed first. |
| rights | the repo and the site are public. Only add art we made or may share. Don't copy Wizards of the Coast's card back in here; Standard already provides it. |

## Registering a sleeve in Tabletop Simulator

There's nothing to register inside TTS: no Workshop upload, no table rebuild, and no
Custom Deck dialog. The table finds sleeves in the published deck list. So:

1. **Add the file** in `tts/sleeves/`, following the specs above.
2. **Build the catalog**: `python3 scripts/build_site.py`. It must list the sleeve in
   `docs/tts/decks.json` under `sleeves`, and copy it to `docs/tts/sleeves/`.
3. **Publish**: commit and push. GitHub Pages serves it a minute or so later at
   `https://hellozhewang.github.io/mtg/tts/sleeves/<file>`. Check that URL opens the picture.
4. **In the game**: open the Cactuar browser (click a Cactuar tile). From v32 it fetches the
   list again when the copy it has is over 2 minutes old; in an open browser, press
   **Refresh**. From v53, **Sleeves ▾** downloads thumbnails only when clicked,
   eight choices per page. Visited pages are cached. Pick a sleeve, then
   **Load into my seat**. v51–v52 used a text list without previews.

Things that trip people up:
- **Decks already on the table keep their old sleeves.** Sleeves are applied as a deck spawns,
  so delete the deck and load it again.
- **Replacing a picture under the same name is fine.** TTS caches pictures by URL, so the
  build adds a content hash to each sleeve's URL (`sleeves/<file>?v=<hash>`); a changed picture
  gets a new URL and is downloaded again.
- **The table must be one built from this repo** (`MTG 6 player Cactuar Ver_v12` or later,
  or the Workshop item once a v12+ save is uploaded). Older builds have no Sleeves menu (v12–v28 call it Card back and read the old
  `backs` list, which the site no longer publishes, so their menu stays disabled).
- **Nothing appears and Refresh doesn't help:** the table reads from Pages, so the back
  isn't pushed yet, or Pages hasn't finished publishing.

## How it flows

Thumbnails: the build also writes a 146 × 204 preview of each sleeve to
`docs/tts/sleeves/thumbs/` (macOS `sips`, cached in `.cache/sleeve-thumbs/`) and lists it as
`thumb`. From v53 the table registers only pages explicitly opened in the Sleeves
chooser, preserving cached pages and shared Inspect/base images. Opening Cactuar
itself does not download them. v51–v52 used names only; older versions eagerly
registered every thumbnail. Standard uses Scryfall's small card back.


1. `scripts/ttsdecks.py` (`sleeve_files()`, `sleeves()`) lists this folder during
   `python3 scripts/build_site.py`. It copies each picture to `docs/tts/sleeves/` and adds
   it to `docs/tts/decks.json` under `sleeves`: Standard first, with an absolute `url`; then
   these files by name, with a `file` relative to `decks.json`.
2. Pushing publishes them on GitHub Pages under `https://hellozhewang.github.io/mtg/tts/sleeves/`.
3. In the table (`tts/cactuar.lua`), `czSleeveJSON` swaps every `"BackURL"` string in the
   deck's objects for the chosen back as it spawns. It edits the strings only and never
   decodes the objects (see `tts/WIP.md`, "Rules that bite").

## Testing before a push

The owner's catalog server on the Mac (`scripts/start_private_server.py`, port 5588) serves
`docs/`. A table whose browser reads from `http://192.168.0.100:5588/tts/` sees a new back
right after the catalog build, once a player clicks **Refresh**. Tables reading from Pages
see it only after the push.

Checks:
- `python3 -m unittest tests.test_ttsdecks`: listing, order, file types, publishing.
- `lua tests/test_cactuar.lua`: the menu, and that only BackURL changes when a back is chosen.

Then load a deck in the game and look at the back.
