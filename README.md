# MTG Commander deckbuilding workspace

A collection of Magic: The Gathering Commander decks, plus the tooling that
builds and checks them — and a Discord bot that can do it
from chat.

**How it works.** Decks are plain `.txt` files, one card per line, importable by
any client that reads a decklist. Around them sit a few Python scripts with no
dependencies beyond the standard library:

| | |
|---|---|
| [`new_deck.py`](scripts/new_deck.py) | seed a decklist from EDHREC's aggregate for a commander |
| [`find_cards.py`](scripts/find_cards.py) | search Scryfall, or look cards up by name |
| [`find_inspiration.py`](scripts/find_inspiration.py) | what other pilots of a commander run that yours doesn't |
| [`validate_deck.py`](scripts/validate_deck.py) | 100 cards, real names, colour identity, bracket legality, singleton, and that Tabletop Simulator's importer loads it |
| [`ttsimport.py`](scripts/ttsimport.py) | ask the Tabletop Simulator deck importer what a pasted list loads as |

Every deck targets a **Commander bracket** and has to obey its restrictions, which
is what most of this document is about. The bracket rules themselves live in
[commander-brackets-and-rules.md](commander-brackets-and-rules.md).

**Browse the decks:** [public/](public/), one folder per owner — or in Discord
via `/deck-list`, `/deck-print` and `/deck-random`.

**Every deck belongs to someone.** Decks live in `public/<user>/<Bracket>/`, and
the folder is the owner: their name is the deck's byline, and the start of its
page URL. When someone asks the Discord builder for a deck, it works in that
person's folder and nowhere else, so its sandbox can only ever write their own
decks. Two people can each have a deck for the same commander; the builder only
checks for duplicates within the asker's own folder.

```bash
./scripts/new_deck.py "Queen Marchesa" -o public/zzwang/Bracket3/Marchesa-Pillowfort.txt
./scripts/validate_deck.py public/zzwang/Bracket3/Marchesa-Pillowfort.txt
./scripts/build_site.py                                      # refresh the catalog
```

A deck is not real until `validate_deck.py` passes it: exactly 100 cards, every
name resolving on Scryfall, one colour identity (two, for a partner pair), the
bracket's Game Changer cap, singleton, format legality, and no mass land denial
below Bracket 4.

The rest of this file is the deckbuilding guide: the rules a deck must follow, the
file format, what each tool does, and the order to use them in.

---

## Core rules

**Catalog placement is part of finishing a deck.** Follow
[Placing decks in the Commander catalog](deck-catalog-strategies.md) when creating
a deck or changing its plan: choose its primary category from the fixed set, add
supported secondary categories, and update the assignment map. Brackets remain the deck folders; categories are metadata, not
another directory hierarchy.

### 1. Follow the house rules

Decks are Bracket 3 unless they sit in a `Bracket4/` or `Bracket5/` folder. **Our
hard rules are only the ones a script can check every time**, and
`validate_deck.py` checks both:

- **0 to 3 Game Changers** (Bracket 4 and 5: uncapped).
- **No mass land denial**: none of the cards named in
  [commander-brackets-and-rules.md](commander-brackets-and-rules.md) (Bracket 4
  and 5: allowed).

Everything else in the official bracket text is about how a game is played, not
what a list may contain, so it is not a deckbuilding rule here:

- **Two-card combos are allowed**, infinite or lock. The table expectation is that
  nobody uses one before turn 6, and a deck's guide says so when it has one.
  `Urza-Combo` is the clearest case of why: Urza, Lord High Artificer taps
  artifacts for mana, so Basalt Monolith with Power Artifact, and Isochron Scepter
  with Dramatic Reversal, are what the commander is *for*.
- **Extra-turn effects are allowed**, chained or not.

There is no Bracket 3.5 any more (removed 2026-10-18). It existed to keep combos
that the official Bracket 3 text discourages; under these rules those decks are
simply Bracket 3, and they moved there. The four-Game-Changer exception went with it.

Never silently exceed the cap. If a requested card would break it, say so and
offer the trade — e.g. adding Cyclonic Rift to a deck already at 3 Game Changers
means cutting one of the existing three. The same goes for a card on the mass
land denial list: say it is out, and why.

### 2. Use the most powerful cards in the bracket — including the newest ones

Within the bracket's limits, take the strongest option available. **Actively favour
recent printings**: power creep is real, and a card from the last few sets is often
strictly better than the staple it replaces. Do not default to a 2015 staple out of
habit.

This is why **web search is mandatory** when researching cards. Training data goes
stale, new sets land constantly, and the Game Changers and ban lists both change.
Check what's current before recommending anything.

### 3. Ignore card prices

**Price is not a constraint. Build for power, not budget.** Underground Sea,
Gaea's Cradle, Moat, Mishra's Workshop, The Tabernacle at Pendrell Vale, full
original dual and fetch suites — all fair game. Never substitute a worse card for
budget reasons, and never mention price as a downside.

---

## Goblin decks: keep the Recruiter package together

**Owner preference (2026-10-10): every Goblin deck running Goblin Recruiter must
also include Muxus, Goblin Grandee and Goblin Ringleader**, unless the owner
explicitly requests an exception. Muxus as the commander already satisfies its
slot; never add a second copy to the 99. Keep considering Krenko, Mob Boss as a
supporting engine when another legend is the commander.

Evaluate Ringleader and Muxus as payoffs for a deliberately arranged Recruiter
pile, even when the deck has too few Goblins for reliable blind reveals. Keep
enough mana and protection to execute it. The guide should give both a four-card
Ringleader refill and a six-creature Muxus deployment using cards actually in that
list, including a sacrifice outlet if its combo requires one. Account for the
draw needed to reach a payoff in the library, intervening shuffles, and Muxus's
restriction to Goblin creature cards with mana value five or less.

## Assumed play context

**Games are 4-player free-for-all (1v1v1v1)** unless stated otherwise. This changes
evaluation a lot:

- Effects reading "each opponent" scale 3×. Drains and symmetric taxes are premium.
- Pure voltron is weak — 21 commander damage × 3 opponents = 63.
- One-for-one removal trades poorly; prefer scalable answers and sweepers.
- Board wipes matter more; three opponents deploy three boards.
- Being the archenemy is a real cost. Lock pieces draw the whole table onto you.

---

## Bracket quick reference

What this repo enforces, against the official guidance it comes from:

| | Bracket 3 (ours) | Bracket 4 | Bracket 5 | Official Bracket 3 |
|---|---|---|---|---|
| Game Changers | **0-3, enforced** | ∞ | ∞ | ≤3 |
| Mass Land Denial | **no, enforced** | yes | yes | no |
| Chaining Extra Turns | allowed | yes | yes | no |
| 2-Card Combos | allowed; use from turn 6 | yes | yes | not before turn 6 |
| Turns before a win | 6+ | 4+ | any | 6+ |

Brackets 1 and 2 are not used here. The full official text is in
[commander-brackets-and-rules.md](commander-brackets-and-rules.md).

**Game Changers are defined by Scryfall's `is:gamechanger` query** — that is the
authoritative source, not any blog post. Currently **53 cards, last updated
February 9 2026**. Re-check it; it changes.

```bash
curl -s -H 'User-Agent: MtgDeckTuner/1.0' -H 'Accept: application/json' \
  'https://api.scryfall.com/cards/search?q=is%3Agamechanger&unique=cards' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["total_cards"])'
```

### Spending the 3 Game Changer slots well

The 3→4 boundary is **speed**. Fast mana and tutors are what buy speed, so a
Bracket 3 deck that spends its slots on Ancient Tomb, Mana Vault and Demonic Tutor
is technically legal but plays like Bracket 4 and feels bad.

Prefer **grindy engines**: Rhystic Study, Smothering Tithe, Necropotence,
Consecrated Sphinx, Seedborn Muse, Orcish Bowmasters, Aura Shards. These accrue
advantage over the 6+ turns the bracket expects.

The exception is a deck that physically cannot function without ramp — the
`{8}{C}{C}` Kozilek list spends all three on fast mana, and that is noted in its
own file as the reason it sits closest to Bracket 4.

---

## Deck file naming

**`<Commander>-<Theme>.txt`**, inside a folder named for the bracket, inside the
owner's folder.

```
zzwang/Bracket3/Zur-Voltron.txt
zzwang/Bracket3/Lathril-Elves.txt
zzwang/Bracket3/Krenko-Combo.txt
ratdos/Bracket3/Obeka-Upkeep.txt
digitalstealth/Bracket3/Shorikai-Prison.txt
```

The commander part is a short recognisable form of the name — first word usually
(`Zur`, `Lathril`, `Yuriko`), or the words closed up when one word is ambiguous
(`GrandArbiter`, not `Grand-Arbiter`). The theme is one word for what the deck
actually does: `Voltron`, `Elves`, `Enchantress`, `Ninjas`, `Attacks`, `Treasure`,
`Lands`, `Annihilator`, `Drain`, `Prison`, `Combo`.

**Exactly one hyphen**, so everything after it is unambiguously the theme. That
matters because `commands.py` resolves `!deck <name>` by folding away case and
punctuation — `!deck zurvoltron`, `!deck Zur-Voltron` and `!deck zur` all hit the
same file. Names only need to be unique per owner. When several owners' decks
match, the asker's own wins, and `!deck ratdos/obeka` names an owner outright.
Rename the file if a deck's plan changes; the name is documentation.

## Deck file format

One `.txt` per deck, importable directly by a client that reads decklists.

```
1 Zur the Enchanter        <- line 1 is ALWAYS the commander
1 Academy Rector
1 All That Glitters
...
16 Swamp
```

- `<count> <exact card name>`, one per line
- Commander on line 1, **no blank line** after it
- **Two commanders** (Partner, Partner with, Partner—Friends forever and other
  `Partner—` qualities, Choose a Background, Doctor's companion): both go first,
  on lines 1 and 2. Line 2 counts as a commander only when it is a legal partner
  for line 1, so the validator and catalog never guess from the rest of the list
  (a deck can run other partner-capable cards in its 98).
- Alphabetised after the commander line(s)
- **No tokens** — they are generated automatically, and token names don't resolve
  against a card database
- Double-faced cards use the **front face only** (`Agadeem's Awakening`, not
  `Agadeem's Awakening // Agadeem, the Undercrypt`)
- Exactly **100 cards** counting the commander
- Optionally, a **pinned printing** at the end of a line: `1 Sol Ring (SLD) 249`.
  It chooses the art and nothing else. See [Pinning art](#pinning-art) below.
- Cards whose Oracle text permits any number of copies, such as **Rat Colony**
  and **Relentless Rats**, may repeat. Write them as one quantity line, such as
  `25 Rat Colony`; color identity and format legality still apply.

---

## Tools

All in [scripts/](scripts/). No dependencies beyond Python 3 stdlib.

### Finding cards — `scripts/find_cards.py`

Wraps Scryfall's search API with this repo's rules baked in: `legal:commander` is
always applied, results are **ordered by EDHREC rank** (the best proxy for "most
powerful / most played", so the top of the list is what rule 2 wants), Game
Changers are flagged `[GC]` so you can count them against the cap, and price is
never shown.

```bash
# strong cheap enchantments Zur can tutor -- colour identity derived from the commander
./scripts/find_cards.py "t:enchantment mv<=3" --commander "Zur the Enchanter"

# power-creep check: genuinely new Mardu attack-triggers, no Game Changers
./scripts/find_cards.py "o:'whenever' o:'attacks'" --ci brw --since 2025 --no-gc

# the current Game Changers list
./scripts/find_cards.py --gc-only

# look cards up BY NAME rather than searching — bulk, cache-first
./scripts/find_cards.py --names "Combat Celebrant" "Winota, Joiner of Forces" --text
```

**`--names` is a different operation from search** and worth knowing about: exact
names, no ranking, cache-first instead of always-live, and it takes as many names as
you like in one call (chunked at 75 per request). Use it to check what a card
actually *does* before crediting it toward a deck's theme. It lives here, not in
`cache.py`, because inspecting a card is a card question — `cache.py` is
administration only.

It prints everything Scryfall knows that matters for deckbuilding: mana cost, mv,
type, P/T or loyalty or defense, colour identity *and* colours when they differ,
`produced_mana`, keywords, rarity/set/printing, `edhrec_rank`, Reserved List status,
related tokens, and full oracle text. `--json` dumps the raw 64-field object.

Two of those fields are there for correctness, not completeness:

- **Commander legality is printed, and flagged when it isn't `legal`.** `--names`
  does *not* apply the `legal:commander` filter that searches do, so `Mana Crypt`
  resolves perfectly happily — and prints `banned   <-- NOT LEGAL IN COMMANDER`.
- **Every card face is shown.** The compact search renderer prints only face 0,
  which silently hides the back of every modal DFC — precisely the face that
  determines whether it's a land.

Note the date is labelled **`printing`**, not "first printed", and tagged
`(a reprint)` where applicable: `released_at` belongs to whichever printing is
cached, so `Sol Ring` reports 2026 off a Marvel Commander reprint despite being a
1993 card. For genuine print dates use `--since`, which adds `not:reprint`.

`-n`, `--max` and `--limit` are all accepted as synonyms here and in
`find_inspiration.py`, deliberately: an agent that learns one tool's spelling will
try it on the other, and a failed call over a synonym is a self-inflicted wound.

Useful query syntax (full reference: <https://scryfall.com/docs/syntax>):

| Fragment | Meaning |
|---|---|
| `id<=wub` | colour identity fits Esper |
| `t:enchantment` / `t:elf` | type or subtype |
| `mv<=3` | mana value 3 or less |
| `o:"whenever ~ attacks"` | oracle text (`~` = the card's own name) |
| `is:gamechanger` | on the Game Changers list |
| `not:reprint` | first printings only |
| `f:commander` / `banned:commander` | legality |

**Gotcha this tool handles for you:** `year>=2025` matches *any printing*, so a
2010 card reprinted last year pollutes a power-creep search — Sun Titan and
Goldspan Dragon both slipped through that way. `--since` therefore adds
`not:reprint` automatically. Use `--include-reprints` to opt out.

### Seeding a deck — `scripts/new_deck.py`

Fetches EDHREC's aggregate deck for a commander so you start from the consensus
shell instead of typing 99 lines from memory.

```bash
./scripts/new_deck.py "Queen Marchesa"                       # preview to stdout
./scripts/new_deck.py "Queen Marchesa" -o public/zzwang/Bracket3/Marchesa-Pillowfort.txt
./scripts/new_deck.py "Queen Marchesa" --lands 38            # force a land count
./scripts/new_deck.py "Queen Marchesa" --flavour average     # the popular build
```

**It defaults to EDHREC's `expensive` cut, on purpose.** The plain average is
dragged down by what players can afford, and rule 3 says price is irrelevant here —
so the expensive cut is strictly closer to what this repo wants. It's where Chrome
Mox, Lotus Petal and the fetch suite live.

EDHREC omits basic lands from its averages, so a fetched list arrives at 79–99
cards. The script counts the nonbasic lands via Scryfall type lines, then pads
basics in the commander's colours to reach either 100 or your `--lands` target, and
reports what it did. It also prints the Game Changer count up front — a seeded list
routinely lands at 5, over the Bracket 3 cap, and you want to know before you tune:

```
note      : added 8 basics (filling to 100): 3 Swamp, 3 Mountain, 2 Plains
note      : 26 nonbasic + 8 basic = 34 lands
game chg  : 5 — Demonic Tutor, Enlightened Tutor, Farewell, Smothering Tithe, Teferi's Protection
            Bracket 3 allows 3. Cut 2.
```

### Inspiration and gaps — `scripts/find_inspiration.py`

Diffs a decklist against what other pilots of that commander run.

```bash
./scripts/find_inspiration.py public/zzwang/Bracket3/Sythis-Enchantress.txt
./scripts/find_inspiration.py public/zzwang/Bracket3/Zur-Voltron.txt --new     # EDHREC's New Cards section
./scripts/find_inspiration.py public/zzwang/Bracket3/Zur-Voltron.txt --trending # rising adoption, any age
./scripts/find_inspiration.py public/zzwang/Bracket3/GrandArbiter-Prison.txt --mine
./scripts/find_inspiration.py --commander "Queen Marchesa"              # no deck yet
```

Two numbers per card, and **they are not the same thing**:

| | meaning |
|---|---|
| `played` | fraction of that commander's decks running it. The useful one. |
| `synergy` | `played` minus the card's rate across every deck that could legally play it. Measures how *characteristic* the card is of this commander — **not** how strong. `Sol Ring` scores ~0 everywhere. |

So `Jukai Naturalist` at 77% / +0.65 is a card nearly every Sythis pilot runs and
nearly nobody else does: a real omission. A land at 44% / +0.07 is just colour
fixing that happens to be legal.

**Three biases, all of which cut against rule 2.** Know them before acting on
output:

1. **It regresses to the mean.** The aggregate is a casual average, so optimising
   toward it makes a deck *more typical*. It's a checklist for things you forgot,
   not a target.
2. **It's price-biased and this repo isn't.** Inclusion reflects what people can
   afford, so EDHREC systematically under-recommends `Moat`, `The Tabernacle at
   Pendrell Vale` and the original duals. It will never tell you to run them.
3. **It lags power creep.** A card needs months of uploads to rank, which is what
   `--new` is for — EDHREC's New Cards section only.

`--mine` inverts the question: what does your deck run that EDHREC never mentions
for this commander? A high count there isn't a warning, it's the measure of how far
the deck has been tuned away from average. `GrandArbiter-Prison` sits at 21.

Game Changers are flagged `[GC]` so the bracket cap is visible before you add
anything.

### What's popular right now — `scripts/find_inspiration.py --top`

Every other EDHREC call starts from a commander you already have in mind. This one
does not — it ranks the most-built commanders by deck count, which is the question
to ask when picking what to build next.

```bash
./scripts/find_inspiration.py --top            # past week (default)
./scripts/find_inspiration.py --top month
./scripts/find_inspiration.py --top year -n 20 # EDHREC calls this "Past 2 Years"
```

```
Past Week — most-built commanders

  #     decks   commander
  1     1,919   Y'shtola, Night's Blessed
  2     1,464   Doctor Doom, King of Latveria
  3     1,396   Hearthhull, the Worldseed
```

The windows disagree, and that is the useful part: `year` is dominated by
accumulated volume (The Ur-Dragon, Edgar Markov), while `week` shows what people
are building *today*. A commander high in both is genuinely rising rather than
coasting.

### Pinning art

A card usually exists in many printings with different pictures: Sol Ring has
more than seventy. A line that ends with a printing pins one of them:

```
1 Sol Ring (SLD) 249          <- that exact printing
1 Sol Ring (CMM)              <- any printing from that set
1 Sol Ring                    <- no pin: whatever the importer defaults to
```

The set code goes in parentheses, then the collector number. This is the form
Arena and Moxfield export. A pin never changes the card: every tool here reads
the line as `Sol Ring`, so legality, colour identity and the Game Changer count
are unaffected.

**Where a pin shows up**

- **Tabletop Simulator.** Paste the list (`/deck-print`, or *Copy decklist* on the
  deck's page) into the table's importer and each pinned card loads as that
  printing.
- **The catalog.** The deck's page, its gallery and its tile show the pinned
  picture. Other decks running the same card keep their own art.

**Finding the set code and number.** On a card's Scryfall page, open *Prints* and
pick the one you want; its address ends in the two values, e.g.
`scryfall.com/card/sld/249/sol-ring` is `(SLD) 249`. Collector numbers are not
always plain numbers (`796★`, `52s`, `MH2-279`); copy them exactly.

**What the importer does with a line** (measured against its server):

- The quantity in front is required. `Sol Ring (SLD) 249` with no `1` is read as
  one long card name and fails with "failed to find card".
- Set codes are case-insensitive. `1 [CMM] Sol Ring` also picks a set.
  `[set:number]` is another importer's syntax and is rejected.
- **A wrong pin is not an error in the game.** A set the card was never printed
  in, or a number that belongs to another card, silently loads different art.

That last point is why `validate_deck.py` checks pins twice: the printing must
exist and be that card (rule 7 below), and the importer must hand back exactly
that printing when sent the list (rule 8).

**How the art in these decks was chosen.** One artwork per card, in this order:

1. A deck built on another universe (Final Fantasy, Marvel, Doctor Who, ...)
   takes that universe's printing wherever a card has one.
2. Otherwise art that shows the deck's own subject: its tribe, its commander,
   its plan.
3. Otherwise art from the commander's home plane or set, when that look is
   distinct.
4. Otherwise the classic picture, the illustration printed most often in ordinary
   sets. Never a crossover or joke printing that clashes with the deck.

The chosen picture is pinned in its plainest printing (no promo stamp, ordinary
frame) unless the frame is the point, such as a wanted poster or a newspaper
front page. Only nonland cards with two or more artworks are pinned; lands are
left alone. When a deck is retuned, keep the pins on the lines that stay and
never carry a pin over to a different card.

### Validating — `scripts/validate_deck.py`

**Required before calling any deck done.** Checks six rules, then two things
about how the list loads in Tabletop Simulator:

1. Exactly **100 cards** including the commander
2. Every name **resolves on Scryfall** (catches typos that would fail import)
3. Every card is **legal in Commander** — the 83 banned cards fail the deck
4. Every card is inside the commanders' **colour identity**: line 1's, or
   the union of a partner pair on lines 1 and 2. A partner left among the 98
   gets a hint to move it to line 2
5. **Game Changer count** within the bracket cap (inferred from folder name)
6. **Singleton** — nonbasic duplicates require the card's own Oracle permission
   for unlimited copies; no repeated lines
7. Every **pinned printing** exists and is that card. A wrong pin does not error
   in Tabletop Simulator, it silently loads other art, so it is an error here.
8. **The Tabletop Simulator importer loads the whole deck.** Once 1–7 pass, the
   list is checked against the importer the table uses (rikrassen's, via
   [`ttsimport.py`](scripts/ttsimport.py)): no "failed to find card", all 100
   cards returned, and each pin loaded as the printing asked for. The line
   `TTS import 100/100 cards, 52/52 pinned printings load` reports it.

   The importer is someone's free service, so it is asked as little as possible.
   **Every card line that loaded is remembered for 30 days** (in
   `.cache/tts-import-cards.json`), and only lines not yet known to load are
   sent. The note says which happened: `(all known good, importer not asked)`
   for a deck with nothing new, `(asked the importer about 3)` when three cards
   were new or changed. A pinned line is remembered only once it came back as
   exactly that printing, and a line that failed is never remembered, so it is
   asked again every time. If the importer cannot be reached and something
   still needs asking, the deck passes anyway and the line says it was not
   checked. `--recheck-import` asks about every card again; `--no-import` (or
   `MTG_NO_IMPORT=1`) skips the step.

Legality is read from each card's own `legalities.commander`, not from a list
copied into this repo, so it tracks Wizards' updates the day Scryfall does. The
readable list is in
[commander-brackets-and-rules.md](commander-brackets-and-rules.md).

```bash
./scripts/validate_deck.py                  # every deck in public/
./scripts/validate_deck.py public/ratdos    # one owner's decks
./scripts/validate_deck.py --max-gc 0 ...   # override the cap
```

Real bugs this caught: `Sunbaked Canyon` is R/W and was illegal in a Jund deck;
`Sling-Gang Lieutenant` is black and was illegal in mono-red Krenko. Both would
have imported as 99-card decks with a silently missing card.

The legality check was added after noticing the validator had no opinion at all
about banned cards — a deck with `Mana Crypt` or `Dockside Extortionist` passed
every check and was simply illegal.

### Publishing the catalog — `scripts/build_site.py`

Renders every deck into a browsable site at
**<https://hellozhewang.github.io/mtg/>** — a menu of decks, then per-deck pages
with the list grouped by card type, a mana curve, hover-to-preview card images, a
click-to-enlarge view (with a flip button for double-faced cards), a gallery mode
and a copy-the-decklist button. The **Random** button in the top bar of every
page picks a deck at random, copies its decklist to the clipboard, and opens its
page with a note saying so. It works over HTTPS, `localhost`, and plain `http` on
the local network; from a `file://` page the note offers a one-click copy instead. Every deck shows its
owner, the folder it lives in; the catalog search matches those usernames, so
typing an owner filters the deck cards the same way typing a commander does.

Deck pages live at `<owner>/<Bracket>/<Deck>.html`. Until 2026-10-18 they were
`<Bracket>/<Deck>.html` (and the owner's then-private decks
`private/<Bracket>/<Deck>.html`); [frontend/redirects.json](frontend/redirects.json)
maps each old path to its deck's new one, and the build writes a tiny redirect
page at every old path, so links already shared keep working.

Every deck shows when it was **added**, and once it has been edited, when it was
**updated**: the last change to its list or its guide, by anyone. Nothing has to
remember to set it. A committed edit dates from its commit; an uncommitted one
from the file's own modified time, so the bot's autopush (which builds before it
commits) publishes the new date along with the edit. Adding a deck is not an
edit, and edits within an hour of a deck first appearing count as building it.

The catalog initially opens in **List**, with decks under individually collapsible
brackets. Brackets start open; click their label to collapse or expand them.
Your browser remembers the chosen view, layout, and collapsed sections when you return.
Switch to **Categories** for seven fixed, collapsible categories, each with
bracket subsections: Aggro & Voltron, Tokens & Aristocrats, Combo, Stax &
Control, Graveyard, Spells & Burn, and Value & Ramp. Each is defined by how the
deck wins. Other Strategies is the catch-all for a plan that fits none of them. Rows / Tiles controls layout separately. Each deck appears once, with
secondary category tags and filters in every view.
See the [placement guide](deck-catalog-strategies.md) for the definitions,
assignment rules, and the metadata locations.

Switch to **Tiers** to rank the collection by power: GOD, SS, S, A, B, C, D
and TRASH, strongest first. Every deck name carries its tier mark in all three
views, and the search box finds a tier by name (`s tier`, `god tier`). A tier is
not a bracket: the bracket is what a deck may run, the tier is how hard the
finished list hits. [deck-tiers.md](deck-tiers.md) has the rubric, the anchor
decks for each tier and how to place a new deck.

```bash
./scripts/build_site.py              # rebuild docs/ from public/ -- PUBLISHED
./scripts/build_site.py --check      # verify TTS images and docs/, write nothing
./scripts/build_site.py --out /tmp/x # build elsewhere to look before publishing
```

To see a build before it is pushed, or from another device on your network, run:

```bash
./scripts/start_private_server.py
```

It serves the generated `docs/` catalog at **http://localhost:5588/**, with one
difference from the published site: its home page is the local index, which
adds a **Goblins** section mirroring every Goblin deck. That category is for the
owner alone and is never published. The server listens on `0.0.0.0:5588`, so
other devices on your local network can use
`http://<server-ip>:5588/`. On macOS it installs and bootstraps a `launchd`
`LaunchAgent` (`~/Library/LaunchAgents/com.cholo.mtg-catalog.plist` with
`RunAtLoad` and `KeepAlive`), so it starts automatically on login/boot and
restarts if it exits; pass `--stop` to unload it. Repeated starts reuse an
existing server serving the same catalog, and an unrelated service on port 5588
is left alone. Logs go to `logs/catalog-5588.log`. Run `build_site.py` after
deck changes; the server serves the updated files without restarting.

Data comes from the decks; **markup, CSS and JS come from `frontend/`**, so a
design change never means editing Python. The templating is two mechanisms and no
dependency: `{{TOKEN}}` substitution, and `<template data-part="tile">` fragments
that live next to the page repeating them.

**The output is deliberately deterministic** — everything sorted, no clock read
anywhere. `bot.py` regenerates the site after every model turn and commits what
changed, so a build timestamp would mean an empty commit on every Discord message.

Authorship is the folder. A deck in `public/ratdos/` is ratdos's, because the
builder only ever writes in the folder of whoever asked, and nothing else records
it. Until 2026-10-18 the bot instead kept a database of who requested each deck
(`bot/.deck-metadata.db`, now retired and never read); the move into owner
folders used it to put each deck where it belonged.

Card images are split by size, because a public git repo keeps every version of a
binary forever:

| | source | size | why |
|---|---|---|---|
| gallery grid, catalog tiles | committed to `docs/img/` | 7.7 MB total | same-origin and instant; the page as it first appears makes no external request |
| hover preview, click-to-enlarge | `cards.scryfall.io` | 0 MB | the same 818 cards at readable size would be **78 MB** in the repo |

Either way the bytes are cached in SQLite, so deleting `docs/` and rebuilding from
scratch downloads nothing.

### Caching — `scripts/cache.py`

A SQLite cache sits under every tool. Lookups hit the DB first; only missing or
stale (>30 day) names go to Scryfall, batched 75 at a time. Validating all ten
decks went from ~40s and 14 API round-trips to **0.06s and zero calls**.

`find_cards.py` **banks every card it finds**. Search already returns complete card
objects, so discovering a card in a search makes it free to validate or look up
later — the cache fills itself as you browse.

**Search results themselves are deliberately not cached.** Only card objects are.
Card data is stable, but which cards *match a query* changes every set release, and
rule 2 says favour new printings — a stale query cache would silently hide exactly
the cards you are looking for.

**`cache.py` is not the cache.** The caching lives in `cardlib/db.py` and happens
automatically on every tool call — nothing needs invoking. This script only inspects
the result and forces a refetch:

```bash
./scripts/cache.py --stats             # both caches: what, how fresh, how big
./scripts/cache.py --warm public/Bracket3   # pre-fetch a folder's cards
# to inspect a card, use find_cards.py --names — that's a card question, not a cache one
./scripts/cache.py --clear pages       # drop EDHREC pages, KEEP the cards
./scripts/cache.py --clear             # wipe everything
```

`--clear` takes a target because the two caches have different lifetimes and very
different refill costs. Refreshing one EDHREC page should not throw away ~1000
cached cards that cost ~14 Scryfall round trips to rebuild:

| table | class | key | TTL | source |
|---|---|---|---|---|
| `cards` + `aliases` | `CardStore` | `oracle_id` | 30 days | Scryfall |
| `pages` | `PageStore` | URL | 24 hours | EDHREC |
| `pages` (`tts:image-check:v1:` prefix) | `PageStore` | exact image URL | validators kept 1 year; availability rechecked every build | TTS image hosts |
| `images` | `ImageStore` | URL | **never** | Scryfall image CDN |
| `toolcalls` | `ToolLogStore` | rowid | **never** | our own tools |

Each store owns only its own tables — `CardStore.clear()` deliberately does *not*
touch `pages`, and each reports its own `stats()`, which `cache.py` merges.

Images never expire because their URLs are **content-addressed**: a card image URL
ends in the printing's UUID plus a `?<version>` stamp that Scryfall changes when it
replaces a scan. A hit is therefore correct forever, and a replaced scan arrives as
a *different* URL via the refreshed card object rather than as stale bytes under the
old one.

Lives at `.cache/cards.db` (repo root, outside the workspace). Pass `--no-cache` to `validate_deck.py` to bypass it.

Two schema details worth knowing:

- Cards are keyed by **`oracle_id`**, not name — one card has many printings.
- **The name you query is not always the name Scryfall returns.** Ask for
  `Agadeem's Awakening` and you get `Agadeem's Awakening // Agadeem, the
  Undercrypt`. An `aliases` table maps query → card so front-face lookups keep
  working. Getting this wrong silently drops every MDFC from your stats.

## Building a deck, step by step

Each tool above does one job. This is the order they compose in, for a human or
Claude session working in an editor or terminal — the Discord bot follows the same
sequence without launching a separate reviewing agent (see `AGENTS.md` below).

1. **Seed the shell.** `new_deck.py "<commander>" -o public/<owner>/Bracket3/<file>.txt`
   gets you a real, importable 100 cards in one command instead of typing 99 lines
   from memory. Expect it to land 4-11 Game Changers, not 3 — it has no bracket
   awareness, it just composes EDHREC's most-played build.

2. **Cut to the cap.** The GC report tells you what to drop for the Bracket 3
   cap of 3, and `validate_deck.py` rejects any mass land denial named in
   `commander-brackets-and-rules.md` that the seed brought along. Those are the
   only two hard rules. Keep the combos; the guide says to use them from turn 6.
   A card that denies lands like the listed ones but is not on the list goes on
   the list, not quietly into or out of a deck.

3. **Tune for power creep.** `find_cards.py "<query>" --since 2025 --no-gc` for a
   specific mechanic you're hunting; `find_inspiration.py <deck> --new` or
   `--trending` for a lower-effort pass over what's already gaining traction with
   this commander. The seeded shell is a casual average by construction, so it's
   behind on new printings — this is where rule 2 actually happens.

4. **Gap check.** `find_inspiration.py <deck>` (no flags) — what other pilots run
   that you don't. Read `played`, not `synergy`: a card at 77% inclusion you're
   missing is probably an oversight, `synergy` only says how *characteristic* a
   card is of the commander. Treat the whole list as a checklist of forgotten
   cards, never a target — following it makes a deck more average, and it will
   never suggest `Moat` or `Tabernacle` because of EDHREC's price bias.

5. **Verify triggers, not vibes.** For every card you're counting toward a theme,
   read what it actually says (`find_cards.py --names "<card>" --text` is the
   fast path, and takes several names at once).
   This step exists because it was skipped once on this repo's own Azorius prison
   build — six cards were credited with "punish the opponent for casting a spell"
   and the real count was zero; every one of them triggered on something else
   (a land entering, an attack, a controller's own upkeep).

6. **Validate. This is the gate.**
   `./scripts/validate_deck.py <path>` — 100 cards, every name
   resolves, colour identity, the GC cap, singleton. A deck that hasn't passed
   this is not done.

7. **Write the guide.** Update the matching `.guide` to explain the finished
   deck's engines, actual wins, weaknesses, opening hands, and sequencing.

8. **Review catalog placement.** Follow [the placement guide](deck-catalog-strategies.md).
   Choose one primary category from the fixed set and any supported secondary
   categories, then save the
   ordered IDs in `frontend/deck-themes.json` under `<owner>/<Deck>`. A
   full-workspace publisher then
   rebuilds and checks the catalog. The Discord builder follows the guide's
   sandbox handoff instructions when it cannot write the mapping itself.

9. **Place it in a power tier.** Every deck gets one of GOD, SS, S, A, B, C, D
   or TRASH, following [deck-tiers.md](deck-tiers.md). Save it in
   `frontend/deck-tiers.json` under `<owner>/<Deck>`.
   A deck with no entry shows as Unrated, `build_site.py` warns about it, and
   the test suite fails for any deck left out. Re-check the tier when
   tuning adds or cuts combo pieces, tutors or fast mana.

10. **Independent second opinion, when appropriate.** `ask_codex.py`, with the validator's result stated as
   settled fact in the prompt so Codex doesn't re-derive it — never ask it to
   count Game Changers, that's a 10-minute web-search detour for something
   `validate_deck.py` answers in milliseconds. Ask only for what no script can
   decide: does the deck deliver the brief, can it actually win, which of your
   own symmetric stax pieces hurt you more than the table.

**The Discord bot also writes the guide, reviews catalog placement and names a
tier (its sandbox cannot save either map, so it hands both off). It does not run
the independent-review command in step 10.**
The bot's working session *is* an agent harness process (see
[The builder's harness](#the-builders-harness)). Having it invoke `ask_codex.py`
would start a nested agent run from inside its own turn, with no outside context
and minutes spent on a report nobody asked for. Step 9 is only meaningful when it comes
from a genuinely separate reviewing context, which the bot never has.

| step | who checks it | can a script verify it? |
|---|---|---|
| 100 cards, names resolve, colour identity, GC cap, singleton | `validate_deck.py` | yes |
| inclusion, synergy, new printings | `find_inspiration.py`, `find_cards.py` | yes |
| named mass land denial | `validate_deck.py` | yes |
| a combo's turn-6 note in the guide | you | no |
| does each card's trigger match the theme | you | no |
| catalog primary and secondary categories | you, against `deck-catalog-strategies.md` | fixed IDs and coverage of every deck; fit needs review |
| whether the deck can actually win | you, or `ask_codex.py` (human sessions only) | no |
| which symmetric stax hurts you more than the table | you, or `ask_codex.py` (human sessions only) | no |

**Steps 1, 3 and 4 are a floor, not a ceiling — do not stop at what they return.**
`new_deck.py` and `find_inspiration.py` surface what other pilots already built;
the actual request is often narrower and stranger than that, and the tools cannot
index a card nobody has tried yet. When a request needs a precise mechanic — "hurt
them for casting," "hurt them for attacking" — write a fresh `find_cards.py` query
for exactly that oracle text rather than settling for whatever the seeded list
already contains.

Case in point, from this repo: the `GrandArbiter-Prison` build needed a card that
punishes an opponent for the *act of casting*, in Azorius specifically. Neither
`new_deck.py`'s seed nor `find_inspiration.py`'s rankings had one, and `ask_codex.py`
came back recommending a colour change to get it. A hand-written query —
`o:"whenever an opponent casts" o:"sacrifices"` — turned up `Spelltithe Enforcer`
in the same colours, first try. Go looking; don't just rank what's already there.

---

## Tabletop Simulator table

**MTG 6 player Cactuar Ver** is the scripted 6-player table from the Workshop
("MTG 6 player table - scripted", 2293586471, by Oops I Baked a Pie) with a deck
browser added. Get it on the Steam Workshop:
**https://steamcommunity.com/sharedfiles/filedetails/?id=3822623414**

Two **Cactuar decks** tiles sit on the table, one beside each side's deck
importer. Clicking one opens the clicker's own browser, which
searches as you type, sorts (newest first by default, or tier or name) and offers filter menus
(bracket, tier, strategy, owner). A separate details panel shows the selected deck's
commander, strategy and stats; filtered counts also show the collection total.
The larger browser shows the selected commander's full card at readable size on the
right. Partner decks have arrows to switch commanders; double-faced commanders have
a **Flip** button. **Read guide** opens that deck's strategy guide inside the browser,
with the website's illustrated rows: card pictures beside explanations and picture
strips for combos and tutor chains. Hover a guide picture to read that card on the
right; moving away restores the commander. **Back to decks** returns to the list.
Decks without a guide show **No guide**. Previews use the deck's pinned printing.
Commander faces come from the catalog; full guide content and pictures load only
when **Read guide** is clicked. Recently viewed pictures are cached for faster switching.
**Load into my seat** puts the chosen deck in
that player's seat: the library face down and shuffled in their library zone,
the commander (or both partners) on their Commander Zones, the tokens beside them.
Everything the table already did is untouched.

**Tournament** mode (a button beside Refresh, per player) narrows the browser to a curated
pool of 24 honest, fair Bracket 3 decks with variety, listed in
[tts/tournament.json](tts/tournament.json) and tagged *Tournament* in the catalog. It offers:
- **All pick:** any pool deck.
- **Draft:** 5 random pool decks; pick one.
- **Random:** one pool deck.

Nothing is restricted: redraws and rerolls are allowed. Instead, everything a player does
in Tournament mode is printed to chat with their name, seat and the time.

The table also shows each seat's **total turn time** for the game under its turn timer
(the "Who goes first?" roll resets it). An **announcer** mocks a turn that reaches 5 and
then 10 minutes ([tts/cactuar_turns.lua](tts/cactuar_turns.lua); chat `announcer off`).
Turn changes after the game starts also play `change-turn.wav` for everyone through
the shared Music Player. TTS's native incoming-player ping remains separate.
`announcer off` mutes custom turn-change and slow-turn clips.
Same-seat turn events play the clip too. Native End Turn can emit no Lua event
when testing alone; chat `turn sound test` tests the clip without advancing a turn.

The shared **FF14 soundtrack** loops Prelude/Discoveries until the cannon fires.
**Ultima** loops only during a player's turn while they have **10+ battlefield
artifacts**, pausing and resuming the same track between qualifying turns. Library,
exile, graveyard and commander columns do not count. Ultima stays loaded while
paused, so custom voice clips are skipped to preserve its position; native beeps
and text alerts still work. Chat `music off` / `music on` controls the soundtrack.

**Inspect contents alphabetically:** right-click a deck or bag and choose **Inspect**.
A private, narrow window shows four scrolling columns and a search bar, using the live
container's names and images independently of our deck catalog. Browsing never reveals
positions or changes the container's order; membership changes refresh automatically.
Search covers the full stored name, card type, description/rules text, stats, tags and
alternate faces, ignoring case and common accents. Click **`.*`** beside the search
field to enable **Regex**, then use patterns such as `creature|artifact`, `draw.*card`
or `\belf\b`. Click it again for plain text. Groups, character classes, repetitions,
line anchors and word boundaries are supported; lookarounds and backreferences are
not. Invalid or overly complex patterns show an error and can be corrected in place.
Search uses the text stored on the imported objects; it cannot read words from an
image when an importer omitted that metadata.
Hover over a thumbnail to enlarge it automatically to the left of Inspect; move away
to dismiss it. No key or binding is needed. Click to keep a preview open and use its
actions; hovering another thumbnail resumes automatic previews. The list and search
bar stay accessible. Identified cards support **Take to hand** and bag
objects **Take out**. Imports with empty card GUIDs can still be browsed and previewed;
retrieval is disabled for those entries to avoid taking a different card by position.
TTS controls custom-menu placement, so Workshop Lua cannot insert Inspect beside native
Search or reuse its actual window. Standard Search remains available.

Single-card textures and custom object images have previews, including WebP through
named UI assets. Multi-card image sheets and built-in 3D object thumbnails remain
searchable by name without a picture. Source:
[cactuar_search.lua](tts/cactuar_search.lua) and [cactuar_search.xml](tts/cactuar_search.xml).

Players can also pick **sleeves** (a custom card back) for the deck they load. The
sleeves are the pictures in [tts/sleeves/](tts/sleeves/); its
[README](tts/sleeves/README.md) gives the image specs. Add one by dropping a picture
there, running the catalog build and pushing, or ask **sleever** in Discord
(`sleever make me sailor moon sleeves`, with pictures attached or links pasted for
reference). sleever paints it on the builder's harness, then
[bot/sleever.py](bot/sleever.py) crops it to spec, saves it, attaches it to the reply and
autopushes it.

New and retuned decks reach the table without a new upload: it reads the deck list
live. A change to the table itself (the browser's code or panel, or the tiles) needs
the Workshop item updated: load the save, then **Modding → Workshop Upload** to item
3822623414.

The data comes from the catalog build. `build_site.py` writes `docs/tts/`
([ttsdecks.py](scripts/ttsdecks.py)):

| | |
|---|---|
| `tts/decks.json` | the index the browser lists |
| `tts/<owner>/<Bracket>/<Deck>.ndjson` | one deck: a header line, then the library, commander(s) and tokens as ready-to-spawn Tabletop Simulator objects, built the way rikrassen's importer builds them |
| `tts/<owner>/<Bracket>/<Deck>.preview.json` | illustrated guide fetched on **Read guide**, content-versioned by the index; commander faces remain included for older table builds |
| `tts/cactuar-tile.jpg` | the picture on the Cactuar tiles |

Card faces use the same image cache as rikrassen's importer (`img.klrmngr.com`),
preserving each printing and its front/back faces. Direct Scryfall card-image
URLs reject Tabletop Simulator's default UnityPlayer client.
The browser also replaces direct Scryfall face URLs in older exports when loading them.

Every catalog build (including `--check`) verifies the exact exported image URLs with
Tabletop Simulator's UnityPlayer User-Agent before writing `docs/`. This covers library
cards, both commanders, tokens, double-faced states and card backs, deduplicated across
decks. HTTP errors, error pages and incomplete or unsupported image bodies fail the
build with the affected deck and URL. Existing published files stay intact on failure.

Successful checks store image format, size and HTTP validators under
`tts:image-check:v1:` in the `pages` table of `.cache/cards.db`. Subsequent builds still
contact the image host: an ETag or Last-Modified conditional GET can return 304 instead
of downloading the image again. This verifies availability at build time; the image
service is third-party and can change afterward. The checks inspect image signatures
and container boundaries rather than running TTS's image decoder.

A deck built or tuned through Discord shows up at the table once Pages has
published it, with no change to the table.

The table itself is built from the Workshop file, which is someone else's work and
is never committed; only what we add is: [tts/cactuar.lua](tts/cactuar.lua),
[tts/cactuar.xml](tts/cactuar.xml), [tts/cactuar_tile.lua](tts/cactuar_tile.lua) and
[build_tts_table.py](scripts/build_tts_table.py).

**Building a numbered table version** is one command, after the change is committed and pushed:

```bash
python3 scripts/release_tts.py --notes "what changed" --notes "and what else"
python3 scripts/release_tts.py --current      # the version we're at
python3 scripts/release_tts.py --dry-run      # build into .cache/release/ only
```

It builds the next `MTG 6 player Cactuar Ver_vN` from HEAD, not the working tree. It
refuses until HEAD is pushed and Pages serves its clips and tile picture, because TTS
caches by URL. It delivers the save and thumbnail to the PC's TTS Saves folder, checks
their SHA-256, removes the previous version, copies the WIP and changelog to the Desktop,
and adds the version's patch notes to [tts/CHANGELOG.md](tts/CHANGELOG.md). Commit and
push the changelog afterwards. The PC's address is in the gitignored
`tts/deploy.local.json` (see `INTERNALS.md`).

Every delivered build, including one intended for testing, gets the next version
number and the canonical `MTG 6 player Cactuar Ver_vN` name. Do not deliver separate
unnumbered Preview builds or replace a version with changed code. Building and
delivering does not publish to Steam: the owner chooses which version to upload.
Only use Workshop upload options when the owner explicitly selects a release.

`--workshop` also updates the Steam Workshop item through Steam's legacy
RemoteStorage API. A TTS Workshop item is one BSON file, `WorkshopUpload`
([scripts/tts_bson.py](scripts/tts_bson.py)), plus its preview. SteamCMD cannot update
this kind of item ("no workshop depot found"). Instead, the release script stages the
files, then launches [scripts/tts_workshop.ps1](scripts/tts_workshop.ps1) in the
owner's logged-in Windows session using a temporary task with ordinary user privileges.
It uses TTS's `steam_api64.dll` and the running Steam client, keeps the existing
PowerShell execution policy, waits for Steam's result, and removes the task afterward.
The title, description and visibility set on Steam are kept.

Steam must be running, signed in and connected to its servers on the PC. A blocking
PowerShell policy is reported rather than changed. The `workshop_id` comes from the
local deployment config; optional `steam_dll` and `workshop_dir` override DLL discovery
and the staging folder. No Steam password or SteamCMD login is needed.

```bash
python3 scripts/release_tts.py --workshop --notes "what changed"
python3 scripts/release_tts.py --workshop-only  # upload the current delivered save, no new version
```

`--workshop-only` reads the current version's save and thumbnail from TTS Saves,
validates its name, and uploads those exact bytes; it never rebuilds under the same
version number. Upload results are kept in `.cache/workshop/`. An upload is only
reported successful after Steam confirms EResult 1 for the requested item without
an outstanding Workshop agreement. Load the item in TTS to confirm it end to end.

The lower-level build, for experiments:

```bash
./scripts/build_tts_table.py 2293586471.json -o "MTG 6 player Cactuar Ver.json"
./scripts/build_tts_table.py 2293586471.json -o test.json --base-url http://192.168.0.100:5588/tts/
lua tests/test_cactuar.lua     # plays the browser against stand-ins for TTS
```

## Builder usage

Use **`/builder-usage`**, **`!builder-usage`**, or **`builder usage`** in Discord
to see the builder's configured model, remaining account allowance, and reset
times. The command works while a build is running and does not start a model turn.
From the terminal:

```bash
python3 bot/bot.py --usage
```

Every builder chat reply includes a usage footer, including busy/error replies.
The Discord deck commands show usage separately from the importable decklist.
On `agy` it comes from Antigravity's own usage panel (`agy --print=/usage
--output-format json`), for the quota group the model draws from (Gemini Flash and
Pro share one, Gemini 4 Argon has its own, Claude and GPT-OSS share another).
Players never see which model or harness runs the builder: the footer reads just
`Usage remaining` / `5h: 93% left · weekly: 97% left`, and the builder's
instructions forbid it to name itself. Only the owner chooses the model.
When the allowance runs out, `bot.py` prints only `deck builder usage limit
reached; try again at <t:…:R>.` (the emptiest window's reset), which the Discord
app turns into "The deck builder is out of usage for now. Try again …"; the
harness's own error, with its model name, goes to the bot log only.
Codex's allowance is read from the signed-in Codex account through
[`account/rateLimits/read`](https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt),
with separate percentages for the returned windows (typically five hours and a
week). These are shared account limits, not a count of messages or tokens left
for this bot alone. Discord renders resets in each reader's local time. If the
lookup fails, the reply says usage is unavailable rather than guessing a number.

## The builder's harness

The Discord builder's model runs inside an agent CLI, its **harness**
([bot/harness.py](bot/harness.py)), chosen by environment variables the Discord app
passes to `bot/bot.py`:

| variable | default | meaning |
|---|---|---|
| `MTG_BOT_HARNESS` | `agy` | `agy` (Google Antigravity CLI) or `codex` (OpenAI Codex CLI) |
| `MTG_BOT_MODEL` | the harness's own | e.g. `gemini-3.8-flash-high` (agy's default), `gemini-4-argon-high`, `claude-opus-5-5-high`, `gpt-6-astra` (codex's default) |
| `MTG_BOT_EFFORT` | the harness's own | Codex reasoning effort; agy models carry it in their id |

Switching needs no restart (the bot runs once per message) but starts every Discord
conversation afresh once: a session id belongs to the harness and model that made it.
Each harness reads the deployed `AGENTS.md` from the deck folder and keeps the
conversation itself; the bot stores only its id.

**How each is confined:**
- **codex** confines itself: `-s workspace-write -C public/<user>`, plus the card cache.
- **agy** runs in turbo (`--dangerously-skip-permissions`: no prompts, which a headless
  turn could not answer; a denied prompt would end the turn with no reply) inside a
  macOS sandbox profile from [bot/sandbox.py](bot/sandbox.py) that the kernel enforces
  on agy and everything it starts. Writes: only `public/<user>/`, the card cache,
  agy's own home (`bot/.harness/agy/`) and temp space. Reads: anything but credential
  stores (`~/.ssh`, cloud and GitHub tokens, the other agent CLIs' sign-ins). Exec:
  `claude`, `codex`, `gh` and `npx` are refused. Network: open, so it can search
  Scryfall and the web. A blocked action fails as "Operation not permitted", which
  the model works around, and the reply still arrives. `tests/test_harness.py` checks
  each of these by trying to escape the real sandbox.
- agy has its own home, `bot/.harness/agy/` (gitignored), so the bot's settings and
  conversations never mix with the owner's own Antigravity. It copies the owner's
  Antigravity sign-in there when that is newer.

To add a harness, subclass `Harness` in `bot/harness.py` (`run`, and `usage` if it
reports an allowance) and register it in `HARNESSES`. Set `images = True` if its turns
can make pictures; sleever needs that, and on a harness without it replies that it
can't make pictures right now, without running a turn.

## Layout

```
mtg/
├── scripts/                 toolchain — READ + EXECUTE only from the bot's view
│   ├── cardlib/               card and deck data access
│   │   ├── api.py               Scryfall HTTP only
│   │   ├── edhrec.py            EDHREC HTTP only (sibling of api.py)
│   │   ├── images.py            card image CDN, HTTP only (another sibling)
│   │   ├── db.py                SQLite storage (CardStore + PageStore + ImageStore)
│   │   └── query.py             orchestration (CardQuery + EdhrecQuery + ImageQuery)
│   ├── workspace.py           owns all path policy (deck root, cache, metadata)
│   ├── deckfile.py            .txt decklist format (incl. pinned printings), read and write
│   ├── frontend.py            {{TOKEN}} + <template data-part> loader
│   ├── toollog.py             tool-invocation log: API + CLI over SQLite
│   ├── find_cards.py          Scryfall search with bracket rules applied
│   ├── new_deck.py            seed a decklist from EDHREC's aggregate
│   ├── find_inspiration.py    what other pilots run that yours doesn't
│   ├── validate_deck.py       the required checks, including the TTS import
│   ├── ttsimport.py           client for the Tabletop Simulator deck importer
│   ├── ttsimages.py           checks exported image URLs before catalog publication
│   ├── deckplacement.py       saves the builder's Categories:/Tier: lines to the maps
│   ├── build_site.py          renders frontend/ + public/ into docs/
│   ├── cache.py               cache admin CLI
│   ├── build_agents.py        HOLDS the agent's instructions (AGENTS_MD) and
│   │                          deploys them to public/<user>/AGENTS.md as 0444
│   └── ask_codex.py           one-off second opinion
├── frontend/                the catalog's source — markup, CSS and JS
│   ├── layout.html            page shell and the deck menu on every page
│   ├── index.html             the catalog
│   ├── deck.html              one deck
│   ├── style.css              copied to docs/ verbatim
│   └── app.js                 hover preview, lightbox, gallery, copy button
├── docs/                    GENERATED SITE — published, do not hand-edit
│   ├── index.html             rebuilt by build_site.py from the two above
│   ├── <owner>/<Bracket>/<Deck>.html
│   ├── img/*.webp             committed card thumbnails
│   └── mana/*.svg             Scryfall's official mana symbols
├── bot/                     the harness — OUTSIDE the workspace it drives
│   ├── bot.py                 persistent builder session the Discord app calls
│   ├── harness.py             the agent CLI it runs on: agy (Gemini) or codex
│   ├── sleever.py             sleever: sleeves from Discord, cropped and published
│   ├── sandbox.py             the macOS sandbox profile around agy
│   ├── commands.py            deterministic !decks / !deck / !help
│   ├── usage.py               read-only Codex allowance lookup (no model turn)
│   ├── .harness/agy/          agy's own home: settings, conversations, sign-in copy
│   ├── .sleever/<user>/       sleever's per-user workspace (+ owners.json); not in git
│   └── .sessions/             one pinned session id per Discord channel and user
├── public/                  every deck, one folder per owner
│   └── <user>/                that user's decks; the builder's only writable tree
│       ├── Bracket3/            while it works for them
│       ├── Bracket4/ Bracket5/   only where a deck is uncapped
│       └── AGENTS.md            GENERATED, 0444 — edit AGENTS_MD in
│                                scripts/build_agents.py, never this file
├── frontend/redirects.json  old deck URLs -> where each deck lives now
├── logs/<utc-date>.log      request + debug log, outside the writable tree
├── .cache/cards.db          generated; writable by the builder
├── commander-brackets-and-rules.md
└── README.md
```

Folder name states the bracket. File name is `Commander-Theme` — see
[Deck file naming](#deck-file-naming).

**`scripts/` and `bot/` both sit deliberately outside `public/`.** The Discord-driven
builder session is rooted at `public/<user>/`, the asker's own folder, confined by
its harness's sandbox (below), so it can edit that user's decks but not anyone else's, and
cannot modify its own toolchain, its own harness, its own session state or its own
logs. A user folder holds decklists, guides and the generated `AGENTS.md`,
nothing else — the workspace boundary is only worth anything if the code that
enforces it lives on the other side of it.

That is also why the agent's instructions are a **string inside
`scripts/build_agents.py`** rather than a markdown file of their own. There is one
copy under version control, so a canonical file and a deployed copy cannot drift
apart, and the source sits in a directory the sandbox cannot write. Each
`public/<user>/AGENTS.md` is generated output — editing it is pointless, since it is overwritten before every
message.

Because both trees live outside the workspace they operate on, neither may infer
paths from `__file__`. `bot/bot.py` is one directory above the repo root's `public/`,
so `Path(__file__).parent.parent` would resolve the "workspace" to the repo root and
silently grant write access to everything. `scripts/workspace.py` owns that policy
and both import it; `MTG_DECKS` overrides the deck root:

```bash
```
