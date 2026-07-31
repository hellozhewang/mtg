# Commander Brackets `beta` (Oct 25)

**This is a communication tool to guide pregame conversations about game expectations and player intent.**

🟠 Casual Mindset ————————————————— 🔴 Competitive Mindset

| 1 | → | 2 | → | 3 | → | 4 | → | 5 |
|---|---|---|---|---|---|---|---|---|
| **Exhibition** | *The difference is* **THEME** | **Core** | *The difference is* **STAPLES** | **Upgraded** | *The difference is* **SPEED** | **Optimized** | *The difference is* **METAGAME** | **cEDH** |

---

## 1 · Exhibition

**PLAYERS EXPECT...**

- ...**decks** to prioritize a goal, theme, or idea over power.
- ...**rules** around card or commander legality to be flexible, if all players agree.
- ...**win conditions** to be highly thematic or substandard.
- ...**gameplay** to be an opportunity to show off their creations.
- ...to play **at least 9 turns** before anyone wins or loses.

**RESTRICTED BY THEME**

- **NO** Game Changers\*
- **NO** Mass Land Denial
- **NO** Chaining Extra Turns\*
- **NO** 2-Card Combos\*
  *Game-enders, lockouts or infinites*

> \*Exceptions can be made for highly thematic cards

---

## 2 · Core

**PLAYERS EXPECT...**

- ...**decks** to be mechanically focused with some cards chosen to maximize creativity and/or entertainment.
- ...**win conditions** to be incremental, telegraphed on the board, and disruptable.
- ...**gameplay** to be low pressure, proactive, and considerate, letting each deck showcase its plan.
- ...to play **at least 8 turns** before anyone wins or loses.

**NO** Game Changers
**NO** Mass Land Denial
**NO** Chaining Extra Turns
**NO** 2-Card Combos
*Game-enders, lockouts or infinites*

---

## 3 · Upgraded

**PLAYERS EXPECT...**

- ...**decks** to be powered up with strong synergy and high card quality. They can effectively disrupt opponents.
- ...**win conditions** that can be played from hand in one turn, usually because of steadily accrued resources.
- ...**gameplay** to feature many proactive and reactive plays.
- ...to play **at least 6 turns** before anyone wins or loses.

**0–3** Game Changers
**NO** Mass Land Denial
**NO** Chaining Extra Turns
**NO** 2-Card Combos (before turn 6)
*Game-enders, lockouts or infinites*

---

## 4 · Optimized

**PLAYERS EXPECT...**

- ...**decks** to be lethal, consistent, and fast, designed to take people down as fast as possible. They do not adhere to the cEDH metagame.
- ...**win conditions** to vary from archetype to archetype, but can end a game quickly and suddenly.
- ...**gameplay** to be explosive and powerful, featuring huge threats and efficient disruption to match.
- ...to play **at least 4 turns** before anyone wins or loses.

**NO DECK RESTRICTIONS**

---

## 5 · cEDH

**PLAYERS EXPECT...**

- ...**decks** that are meticulously designed to battle in the cEDH metagame, with the ability to win quickly or generate overwhelming resources; often built using existing cEDH knowledge, tools, and/or decklists.
- ...**win conditions** to be optimized for efficiency and consistency.
- ...**gameplay** to be intricate and advanced, with razor-thin margins for error; players prioritize victory over all else.
- ...games could end on **any turn**.

**NO DECK RESTRICTIONS**

---

## Quick reference

| | 1 Exhibition | 2 Core | 3 Upgraded | 4 Optimized | 5 cEDH |
|---|---|---|---|---|---|
| **Game Changers** | NO\* | NO | 0–3 | — | — |
| **Mass Land Denial** | NO | NO | NO | — | — |
| **Chaining Extra Turns** | NO\* | NO | NO | — | — |
| **2-Card Combos** | NO\* | NO | NO (before turn 6) | — | — |
| **Turns before a win/loss** | at least 9 | at least 8 | at least 6 | at least 4 | any turn |
| **Deck restrictions** | Restricted by theme | — | — | None | None |

2-Card Combos = game-enders, lockouts or infinites.
\*Exceptions can be made for highly thematic cards.

---

## Definitions

The table above says what is restricted. This section says what the restricted
categories actually **mean**, so no card judgement needs a web search.

### Game Changers

Defined by **Scryfall's `is:gamechanger`**. That query is the authoritative list,
not any article or blog post. Check it, never recall it:

```bash
./scripts/find_cards.py --gc-only
```

**The commander counts.** A Bracket 3 deck led by Grand Arbiter Augustin IV has
already spent one of its three slots before the 99 is built.

`validate_deck.py` checks this automatically off each card's `game_changer`
boolean, so never ask a human or another model to count them.

### Mass Land Denial

WotC's definition — cards that

> regularly **destroy, exile, bounce, keep lands tapped, or change what mana is
> produced by four or more lands per player** without replacing them.

Named examples: **Armageddon, Ruination, Sunder, Winter Orb, Blood Moon.**
Banned in Brackets 1–3. Note this is broader than land *destruction*: the
"keep lands tapped" and "change what mana is produced" clauses pull in whole
stax and prison staples that read as fair.

**Caught by it** — do not put these in a Bracket 3 deck:
Armageddon · Ravages of War · Ruination · Sunder · Obliterate ·
**Winter Orb** · **Static Orb** · **Stasis** · **Winter Moon** · Rising Waters ·
**Blood Moon** · Magus of the Moon · Contamination

**Not caught by it**, and the distinction that matters most:

- **"Enters tapped" is not "kept tapped."** A land that enters tapped untaps
  normally next turn, so it is delayed, not denied. Archon of Emeria, Thalia
  Heretic Cathar, Blind Obedience and Kismet are all fine.
- **Single-target land destruction is not mass.** Field of Ruin and Ghost
  Quarter hit one land and replace it. Four-or-more-per-player is the threshold.
- **Taxing lands is not denying them.** Ankh of Mishra punishes a land drop but
  does not stop, tap or change it.
- **Limiting land *plays* is not land denial.** Archon of Emeria's one-land-per-turn
  clause restricts a future play, not existing lands.

### Chaining Extra Turns

Taking repeated or looped extra turns — Time Warp plus a way to recur it, or any
Nexus-of-Fate-style engine. A single extra turn effect is fine; a deck built to
take them back to back is not. Banned in Brackets 1–3.

### 2-Card Combos

Two cards that together **end the game, lock the table out, or go infinite**.
Bracket 2 forbids them outright; Bracket 3 forbids ones that come together
"cheaply and in about the first six or so turns." Intent matters — a loop nobody
built toward that emerges mid-game is not a violation.

**Lockout counts, not just infinite kills.** Prison decks trip this most often:

- Knowledge Pool + any one-spell-per-turn effect (Rule of Law, Arcane
  Laboratory, Eidolon of Rhetoric, Archon of Emeria) — nobody casts anything
  again, ever. This is why Knowledge Pool stays out of a Bracket 3 prison deck.
- Knowledge Pool + Teferi, Mage of Zhalfir — same lock.
- Possibility Storm + Rule of Law — same lock.

Redundant stax pieces are **not** a combo. Sphere of Resistance plus Thorn of
Amethyst is just two taxes stacking; the table can still play.

---

## Banned in Commander

**83 cards.** A banned card makes a deck illegal in every bracket — this is
not a bracket restriction, it is the format's own list, and it overrides
everything below.

`validate_deck.py` enforces this automatically. It reads each card's own
`legalities.commander` from Scryfall rather than a list copied into this repo, so
it cannot go stale: Wizards updates the list a few times a year and Scryfall
reflects it the same day. The list here is for reading; the validator is the
check. Regenerate it with:

```bash
python3 -c "import sys;sys.path.insert(0,'scripts');from cardlib import ScryfallAPI;\
print('\n'.join(sorted(c['name'] for c in ScryfallAPI().search('banned:commander')[0])))"
```

Note `find_cards.py` cannot show you these — it always prepends `legal:commander`,
so `banned:commander` returns nothing through it. That is deliberate: the search
tool exists to find cards you may actually play.

### Banned on power level (38)

```
Ancestral Recall                              Balance                                       Black Lotus
Channel                                       Dockside Extortionist                         Emrakul, the Aeons Torn
Erayo, Soratami Ascendant // Erayo's Essence  Fastbond                                      Flash
Golos, Tireless Pilgrim                       Griselbrand                                   Hullbreacher
Iona, Shield of Emeria                        Jeweled Lotus                                 Karakas
Leovold, Emissary of Trest                    Library of Alexandria                         Mana Crypt
Mox Emerald                                   Mox Jet                                       Mox Pearl
Mox Ruby                                      Mox Sapphire                                  Nadu, Winged Wisdom
Paradox Engine                                Primeval Titan                                Prophet of Kruphix
Recurring Nightmare                           Rofellos, Llanowar Emissary                   Sundering Titan
Sylvan Primordial                             Time Vault                                    Time Walk
Tinker                                        Tolarian Academy                              Trade Secrets
Upheaval                                      Yawgmoth's Bargain
```

### Banned for other reasons (45)

Ante, conspiracy/draft-matters cards that do nothing in a normal game, dexterity
cards, and cards withdrawn for offensive art or text.

```
Adriana's Valor             Advantageous Proclamation   Amulet of Quoz
Assemble the Rank and Vile  Backup Plan                 Brago's Favor
Bronze Tablet               Chaos Orb                   Cleanse
Contract from Below         Crusade                     Darkpact
Demonic Attorney            Double Stroke               Echoing Boon
Emissary's Ploy             Falling Star                Hired Heist
Hold the Perimeter          Hymn of the Wilds           Immediate Action
Imprison                    Incendiary Dissent          Invoke Prejudice
Iterative Analysis          Jeweled Bird                Jihad
Limited Resources           Muzzio's Preparations       Natural Unity
Power Play                  Pradesh Gypsies             Rebirth
Secret Summoning            Secrets of Paradise         Sentinel Dispatch
Shahrazad                   Sovereign's Realm           Stone-Throwing Devils
Summoner's Bond             Tempest Efreet              Timmerian Fiends
Unexpected Potential        Weight Advantage            Worldknit
```
