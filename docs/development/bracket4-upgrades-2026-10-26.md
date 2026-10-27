# Bracket 4 copies — 2026-10-26

Owner request: create eight separate Bracket 4 versions, cloning existing lists
where available. **Do not alter the Bracket 3 originals.** All new files belong to
`public/zzwang/Bracket4/`, with matching `.guide` files. Stems are distinct because
catalog themes and tiers use `owner/stem` keys without the bracket.

Yuna is **Yuna, Hope of Spira**, copied from Yuna-Enchantments, not either Grand
Summoner deck. Krenko is **Krenko, Mob Boss**, copied from Krenko-Combo. No Ral list
existed, so Ral, Monsoon Mage starts from `new_deck.py`'s expensive EDHREC shell.
The existing Bracket 5 Kinnan-Combo also stays unchanged.

## Resulting lists

Lands below are true front-face lands; modal spell/lands are additional. Average
mana value is the validator's nonland figure. Power tiers are list reviews, not
measured matchup results. The Goblin lists retain narrower tutor access than the
blue or green shells and are conservatively S, rather than earning SS just from
uncapped Game Changers.

| Source | New deck | Swaps | Lands | Game Changers | Avg MV | Tier | Main improvement |
|---|---|---:|---:|---:|---:|---|---|
| Krenko-Combo | [Krenko-Turbo](../../public/zzwang/Bracket4/Krenko-Turbo.txt) | 18 | 31 | 7 | 2.23 | S | Staff/Prospector loops, the complete Snoop line and Kiki/Conscripts; fast mana, haste and recovery. |
| Muxus-Goblins | [Muxus-Turbo](../../public/zzwang/Bracket4/Muxus-Turbo.txt) | 15 | 32 | 6 | 2.18 | S | Recruiter-stacked Muxus deployments, Snoop and Kiki/Crafter; retained 35 Goblin cards. |
| Kilo-Infinite | [Kilo-Turbo](../../public/zzwang/Bracket4/Kilo-Turbo.txt) | 13 | 34 | 13 | 1.94 | SS | Mana-neutral proliferate into poison or seeded Ballista, plus independent Heliod and Scepter lines. |
| Yuna-Enchantments | [Yuna-Combo](../../public/zzwang/Bracket4/Yuna-Combo.txt) | 16 | 33 | 11 | 2.16 | SS | Hope of Spira; adds Druid/Vizier and faster access to Weaver, Heliod and Earthcraft wins. |
| Kinnan-Infinite | [Kinnan-Optimized](../../public/zzwang/Bracket4/Kinnan-Optimized.txt) | 16 | 30 | 13 | 1.96 | SS | Adds Grim Monolith, free protection, draw and faster tutors; explicit colorless-to-outlet sequencing. |
| Vivi-Spellslinger | [Vivi-Turbo](../../public/zzwang/Bracket4/Vivi-Turbo.txt) | 14 | 30 | 13 | 1.81 | SS | Breach/LED/Freeze plus Elemental or Cauldron mana into Ballista; adds free protection and fast mana. |
| EDHREC seed | [Ral-Storm](../../public/zzwang/Bracket4/Ral-Storm.txt) | 19 | 26 | 13 | 2.05 | SS | New Ral, Monsoon Mage list; protected ritual/storm and Breach, with safe transformed-Ral loop instructions. |
| Zada-Goblins | [Zada-Turbo](../../public/zzwang/Bracket4/Zada-Turbo.txt) | 13 | 30 | 7 | 2.19 | S | Retains Goblin Snoop package; adds fast mana, rituals, Empty the Warrens and a third Dualcaster copy spell. |

## Research and combo review

Compared all seven existing shells against EDHREC's missing-card and New Cards
sections, and checked current optimized commander pages. Selected cards for the
actual plan instead of following casual inclusion counts. Oracle text and legality
came through `CardQuery`/`find_cards.py`; retained cards keep their existing printing
pins. No price cap was applied.

Every Snoop deck keeps Kiki-Jiki, Torch Courier, Ringleader and Mogg Fanatic, plus
the owner's Recruiter/Muxus/Ringleader package. Each Goblin guide includes a four-card
Ringleader refill, six-hit Muxus deployment, explicit draw/shuffle prerequisites,
Snoop haste and the Recruiter-copy-to-Fanatic finish. If an exile trigger would change
the top card, activate the required sacrifices before resolving it.

Zada uses Infernal Plunge rather than an unreliable early metalcraft mox; its
creature-heavy shell has too few ordinary artifacts to count Opal as opening mana.

The guides cover resource costs and actual outlets: Kilo's Prism starts with two
counters; poison must be seeded; Heliod/Ballista starts with two counters; Weaver
needs four enchantments for Gauntlets or five for Staff. Earthcraft/Nest without
Station leaves tapped tokens rather than an immediate combat win. A tutor putting
Ballista directly into play does not supply X counters.

Vivi/Elemental's copied mana ability uses Elemental's power; the Cauldron variant
on Vivi uses Vivi's power instead. Both get a real Ballista outlet. Breach lines
budget escape fodder, and Intuition is not advertised as a guaranteed standalone
three-card assembly without recovery already available. Ral's guide transforms
away from creature-side coin-flip damage before a long loop and distinguishes
mana-neutral storm from mana-positive loops.

## Validation and preservation

All eight final lists pass `validate_deck.py`: 100 cards, Commander legality,
color identity, singleton, uncapped Bracket 4 Game Changers, retained printing pins,
and **TTS import 100/100** each. Every card row in every new guide resolves to a
card actually in that list. Each guide has 32–36 explanatory rows and ends with
opening hands and sequencing.

A SHA-256 snapshot verifies every preexisting file under `public/` is byte-identical,
including all Bracket 3 decklists and guides. Preserve original file creation
dates in the isolated checkout so the catalog does not rewrite their "added"
metadata. All 197 preexisting TTS catalog entries remain identical; the deck count
increases only from 197 to 205. Existing deck-page changes are navigation updates.

Publication checks: 91 relevant regression tests pass; the full catalog build and
`build_site.py --check` pass; **4,980 unique TTS image URLs** are verified. The initial
cold check had a Scryfall 429 and five transient image-server connection resets.
Respect the API cooldown, bulk-warm missing card metadata with the existing
`CardQuery` interface, and retry only the remaining unverified image URLs through
the normal validation cache. No image-validation bypass was used.

This is a deck/catalog publication,
with no table code change, new save version or Steam upload. The faster construction
target is protected turn-four-or-later opportunities; no goldfish percentage or
competitive tournament result is claimed.

## Exact card changes

### Krenko-Turbo

Added: Chrome Mox; Mox Diamond; Jeska's Will; Rite of Flame; Desperate Ritual; Seething Song; Underworld Breach; Samut, Hazoret's Champion; General Kreat, the Boltbringer; Rundvelt Hordemaster; Howlsquad Heavy; Goblin Welder; Springleaf Drum; Mox Opal; Gempalm Incinerator; City of Traitors; Gemstone Caverns; Goblin Cratermaker.

Removed: Massive Raid; Herald's Horn; Shared Animosity; Boggart Shenanigans; Combat Celebrant; Dragon Fodder; Krenko's Command; Mind Stone; Fellwar Stone; Swiftfoot Boots; Goblin Trashmaster; Warren Instigator; Blast Zone; Buried Ruin; Command Beacon; Castle Embereth; Hall of the Bandit Lord; Hanweir Battlements.

### Muxus-Turbo

Added: Chrome Mox; Mox Diamond; Mox Opal; Gamble; Wheel of Fortune; Desperate Ritual; Pyretic Ritual; Rite of Flame; Seething Song; Simian Spirit Guide; Battle Hymn; Goblin Welder; Wily Goblin; City of Traitors; Crystal Vein.

Removed: Blasphemous Act; Mana Geyser; Mind Stone; The Fire Crystal; Village Pillagers; Goblin Chainwhirler; Goblin Sledder; Legion Loyalist; Broadside Bombardiers; Pyre of Heroes; Buried Ruin; War Room; Mountain; Mountain; Mountain.

### Kilo-Turbo

Added: Ancient Tomb; Chrome Mox; Mox Diamond; Grim Monolith; Force of Will; Fierce Guardianship; Mystical Tutor; Rhystic Study; Cyclonic Rift; Teferi, Time Raveler; Smothering Tithe; Mox Amber; Spellskite.

Removed: Uthros, Titanic Godcore; Propaganda; Ghostly Prison; Insight Engine; Inspirit, Flagship Vessel; The Seriema; Uthros Research Craft; Unwinding Clock; Tezzeret the Seeker; Jhoira, Weatherlight Captain; Thought Monitor; Padeem, Consul of Innovation; Idyllic Tutor.

### Yuna-Combo

Added: Ancient Tomb; Gaea's Cradle; Chrome Mox; Mox Diamond; Mana Vault; Crop Rotation; Worldly Tutor; Chord of Calling; Eldritch Evolution; Carpet of Flowers; Smothering Tithe; Devoted Druid; Vizier of Remedies; Delighted Halfling; Bloom Tender; Voice of Victory.

Removed: Nesting Grounds; Overgrown Farmland; Summon: Fenrir; Summon: Knights of Round; Summon: Yojimbo; Hallowed Haunting; Calix, Guided by Fate; Greater Good; Commune with the Gods; Nature's Lore; Three Visits; Jukai Naturalist; Enduring Vitality; Beast Within; Path to Exile; Fauna Shaman.

### Kinnan-Optimized

Added: Ancient Tomb; Gaea's Cradle; Consecrated Sphinx; Seedborn Muse; Worldly Tutor; Mystical Tutor; Force of Will; Carpet of Flowers; Pia, Aether Ascetic; Grim Monolith; Chrome Mox; Mox Diamond; Training Grounds; Fellwar Stone; Forest; Island.

Removed: Turbulent Wilderness; Treasure Vault; Nezahal, Primal Tide; Tezzeret the Seeker; Drift of Phantasms; Fabricate; Misdirection; Enduring Vitality; Trophy Mage; Simic Signet; Springleaf Drum; Spellskite; Borne Upon a Wind; Dispel; Delay; Muddle the Mixture.

### Vivi-Turbo

Added: Chrome Mox; Mox Diamond; Mana Vault; Jeska's Will; Mystical Tutor; Force of Will; Fierce Guardianship; Intuition; Lion's Eye Diamond; Ancient Tomb; Samut, Tyrant of Naktamun; Agatha's Soul Cauldron; Past in Flames; Walking Ballista.

Removed: Arcane Signet; Fellwar Stone; Izzet Signet; Talisman of Creativity; Jeweled Amulet; Long-Term Plans; Step Through; Wizard's Staff; Perfected Theory; Haze of Rage; Thundering Falls; Magic Damper; Seething Anger; Windfall.

### Ral-Storm

Added: City of Brass; Mana Confluence; Fiery Islet; Shivan Reef; Riverpyre Verge; Spirebluff Canal; Mistrise Village; Otawara, Soaring City; Sulfur Falls; Force of Will; Merchant Scroll; Personal Tutor; Ponder; Preordain; Brainstorm; Consider; Samut, Tyrant of Naktamun; Cyclonic Rift; Geist of Saint Thalia.

Removed: _____ Goblin; Abandon Attachments; Highway Robbery; Rob the Archives; Recoup; Return the Favor; Twinferno; Will of the Jeskai; Wheel of Misfortune; Demand Answers; Overmaster; Vexing Bauble; Tibalt's Trickery; Daze; Gut Shot; Springleaf Drum; Quiet Speculation; Witch's Mark; Tavern Scoundrel.

### Zada-Turbo

Added: Ancient Tomb; City of Traitors; Gemstone Caverns; Chrome Mox; Mox Diamond; Infernal Plunge; Mana Vault; Desperate Ritual; Pyretic Ritual; Seething Song; Empty the Warrens; Heat Shimmer; Goblin Warchief.

Removed: Swiftfoot Boots; Hordeling Outburst; Howlsquad Heavy; Mox Amber; Runaway Steam-Kin; Impact Tremors; Krenko, Mob Boss; Mountain; Mountain; Mountain; Mountain; Mountain; Mountain.

## Sources

- [EDHREC Krenko](https://edhrec.com/commanders/krenko-mob-boss), [Muxus](https://edhrec.com/commanders/muxus-goblin-grandee), [Zada optimized](https://edhrec.com/commanders/zada-hedron-grinder/optimized).
- [EDHREC Kilo optimized](https://edhrec.com/commanders/kilo-apogee-mind/optimized), [Yuna optimized](https://edhrec.com/commanders/yuna-hope-of-spira/optimized), [Kinnan optimized](https://edhrec.com/commanders/kinnan-bonder-prodigy/optimized).
- [EDHREC Vivi optimized](https://edhrec.com/commanders/vivi-ornitier/optimized), [Ral optimized](https://edhrec.com/commanders/ral-monsoon-mage/optimized).
- [Official Commander format and brackets](https://magic.wizards.com/en/formats/commander).
