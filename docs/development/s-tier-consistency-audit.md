# S-tier turn-six consistency audit

Status: baseline review with unpublished tuning in progress, 2026-10-23. Owner requested S-tier lists that
reliably win on turn six from ordinary hands rather than exceptional draws.
This audit does **not** certify a win percentage or change deck ratings. The
existing S labels were structural judgments, not measured turn-six results.

The original baseline had 26 S-tier lists: 23 owned by zzwang, two by ratdos and one by
kupo7. All 26 passed the baseline validator: 100 cards, legal identities and
singletons, three Game Changers, no prohibited mass land denial, and TTS import
100/100. This establishes legality and importability, not speed or consistency.

## Confirmed scope and current work

The owner confirmed **tuning every owner's S-tier lists** and a target of
**80% of unopposed goldfish games won by the end of turn six**. This authorizes
cross-owner tuning for this task. Protected attempts and recovery remain separate
questions; they are not part of the confirmed percentage.

The catalog has since grown to 30 S-tier decks. Draft list tuning for 29 and an
experimental restricted pilot are preserved in the `codex/s-tier-bench-20261023`
worktree; the newly added Ultimecia list still needs inclusion. These candidates
are unpublished. Their guides, complete effect coverage and comparative benchmark
are unfinished. The pilot models selected routes and has 44 regression tests;
its unsupported-card failures do not establish the decks' real win rates. No
80% result or full-rules certification is claimed.

A separate finished package update covers all seven currently published Snoop
lists. Every Conspicuous Snoop deck must include Kiki-Jiki, Mirror Breaker,
Torch Courier, Goblin Ringleader and Mogg Fanatic. Six lists needed ten added
slots; Muxus was already complete. All seven validate at 100 cards, 3/3 Game
Changers and TTS import 100/100; all guides explain haste, top-card sequencing and
the Fanatic finish. The nine Snoop lists in the draft worktree also satisfy the
package, including Baylen and Jetmir. This package validation is not a speed test.

## What a valid benchmark must count

Use four-player Commander, 40 starting life and the commander in the command
zone. The starting player also draws on turn one. Use London mulligans with the
first multiplayer mulligan free; record all mulligans and a keep policy fixed
before seeing future cards. Never select a starting hand using the later draws.

Fix or rotate seat order and record it; reactive decks can win on opponents' turns.
Count a win against the entire pod by the end of the player's sixth turn, not
merely infinite mana, one eliminated opponent, a large board, or a library that
will cause a loss on a later draw step. Respect the house rule against executing
compact wins before turn six: an early-ready line may be staged, but the test
must keep playing and preserve the state until turn six.

A trace must pay colored mana, tutor costs, alternative/additional costs, equip
costs, initial counters and starter mana. Track summoning sickness, attack and
upkeep timing, card zones, free-cast X values, required targets and mandatory
draws. Cards drawn out of a scripted library-dependent line must be handled
properly; they cannot be silently treated as still available in the library.

Run and report three separate conditions:

1. **Unopposed:** no removal or blockers. Explicitly state opponent spell/draw
   assumptions; do not silently feed Rhystic Study, Remora, Tithe or rituals.
2. **Protected attempt:** produce the same lethal line with a usable protection
   answer and enough mana or pitch cards. Protection must actually answer the
   relevant disruption; a generic count of counterspells is insufficient.
3. **Recovery:** test a specified disruption at a specified window, such as
   commander removal or a counter on the key spell. Report recovery timing
   separately; do not claim every possible disruption was tested.

Freeze the deck hash, trial count, random seed, keep policy and opponent model.
Publish the win-turn distribution and failure reasons, including mana/color
shortage, missing piece/outlet, failed timing, loss to mandatory draw, or an
unrecovered disruption. Use enough trials and give sampling uncertainty before
calling a percentage consistent. Hand-picked example lines, average mana value,
tutor counts and card-access-only simulations do not measure actual wins.

## Current list review

These are prerequisites and review priorities, **not measured pass/fail rates**.
This table records the original baseline; draft cross-owner tuning is not yet published.

| Deck | Ordinary-hand requirement and main risk to check |
|---|---|
| zzwang/EmetSelch-Graveyard | The current Consultation/Pact wins use Maniac or Jace plus a draw, not Oracle. Separate that setup from the fourteen-card graveyard/upkeep transformation. Many expensive reanimation targets compete with finding and protecting the kill. |
| zzwang/Minstrel-Lands | Current loops need Kodama, a bounceland and a token maker alongside Minstrel. Fresh unlimited tokens do not automatically attack this turn; mana alone also is not lethal. Count a genuine immediate outlet and the cost of finding Kodama. |
| zzwang/Terra-Enchantress | Trance costs six AND taps Terra. Returning her front face creates a new summoning-sick object. Weaver/Freed mana requires a real outlet; repeated Spinner animations do not add arbitrary power. Correct these premises before timing the list. |
| zzwang/Kefka-Discard | Oracle/Consultation or Pact is a compact route; Dualcaster/Duplication needs its initial target and colored mana. Measure tutor costs, protection and actual cards seen without assuming unlimited opposing discard/draw. |
| zzwang/Sephiroth-Aristocrats | Several three-card sacrifice and Citadel engines exist, but require bodies, starter mana/life and an outlet. Measure how often those requirements coincide by six, not the number of theoretical combinations. |
| kupo7/Yuna-Counters | Graftmate mana lines need counters, a sufficiently productive creature and summoning-sickness clearance. Broodscale/Rosie needs a real same-turn finish. Broad creature-tutor counts do not waive those requirements. |
| ratdos/BruceBanner-Combo | Distinguish transforming the commander and starting a legal combat loop from a Monolith/Ballista finish. Count the transformation/untap/attack windows and protection rather than assuming the back face is available. |
| zzwang/Kilo-Infinite | Count the counter seeds, mana ability, untapper and actual poison/damage finish. Proliferation cannot give the first poison or first charge counter. Haste does not supply missing colored mana. |
| zzwang/Animar-Storm | Statue needs counters or paid setup and a finish. Colored creature costs remain payable, and mandatory draw can prevent an arbitrarily long Statue loop. A giant Animar or X=60 Ballista is not automatically lethal to three 40-life opponents. |
| zzwang/Prossh-Kobolds | Food Chain mana only pays for creature spells. Verify the payoff is castable/fetchable with the resources actually left, including any noncreature tutor. Count six-mana commander setup and protected access to Chain. |
| zzwang/Ghave-Saprolings | Token doublers and expensive redundant engines are not substitutes for early access to a complete Broodscale or sacrifice line. Count the seed, sacrifice/mana loop and drain outlet independently. |
| zzwang/Godo-Combats | Godo plus equip normally totals eleven mana; staging across turns is allowed but leaves a vulnerable board. Record how often ordinary keeps produce the mana or a cheaper Dualcaster line, with protection. |
| zzwang/Heliod-Lifegain | Correct Ballista line needs two counters, lifelink and Heliod; default finishing-turn cost is six with Heliod already out. Tutors and self-imposed spell limits consume real earlier turns. Triskelion redundancy does not prove median speed. |
| zzwang/Zada-Goblins | Cantrip and ritual yields depend on actual creatures present and legal single targets. Do not assume a free starting army, unbounded ritual output or a safe combat step. Tutor stacks need real draws/haste. |
| zzwang/KrenkoTinStreet-Goblins | Commander combat growth and Assault loops need attack, damage and mana thresholds. Separately measure the Recruiter/Snoop route and whether its drawn top card/haste state remains correct on six. |
| zzwang/Baylen-Goblins | Token mana requires two untapped tokens per mana; drawing consumes three untapped tokens. Those taps compete. Mantle loops require enough Goblins/tokens to pay untaps, plus an immediate finish. |
| zzwang/GeneralKreat-Goblins | Token-entry damage needs an actual repeatable token engine. Separate Recruiter access, Snoop readiness and a finishing ability from fair Goblin value or a future large attack. |
| zzwang/Jetmir-Goblins | Nine creatures unlock the full bonus but do not automatically deal 120 damage. Measure actual attackers, blockers and damage, or a fully assembled Kiki/Snoop finish, rather than the threshold alone. |
| zzwang/Najeela-Warriors | Repeated combat requires recurring WUBRG and the relevant attack/damage threshold. Newly created attacking tokens are not declared attackers. Goldfish combat success must be distinguished from connecting through blockers. |
| zzwang/Inalla-Wizards | Spellseeker is a compact starter, but the chain assumes support cards in the right zones, exact trigger order, colored mana and life. Test drawn support cards and an interrupted search/reanimation separately. |
| ratdos/Beamtown-Gifts | Eliminating one opponent with a gift is not defeating the whole pod. Count legal activation windows, untaps, all opponents' elimination timing and graveyard protection. |
| zzwang/Kinnan-Infinite | Basalt provides colorless; the kill or library converter must be accessible and legally payable. Many tutors overlap, but evaluate their costs and constraints before counting them as identical copies. |
| zzwang/Vivi-Spellslinger | Quicksilver/setup, copied abilities, once-per-turn restrictions and colored buyback costs matter. Breach requires finite graveyard fuel. Test the independent Dualcaster route separately from the commander engine. |
| zzwang/Urza-Combo | The recent revision adds cheaper engines and protection, but its turn-six rate is unmeasured. Require a mana-positive loop AND accessible Cannon/Ballista/Staff, including tutor and colored setup costs. |
| zzwang/Gwenom-Drain | Five-mana commander needs an attack, haste or a prior turn. Top casting consumes life and follows timing restrictions. Specify exact Doomsday/Chain or Citadel piles rather than counting every high-cost finisher as a fast line. |
| zzwang/Krenko-Combo | Staff needs equip mana; Krenko needs tap readiness, an untap/death engine and a finish. Recruiter stacks need legal next draws and either haste or time. An arbitrarily large fresh army is not automatically this turn's win. |

## Rules errors that already undermine the existing estimates

Named lookups through `find_cards.py --names ... --text` verified these concrete
problems in the current sources:

- **Terra:** Trance includes a tap cost. Her own Chapter IV is not automatically
  reached when a copied Summon gets extra lore counters. The commander is a new
  object when returned front face up and needs haste to tap immediately again.
- **Destiny Spinner:** animation sets each land's power/toughness to the
  enchantment count; repeated activations do not accumulate unlimited power.
- **Sterling Grove:** finds an enchantment on top, not Replenish (a sorcery).
  Its shroud also prevents targeting Sanctum Weaver with a new Aura while Grove
  is out. Sequencing must account for that restriction.
- **Minstrel:** Crop Rotation puts Boseiju onto the battlefield; it does not put
  the card in hand to channel. The printed eight-mana team pump needs an actual
  attacking board and does stack, unlike Spinner's fixed-size animation.
- **Animar:** generic cost reduction does not remove Cloud of Faeries' blue
  requirement. The Great Henge still needs GG and is not discounted by Animar
  as a creature spell. Mandatory draw engines constrain repeated casts.

These findings require guide/list corrections regardless of the final percentage
chosen. No unperformed game tests are represented as results here.

## Sources and reproducibility

- Baseline: main commit `2c6c1338`, published `docs/tts/decks.json`, source lists
  and matching guides under `public/<owner>/Bracket3/`.
- Validate the baseline with `scripts/common/validate_deck.py` on all 26 S-tier paths;
  result: 26/26 pass, TTS import 100/100 for each.
- Card mechanics were read through the project's cache-first `find_cards.py`
  named lookups, backed by Scryfall Oracle data.
- [Wizards multiplayer rules](https://magic.wizards.com/en/news/feature/multiplayer-rules-2004-07-12): first-turn draw.
- [Wizards London mulligan notes](https://magic.wizards.com/en/news/feature/core-set-2020-release-notes-2019-06-25): first multiplayer mulligan free.
- [Wizards Urza release notes](https://magic.wizards.com/en/news/feature/modern-horizons-release-notes-2019-05-31): Urza timing, summoning sickness and free-cast X constraints.
