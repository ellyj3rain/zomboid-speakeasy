# People through mods - the catalogue

| | |
|---|---|
| Status | DRAFT 2026-09-06, part 1 of 2: bodies and age. Part 2, traits and health conditions, follows. Feeds DR-032 on the SAO side: which mods SAO requires is decided through Crucible, mod by mod, after part 2. |
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
