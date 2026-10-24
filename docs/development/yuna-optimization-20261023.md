# Yuna deck optimization — 2026-10-23

Scope: only **zzwang/Yuna-Summoner** (Yuna, Grand Summoner) and
**zzwang/Yuna-Enchantments** (Yuna, Hope of Spira), at owner request. Baseline
`d0a42b72`. Do not confuse either with kupo7/Yuna-Counters, which is unchanged.
The owner asked for maximum power within the existing Bracket 3 house rules,
without a budget limit, and detailed guides. Neither deck changes commander,
filename or bracket. Both original lists were unpinned; no printing choices
were removed from retained cards.

## Result and limits

| Deck | Mana sources | Nonland MV before → after | Game Changers | Tutor cards reaching combo pieces | Guide |
|---|---|---|---|---|---|
| Yuna-Summoner | 33 lands + 2 MDFCs | 2.37 → 1.88 | Enlightened Tutor, Worldly Tutor, Rhystic Study | 15, with different predicates and costs | 42 card/chain rows; roughly 2,800 words |
| Yuna-Enchantments | 33 lands + 2 MDFCs | 3.14 → 2.46 | Enlightened Tutor, Survival of the Fittest, Serra's Sanctum | 12, with different predicates and costs | 43 card/chain rows; roughly 3,200 words |

Both validate: 100 cards, correct identity, singleton, Commander legality,
3/3 Game Changers, no named mass land denial and TTS import 100/100. Two added
lines were freshly checked by the importer for Grand Summoner and four for
Hope; other lines use the importer's known-good cache. Guide references all
belong to their lists (45 distinct row references for Grand, 47 for Hope).
Twenty-three theme/tier/guide tests pass. Finite mana/counter arithmetic was
checked for the described loops; no game simulation or empirical win rate is
claimed. Conditional opposing card draws are not free resources in the guides.

Both move from A to **S as a structural catalog assessment**, using the existing
tier definition: compact finishes, redundant engines, many relevant tutors and
cheap protection under the three-Game-Changer cap. This is NOT certification of
the separately requested 80% turn-six goldfish target. Include these lists in
future measured consistency work rather than treating the new S tags as proof.

## Grand Summoner choices

Replace the fair counter-doubling and high-cost combat package with cheap mana,
three-mana-or-cheaper tutor creatures, haste on demand and independent finishes.
The primary counter engine is Yuna plus either blue untap Aura: every tap/untap
banks another delayed entry-counter effect for the next creature spell, so a
zero-mana Ballista can enter with at least 120 counters. It does not need a
five-mana doubler or an already productive second mana creature.

Heliod/Ballista is an independent two-card damage loop. Devoted Druid pairs with
Swift Reconfiguration or Vizier; Incubation Druid and Kami work with the Auras
or Graftmage at the documented thresholds. Tender/Elder provide further mana
engines using the same untappers. Ballista, Thrasios, Staff, large-X Finale and
Cauldron's graveyard recovery cover different outlet access states. Unlimited
mana is never labeled a kill without an accessible outlet/converter.

The two new Game Changer tutors replace Rift and Tithe; Rhystic stays for cards.
Fifteen tutor cards include top-deck, hand, direct-deployment, transmute and
sacrifice/discard tutors; they are not fifteen equivalent free copies. The guide
states each predicate, resource payment, readiness and cast-versus-put limit.
Keep three basics, add five untapped duals and two fetches, and replace the
always-tapped triome. Sink and Recovery provide useful spells in mana slots.
Pia and Formidable Speaker provide recent direct-to-hand access; Nature's Rhythm
adds a reusable creature search. Older redundant body buffs lost their slots.

## Hope of Spira choices

Keep enchantress casting, constellation returns, finality management and the
strongest Summon targets. Add three genuinely different finishing paths:
Heliod/Ballista, Earthcraft/Nest/Station and Weaver/Gauntlets or Staff into
Ballista. Earthcraft's fresh-token cost works through creature-activation hate;
Station still needs artifact activations. The guide identifies both kinds of
hate and the removal available, rather than calling any line disruption-proof.

Survival both searches creatures and discards Summons for Yuna. Pia can discard
any card and find enchantments; Formidable and Fauna find creatures. Rumble and
Commune filter while seeding the graveyard. Yuna can return missing noncreature
enchantments too; she need not be cast before the independent combos work.
Sanctum replaces a colorless hand-size land. Sanctum and Survival take the old
Tithe/Protection Game Changer slots; Enlightened Tutor stays. The deck has 27
enchantments and seven basic lands, with eight fetches and 35 total mana sources.

Remove the slow redundant top end and Solemnity. Counter prevention shuts off
Saga lore and Ballista counters as well as finality, so it actively conflicts
with the revised finish. Keep Power Conduit and Nesting Grounds, explaining
that Conduit can respond to the last chapter and Grounds cannot. Bahamut,
Knights, Fenrir and Yojimbo remain as purposeful Summons, not mandatory casts
before a combo. Replenish rebuilds without finality, but returned Auras cannot
attach to creatures entering in that same batch.

## Rules corrections in the rewritten guides

- Sage's heroic ability triggers on a targeting spell being cast; it does not
  generate counters simply from entering. The old claimed repeatable extra-turn
  line had no legal repeatable source of five counters.
- Tender's single blue pays the untap. Its loop banks green/white rather than
  unlimited blue; those colors can still pay Ballista or generic converters.
- Kami's replacement effect does not add a counter to its own entry. Grand
  Summon alone makes it a power-three Kami, sufficient for the Graftmage line.
- Ballista normally needs two counters before the Heliod loop. An unboosted
  last-counter Ballista dies before lifelink can reload it. Yuna, Hope of Spira
  does not grant lifelink to an ordinary artifact Ballista.
- Swift keeps Druid's abilities; not being a creature prevents the negative
  toughness death and removes creature summoning-sickness restrictions. Do not
  crew the vehicle after accumulating lethal negative counters.
- Finale finds one creature. An ordinary free zero-counter Ballista dies, while
  Finale's X-at-least-ten temporary toughness bonus can preserve it long enough
  to add counters with an already available mana engine.
- A Saga's last chapter can resolve after a lore counter is removed in response.
  Moving lore later at sorcery speed is too late to prevent the sacrifice.
- Finality replaces a trip to the graveyard with exile. Indestructible does not
  bypass sacrifice or that replacement, and normal dies triggers do not fire
  when the creature was exiled instead.
- Returning an Aura does not target its chosen attachment, so a preexisting
  shrouded Weaver may receive one through Yuna/Replenish if otherwise legal.
  Casting an Aura or targeting Weaver with Staff still conflicts with Grove.

## Research and validation sources

Read EDHREC's normal, new and trending sections for both commanders using
`find_inspiration.py`, searched recent low-cost mana/tutor/draw options with
`find_cards.py --since 2025 --no-gc`, and read exact named Oracle text through
the project's CardQuery-backed tools. Inclusion is a checklist, not a power
ranking. Rejected the six-mana Kwia, slower conditional Treasure/draw options and
the currently not-Commander-legal Inner Light rather than adding new cards merely
because they are new. All selected cards pass current legality validation.

- [Grand Summoner EDHREC](https://edhrec.com/commanders/yuna-grand-summoner)
- [Hope of Spira EDHREC](https://edhrec.com/commanders/yuna-hope-of-spira)
- [Wizards FINAL FANTASY release notes](https://magic.wizards.com/en/news/feature/final-fantasy-release-notes): both Yunas and finality.
- [Wizards FINAL FANTASY mechanics](https://magic.wizards.com/en/news/feature/final-fantasy-mechanics): Saga chapters and sacrifice timing.
- [Wizards March of the Machine release notes](https://media.wizards.com/2023/downloads/MOM_Release_Notes/EN_MTGMOM_ReleaseNotes_20230412.pdf): Kami's own-entry exception.
- [Wizards Neon Dynasty release notes](https://magic.wizards.com/en/news/feature/kamigawa-neon-dynasty-release-notes-2022-02-09): Swift retains abilities and changes card types.
- [Grand Summoner / Freed line](https://commanderspellbook.com/combo/4222-6566/): corroborates the delayed-counter engine, not a measured win rate.

## Scoped publication verification

Verified 166 unique exported TTS image URLs: nine downloaded and validated, 157
trusted through recent successful checks. Both payloads contain 99 library cards
and the correct standalone commander. Source/published lists and every guide
section match; all referenced local thumbnails and mana symbols exist. Preserve
all 189 unrelated catalog records and spawn payloads, including kupo7's Yuna,
and preserve both original added dates. Music metadata adds only Devoted Druid
and Vizier colors, retaining every existing entry. No audio or table runtime
changes and no Steam upload are needed; the existing table imports the new data.

## Exact source changes

The following changes include mana-source and utility-slot adjustments, not just
nonland swaps. Preserve the stable deck paths so existing catalog links work.

### Yuna-Summoner

- Branching Evolution → Enlightened Tutor
- Bristly Bill, Spine Sower → Worldly Tutor
- Counterspell → Heliod, Sun-Crowned
- Cyclonic Rift → Devoted Druid
- Damning Verdict → Swift Reconfiguration
- Doubling Season → Vizier of Remedies
- Eternal Witness → Vigean Graftmage
- Farseek → Faeburrow Elder
- Fathom Mage → Pia, Aether Ascetic
- Forgotten Ancient → Formidable Speaker
- Gyre Sage → Fauna Shaman
- Hangarback Walker → Recruiter of the Guard
- Hardened Scales → Drift of Phantasms
- Herald of Secret Streams → Green Sun's Zenith
- Inspiring Call → Nature's Rhythm
- Kalonian Hydra → Chord of Calling
- Kutzil, Malamet Exemplar → Sylvan Library
- Maester Seymour → Pact of Negation
- Ouroboroid → Flusterstorm
- Ozolith, the Shattered Spire → Nature's Claim
- Path to Exile → Concordant Crossroads
- Rikku, Resourceful Guardian → Llanowar Elves
- Sage of Hours → Fyndhorn Elves
- Smothering Tithe → Elvish Mystic
- Sphere Grid → Avacyn's Pilgrim
- The Great Henge → Mox Amber
- The Ozolith → Staff of Domination
- Tidus, Yuna's Guardian → Eldritch Evolution
- Arcane Signet → Bala Ged Recovery
- Terrasymbiosis → Endurance
- Forest → Botanical Sanctum
- Forest → Yavimaya Coast
- Forest → Veil of Summer
- Forest → Scalding Tarn
- Island → Sink into Stupor
- Island → Adarkar Wastes
- Plains → Brushland
- Plains → Razorverge Thicket
- Spara's Headquarters → Arid Mesa

Source SHA-256: `7f5250b76766eb39c1481caec33d6e29ebe65ba8ff1f319d9f02a32ae4dc7a35`.

### Yuna-Enchantments

- Arcane Signet → Heliod, Sun-Crowned
- Courser of Kruphix → Walking Ballista
- Darksteel Mutation → Earthcraft
- Dryad of the Ilysian Grove → Squirrel Nest
- Exploration → Blasting Station
- Ghostly Prison → Gauntlets of Light
- Greater Auramancy → Staff of Domination
- Herald of the Pantheon → Survival of the Fittest
- Karametra, God of Harvests → Green Sun's Zenith
- Lightning Greaves → Finale of Devastation
- Mirari's Wake → Fauna Shaman
- Nyxbloom Ancient → Pia, Aether Ascetic
- Ondu Spiritdancer → Formidable Speaker
- Overlord of the Hauntwoods → Ranger-Captain of Eos
- Satyr Enchanter → Grand Abolisher
- Sigil of the Empty Throne → Silence
- Smothering Tithe → Veil of Summer
- Soaring Lightbringer → Force of Vigor
- Solemnity → Nature's Claim
- Sphere of Safety → Touch the Spirit Realm
- Starfield of Nyx → Malevolent Rumble
- Summon: Ixion → Commune with the Gods
- Summon: Magus Sisters → Greater Good
- Summoner's Grimoire → Seal of Cleansing
- Teferi's Protection → Llanowar Elves
- Weaver of Harmony → Avacyn's Pilgrim
- Nylea's Colossus → Lotus Petal
- Esper Origins → Esper Sentinel
- Forest → Nature's Rhythm
- Forest → Misty Rainforest
- Forest → Verdant Catacombs
- Forest → Wooded Foothills
- Plains → Witch Enchanter
- Plains → Arid Mesa
- Plains → Flooded Strand
- Plains → Marsh Flats
- Reliquary Tower → Serra's Sanctum
- Ishgard, the Holy See → Eiganjo, Seat of the Empire
- Lush Portico → Horizon Canopy
- Canopy Vista → Razorverge Thicket
- Nykthos, Shrine to Nyx → Prismatic Vista
- Strength of the Harvest → Bala Ged Recovery

Source SHA-256: `7d6c4c956a448e548010c17403d6f0669a281f39273f696b60330b762c6dd3f6`.
