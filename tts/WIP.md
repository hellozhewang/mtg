# WIP: Cactuar table

Status notes for the table work. The README's "Tabletop Simulator table" section is the
lasting description; this file tracks what is in flight.

## Where things are (2026-10-18)

- Steam Workshop item: **https://steamcommunity.com/sharedfiles/filedetails/?id=3822623414**
  (private). The upload is still the first test build, which read decks from a LAN address.
- The current build is **MTG 6 player Cactuar Ver_v2**, in the owner's Tabletop Simulator
  Saves. It isn't uploaded yet. To update the Workshop item: load the save, then
  **Modding → Workshop Upload**, update item 3822623414.
- Deck data is live from GitHub Pages (`docs/tts/`). New or retuned decks need no upload.

## v2 (this round)

1. **Blank deck rows, fixed.** The panel listed 149 decks, but every row button was empty.
   Tabletop Simulator ignores `UI.setValue` on a `<Button>`: a button's label is its `text`
   attribute. The EDH precon browser mod (2782327534) does it the same way. Rows and filter
   buttons now use `UI.setAttribute(id, "text", ...)`. `tests/test_cactuar.lua` now fails on
   `setValue` against any Button id in `tts/cactuar.xml`; the old code trips it 96 times.
2. **Tiles on the table instead of the screen button.** There are two locked
   "Cactuar decks" tiles (`tts/cactuar_tile.lua`, picture `tts/cactuar-tile.jpg`), placed
   where the owner marked:

   | tile | side | position | notes |
   |---|---|---|---|
   | `c4c7a1` | south seats | x -48.2, z -24.5, rotY 180 | below the Card Importer |
   | `c4c7a2` | north seats | x 48.2, z 24.5, rotY 0 | above rikrassen's importer tile |

   A click calls `Global.call("czOpenFor", {color})`, which opens the clicker's own panel;
   a second click closes it.
3. The Workshop link is in the README.

## Check in-game (untested in Tabletop Simulator)

- The tiles: size (scale 2.2), position and facing. The whole-tile button is transparent
  with a hover tint, sized 1000x1000 like rikrassen's tile button.
- The rows show deck names, with tier colours in rich text.
- **Load into my seat**:
  - the library lands face down in the library zone and gets shuffled;
  - the commander goes on the Commander Zone, partners on both;
  - the tokens go beyond them.
- The user reported "nothing loads" with v1. That's probably the blank rows, which left
  nothing to pick, but loading itself has never run in-game.

## Open options

- **Self-updating table.** The tile would fetch its script from Pages, then run
  `self.setLuaScript` and `self.reload()` when the version changes, the way the Card
  Importer updates itself. It would add its panels to the Global UI (`UI.setXmlTable`,
  `onClick="<guid>/fn"`). After that, the Workshop item would only need uploading when
  objects move. Not built: every copy of the table would then run whatever is on Pages.
- Put the Workshop link on the catalog page too.
- Take a real in-game screenshot with the browser open for the Workshop page. The current
  screenshots are the base mod's.
