# Bracket 4 competitive gap audit — 2026-10-27

Owner asked to add Blood Moon to the newly created Krenko and check the other
seven new Bracket 4 lists against cEDH builds. Scope is exactly the eight copies
created on October 26, not every owner's Bracket 4 deck. All Bracket 3 lists and
guides, and the separate Bracket 5 Kinnan, remain unchanged. Retained cards keep
their printing pins. This follows the [initial upgrade record](bracket4-upgrades-2026-10-26.md).

## What the initial pass missed

Acceleration, tutors and compact combos were reviewed more thoroughly than
proactive disruption and commander-specific engines. Blood Moon is legal here;
its omission was not a bracket restriction. Current EDHREC user-selected Bracket 5
samples and authored primers supplied candidates, followed by Oracle-text and
actual-list checks. Inclusion rates are not tournament win rates, and an uploaded
list calling itself cEDH is not proof that it is competitive.

| List | Gap corrected | Why these changes fit |
|---|---|---|
| Krenko-Turbo | Moon effects, protection, repeatable mana and refill | Blood Moon/Magus disrupt multicolor nonbasics while 21 Mountains work. Defense Grid taxes responses. Staff/Altar/Ogre improve conversion; Ring rebuilds. Cut redundant tribal payoffs and slower acceleration. |
| Muxus-Turbo | Proactive denial, a tutorable creature answer, artifact recovery | Blood Moon buys time; Stingscourger and Engineer remain useful Goblin hits. Ogre/Monolith help pay six; Breach recovers interrupted pieces; Redirect protects targeted spells or abilities. |
| Zada-Turbo | Moon effects and spell-chain redundancy | Magus is another copy target. Steam-Kin rewards original red casts, Witch's Mark filters into the graveyard, Crescendo exposes more spells, Ogre supplies startup mana. Keep the cheap haste cantrips and two Dualcaster copy spells. |
| Vivi-Turbo | Redundant damage-to-draw engines and a direct cast-loop finish | Eye and Lookout supplement Curiosity. Horror/Ring/zero-cost-artifact casts deal repeated damage through Vivi; Signet repairs colored mana and Borne opens flash windows. Remove a separate Dualcaster package and narrower setup slots. |
| Kinnan-Optimized | Colorless-to-colored conversion and cheaper interaction | Mirror's queued-copy line filters Monolith mana; Vitality turns utility creatures into colored sources. Misstep/Trap preserve activation mana; Borne lets noninstant setup enter contested windows. |
| Kilo-Turbo | One-sided disruption and artifact-specific conversion | Urza taps Kilo for blue/proliferate and taps Orb before your untap. Drannith and Voice create windows; Transmute and cheap counters replace broader or slower options. |
| Yuna-Combo | An immediate Druid line and asymmetric development | Swift makes Druid a noncreature Vehicle, bypassing sickness and toughness. Drannith stops opposing non-hand casts; Deafening Silence allows multiple creature spells and reanimation. Orb rewards established nonland mana. |
| Ral-Storm | Commander-specific resource engines | Restore Scoundrel and Will of the Jeskai. Red two-mana draw becomes one red with Ral; Drum uses a fresh creature. Remove the buyback/fork package and two wheels that refill opponents or shuffle away graveyard fuel. |

## Evidence and limits

EDHREC JSON was fetched on October 27 through the existing cache-aware EdhrecQuery
interface, using each commander's `/cedh` page, rather than the unrestricted casual
aggregate. Snapshot counts are observations, not promises of future inclusion:

- Krenko: Blood Moon 241/306; Staff 206/306; Phyrexian Altar 185/306;
  Ring 156/306. Authored Krenko's Playground also contains Blood Moon.
- Muxus: Ogre 35/40, Engineer 30/40, Stingscourger 23/40 and Moon 15/40.
  The October 24 Miguel event list supports Ogre/Engineer/Stingscourger and
  Redirect, but does NOT run Moon. Denial is not universal even among event lists.
- Zada: Steam-Kin 115/130, Crescendo 105/130, Ogre 96/130, Witch's Mark
  93/130; Magus 47/130 and Moon 38/130. Moon choices remain a matchup decision.
- Vivi: Eye 2890/3076, Lookout 2709/3076 and Horror 2272/3076. The authored
  Vivi primer explains the same cast-loop and the mandatory-draw hazard.
- Kinnan: Vitality 4084/4817, Mirror 3702/4817, Misstep 4163/4817 and
  Trap 4032/4817. Compare the named No Bad Cards and other lists linked by
  the Kinnan primer; do not copy every expensive creature from the aggregate.
- Kilo: 131 self-selected Bracket 5 lists. Flusterstorm 97/131, Misstep
  94/131, Voice 87/131 and Urza 84/131. The authored Kilo example also
  uses Urza, but does not establish the Orb package as tournament consensus.
- Yuna: only TWO Bracket 5 lists. Swift appears in both; this sample cannot
  establish an optimized cEDH standard. The stax choices are a construction
  judgment checked against this list's actual creature and activated wins.
- Ral: Scoundrel 1350/1418, Will 1249/1390, Rob the Archives 1187/1418,
  Highway Robbery 1181/1418 and Drum 1244/1418. Current authored Ral
  material also prioritizes discounted draw, deliberate transformation and Breach.

## Self-interaction review and deliberate exclusions

- Moon removes our special nonbasic-land abilities too. Zada's Saga sacrifices
  under Moon; the guide explicitly sequences it before Moon or accepts the loss.
  Muxus does not add Magus as a second non-Goblin denial slot: keep useful Goblin
  hits and the owner-required Recruiter/Ringleader/Muxus/Snoop package.
- Winter Orb is untapped through opponents' untap steps in Kilo, then tapped
  with Urza in the last opponent's end step. It is tapped as our untap begins,
  so all our lands untap with Orb. Without Urza it is symmetrical. Yuna has no
  such tap bypass: use Orb only after establishing dorks/Weaver/productive lands;
  Earthcraft's untaps outside the untap step still work.
- Do not blanket-add Blood Moon/Back to Basics to the multicolor shells or Orbs
  to storm. Our blue-red and Simic manabases are heavily nonbasic, and a card
  slowing our own engine can be worse than another answer. The three red Goblin
  decks use Moon, Kilo and Yuna use Orb, and the other three improve interaction.
- Yuna's Deafening Silence counts our noncreature spells too. Tutors, Silence and
  Auras must be staged, or protection comes from creatures. Druid/Vizier,
  Heliod/Ballista and activated loops can function through it. Yuna reanimation
  does not cast a spell. Do not add Collector Ouphe/Stony Silence while relying
  on Ballista, Staff, Station and mana rocks; do not add graveyard-exile locks
  while relying on Yuna and Replenish.
- Swift Druid must stay a noncreature after accumulating -1/-1 counters. Do not
  crew it. The list retains Vizier as a separately tutorable second enabler.
- Vivi's Eye and Curiosity draws are optional; Lookout's are mandatory. Bounce
  Lookout before an arbitrary damage loop if its draws would deck you. Retain a
  real outlet: Ballista for the mana loop, or Vivi damage from Horror casts.
- Mirror must queue its copy activations BEFORE becoming another artifact.
  Copies lose its native ability. Resolve alternating Basalt untap and Signet
  colored taps using an already-funded colorless bank; do not call one copied
  Signet infinite colored mana.
- Ral losses still deal damage. Scoundrel's Treasures only come from wins and
  stop being supplied by Ral after transformation. Will's wheel is optional for
  each opponent, so it does not force a milled opponent to draw and lose.
- Borne supplies flash permission, not permission to use Vivi's mana on another
  player's turn or to activate sorcery-speed abilities at instant speed.
- No sanctioned tournament legality exceptions: older primers with Dockside,
  Mana Crypt or Jeweled Lotus are historical references,
  not cards to copy into current lists.

## Placement

Keep all eight in Bracket 4 as requested; do not silently move or clone them into
Bracket 5. Primary categories remain combo. Add `control` as a secondary to
Krenko, Kilo and Yuna, whose guides now deliberately deploy a disruption package;
a single Moon does not establish another deck's primary strategy.

Retain existing tiers: Krenko/Muxus/Zada S, the other five SS. Denial does not add
tutor redundancy or prove measured consistency. The blue competitive shells remain
near the Bracket 4/5 boundary; these changes are not certification that they fit
all Bracket 4 pods. No measured goldfish percentage, cEDH matchup win rate or
strongest-possible claim is made.

## Exact swaps

### Krenko-Turbo

| Removed | Added |
|---|---|
| Siege-Gang Commander | Blood Moon |
| Hobgoblin Bandit Lord | Magus of the Moon |
| Krenko, Tin Street Kingpin | Staff of Domination |
| Purphoros, God of the Forge | The One Ring |
| Arcane Signet | Defense Grid |
| Seething Song | Treasonous Ogre |
| Ashnod's Altar | Phyrexian Altar |

### Muxus-Turbo

| Removed | Added |
|---|---|
| Siege-Gang Commander | Blood Moon |
| Goblin-town Flunkies | Stingscourger |
| Hobgoblin Bandit Lord | Goblin Engineer |
| Warren Instigator | Treasonous Ogre |
| Arcane Signet | Grim Monolith |
| Thornbite Staff | Underworld Breach |
| Pyretic Ritual | Redirect Lightning |

### Zada-Turbo

| Removed | Added |
|---|---|
| Temur Battle Rage | Blood Moon |
| Untimely Malfunction | Magus of the Moon |
| Grinning Ignus | Runaway Steam-Kin |
| Ancestors' Aid | Witch's Mark |
| Accelerate | Blazing Crescendo |
| Molten Duplication | Treasonous Ogre |

### Vivi-Turbo

| Removed | Added |
|---|---|
| Dualcaster Mage | Tandem Lookout |
| Molten Duplication | Ophidian Eye |
| Storm-Kiln Artist | Hullbreaker Horror |
| Dizzy Spell | Arcane Signet |
| Mishra's Bauble | Borne Upon a Wind |

### Kinnan-Optimized

| Removed | Added |
|---|---|
| Pemmin's Aura | Mirage Mirror |
| Pia, Aether Ascetic | Enduring Vitality |
| Pongify | Mental Misstep |
| Mana Drain | Mindbreak Trap |
| Whir of Invention | Borne Upon a Wind |

### Kilo-Turbo

| Removed | Added |
|---|---|
| Boros Charm | Flusterstorm |
| Dispatch | Mental Misstep |
| Spellskite | Voice of Victory |
| Open the Armory | Transmute Artifact |
| Fabricate | Urza, Lord High Artificer |
| Smothering Tithe | Winter Orb |
| Shuri, Wakandan Inventor | Drannith Magistrate |

### Yuna-Combo

| Removed | Added |
|---|---|
| Power Conduit | Swift Reconfiguration |
| Mesa Enchantress | Drannith Magistrate |
| Eidolon of Blossoms | Deafening Silence |
| Smothering Tithe | Winter Orb |

### Ral-Storm

| Removed | Added |
|---|---|
| Bonus Round | Tavern Scoundrel |
| Reiterate | Will of the Jeskai |
| Timetwister | Highway Robbery |
| Windfall | Rob the Archives |
| Arcane Signet | Springleaf Drum |

## Validation

All eight pass validate_deck.py: 100 cards, color identity, singleton, Commander
legality, preserved retained pins, and TTS import 100/100 each. Guides have 36–41
card rows each; every pictured card is in its list and the last section covers
opening hands and sequencing. SHA-256 comparison against the start-of-turn
snapshot confirms all other public decklists and guides are unchanged.

85 deck/guide regression tests and the catalog-wide Goblin-package test pass.
Full static catalog build passes: 5,005 unique TTS image URLs verified. This is
a catalog update, with no table save build or Steam upload.

The first full build found five unrelated, unpinned defaults refreshed to TRC
reprints that the external image cache returned as HTTP 404. Restore the five
previously published default printings through CardQuery using fresh Scryfall
metadata and matching oracle IDs, after verifying their exact images with the
normal Unity-user-agent checker. No source list, explicit pin or validation gate
is changed. The final full build must still validate every exported URL. The
local default selection is cached, not a permanent repair of the upstream host.

## Sources

Direct card text and legality: existing CardQuery/find_cards.py and Scryfall,
queried in this turn. EDHREC pages below explicitly filter to user-selected
Bracket 5; they are popularity observations, not competitive performance data.

- [EDHREC: krenko-mob-boss](https://edhrec.com/commanders/krenko-mob-boss/cedh)
- [EDHREC: muxus-goblin-grandee](https://edhrec.com/commanders/muxus-goblin-grandee/cedh)
- [EDHREC: zada-hedron-grinder](https://edhrec.com/commanders/zada-hedron-grinder/cedh)
- [EDHREC: vivi-ornitier](https://edhrec.com/commanders/vivi-ornitier/cedh)
- [EDHREC: kinnan-bonder-prodigy](https://edhrec.com/commanders/kinnan-bonder-prodigy/cedh)
- [EDHREC: kilo-apogee-mind](https://edhrec.com/commanders/kilo-apogee-mind/cedh)
- [EDHREC: yuna-hope-of-spira](https://edhrec.com/commanders/yuna-hope-of-spira/cedh)
- [EDHREC: ral-monsoon-mage](https://edhrec.com/commanders/ral-monsoon-mage/cedh)
- [Authored Krenko's Playground list](https://playgroup.gg/profiles/182776-dalberg87/decks/781866-cedh-krenko-mob-boss-s-playground-primer/cards)
- [Miguel's Muxus event list, October 24](https://www.spellbinder.gg/decks/muxus-goblin-grandee-h6y8v2tzxu)
- [Authored Kilo list](https://archidekt.com/decks/14810192/kilo_apogee_mind_cedh)
- [Kinnan primer and named reference lists](https://learncedh.com/decklists/kinnan)
- [Vivi primer and named reference lists](https://learncedh.com/decklists/vivi)
- [Ral primer and named reference lists](https://learncedh.com/decklists/ral)
- [Historical Zada primer; banned cards are not copied](https://tappedout.net/mtg-decks/surprise-godo-1/)
