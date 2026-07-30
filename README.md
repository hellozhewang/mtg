# Deck Building Guide

How decks in this repo get built. Read this before adding or tuning a list.

---

## Core rules

### 1. Follow the bracket rules

Every deck targets a specific Commander bracket and must obey that bracket's
restrictions. The full rules are in [commander-brackets-and-rules.md](commander-brackets-and-rules.md).

**Exception: the user can explicitly say a deck may break its bracket.** When that
happens, put the deck in its own folder and name the folder honestly — see
`Bracket3.5/` (Krenko), which respects Bracket 3's Game Changer cap of 3 but
deliberately keeps two-card infinite combos that Bracket 3 forbids.

Never silently exceed a bracket. If a requested card would break the cap, say so
and offer the trade — e.g. adding Cyclonic Rift to a deck already at 3 Game
Changers means cutting one of the existing three.

### 2. Use the most powerful cards in the bracket — including the newest ones

Within the bracket's limits, take the strongest option available. **Actively favour
recent printings**: power creep is real, and a card from the last few sets is often
strictly better than the staple it replaces. Do not default to a 2015 staple out of
habit.

This is why **web search is mandatory** when researching cards. Training data goes
stale, new sets land constantly, and the Game Changers and ban lists both change.
Check what's current before recommending anything.

### 3. Ignore physical card cost

**These decks are for Tabletop Simulator.** Price is irrelevant. Underground Sea,
Gaea's Cradle, Moat, Mishra's Workshop, The Tabernacle at Pendrell Vale, full
original dual and fetch suites — all fair game. Never substitute a worse card for
budget reasons, and never mention price as a downside.

---

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

| | B1 Exhibition | B2 Core | B3 Upgraded | B4 Optimized | B5 cEDH |
|---|---|---|---|---|---|
| Game Changers | 0 | 0 | **≤3** | ∞ | ∞ |
| Mass Land Denial | no | no | no | yes | yes |
| Chaining Extra Turns | no | no | no | yes | yes |
| 2-Card Combos | no | no | **not before turn 6** | yes | yes |
| Turns before a win | 9+ | 8+ | 6+ | 4+ | any |

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

**`<Commander>-<Theme>.txt`**, inside a folder named for the bracket.

```
Bracket3/Zur-Voltron.txt
Bracket3/Lathril-Elves.txt
Bracket3/GrandArbiter-Prison.txt
Bracket3.5/Krenko-Combo.txt
```

The commander part is a short recognisable form of the name — first word usually
(`Zur`, `Lathril`, `Yuriko`), or the words closed up when one word is ambiguous
(`GrandArbiter`, not `Grand-Arbiter`). The theme is one word for what the deck
actually does: `Voltron`, `Elves`, `Enchantress`, `Ninjas`, `Attacks`, `Treasure`,
`Lands`, `Annihilator`, `Drain`, `Prison`, `Combo`.

**Exactly one hyphen**, so everything after it is unambiguously the theme. That
matters because `commands.py` resolves `!deck <name>` by folding away case and
punctuation — `!deck zurvoltron`, `!deck Zur-Voltron` and `!deck zur` all hit the
same file. Rename the file if a deck's plan changes; the name is documentation.

## Deck file format

One `.txt` per deck, importable directly into Tabletop Simulator.

```
1 Zur the Enchanter        <- line 1 is ALWAYS the commander
1 Academy Rector
1 All That Glitters
...
16 Swamp
```

- `<count> <exact card name>`, one per line
- Commander on line 1, **no blank line** after it
- Alphabetised after the commander line
- **No tokens** — TTS generates them automatically, and token names don't resolve
  against a card database
- Double-faced cards use the **front face only** (`Agadeem's Awakening`, not
  `Agadeem's Awakening // Agadeem, the Undercrypt`)
- Exactly **100 cards** counting the commander

### Source of truth

The original decks live as **Tabletop Simulator Saved Objects** (JSON), not text:

```
.../Tabletop Simulator/Saves/Saved Objects/<Bracket>/<Deck>.json
```

`ObjectStates[0]` is a `Bag` holding a `DeckCustom` named "Deck", an optional
`DeckCustom` named "Tokens", and the commander as a loose `Card`. Card name and
type live in `Nickname` as `"Name\nTypeLine NCMC"`; oracle text plus `[b]P/T[/b]`
in `Description`. Those files are UTF-8 **without BOM**.

---

## Tools

All in [scripts/](scripts/). No dependencies beyond Python 3 stdlib.

### Architecture

Card data access is split into three layers, so each has one job:

```
cardlib/api.py     Scryfall HTTP only.    Knows nothing about storage.
cardlib/edhrec.py  EDHREC HTTP only.      A sibling of api.py, not a layer above.
cardlib/db.py      SQLite storage only.   Knows nothing about the network.
cardlib/query.py   Orchestration.         The only module aware of both.
```

Two upstreams, because they answer different questions. Scryfall answers *what is
this card*; EDHREC answers *what do other people play with this commander*. Two
orchestrators in `query.py` to match — `CardQuery` and `EdhrecQuery` — sharing one
SQLite file but separate tables and TTLs.

`edhrec.py` is split into `url_*` / `get` / `parse_*` methods precisely so the
cache can be inserted above it without it knowing storage exists.

Everything above imports `CardQuery` and nothing else:

```python
from cardlib import CardQuery
q = CardQuery()
cards, missing   = q.cards(["Sol Ring", "Rhystic Study"])   # cache-first
hits, total, new = q.search("t:enchantment mv<=3 id<=wub")  # always live
```

`deckfile.py` is a fourth, separate concern: the `.txt` decklist format, with no
knowledge of Scryfall or brackets. `find_cards.py`, `validate_deck.py` and
`cache.py` are then pure business logic — query construction, rule checking and
presentation.

The split means every Scryfall quirk (required headers, the 75-identifier POST
cap, 404-means-empty, pagination) is contained in `api.py`, and every schema
detail (oracle_id keying, the alias table) is contained in `db.py`. Both layers
are injectable, so business logic can be tested without a network or a database.

**Caching policy lives in `query.py`, deliberately:**

- **Card lookups are cache-first.** Card data is stable; a 30-day TTL is fine.
- **Searches are always live.** Which cards *match* a query changes every set
  release, and rule 2 says favour new printings — a cached search would silently
  hide exactly the cards you are looking for. Results are still banked, since
  they are complete card objects.
- **EDHREC pages are cached for 24 hours.** The opposite call from searches, for
  two reasons that don't apply to Scryfall: the payloads are large (a commander
  page is ~90 KB, a full deck index ~3.5 MB) and the numbers inside move over
  *days*, so a one-day TTL can't hide a trend that takes weeks to form. Without
  it, one tuning session re-downloads megabytes per question from a free service
  that asks for no API key.

That difference in lifetime is why `PageStore` is a separate class from
`CardStore` rather than a third method on it — one class would mean one TTL for
card objects and fetched pages both.

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
./scripts/new_deck.py "Queen Marchesa" -o public/Bracket3/Marchesa-Pillowfort.txt
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
./scripts/find_inspiration.py public/Bracket3/Sythis-Enchantress.txt
./scripts/find_inspiration.py public/Bracket3/Zur-Voltron.txt --new     # EDHREC's New Cards section
./scripts/find_inspiration.py public/Bracket3/Zur-Voltron.txt --trending # rising adoption, any age
./scripts/find_inspiration.py public/Bracket3/GrandArbiter-Prison.txt --mine
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

### Validating — `scripts/validate_deck.py`

**Required before calling any deck done.** Checks all five rules:

1. Exactly **100 cards** including the commander
2. Every name **resolves on Scryfall** (catches typos that would fail TTS import)
3. Every card is inside the commander's **colour identity**
4. **Game Changer count** within the bracket cap (inferred from folder name)
5. **Singleton** — no duplicate non-basic entries, no repeated lines

```bash
./scripts/validate_deck.py                  # every deck in public/
./scripts/validate_deck.py public/Bracket3  # one folder
./scripts/validate_deck.py --max-gc 0 ...   # override the cap
```

Real bugs this caught: `Sunbaked Canyon` is R/W and was illegal in a Jund deck;
`Sling-Gang Lieutenant` is black and was illegal in mono-red Krenko. Both would
have imported as 99-card decks with a silently missing card.

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

Each store owns only its own tables — `CardStore.clear()` deliberately does *not*
touch `pages`, and each reports its own `stats()`, which `cache.py` merges.

Lives at `.cache/cards.db` (repo root, outside the workspace). Pass `--no-cache` to `validate_deck.py` to bypass it.

Two schema details worth knowing:

- Cards are keyed by **`oracle_id`**, not name — one card has many printings.
- **The name you query is not always the name Scryfall returns.** Ask for
  `Agadeem's Awakening` and you get `Agadeem's Awakening // Agadeem, the
  Undercrypt`. An `aliases` table maps query → card so front-face lookups keep
  working. Getting this wrong silently drops every MDFC from your stats.

### Scryfall API notes

- **Requests without both `User-Agent` and `Accept` headers get HTTP 400.**
- `/cards/collection` accepts **at most 75 identifiers per POST** — chunk longer
  lists or you get a 400.
- Sleep ~100ms between calls to be polite.
- Each card object carries a **`game_changer` boolean**, so bracket checking needs
  no separate `is:gamechanger` query.
- **Modal DFCs count as lands only on their back face.** `Malakir Rebirth` is
  `Instant // Land` — playable as a tapped land, but not a mana source you can
  plan around. The validator reports these separately as `(+N MDFC)`.

### Line endings

Files written on Windows carry **CRLF**. In Linux tooling that makes the last card
parse as `"Sol Ring\r"`. Convert when working in WSL:

```bash
find . -name '*.txt' -exec sed -i 's/\r$//' {} +
```

---

### Second opinion — `scripts/ask_codex.py`

Queries Codex for an independent review. Model and reasoning effort are resolved
**dynamically** from `~/.codex/models_cache.json` on every run — nothing is
hardcoded, so a new tier is picked up automatically. Runs read-only with web
search on.

```bash
./scripts/ask_codex.py "Review Bracket3/Sythis.txt for Bracket 3 legality"
./scripts/ask_codex.py --list                       # models + effort tiers
./scripts/ask_codex.py "q" --model gpt-5.6-luna --effort low
```

Codex reads the same `.txt` files but **has no access to the conversation** — it
won't know the bracket target, the 4-player context, or why any swap was made.
Spell that out in the prompt, and point it at `commander-brackets-and-rules.md` for the
ruleset.

Codex CLI gotchas encoded in the script:

- **`--search` is top-level only and is rejected by `codex exec`.** Web search on
  exec requires `-c tools.web_search=true`.
- **`-a/--ask-for-approval` is likewise top-level only**; exec is already
  non-interactive.
- **`--skip-git-repo-check` is required** — this folder is not a git repo and
  codex refuses to run without it.
- If the model list looks stale, **update the CLI**. A newer Codex writes effort
  values an older build can't parse, so `models_cache.json` fails to load
  entirely and silently falls back to an old list — that hid the whole 5.6 family
  behind a phantom "5.5 is newest".

---

## Building a deck, step by step

Each tool above does one job. This is the order they compose in, for a human or
Claude session working in an editor or terminal — the Discord bot follows the same
sequence minus the last step (see `AGENTS.md`, and why below).

1. **Seed the shell.** `new_deck.py "<commander>" -o private/Bracket3/<file>.txt`
   gets you a real, importable 100 cards in one command instead of typing 99 lines
   from memory. Expect it to land 4-11 Game Changers, not 3 — it has no bracket
   awareness, it just composes EDHREC's most-played build.

2. **Cut to the cap — and check the two things no tool checks.** The GC report
   tells you what to drop for the Bracket 3 cap of 3. While you're cutting, check
   **mass land denial** and **two-card lockouts** by hand against
   `commander-brackets-and-rules.md` — `validate_deck.py` does not catch either of
   these, only the GC count.

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
   `MTG_DECKS=./private ./scripts/validate_deck.py <path>` — 100 cards, every name
   resolves, colour identity, the GC cap, singleton. A deck that hasn't passed
   this is not done.

7. **Second opinion.** `ask_codex.py`, with the validator's result stated as
   settled fact in the prompt so Codex doesn't re-derive it — never ask it to
   count Game Changers, that's a 10-minute web-search detour for something
   `validate_deck.py` answers in milliseconds. Ask only for what no script can
   decide: does the deck deliver the brief, can it actually win, which of your
   own symmetric stax pieces hurt you more than the table, and rules judgment
   calls (MLD, lockouts) as a check against step 2.

**The Discord bot's own instructions (`AGENTS.md`) stop at step 6, deliberately.**
The bot's working session *is* a Codex `exec` process. Having it invoke
`ask_codex.py` would be Codex asking Codex to review Codex's own output — no
independent model, no outside context, and a second multi-minute `codex exec` call
burned for a report with no real signal. Step 7 is only meaningful when it comes
from a genuinely separate reviewing context, which the bot never has.

| step | who checks it | can a script verify it? |
|---|---|---|
| 100 cards, names resolve, colour identity, GC cap, singleton | `validate_deck.py` | yes |
| inclusion, synergy, new printings | `find_inspiration.py`, `find_cards.py` | yes |
| mass land denial, two-card lockouts | you, against `commander-brackets-and-rules.md` | no |
| does each card's trigger match the theme | you | no |
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

## Layout

```
mtg/
├── scripts/                 toolchain — READ + EXECUTE only from the bot's view
│   ├── cardlib/               card and deck data access
│   │   ├── api.py               Scryfall HTTP only
│   │   ├── edhrec.py            EDHREC HTTP only (sibling of api.py)
│   │   ├── db.py                SQLite storage only (CardStore + PageStore)
│   │   └── query.py             orchestration (CardQuery + EdhrecQuery)
│   ├── workspace.py           owns all path policy (deck root, cache location)
│   ├── deckfile.py            .txt decklist format, read and write
│   ├── find_cards.py          Scryfall search with bracket rules applied
│   ├── new_deck.py            seed a decklist from EDHREC's aggregate
│   ├── find_inspiration.py    what other pilots run that yours doesn't
│   ├── validate_deck.py       the five required checks
│   ├── cache.py               cache admin CLI
│   ├── build_agents.py        HOLDS the agent's instructions (AGENTS_MD) and
│   │                          deploys them to public/AGENTS.md as 0444
│   └── ask_codex.py           one-off second opinion
├── bot/                     the harness — OUTSIDE the workspace it drives
│   ├── bot.py                 persistent Codex session the Discord app calls
│   ├── commands.py            deterministic !decks / !deck / !help
│   └── .sessions/             one pinned session UUID per Discord channel
├── public/                  THE WORKSPACE — the only writable tree
│   ├── Bracket3/              bracket-legal decks (≤3 Game Changers)
│   ├── Bracket3.5/            deliberately breaks Bracket 3, by request
│   └── AGENTS.md              GENERATED, 0444 — edit AGENTS_MD in
│                              scripts/build_agents.py, never this file
├── private/                 a second deck collection — readable, never writable
├── todo/                    known gaps, written up but not acted on
├── logs/<utc-date>.log      request + debug log, outside the writable tree
├── .cache/cards.db          generated; granted to the bot via --add-dir
├── commander-brackets-and-rules.md
└── README.md
```

Folder name states the bracket. File name is `Commander-Theme` — see
[Deck file naming](#deck-file-naming).

Decks Claude builds in an interactive session go to **`private/`**; `public/` is the
Discord bot's tree. They started as byte-identical copies and will drift.

**`scripts/` and `bot/` both sit deliberately outside `public/`.** The Discord-driven
Codex session is rooted at `public/` with `-s workspace-write`, so it can edit decks
but cannot modify its own toolchain, its own harness, its own session state, its own
logs, or reach `private/`. `public/` holds decklists and the generated `AGENTS.md`,
nothing else — the workspace boundary is only worth anything if the code that
enforces it lives on the other side of it.

That is also why the agent's instructions are a **string inside
`scripts/build_agents.py`** rather than a markdown file of their own. There is one
copy under version control, so a canonical file and a deployed copy cannot drift
apart, and the source sits in a directory the sandbox cannot write. `public/AGENTS.md`
is generated output — editing it is pointless, since it is overwritten before every
message.

Because both trees live outside the workspace they operate on, neither may infer
paths from `__file__`. `bot/bot.py` is one directory above the repo root's `public/`,
so `Path(__file__).parent.parent` would resolve the "workspace" to the repo root and
silently grant write access to everything. `scripts/workspace.py` owns that policy
and both import it; `MTG_DECKS` overrides the deck root:

```bash
MTG_DECKS=./private ./scripts/validate_deck.py    # validate the other collection
```

## The sandbox boundary, measured

Tested rather than assumed, with `codex exec -C public -s workspace-write`:

| | Result |
|---|---|
| Write `public/` (decks) | **allowed** |
| Write `../scripts/` | **blocked** — `operation not permitted` |
| Write `../private/` | **blocked** |
| Write `../.cache/` | allowed **only** via `--add-dir` |
| **Read** anything, anywhere | **allowed — `-C` is not a read boundary** |
| Network (Scryfall) | blocked by default; needs `sandbox_workspace_write.network_access=true` |
| Run `claude` by bare name | **blocked** — `command not found` |
| Run `/opt/homebrew/bin/claude` by absolute path | **allowed** — PATH is not a real exec boundary |
| Run `python3`, `git`, `diff`, `grep`, `curl` | allowed — all standard system tools kept |

Two of those are easy to get wrong. `-C` bounds *writes*, not *reads* — a session
rooted at `public/` can `cat ../private/*` freely, so this is not a confidentiality
boundary. And `workspace-write` blocks network egress, which surfaces as a **DNS
error** from `find_cards.py` rather than a permission error; the config key above is
what makes live card search work.

**The two exec rows are a different mechanism from everything else in this table**,
and are deliberately the *weak* form. The other rows are `codex exec`'s own sandbox
flags; these are `bot.py` handing the subprocess an allowlist `PATH`
(`/usr/bin:/bin:/usr/sbin:/sbin:/usr/libexec`) instead of inheriting its own. All
standard system tools are kept on purpose — this agent legitimately runs `python3`,
`diff` and `grep`. What's excluded is the homebrew prefix, where `claude` lives.

Why bother, and why it's honestly labelled weak. `AGENTS.md` tells the session never
to invoke another LLM/agent CLI, but that's advisory like anything a prompt says.
`claude` is installed here, on the PATH a naive subprocess inherits whole, running as
the same OS user — so it would start already authenticated, not fail on login. The
PATH allowlist raises that from one obvious command to a deliberate act. It does not
prevent it: measured live, `which claude` returns "not found" but
`/opt/homebrew/bin/claude --version` still prints `2.1.177`.

**The proper fix does not work here, and that's worth recording.** The sibling
discord-bot project's `src/infra/execSandbox.ts` wraps codex in a macOS Seatbelt
profile that denies `process-exec` at kernel level, which absolute paths cannot
bypass. Porting it was attempted and measured:

> codex applies its **own** Seatbelt profile per shell tool-call, and macOS denies a
> nested `sandbox_apply`. Under an outer `sandbox-exec` wrapper codex starts and
> answers normally, but every tool call fails with
> `sandbox-exec: sandbox_apply: Operation not permitted`. Confirmed on **both**
> `-s read-only` and `-s workspace-write`, so it isn't a workspace-write quirk.

That is precisely why the approach suits that project and not this one: it locks down
a *chat* backend that must never run a shell command, whereas running commands is
this agent's whole job. Wrapping this one in Seatbelt breaks the tools instead of
protecting them.

Two things that did survive from the port. `bot.py` now execs codex's **native
compiled binary** rather than the npm `#!/usr/bin/env node` shim — the shim would drag
`node` in, and `node` lives in the same homebrew directory as `claude`, so supporting
it meant either exposing that directory or maintaining a symlink workaround. Going
native removes `node` from the picture entirely (verified: `which node` → not found,
codex still works). And codex's own undocumented `execpolicy` `.rules` mechanism (see
`--ignore-rules`) would not conflict, being *inside* codex rather than wrapped around
it — that's the thing to revisit if this ever needs to be a real boundary, though its
parser is unstable and undocumented today.

If this needs to be genuinely airtight, the answer isn't a PATH tweak: run the
sandboxed session as a **separate OS user**. Note that reads are unrestricted and
`curl` is deliberately present, so a determined session could read a credentials file
and POST it over raw HTTP without ever invoking `claude` — the PATH allowlist does
nothing about that path. Written up, not done:
[todo/service-user-isolation.md](todo/service-user-isolation.md).
