# People through mods - the catalogue

| | |
|---|---|
| Status | DRAFT 2026-09-06. Part 1: bodies and age. Part 2: traits and health conditions. Part 3, repositories and non-Workshop hosts, pending. Feeds DR-032 on the SAO side: which mods SAO requires, takes from, or declines is decided through Crucible, mod by mod. |
| Rule | Every row was read from the mod's own Workshop page (Steam rate-limited the fetch tool, so the pages were read by direct request and cross-checked against Steam's item-details API for title, app, dates and tags). No row rests on a search snippet. |
| Why it exists | The operator ruled 2026-09-06 that the county is to have children and elders, and people with the conditions that shape knowledge and memory, and that the mods supplying them become native requirements. The engine supplies none of it (below). |
| Permissions and credit | The license column records what a page states and nothing more; "none stated" is a fact, not a verdict. Permission is the operator's business and has been dealt with directly with the authors; a visible repository is usable. Nothing here argues for or against a mod on licensing grounds - only on technical ones. Integration credits through SAO's existing CREDITS.md convention (a required mod gets a hard-runtime-dependency entry, as ZombieBuddy has); no new standard. Selection goes to the operator first. |
| Scope of the search | Part 1 read the Workshop and Steam's item API, and followed repositories only where a page pointed at one. A sweep of GitHub, GitLab, Codeberg, Nexus Mods, ModDB, the Indie Stone forums and itch.io is in progress (2026-09-06) and lands as part 3. |

## What the engine holds (verified 2026-09-06 against the installed 42.20 tree and jar)

- Two human meshes, `MaleBody.x` and `FemaleBody.x`, with their
  skeletons, in `media/models_X/Skinned`; animation sets for player,
  player-avatar, player-editor, player-vehicle, zombie, zombie-crawler
  and the animals. No child, teen or elder mesh or animation set.
- `IsoGameCharacter.getAge` / `setAge` store an integer nothing in the
  jar reads; the shipped Lua calls `getAge()` only on animals and trap
  bait.
- A model instance carries a scale: `ModelInstance.scale` (public) and
  `applyModelScriptScale(String)`, the mechanism by which a calf is a
  scaled cow. A child as a scaled adult mesh with the adult's
  animations is therefore reachable from SAO's own Java bridge with no
  third-party dependency; it is the same crude path the one child mod
  takes, without its dependencies.
- The developer's stated policy, from two Steam discussion posts by
  nasKo of The Indie Stone (developer badge, read directly): June 20,
  2018 - children are "not something we want to have in the game," with
  no objection to people modding it in; September 21, 2023 - the same
  refusal, restated without justification, thread locked. Sources:
  steamcommunity.com/app/108600/discussions/0/1728701877451985354/ and
  .../3882722163303225908/.

## Child bodies

| Mod | Workshop id | Author | Adds | Build 42 standing (page) | Requires | License | Source |
|---|---|---|---|---|---|---|---|
| Growing Up - Kid mod challenge ([PZCh]) | 3701972216 | PZ Chronicles; contributors Re-Animated, Kahned, silvast | A playable child: start at 8 to 14 and grow to 18 with changing body scale, height, weight and movement; six child archetypes with traits and items; a fear system; literacy progression; age-gated skills; driving and firearm penalties; a scripted school-escape opening; child-sized infected in the world; a growth display; custom voice lines | "GROWING UP Build 42 challenge scenario"; no 42.x number given. Posted Apr 7, 2026; updated Apr 27, 2026 | [PZCh] Realism (3701964565), which requires Moodle Framework (3396446795), Tomb's Player Body Overhaul (3429790870) and [B42+] Sandbox Options (3386906181), plus a manual copy of a folder of `zombie` Java classes into the game directory | none stated | closed |

This is the only mod found that adds a child body of any kind. It is
a challenge scenario, closed and unlicensed, and its manual copy of
Java classes into the game directory is an engine patch, not a mod
dependency. The "Zombie kids" items that search engines return for
Project Zomboid queries (2832590702, 2833712631) are DayZ items and
are excluded; a third (2970602033) could not be read at all.

## Elders

No elder mesh exists, and none is needed - the operator ruled it on
2026-09-06: an elderly person is represented on the adult body by
hair, condition, behavior and age, not by a separate model. What
exists, and what matters here, is age as a system on the adult mesh:

| Mod | Workshop id | Author | Adds | Build standing (page) | Requires | License | Source |
|---|---|---|---|---|---|---|---|
| Getting Old ([B42.20] [SP/MP]) | 3643959369 | Devlin | An age and date of birth per survivor; five life stages from 12-17 to 61 and over; creation traits starting at 12, 21, 30, 45 or 70; hair and beard grey from 30; age scales endurance, fatigue, pain and stress; the elderly may stumble and fall; death of old age, optional heart attacks; sandbox options. No new meshes | "Project Zomboid Build 42.20", single- and multiplayer, does not change zombie behavior. Posted Jan 10, 2026; updated Sep 3, 2026 | none | none stated | closed |
| Aging Mod | 3486968089 | Vivi | Hair color changes with age; death of old age between 70 and 100; more sickness and faster loss of condition when old; extra effects at 80 and 90; three difficulty levels; a visual-only toggle; single-player only | Workshop tag Build 42; no build named in the text. Posted May 24, 2025; updated Jun 27, 2025 | none | none stated | closed |
| This Is How You Died (TIHYD) | 3013368173 | Dy0gu | Uses the engine's unused age field; age rises with the game's years; hair greys and whitens; death past a configurable age weighted by health traits; exposes the age to other mods; single- and multiplayer | Build 41 tag; never updated since Aug 1, 2023 | none | GPL-3.0 (stated on the page) | open: github.com/dy0gu/tihyd |
| Aging | 2982401230 | Pao, commissioned by Fematrax-21 | Hair greys with age | Build 41 tag. Posted May 29, 2023; updated Jul 14, 2023 | none | none stated | closed |
| Age Traits | 2796508003 | Mxswat | Traits Age 30, 40, 50, 60: +1 to +4 skills, -1 to -4 fitness; no body change | 2022, Build 41 | Profession Framework (1343686691) | none stated | closed |

## Babies

| Mod | Workshop id | Author | Adds | Build standing (page) | Requires | License | Source |
|---|---|---|---|---|---|---|---|
| Babies [41] | 2955134683 | Scimmia | Baby props as items: hand-held baby models, carriers, bottle, formula, nappies, a plush; the baby cries after six hours unfed and vomits if fed early; it cannot die; not in loot, spawned by admins. Items, not characters | "working on 41 only (for now)", though tagged Build 41 and Build 42. Posted Mar 30, 2023; updated May 31, 2026 | none; the addon Parent Occupation (3382884058, G.E.G.O, Dec 11, 2024) adds a Parent profession that starts with a baby and requires Profession Framework | none stated | closed |

## Adjacent, no age

Dynamic Body Shape (3066054201, Fed-cap, Build 41 to 42: physique
meshes by weight); True Model Z (3686098703, EtherealShigure and
Freylith, a Build 42 body framework; survivor and zombie height is
listed as coming); Tomb's Player Body Overhaul (3429790870; page
unreadable twice, API record: Build 41 and 42, updated Dec 25, 2025).

## What this means for DR-032 (for the Crucible after part 2)

1. A native requirement on the one child-body mod is not sound on
   technical grounds: it is a challenge scenario, dependent on four
   other mods, and it patches the game directory by hand with copied
   Java classes - an engine patch SAO cannot carry as a dependency.
2. Elders need no body work at all (ruled 2026-09-06): the adult
   mesh with grey hair from the visual layer, plus SAO's own age and
   whatever age system is chosen for condition and behavior. The age
   bands extend above 68 without a model.
3. Children are the only case that needs a smaller body, and the
   engine-native path exists: a scaled adult mesh with the adult's
   animations (the engine's own calf-from-cow mechanism), set from
   SAO's Java bridge. Crude, dependency-free, and the same thing the
   child mod does underneath.
4. Age as a system: Getting Old is Build 42.20, single- and
   multiplayer, updated this month, with no public repository found
   yet; TIHYD's repository is public (GPL-3.0 stated) but it is Build
   41 and untouched since 2023; SAO already derives its own age
   (`SAO_History.ageOf`), so the fork is between requiring an age
   system, taking what is usable from one into SAO's own, and
   extending SAO's own outright. Two things are verifiable before
   any of these: whether an age mod written for the player reaches
   SAO's off-slot people at all (its Lua is readable once
   subscribed), and which age is the one source of truth.

## Could not source

- Zombie Kids (2970602033): Steam returns its error page; the API
  returns "file not found"; game and content unverifiable.
- The projectzomboid.com FAQ and modding policy and the pzwiki FAQ:
  HTTP 403; not used.
- The forum sticky that older posts cite for the developers' refusal
  of children: not located; the 2014 and 2016 posts render as deleted
  accounts, so no staff badge can be verified for them. The two
  badged posts above stand instead.
- No public repository for Growing Up, Getting Old, Aging Mod, Aging
  or Babies.

# Part 2 - traits and health conditions (2026-09-06)

Every row was read from the mod's own Workshop page or, where Steam
throttled the reads after about twenty pages, from Steam's item
details for the same id (descriptions, tags, dates); creator names
from Steam profiles. The license column records what the page states.
Steam omits the year on current-year dates; they are rendered as 2026.

## Build 42

| Mod | Workshop id | Author | Adds | Build 42 standing (page, updated) | Requires | License (as stated) | Source |
|---|---|---|---|---|---|---|---|
| SOTO - Simple Overhaul: Traits and Occupations | 2840805724 | hea | Rebalanced vanilla traits and occupations; more than 40 new traits; 26 occupations; traits gained or lost in play (Brave; quitting smoking) | "works completely fine" in Build 42 single-player; "does not work fine" in Build 42 multiplayer (2026-03-09); a multiplayer fork exists (3763874285, Logosh, 2026-09-02, needs UCWF 3682045254) | none | modify only with permission; modpacks unaltered; copyright hea 2022-2026 | closed |
| More Traits (Legacy) | 1299328280 | HypnoToadTrance, Fajdek, MusicManiac | 90+ traits (gear, skills, infection immunity, Alcoholic); a Dynamic submod with 50+ traits earned or lost by skill level and 120 sandbox options | tagged Build 41 and 42; "no support, bugfixes, updates or compatibility patches anymore" (2026-08-29) | UCWF 3682045254 | none stated; the repository has no license file | github.com/hypnotoadtrance/MoreTraits (archived) |
| Evolving Traits World, with the More Traits continuation | 2914075159 | MusicManiac | 68 new traits; dynamic gain and loss from actions; an in-game UI; per-trait sandbox options | tagged Build 42, work in progress; a Build 41 legacy version is separate (2026-09-06); a patch exists (3638474577, pimat.studio, 2026-01-03) | KillCount 2553809727; Moodle Framework 3396446795; UCWF 3682045254 | redistribution prohibited; copyright MusicManiac 2026 | github.com/MusicManiac/EvolvingTraitsWorld (public, no license file) |
| Dynamic Traits and Expanded Moodles | 2459400130 | PepperCat, Afyrmo | Traits gained or lost by actions, skills, body, mood and survival time; trait and profession rebalance; expanded moodles; overdose, allergies, addiction progression (Alcoholic, Smoker, Anorexia) | "Build 42 - Coming Soon", still the Build 41 release (2025-04-10); a Build 42 patch exists (3733338286, NoR, 2026-05-26, needs Moodle Framework 3396446795) | Moodle Framework B41 2859296947 | copyright PepperCat 2022; republishing only under the author's account | closed |
| Authentic Dynamic Traits B42 | 3535431821 | Daisaak | Vanilla traits gained or removed by playstyle; new negatives: Alcoholic, Paranoid (light sleep, phantom sounds), ADHD (forgetful, drops items), Tourette, Sleepwalker, Afraid of Darkness, Grumpy (heart attack), Smoking cough | heading says Build 41 and 42; tagged Build 41 only (2025-12-02) | none | none stated | closed |
| Adaptive Traits | 3622328997 | Mich | 30 vanilla traits gained or lost by time or kills (Fast and Slow Reader, the phobias, Cowardly, Smoker, others) | "Game version 42.13 or newer" (2026-01-20) | none | none stated | closed |
| Traits As Skills | 3784847437 | GersonRess | Traits as leveled skills with experience; kills build Courage; Cowardly or Agoraphobia cleared on level-up; an API; a More Traits addon | tagged Build 42, work in progress; single- and multiplayer (2026-09-02) | none | none stated | documentation only: github.com/GersonRess/TAS_Docs |
| Even More Traits (42.20) | 3777663603 | Darkyosh, a port of Dr. Lalaoz's 2855320431 | over 30 traits: Insanity, PTSD, Addict, Anorexic, ADHD, Codependant, combat traits; its own stat engine | "brought up to 42.20"; single- and multiplayer (2026-08-09); the Build 41 original needs Stat Tweaks Lib 3415375593 | none | none stated; a take-down offered to the original author | closed |
| Hephas Occupations and Traits | 3256482412 | Hephaistos, Nox | occupations and skill traits with their own items; dynamic Brave and Desensitized gain, Cowardly loss | tagged Build 41 and 42; Profession Framework not needed on Build 42 (2026-09-03) | Profession Framework 1343686691 on Build 41 | "ask for permission" | closed |
| New Professions and Traits (B42) | 3744666572 | ASINSINA, ElBatu | 103 professions, 53 traits (Spanish, translated) | "Compatibility: Build 42" (2026-08-01); a Build 41 original (3596317718) | none | none stated | closed |
| Getting Old (B42.20, SP/MP) | 3643959369 | Devlin | age and birthday; five life-stage traits (12-17 to 61 and over) driving endurance, fatigue, pain, stress and stumbles; stage changes swap the traits; death past a deadly age; optional heart attacks | "Project Zomboid Build 42.20"; single- and multiplayer (2026-09-03) | none | none stated | closed |
| Aging Mod | 3486968089 | Vivi | aging to death between 70 and 100; more sickness and faster fitness loss when old; extra effects at 80 and 90; single-player only | tagged Build 42 (2025-06-27) | none | none stated | closed |
| Infirmities (B42.20) | 3579088411 | Twuben | Schizophrenia, Parkinson's, Anxiety, Narcolepsy, Scoliosis, dynamic addictions (effects not itemized on the page) | "Compatible with Build 42.20 and all prior 42 builds" (2026-07-29) | Moodle Framework 3396446795; TchernoLib 3389605231 | use, collections and extension allowed with credit; copyright Twuben 2026 | closed |
| Asthma mod | 3470657747 | DocRP | an Asthma trait: lower stamina; attacks from stress, panic, cold and heat that cost health and empty stamina; an inhaler item; excludes Smoker and Athletic | "Works on Build 42" (2025-07-04) | Moodle Framework 3396446795 | "MIT License rules: attribution required" | not published |
| Phobia Traits v3 | 3741356566 | OmarJohnny | fourteen phobia traits raising panic at their triggers: darkness, books, corpses, zombies, fire, noise, heights, vehicles, needles, plants, cooking, dirt, weight change | "Made for Project Zomboid Build 42+", work in progress (2026-06-09) | none | none stated | closed |
| Food Allergy Traits (41-42.12) | 3414814170 | TwinCrows | seafood and peanut allergies (lactose on Build 41 only): damage, nausea, anaphylactic shock, scaled by gut and illness traits | "included and working for B42" (2025-03-08) | Moodle Framework 3396446795 | none stated | closed |
| Psychology Skill | 3561213456 | WindLother | a psychology skill lowering stress, panic and unhappiness; books, a CBT workbook, breathing; nicotine and alcohol dependency with withdrawal and recovery | "Fully supports Build 41. Fully supports Build 42.20+" (2026-08-07) | none | none stated | closed |
| Sanity B42 | 3390307636 | ROCKY | a sanity value fed by needs, stress, dirt, sickness, temperature, morale and fear; low sanity brings mumbling, shaking, erratic actions | "BETA for Build 42" (2025-01-01); a Build 41 original (2883974010) | Moodle Framework (B41) listed as required | none stated | closed |
| Just Drugs - DLC | 3339758426 | Leuan | three traits, 31 drugs, addiction, withdrawal, overdose, hallucinations | "B42 and B41 compatibility" (2025-11-02) | none | none stated | closed |
| Drugs of '93 | 3784734412 | Red Jones | period drugs with come-up, crash, tolerance, addiction, withdrawal and relapse; a four-stage overdose; an Alcoholic trait planned | Build 42 only (2026-09-06) | Moodle Framework 3396446795; Moodles in lua 3395171770; Dynamic Moodles 3674800555 | collections allowed, no reupload | closed |
| N and C's Narcotics (42.20) | 3404956403 | Neely, a_COW_says | drugs with gradual effects, hangovers and overdose; eight dependency traits (benzodiazepines, cocaine, methamphetamine, MDMA, opioids, steroids, cannabis, paranoid user) gained by frequent use and lost after eighteen to twenty clean days, with tiered withdrawals | "currently only on Build 42" (2026-08-24) | none | none stated | closed |
| Hemophilia Trait | 2933878989 | Hemostaza | moderate and severe hemophilia A: external bleeding rarely stops and wounds stay open without factor VIII | "supports B42 and works in multiplayer" (2026-08-04) | none | none stated | closed |
| Alcoholic Trait (B41) | 3341274162 | (blank Steam name) | a Drinker trait: anger when sober, then headache, sleeplessness and boredom feeding depression; sandbox timings | tagged Build 41 and 42, no Build 42 text (2026-03-03) | none | none stated | closed |
| The Only Cure (B42.20) | 3580276809 | Pao | amputate infected limbs; wound care; hook and arm prostheses; a prosthesis-familiarity perk; a missing hand blocks two-handed weapons | "[B42.20]"; single- and multiplayer, host mode unsupported (2026-08-23); a Build 41 version (3236152598) | none | GPL-3.0 | github.com/ZioPao/The-Only-Cure |
| Myopia and Hyperopia traits with Functioning Glasses | 2698765788 | Onkeen | Myopic and Hyperopic traits: blur without glasses; cannot read books or forage without glasses; glasses fall, break and are repaired | "[b41/b42]"; Build 42 personal glasses (2024-12-27) | none | none stated | closed |
| Hearing Aid (B42.13+) | 3697034338 | Zed | a tiered hearing-aid item: removes Hard of Hearing, turns Deaf into Hard of Hearing, boosted gives Keen Hearing | tagged Build 42 (2026-04-19); a fork of 2931424725 (Build 41) | none | none shown | github.com/zed-0xff/PZ_HearingAid |
| Extensive Health Rework Evolved | 3726328119 | Frozen_Heart | diseases with overlapping symptoms; an immune system; blood and transfusion; a disease handbook and medical knowledge; a surgeon perk | "42.20" listed as working; multiplayer "will have bugs" (2026-08-30) | none | none stated | closed |
| Realistic Disease Mod (B42 stable) | 3629659534 | KingYufka | multi-day diseases with hallucinations and neurological symptoms; an immune system; blood sugar; diabetes "not yet available" | "What's supported: Build 42" (2026-08-15) | TchernoLib 3389605231 | "ask for permission" | closed |

## Build 41 only

| Mod | Workshop id | Author | Adds | Standing (page, updated) | Requires | License (as stated) | Source |
|---|---|---|---|---|---|---|---|
| More Simple Traits | 2792245343 | hea | +1 skill traits; Optimist, Depressive, Panic Attacks, Allergic, Weather Sensitive, Owl and Lark sleep, Alcoholic | single- and multiplayer 41.71+ (2023-06-30) | none | the same terms as SOTO | closed |
| Expanded Traits | 2730251452 | Draco | Alcoholic and Opiate Addict (withdrawal, detox); Heart Palpitations (daily beta blockers); Fibromyalgia; Chronic Gout; Chronic Kidney Stones; ADHD (no skill-book gains without beta blockers) | tagged Build 41 (2022-01-27) | none | modpacks permitted | closed |
| Neurodiverse Traits | 2754581597 | Mxswat | ADHD (daily hyperfocus or hypofocus swapping the learner, reader, organized and dexterity traits; Adderall); Bipolar I; Tourette; Alzheimer's (each day, each skill has a 50 percent chance to lose 2.5 percent of its experience) | tagged Build 41 (2022-06-06) | Profession Framework 1343686691 | none stated | github.com/mxswat/pz-neurodiverse-traits (public, no license file) |
| Schizophrenia Trait Mod | 2711720885 | Mistor Love | false sounds, stress-linked attacks, night terrors, hallucinated zombies, a meltdown at a comrade's death; chlorpromazine | "Working on it" for Build 42 (2023-02-11) | none in the description | no edits or republishing; modpacks with credit | closed |
| Custom Traits Mod | 3408520770 | 0x00sec | Dyslexia (reading a quarter slower, a tenth less experience), Over Thinker, Nightmares (waking in panic), Heavy Sleeper, Day Dreamer | tagged Build 41 (2025-02-06) | none listed | none stated | closed |
| Diabetes | 3354126057 | Alex | type 1 (a trait) and type 2; glucose from -3 to +3 with stamina loss, blurred vision and health decline; a glucometer; food labels; remission after three normal days | tagged Build 41 (2024-10-24) | none in the description | none stated | closed |
| Health Plus | 2960476396 | spoon | lasting complications with random pain; may gain Prone to Illness or Slow Healer; cigarette and alcohol addiction; a Crazy trait that hears voices | tagged Build 41 (2023-06-13) | none in the description | none stated | closed |
| Blind Trait Mod | 546189296 | Onkeen | Blind: a tiny sight frame, cannot read any books, echolocation by calling out, a shader | "remain a b41 mod until further notice" (2022-09-24) | none in the description | none stated | closed |
| Immersive Blind Trait | 3121062639 | marley-star7 | Blind: shouting lights the world briefly; the blind cannot read; scales with the hearing traits | tagged Build 41 (2024-01-27) | none in the description | "basically entirely open, just credit" | closed |
| Blind without glasses | 2921510330 | Kees | without its glasses no foraging or reading, All Thumbs, blur; glasses drop and break | tagged Build 41 (2023-07-27) | none in the description | none stated | closed |
| This Is How You Died | 3013368173 | Dy0gu | ages with the years survived; death past an age weighted by weight, smoking and luck; grey hair; trait loss planned | tagged Build 41 (2023-08-01) | none | GPL-3.0 (repository) | github.com/Dy0gu/TIHYD |
| The Alcoholic | 2679739572 | axxessdenied | a four-point dynamic Alcoholic trait with four withdrawal phases up to a risk of death | "41.xx compatible" (2024-08-27) | none in the description | MIT | github.com/axxessdenied/thealcoholic |

## The vanilla traits, classified

From the installed 42.20 files (`Translate/EN/UI.json`,
`character_traits.txt`). KNOWLEDGE = bears on what a person can
know or take in; LIVING = bears on habits and what they do. None
bears on MEMORY: vanilla has no trait that removes what a person
already holds; its learning traits change the rate of acquisition
only.

| Key | Name (cost) | Bears on | The game's own description |
|---|---|---|---|
| illiterate | Illiterate (-10) | KNOWLEDGE | cannot read any books or in-world text |
| slowreader | Slow Reader (-2) | KNOWLEDGE | takes longer to read books and other literature |
| fastreader | Fast Reader (+2) | KNOWLEDGE | takes less time to read books |
| slowlearner | Slow Learner (-6) | KNOWLEDGE | decreased experience gains |
| fastlearner | Fast Learner (+6) | KNOWLEDGE | increased experience gains |
| deaf | Deaf (-12) | KNOWLEDGE | cannot hear sound |
| hardofhearing | Hard of Hearing (-4) | KNOWLEDGE | smaller perception radius, smaller hearing range |
| keenhearing | Keen Hearing (+6) | KNOWLEDGE | larger perception radius |
| shortsighted | Short Sighted (-2) | KNOWLEDGE | smaller view distance; slower visibility fade; sights less effective |
| eagleeyed | Eagle Eyed (+4) | KNOWLEDGE | faster visibility fade; higher visibility arc; sights more effective at range |
| pacifist | Reluctant Fighter (-5) | KNOWLEDGE | decreased combat experience gains |
| asthmatic | Short of Breath (-5) | LIVING | faster endurance loss |
| pronetoillness | Prone to Illness (-4) | LIVING | more prone to disease; faster zombification |
| weakstomach | Weak Stomach (-2) | LIVING | higher chance of food illness |
| irongut | Iron Gut (+2) | LIVING | less chance of food illness |
| insomniac | Restless Sleeper (-6) | LIVING | slow loss of tiredness while sleeping |
| needsmoresleep | Sleepyhead (-4) | LIVING | needs more sleep |
| needslesssleep | Wakeful (+3) | LIVING | needs less sleep |
| nightowl | Night Owl (0) | LIVING | requires little sleep; stays alert even when sleeping |
| smoker | Smoker (-3) | LIVING | unhappiness rises without tobacco; stress and unhappiness fall after smoking |
| desensitized | Desensitized (0) | LIVING | far less prone to panic; ignores discomfort |
| agoraphobic | Agoraphobic (-4) | LIVING | panics outdoors |
| claustrophobic | Claustrophobic (-4) | LIVING | panics in small rooms |
| hemophobic | Fear of Blood (-5) | LIVING | panics at first aid on self; cannot treat others; stressed when bloody |
| cowardly | Cowardly (-2) | LIVING | especially prone to panic |
| brave | Brave (+4) | LIVING | less prone to panic |
| adrenalinejunkie | Adrenaline Junkie (+4) | LIVING | moves faster when highly panicked |
| obese | Very High Weight (0; fitness -2) | LIVING | reduced running speed, very low endurance, prone to injury |
| overweight | High Weight (0; fitness -1) | LIVING | reduced running speed, low endurance, prone to injury |
| underweight | Low Weight (0; fitness -1) | LIVING | low strength, low endurance, prone to injury |
| emaciated | Emaciated (-10) | LIVING | low strength, low endurance, prone to injury |
| feeble | Weak (-6; strength -2) | LIVING | less knockback; decreased carrying weight |
| weak | Puny (-10; strength -5) | LIVING | far less knockback; extremely small carrying weight |
| unfit | Unfit (-10; fitness -4) | LIVING | very low endurance and regeneration |
| fit | Fit (+6; fitness +2) | LIVING | no description string shipped; grants fitness |
| athletic | Athletic (+10; fitness +4) | LIVING | faster running; runs longer without tiring |
| thinskinned | Thin-skinned (-8) | LIVING | higher chance of scratches and bites |
| thickskinned | Thick-skinned (+8) | LIVING | lower chance of scratches and bites |
| slowhealer | Slow Healer (-3) | LIVING | recovers slowly from injury and illness |
| fasthealer | Fast Healer (+6) | LIVING | recovers quickly from injury and illness |
| resilient | Resilient (+4) | LIVING | less prone to disease; slower zombification |

## Notes on part 2

- Memory: no Build 42 mod found removes knowledge a person already
  holds. The nearest are Build 41: the Alzheimer's trait in
  Neurodiverse Traits (daily loss of skill experience), Dyslexia in
  Custom Traits, and the ADHD forgetfulness in Authentic Dynamic
  Traits (rendered as dropped items). What Build 42 has bears on
  attention, substances, sleep and the senses.
- Frameworks recur as dependencies: Moodle Framework (3396446795),
  UCWF (3682045254), TchernoLib (3389605231), the Moodles-in-lua and
  Dynamic Moodles pair for Drugs of '93. Requiring a mod inherits
  its frameworks.
- Excluded: Amputations RP 2986581203 (cosmetic props);
  starting-injury packs 3634630898 and 3094590007; infection traits
  3400049129 and 3493150396; Murdock Blind Trait 2908975227 and Blood
  Sugar 3017146233 (Build 41 variants of listed rows).

## Could not source (part 2)

- Dementia (3176439783, carsakiller): the page is banner images
  with no text, file size zero, a multiplayer tag only, updated
  2024-03-11. Nothing to catalogue.
- Schizophrenia Trait (B42, not maintained; 3434202913) and Zombie
  Phobia (3732781009): Steam's item details return "not available";
  index only.
- Scotty's Mental Health Expansion (Depression, Anxiety, PTSD,
  Insomnia, Psychosis, OCD; MIT; targets 41.78.16 and later): on
  GitHub only, no Workshop id; part 3 follows it.
- SilverCraft (667365379): the index describes a planned diabetes
  trait; the page was not read.
- SOTO and New Professions and Traits keep their trait lists in
  discussions or images; not itemized.
