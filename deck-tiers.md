# Power tiers

Every deck in the collection sits in one of eight tiers: **GOD, SS, S, A, B, C,
D, TRASH**, strongest first. The catalog's **Tiers** view groups decks this way,
and every deck name carries its tier mark.

**A tier is not a bracket.** The bracket folder is a rules ceiling: what the deck
is allowed to run. The tier is a judgment of what the finished list actually does
at a four-player table: how fast it wins, how reliably, and through how much
interaction. Two Bracket 3.5 decks can be tiers apart, and a Bracket 3 deck can
outrank a 3.5 one.

## The tiers

| Tier | What it looks like | Usual kill |
|---|---|---|
| **GOD** | cEDH. Full fast mana (moxen, Mana Vault, rituals), free counterspells, a deep tutor suite and compact wins, led by a recognised cEDH commander. Built for Bracket 5. | turns 1-4, through interaction |
| **SS** | Fringe cEDH. Uncapped Game Changers: fast mana (Chrome Mox, Mox Diamond, Mana Vault) plus 8 or more tutors aimed at redundant game-ending lines or a hard lock. Bracket 4 or 5. | turns 3-6 |
| **S** | The ceiling of a three-Game-Changer deck. The commander is a combo piece or a must-answer engine; several compact wins; four or more tutors that reach them. A cEDH commander's core combo kept inside the cap lands here. | turns 5-7 |
| **A** | Strong. A combo deck with less redundancy, fewer tutors or a slower shell, or a top engine deck without combos that still kills reliably. The table's archenemy. | turns 6-8 |
| **B** | Solid Bracket 3. A coherent plan with enough ramp, draw and answers, and a good commander, but no compact win. | turns 7-9 |
| **C** | Fair. Works, but slow, commander-dependent, top-heavy or light on interaction; folds to one sweeper or one removal spell on the commander. | turn 9 or later |
| **D** | Weak. Theme first, or aimed at one kind of opponent; easily disrupted and struggles against a table of B decks. | rarely on its own |
| **TRASH** | Does not work as built (core pieces missing, the plan cannot execute), or another deck here does the same job strictly better. Rebuild or delete it. | — |

A **compact win** is two cards, or the commander plus one card, that end the
game, go infinite or lock the table out (the same definition as the bracket
rules' 2-Card Combos).

## Placing a deck

Judge the list you shipped and its guide, not the commander's reputation and not
the folder it sits in.

1. **Find the compact wins.** List every two-card and commander-plus-one line,
   and note how many different pairs exist. Three-card lines count for less.
2. **Count the speed inputs.** Fast mana (0-1 mana rocks and rituals, Ancient
   Tomb, Mana Vault; mana dorks count for less), tutors that can fetch a win or
   its missing piece, and free interaction (Force of Will, Fierce Guardianship,
   Deflecting Swat and the like).
3. **Estimate the kill turn** on a good but not perfect draw, and ask what one
   removal spell on the commander does to that plan.
4. **Apply the ceilings.**
   - No compact win means **A at most**. Prison decks count their lock pieces
     as compact wins only when the lock actually stops the table.
   - **GOD** needs Bracket 5 construction: fast mana, free counterspells and
     compact wins together.
   - A deck capped at three Game Changers (Bracket 3 or 3.5) tops out at **S**.
     **SS** needs uncapped fast mana and many tutors behind redundant compact
     wins or a hard lock.
   - Fewer than about four tutors that reach the wins usually means **A**
     rather than S, however many combos the list holds.
   - Uncapped Game Changers do not lift a slow plan. A Bracket 4 deck whose
     wins take several turns of setup sits where its speed puts it.
   - A commander of 7 or more mana that the plan needs, with nothing to cheat it
     out, usually means **C** or lower unless the rest of the deck carries it.
5. **Compare with the anchors** below. Put the deck in the tier whose anchors it
   would trade evenly with: it should beat most of the tier beneath it and lose
   to most of the tier above.
6. **Save it.** Add `"Stem": "TIER"` to the map (below).

Re-check the tier whenever tuning adds or cuts combo pieces, tutors or fast
mana, when a deck changes bracket, or when its plan changes. Ordinary card swaps
do not need a re-check.

## Anchors

Comparison points from the current collection. These are examples, not the full
list; the maps hold every placement.

| Tier | Anchors |
|---|---|
| **GOD** | Kinnan-Combo |
| **SS** | CaptainSisay-Prison |
| **S** | Kinnan-Infinite, Urza-Combo, Najeela-Warriors, Krenko-Combo, Beamtown-Gifts, Gwenom-Drain |
| **A** | Esika-Superfriends, Edgar-Vampires, Torbran-Burn, Korvold-Sacrifice, Yuriko-Ninjas, Greasefang-Vehicles |
| **B** | Teysa-Aristocrats, Prosper-Treasure, Atraxa-Blink, Glarb-Topdeck, Gishath-Dinosaurs |
| **C** | Jace-Tokens, Feldon-Reanimator, Kozilek-Annihilator, MaelstromWanderer-Roulette, Saruman-Antistax |
| **D** | NicolBolas-Superfriends, Capitoline-Emblem |
| **TRASH** | none at present |

How the current placements were made (2026-10-03): every list and guide was
read, combos were cross-checked against Commander Spellbook, and an independent
Codex review tiered all 109 decks blind. Where the two disagreed, the rules above
decided it. Esika-Superfriends shows why a bracket is not a tier: it has fifteen
Game Changers but sits in A, because its planeswalker wins take turns to set up.

## Where tiers are stored

| Deck visibility | Tier map |
|---|---|
| Public | [`frontend/deck-tiers.json`](frontend/deck-tiers.json) |
| Private | `private/deck-tiers.json` (ignored; local only) |

The key is the exact filename stem; the value is one of `GOD`, `SS`, `S`, `A`,
`B`, `C`, `D`, `TRASH`. Keep one deck per line, keys sorted. As with themes, the
two maps are independent: never put a private deck in the public map.

There is no filename fallback. A deck with no entry shows as **Unrated** with a
"?" mark, `build_site.py` prints a warning naming it, and
`tests/test_deck_tiers.py` fails for any public deck missing from the map (or
any map entry whose deck no longer exists). A typo in a tier fails the build.

## The Discord builder

The bot's sandbox can read the map but cannot write it. It ends every new-deck
reply with one line, `Tier: <TIER> — <the cards or lines that put it there>`, and
a full-workspace maintainer saves that to `frontend/deck-tiers.json`, then
rebuilds the site. Until then the deck shows as Unrated.
