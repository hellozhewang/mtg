# Card backs

> **Drop pictures in the repo's `tts/backs/`, not `docs/tts/backs/`.** `docs/` is the
> catalog build's output: the build copies this README and the pictures there, and it
> deletes anything in `docs/` it didn't write.

Every picture in this folder is a card back players can choose in the Cactuar table's
deck browser (**Card back ▾**, above **Load into my seat**). The choice is per player and
applies to every card of the next deck they load: library, commanders and tokens.

To add one: put the picture here, run the catalog build and push. No table rebuild or
Workshop upload is needed, because the table reads the list from the published site.

## Image specs

| | |
|---|---|
| format | `.jpg`, `.jpeg` or `.png`. Nothing else is offered as a back; this README is published beside them as documentation. |
| shape | portrait, a Magic card's 63:88. **745 × 1040** is the reference size. Other shapes are stretched to fit. |
| size | keep it under ~500 KB. JPEG quality 85–90 is plenty; `cactuar.jpg` is about 130 KB. Every player downloads it. |
| corners | fill the whole rectangle: Tabletop Simulator rounds the card's corners itself. Leave about 25 px of border free of anything important. |
| file name | lowercase `a-z`, `0-9`, `-` or `_`, with no spaces (it becomes a URL). It must be unique by name, ignoring the extension. |
| label | the menu shows the file name without its extension, title-cased, with `-` and `_` as spaces: `dragon_fire.png` → "Dragon Fire". |
| reserved | don't name a file `standard.*`. `standard` is the built-in choice, Magic's own back from Scryfall, which is always listed first. |
| rights | the repo and the site are public. Only add art we made or may share. Don't copy Wizards of the Coast's card back in here; Standard already provides it. |

## Registering a back in Tabletop Simulator

There's nothing to register inside TTS: no Workshop upload, no table rebuild, and no
Custom Deck dialog. The table finds backs from the published deck list. So:

1. **Add the file** here, following the specs above.
2. **Build the catalog**: `python3 scripts/build_site.py`. It must list the back in
   `docs/tts/decks.json` under `backs`, and copy it to `docs/tts/backs/`.
3. **Publish**: commit and push. GitHub Pages serves it a minute or so later at
   `https://hellozhewang.github.io/mtg/tts/backs/<file>`. Check that URL opens the picture.
4. **In the game**: open the Cactuar browser (click a Cactuar tile) and press **Refresh**,
   because the browser keeps the deck list it fetched when it first opened. The new back is
   now in **Card back ▾**. Pick it, then **Load into my seat**.

Things that trip people up:
- **Decks already on the table keep their old back.** The back is applied as a deck spawns,
  so delete the deck and load it again.
- **Replacing a picture under the same name is fine.** TTS caches pictures by URL, so the
  build adds a content hash to each back's URL (`backs/<file>?v=<hash>`); a changed picture
  gets a new URL and is downloaded again.
- **The table must be one built from this repo** (`MTG 6 player Cactuar Ver_v12` or later,
  or the Workshop item once a v12+ save is uploaded). Older builds have no Card back menu.
- **Nothing appears and Refresh doesn't help:** the table reads from Pages, so the back
  isn't pushed yet, or Pages hasn't finished publishing.

## How it flows

1. `scripts/ttsdecks.py` (`back_files()`, `backs()`) lists this folder during
   `python3 scripts/build_site.py`. It copies each picture to `docs/tts/backs/` and adds
   it to `docs/tts/decks.json` under `backs`: Standard first, with an absolute `url`; then
   these files by name, with a `file` relative to `decks.json`.
2. Pushing publishes them on GitHub Pages under `https://hellozhewang.github.io/mtg/tts/backs/`.
3. In the table (`tts/cactuar.lua`), `czBackJSON` swaps every `"BackURL"` string in the
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
