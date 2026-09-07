# People through mods - the catalogue

| | |
|---|---|
| Status | DRAFT 2026-09-06. Part 1: bodies and age. Part 2: traits and health conditions. Part 3: repositories and non-Workshop hosts. Feeds DR-032 on the SAO side: which mods SAO requires, takes from, or declines is decided through Crucible, mod by mod. |
| Rule | Every row was read from the mod's own Workshop page (Steam rate-limited the fetch tool, so the pages were read by direct request and cross-checked against Steam's item-details API for title, app, dates and tags). No row rests on a search snippet. |
| Why it exists | The operator ruled 2026-09-06 that the county is to have children and elders, and people with the conditions that shape knowledge and memory, and that the mods supplying them become native requirements. The engine supplies none of it (below). |
| Permissions and credit | The license column records what a page states and nothing more; "none stated" is a fact, not a verdict. Permission is the operator's business and has been dealt with directly with the authors; a visible repository is usable. Nothing here argues for or against a mod on licensing grounds - only on technical ones. Integration credits through SAO's existing CREDITS.md convention (a required mod gets a hard-runtime-dependency entry, as ZombieBuddy has); no new standard. Selection goes to the operator first. |
| Scope of the search | Parts 1 and 2 read the Workshop and Steam's item API, and followed repositories only where a page pointed at one. Part 3 swept GitHub (keyword, topic and code search), GitLab, Codeberg, Nexus Mods (every listing page), ModDB, the Indie Stone forums and itch.io. |

## What the engine holds (verified 2026-09-06 against the installed 42.20 tree and jar)

- Two human meshes, `MaleBody.x` and `FemaleBody.x`, with their
  skeletons, in `media/models_X/Skinned`; animation sets for player,
  player-avatar, player-editor, player-vehicle, zombie, zombie-crawler
  and the animals. No child, teen or elder mesh or animation set.
- `IsoGameCharacter.getAge` / `setAge` store an integer nothing in the
  jar reads; the shipped Lua calls `getAge()` only on animals and trap
  bait.
- CORRECTED 2026-09-06, the same evening. A model instance carries a
  public `scale` field, filled from the model script by
  `applyModelScriptScale`, and an earlier draft here called it the
  engine-native path to a child body. The jar says otherwise: nothing
  in the character render path reads `ModelInstance.scale` - its only
  reader is the vehicle class - and `ModelScript.scale` is read only
  by the drawers of world objects and items. A calf is not a scaled
  cow; it is its own mesh (`Calf_Skeleton_NoHead.x` is in the tree).
  TOTC (part 3) sets `modelInstance.scale` from Lua and its README
  says its zombies are child-sized; the bytecode gives that write no
  effect on a character, and the class is not exposed to Lua in the
  vanilla exposer either. The claim is withdrawn until someone sees
  it on screen. What remains true: per-character scaling of a human
  body exists in this engine only where the animation player's bone
  transforms are changed - which is exactly what Realism does by
  replacing that class, and what SAO's own Java agent could do by
  instrumenting it at load. That is a real piece of work, not a
  field write.
- The developer's stated policy, from two Steam discussion posts by
  nasKo of The Indie Stone (developer badge, read directly): June 20,
  2018 - children are "not something we want to have in the game," with
  no objection to people modding it in; September 21, 2023 - the same
  refusal, restated without justification, thread locked. Sources:
  steamcommunity.com/app/108600/discussions/0/1728701877451985354/ and
  .../3882722163303225908/.

## Child bodies

On the source question (asked by the operator 2026-09-06): a
Workshop mod's Lua is on disk for anyone subscribed, so Growing Up's
Lua is readable that way (it is not subscribed here); what has no
source is the folder of compiled `zombie` Java classes it asks the
player to copy into the game directory, and that mechanism - not
availability - is the objection: it replaces engine classes, so it
breaks on every game update and conflicts with anything else that
touches the same classes. The scaled-mesh path below needs none of
it.

| Mod | Workshop id | Author | Adds | Build 42 standing (page) | Requires | License | Source |
|---|---|---|---|---|---|---|---|
| Growing Up - Kid mod challenge ([PZCh]) | 3701972216 | PZ Chronicles; contributors Re-Animated, Kahned, silvast | A playable child: start at 8 to 14 and grow to 18 with changing body scale, height, weight and movement; six child archetypes with traits and items; a fear system; literacy progression; age-gated skills; driving and firearm penalties; a scripted school-escape opening; child-sized infected in the world; a growth display; custom voice lines | "GROWING UP Build 42 challenge scenario"; no 42.x number given. Posted Apr 7, 2026; updated Apr 27, 2026 | [PZCh] Realism (3701964565), which requires Moodle Framework (3396446795), Tomb's Player Body Overhaul (3429790870) and [B42+] Sandbox Options (3386906181), plus a manual copy of a folder of `zombie` Java classes into the game directory | none stated | closed |

This is the only mod found that adds a child body of any kind. It is
a challenge scenario, closed and unlicensed, and its manual copy of
Java classes into the game directory is an engine patch, not a mod
dependency. The "Zombie kids" items that search engines return for
Project Zomboid queries (2832590702, 2833712631) are DayZ items and
are excluded; a third (2970602033) could not be read at all.

## What Getting Old does, read from its source (for the port)

`ClientAgeInit.lua` hooks `OnPlayerUpdate` and `OnGameStart` and acts
on `getPlayer()` only - the local player; nothing reaches other
`IsoPlayer` objects. Age and birthday live in the player's modData
(`Age`, `birthDay`, `birthMonth`, `birthYear`, with `_AgeAssigned`
and `_AgeClientInit` flags); the assignment happens server-side.
`AgeEffects.lua` is written against a passed character
(`AgeSystem.apply(player)`, `AgeSystem.updatePlayerHair(player)`),
which is what makes the port straightforward: called per SAO person
with SAO's age in the same modData key, it does the rest. Its
effects: under 30, small per-tick gains (endurance up, fatigue and
pain down, 0.015 at a 60 percent chance); 30 to 69, the reverse plus
stress (0.010); 70 and over, larger losses (0.02), hair greying from
30 on a fifty-year blend toward white through `setHairColor` and
`setBeardColor`, a death-of-old-age roll from 80 (base 0.002 scaled
by how far past 70), an accelerated decline once dying, and
stumbling through `stats:setTripping(true)`. Multiplayer sync by
`transmitModData` and `transmitVisual`. `AgeGroups.lua` names five
stages: Zoomer 12-17, Young 18-25, Adult 26-40, Middle 41-60,
Elderly 61-90.

## What Growing Up does, read from its files (2026-09-06, subscribed and read)

**The body.** Growing Up never touches a model itself. Each day it
writes a height scale into the player's mod data
(`md.rsf.heightScale`; display height over 170 cm, 0.753 at age 8,
1.0 at 18 on a slow-then-fast curve) and, on birthdays, a set of ten
bone-group sliders for child proportions (at 8: head +13 percent,
torso +4, hands +6, fading to nothing by 14). Realism V4 applies
them every tick through `ModelManager.setUniformScale`,
`setBoneScaleOverride` and `setHeightScaleOverride` - static methods
that exist only in Realism's replacement `ModelManager` (55 public
members added to the engine's), backed by Realism's own
`zombie.modelz.BoneScaleApplicator` inside replaced copies of the
animation player, the animated model, the model instance, the model
slot renderer, the human visual, the texture creator, the model
script and the Lua exposer. Forty-one engine classes in all, built
for 42.17-42.18 and copied over the installed 42.20; the replacement
`ModelManager` lacks two public members the installed one has and
`ItemContainer` lacks three - the mark of a different game revision.
Speed follows age (0.70 at 8 to 1.00 at 18, plus 0.15 sprinting);
weight runs 25 to 70 kg, with the Java nutrition told a floor of 60
kg so vanilla hunger and emaciation do not punish a child's body;
hair is policed (no beards, a child hair pool). Child zombies get
the same treatment through `md.GU_KidZombie` and Realism's zombie
preset registry.

**Growth.** Forty-five game days per year by default (configurable),
start at 8 to 14, adult at 18. Birthdays raise Strength and Fitness
floors to 5 and 5 by 18, fire archetype milestones (traits removed
at ages: Short Sighted at 10, Feeble at 14, Slow Learner at 14 or
16, Cowardly at 16, Hearty Appetite at 12 or 18, the child trait at
18), and growth spurts spike hunger.

**Fear.** A panic floor of 55 at 8 falling linearly to 0 at 18,
lowered by half a point per zombie killed; a first kill spikes panic
by 30; night terrors add panic from 22:00 to 05:00 (20 under 12, 10
at 12 to 14, none from 15); a carried teddy bear lowers the floor
and lets the child sleep through mild panic; a panicked sleeper can
wake screaming.

**Skills.** Experience is scaled by age (a quarter under 10, half to
14, full after; Strength, Fitness and Sprinting exempt); no hard
skill locks remain; archetypes may override.

**Literacy - the part that maps straight onto the scoping index.**
Children start illiterate (the Nerd excepted). Only easy reads -
comics, magazines, newspapers - are allowed; fifty of them grant
Slow Reader and a sticky literacy; a hundred books remove Slow
Reader; two hundred and fifty grant Fast Reader. The gate sits on
`ISReadABook.isValid`. This is the "read" provenance path opening
with age, written as play.

**Driving** from 10 with an adaptation curve; a mechanics manual
unlocks it earlier.

**Archetypes.** Scout, Jock, Nerd, Shy, Bully, Crybaby - each a set
of traits, starting perks, items (the vanilla children's school bag,
a teddy bear), clothing, milestones.

**What SAO can take natively, with the author's permission as the
operator has settled it:** the age curves for speed and weight; the
fear model by age; the literacy progression; the experience throttle
and the birthday floors; the archetypes as household roles; the hair
rule and the children's items. **What it cannot take without
changing the renderer:** any change of body size or proportion - the
vanilla renderer reads no per-character scale (corrected above), so
a child body needs SAO's own Java agent to instrument the animation
player at load, the route the javaagent already has, and a separate
and heavy piece of work.

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
   multiplayer, updated this month, and its full source is public
   (part 3); TIHYD's repository is public (GPL-3.0) but Build 41 and
   untouched since 2023; Pao's Aging has a public GPL-3.0 repository
   with a Build 42 folder in progress. SAO already derives its own
   age (`SAO_History.ageOf`), so the fork is between requiring an
   age system at runtime, taking its mechanics into SAO's own, and
   extending SAO's own outright. Two things are verifiable before
   any of these: whether an age mod written for the player reaches
   SAO's off-slot people at all (the source is readable now), and
   which age is the one source of truth.

# Ruled 2026-09-06 (Crucible, after part 3)

1. **Age: Getting Old's mechanics come into SAO.** Its source is
   public; SAO's own age stays the one source of truth and the
   life-stage effects run natively on SAO's people, credited through
   CREDITS.md. No runtime dependency. (Verification before the port:
   how the mod attaches to a character, so the port attaches to
   SAO's off-slot people.)
2. **Memory and cognition: both.** The Build 42 condition mods are
   required at runtime for the conditions players see - Infirmities,
   Even More Traits, and Humans: Are Weak as it fills in - with their
   frameworks; and the memory conditions are ported into SAO as its
   own: the Alzheimer's, ADHD and Bipolar traits of Neurodiverse
   Traits, Dyslexia from Custom Traits, Scotty's Mental Health
   Expansion's six conditions, and the Build 42 ADHD Trait. These
   feed the decay rule in who-knows-what.md.
3. **Substances and habits: the dependency model comes into SAO's
   habits** (the society arc's S6): the eight-dependency pattern of N
   and C's Narcotics and the period set of Drugs of '93 inform SAO's
   own; The Alcoholic and Just Drugs are taken from. No dependency.
4. **Children's bodies: re-opened the same evening.** The ruling
   "native scale plus Growing Up's systems" rested on a claim this
   record has since withdrawn (the corrected engine bullet above):
   the vanilla renderer does not scale a character by the model
   instance's field. Growing Up's plain-Lua systems - the age curves,
   the fear model, the literacy progression, the experience throttle,
   the archetypes - still come into SAO as ruled. The body itself
   went back to the operator with the corrected facts, and they
   ruled: SAO's own Java agent instruments the animation player
   first - a load-time transformer that scales bone transforms per
   character, verified live - and the age systems follow it. The
   body batch comes before the age batch.

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

# Part 3 - repositories and non-Workshop hosts (2026-09-06)

GitHub was swept by keyword, topic (project-zomboid and its
variants, every page) and code search; Nexus Mods' whole Project
Zomboid section (fourteen listing pages) was read; ModDB, GitLab,
Codeberg, itch.io and the Indie Stone forums were searched. Nexus,
ModDB and the forums refuse the fetch tool and were read through the
browser pane; rows marked (index) were not opened. The license
column records what a page or file states.

## Homes of the catalogued mods

| Mod | Home | Holds | Build | Last update | License (as stated) | Author | Workshop id |
|---|---|---|---|---|---|---|---|
| Getting Old | github.com/Bruce-Devlin/ProjectZomboidMods, folder Mods/GettingOld | full source, workshop.txt, preview (the repository also holds two other mods) | "Updated for Project Zomboid Build 42.20 stable"; tags Build 42, framework, multiplayer, traits, WIP | 2026-08-05 | none stated (no license file) | Bruce-Devlin | 3643959369 |
| This Is How You Died | github.com/dy0gu/tihyd; also Nexus mods/199 | full source, README, license | not stated | 2023-12-01 (Nexus upload July 2024) | GPL-3.0 (license file; the Nexus page repeats it and asks for credit) | dy0gu | 3013368173 |
| Aging (Pao) | github.com/ZioPao/Aging | full source with a 42 folder ("wip for b42"), a Build 41 mod.info, workshop.txt | Build 41 tag; Build 42 work in progress | 2025-04-13 | GPL-3.0 (license file) | ZioPao | 2982401230 |
| Age Traits | github.com/mxswat/pz-age-trait | full source, workshop.txt | Build 41 | 2022-04-18 | none stated | mxswat | 2796508003 |
| Neurodiverse Traits | github.com/mxswat/pz-neurodiverse-traits | full source, workshop.txt (ADHD, Bipolar I, Tourette, Alzheimer's with daily skill loss) | Build 41 | 2022-06-06 | none stated | mxswat | 2754581597 |
| The Only Cure | github.com/ZioPao/The-Only-Cure | full source (42 and common), mod.info | Build 42.20 | 2026-08-23 | GPL-3.0 | ZioPao | 3580276809 |
| Psychology - Mental Resilience Skill | github.com/WindLother/ZModPsychologySkill | full source, tests, workshop.txt | Build 41 and 42.20.2 | 2026-08-07 | none stated | WindLother | 3561213456 |
| Just Drugs - DLC | github.com/Leuansin/Just-Drugs---DLC; a Nexus listing (mods/215, index) | full source, readme | Build 41 and 42 | 2025-10-30 | none stated | Leuansin | 3339758426 |
| The Alcoholic | github.com/axxessdenied/thealcoholic | full source | not stated (Build 41 era) | 2024-08-27 | MIT | axxessdenied | 2679739572 |
| Evolving Traits World | github.com/MusicManiac/EvolvingTraitsWorld | full source, workshop content, changelog | Build 42; a Build 41 legacy at 3773982162 | 2026-09-06 | no license file; redistribution prohibited without permission | MusicManiac | 2914075159 |
| More Traits | github.com/hypnotoadtrance/MoreTraits (archived Sept 2, 2026) | full source, authors file, changelog | Build 41 and 42 | 2026-08-29 | none stated | HypnoToadTrance, Fajdek, MusicManiac | 1299328280 |
| Tomb's Player Body | a Sketchfab model listing only (tomb_art) | the model's description; no download stated | not stated | Feb 18, 2025 | a NoAI tag | tomb_art | 3429790870 (by name) |
| HGO Expansion B42 | ModDB moddb.com/mods/hgo-expansion-b42; Nexus mods/247 | a cannabis system with sandbox smoking effects | Build 42 | Feb 9, 2025 (release); Aug 19, 2025 | no repacks, reuploads or edits without permission; credit required | HGO | 3424309174 |

## Mods found only outside the Workshop, or not yet uploaded

| Category | Mod | Home | Holds | Build | Last update | License (as stated) | Author | Workshop |
|---|---|---|---|---|---|---|---|---|
| child bodies | TOTC: Think Of The Children | github.com/Zomboides/TOTC | full source (common and 42 folders), documentation, a site - child-sized zombies | 42.13.1 | 2026-01-14 | MIT (README; no license file at root) | Zomboides / raulillana | not stated |
| health | Humans: Are Weak | github.com/SeahDokki/seah_haw_pz | full source, README, design documents: thirteen negative traits (Epileptic, Narcoleptic, Diabetic, Depressive, Immunocompromised, Asthmatic, Ehlers-Danlos, Neuralgia, Tourette's, Allergic, Osteoarthritis, ADHD, Colour Blind), partly implemented | Build 42 | 2026-09-02 | a non-commercial source-available license, version 1.0 ("not Open Source") | SeahDokki | none stated |
| health | Humans: Are Resilient; Humans: Are Shaped | github.com/SeahDokki/seah_har_pz; seah_hash_pz | eleven positive traits (behavior pending); five occupations and starting-kit fixes | Build 42 | 2026-09-01 | the same source-available terms | SeahDokki | none stated |
| health | PzDiabetes | github.com/fopwoc/PzDiabetes | full source, tests, README, license | Build 42.20 | 2026-08-23 (one commit) | WTFPL | fopwoc | none stated |
| health | Tourette Syndrome | github.com/pavel-voronin/pz-tourette-syndrome | full source, README, workshop.txt | not stated | 2025-05-31 | MIT | pavel-voronin | 3490803451 |
| cognition | ADHD Trait | github.com/JoshuaSHenderson/ProjectZomboid-ADHD-Trait | full source, README (the Build 41 tree removed) | Build 42 only | 2026-08-04 | MIT | JoshuaSHenderson | not uploaded |
| mental health | Scotty's Mental Health Expansion | github.com/ScottyVenable/Project-Zomboid-Mod--Scottys-Mental-Health-Expansion | media, docs, mod.info, README: Depression, Anxiety, PTSD, Insomnia, Psychosis, OCD, with fictional medications | Build 41.78.16 and later | 2025-06-22 | MIT | ScottyVenable | "coming soon" |
| sight | EyeTraits | github.com/Aurocka/EyeTraits-Project-Zomboid | an idea text only (photophobia, night blindness, cataracts, permanent blindness) | not stated | 2025-01-15 | none stated | Aurocka | none |
| sight | PZ_BlindTrait | github.com/JulienLaclaverie/PZ_BlindTrait | a 2017 mod folder | 2016-17 era | 2017-06-15 | none stated | JulienLaclaverie | none |
| substances | Cryzers-Drugs | github.com/CryzerFranz/Cryzers-Drugs | full source (cannabis growing, joints) | not stated | 2025-04-24 | MIT | CryzerFranz | none |
| substances | pz-dnd; AddictionMod; lactoseIntolerantMod | GitHub (SirNoName2705; 7Roses; brycepg) | a template with little content (2020); a 2013 nicotine script; a lactose-intolerance trait (2023) | old | 2020; 2013; 2023 | MIT; none; not checked | - | none |
| substances | Reefer Madness (B42) | Nexus mods/252 (index) | marijuana items and a high moodle | Build 42 | Nov 5, 2025 | not read | a deleted user | not read |
| traits and occupations | SOTO-Refactored | github.com/Susjin/SOTO-Refactored | full source, documentation, to-do - a refactor of SOTO | Build 42 stable | 2026-09-05 | MIT (copyright Pedro Henrique 2026) | Susjin | none stated (SOTO is 2840805724) |
| traits and occupations | Universal Traits (UT_CORE) | github.com/rk-gamemods/pz-universal-traits | full source, tests, audit and planning documents | Build 42, single-player | 2026-07-25 | "No open-source license has been granted"; public for review and collaboration | rk-gamemods | none stated |
| traits and occupations | Overkill Traits and Professions | github.com/CThurston2003/OverkillTraitsAndProfessions | full source, README | not stated | 2026-05-25 | MIT | CThurston2003 | none stated |
| traits and occupations | Traits and Occupations Expanded | github.com/1SnowFall1/Traits-and-Occupations-Expanded | mod.info (Portuguese), registries, media | Build 42 layout | 2026-05-06 | none stated | 1SnowFall1 | none stated |
| traits and occupations | Survival Instincts | github.com/Fenris91/SurvivalInstincts | full source, README (dynamic perks, negative traits) | Build 42 | 2026-03-13 | MIT | Fenris91 | "coming soon" |
| traits and occupations | Kentucky National Guard Professions | github.com/CyclingGoose/Goose-s-Kentucky-National-Guard-Professions-B42 | full source in version folders 42.13 to 42.15 | Build 42.13 and later | 2026-08-15 | MIT (license file) | CyclingGoose | 3659605156 |
| traits and occupations | ra's Professions | github.com/razab87/rasProfessions | full source, releases | Build 41 stable and 42 unstable | 2026-03-15 | a custom text: free to use, modify and share any element, as long as no plain copy is published on Steam | razab87 | 2675128168 |
| traits and occupations | True Detective | github.com/kodexArg/TrueDetective | full source, docs, CI | Build 42.20 | 2026-08-19 | MIT | kodexArg | 3383387174 |
| traits and occupations | Hardwork Rework; Project_Survival; Biochemistry Occupation Traits Skills | GitHub (ruEngineer; Grammarsalad; Grammarsalad) | full source; Lua source (a Survival skill, occupations, traits); an add-on for Biochemistry of Life | not stated | 2025-08-15; 2024-06-27; 2024-06-18 | none stated; not checked; not checked | - | workshop.txt present (id not read); none; none |
| traits and occupations | Profession Framework | github.com/FWolfe/ProfessionFramework (archived Sept 13, 2023) | media, docs, examples, mod.info - the framework Build 41 profession mods required | not stated | 2022-02-14 | none stated | FWolfe | 1343686691 |
| traits and occupations | Dan's Rebalance; A-anon's Professions; ProfessionMod | Nexus mods/107, mods/43, mods/287 (browser pane) | a point rebalance with Couch Potato and Desk Jockey traits and a Streamer profession; five professions; a Soldier profession with a Military Training trait | not stated; not stated; Build 41.78 | May 2023; Apr 2021; Apr 2026 | none quoted | thedanofdans; Aanon0133; Abad | not stated |
| traits and occupations | (WIP) More Occupations; The Trait Modifier | Indie Stone forums (index; threads not opened) | a Build 41 occupations thread with starting equipment; a 2015 trait modifier | Build 41; version 31 | 2021; 2015 | none stated | fritozy101; not captured | not captured |

## Notes on part 3

- Nothing on any host swept models dementia, memory loss or
  cognitive decline for Build 42. The nearest remain the Build 41
  Alzheimer's trait in Neurodiverse Traits (source public) and the
  Build 41 Dyslexia in Custom Traits (Workshop only); ADHD exists for
  Build 42 with MIT source.
- No child, teen or elder player-body mod exists outside the
  Workshop for Build 42; TOTC's child-sized zombies (MIT, full
  source, 42.13) are the nearest, and a working reference for a
  scaled child mesh in this engine.
- Three re-uploads of PepperCat's Dynamic Traits sit in other
  people's repositories (NoR734/Dynamic, besterry/HC-modpack,
  jguz1990/mods-pz); none is an author's home and they are not
  tabled. VsCodeHubb/pz-chronicles is an empty repository, not a
  home for PZ Chronicles.
- Dynamic Body Shape ships Java classes inside its Workshop folder
  (a `zombie` folder for Build 41, a `42` folder for Build 42), as
  Realism does; True Model Z's page states that anyone may add to
  and extend it with credit in the files.

## Could not source (part 3)

- Growing Up and Realism (PZ Chronicles): no repository, Nexus,
  ModDB, forum or itch.io listing; only a Discord and Ko-fi pages.
- Aging Mod (Vivi), Babies (Scimmia; a Build 42 port is said to be
  planned in the page's comments), Tomb's Player Body Overhaul (a
  Sketchfab listing only), True Model Z, Dynamic Body Shape, Moodle
  Framework, [B42+] Sandbox Options: nothing outside the Workshop.
- Nexus mods/29, returned by search as an aging mod: hidden behind
  the adult-content preference; unread. Nexus mods/16: not read.

# Operator-added, 2026-09-06: Starving Zombies: Realism (B42.20)

Subscribed by the operator the same evening (Workshop 3793611785,
Amostradinho, version 2.3, versionMin 42.20.4, Lua only, single- and
multiplayer; incompatible with the older Starving Zombies). Read from
its files: zombie hunger (fed hours, starving after hours, a starving
scent multiplier), scent carried on wind, rain, fog and temperature
from bodies (fresh, peak, fade, dry, burned) and from the player
(blood, wounds, clean and dirty bandages, infected wounds, perfume
and cologne masking), feeding on corpses (eat time, eaters per body,
feeding effects, frenzy radius and size, blood trails, corpse
flies), world stories, physical stability and trips, and a push
system. It writes its state on the zombie and the world (`szrHungerState`,
`szrFedUntil`, `szrTargetKind`, `szTarget`, `szrFragranceUntilHours`,
the body-yield and trail keys) and exposes globals (`SZRealism`,
`SZRealismClient`, `SZBodyGroup`, `SZBodyGrid`, `SZPlayerTrips`); it
hooks `OnZombieUpdate`, `OnDeadBodySpawn`, `OnWeaponHitCharacter`,
`LoadGridsquare` and the tick and player updates. Sixty-one sandbox
options.

What it is to SAO: a change in what a survivor has to know - that
the dead smell blood and wounds, that they feed and gather to feed,
that scent travels on the wind - and a state SAO can read where the
mod is present (the standing rule: recognised, never named in code).
It belongs with the lessons and the knowledge surface, not with the
people catalogue; recorded here because the operator added it in
this pass. Its place in the design is the operator's call.
