# Who knows what - the scoping index

| | |
|---|---|
| Status | DRAFT 2026-09-06 - a design index for review; not the floor. Written the day the operator asked that the world model be cut by personal history built from the attributes the game makes available, never one shared encyclopedia. |
| What it is | The explicit map from a person's attributes to the slices of the world documents they carry, and the rules that resolve every "who carries it" tag per person. |
| Rule | A claim reaches a person only if (1) the person's attributes match its carriers, (2) its date is inside the person's horizon, and (3) a provenance path exists for that person (read, heard, lived, told). Otherwise the person does not have it, and the models are taught that they do not. |

## The inputs - what a person is

### From the engine (verified 2026-09-06 against the installed jar and scripts)

Per character the engine holds:

- **Name:** `SurvivorDesc.getForename` / `getSurname`.
- **Gender:** `isFemale`, `getCharacterGender`.
- **Age:** `IsoGameCharacter.getAge` / `setAge` - an integer the
  engine stores and nothing reads: no body, animation or behavior
  changes with it, and the jar has no child or elder class at all
  (verified 2026-09-06). Children and elders therefore come only
  through mods (ruled below).
- **Profession:** `SurvivorDesc.getCharacterProfession` - 25 shipped
  definitions in `character_professions.txt` (burglar, burger
  flipper, carpenter, chef, construction worker, doctor,
  electrician, engineer, farmer, fire officer, fisherman, fitness
  instructor, lumberjack, mechanic, metalworker, nurse, park ranger,
  police officer, rancher, repairman, security guard, smith, tailor,
  unemployed, veteran), each with granted traits and skill boosts;
  mods add more through the same registry.
- **Traits:** `IsoGameCharacter.getCharacterTraits` / `hasTrait` -
  97 shipped definitions in `character_traits.txt`, each with a
  cost, exclusions, skill boosts and sometimes granted recipes. The
  ones that bear on knowledge: illiterate, slow reader, fast reader;
  deaf, hard of hearing, keen hearing; night owl, insomniac, needs
  more sleep; former scout, hunter, outdoorsman, wilderness
  knowledge, herbalist, fishing, gardener, cook, first aid,
  mechanics, blacksmith, tailor, whittler, tinkerer, artisan,
  baseball player, jogger, hiker; smoker; desensitized; pacifist.
- **Personality:** eight floats on the descriptor - bravery, loner,
  aggressiveness, compassion, temper, friendliness, favour-indoors,
  loyalty.
- **Skills:** perk levels, with the profession's and traits' boosts.
- **Voice:** type, pitch, prefix. Appearance and outfit.
- **Observations:** `getObservations()` - the engine's own remarks
  about a character.

Not in the engine: where a person is from, what schooling they had,
who their family is, whether they served, what they read or
listened to. Nothing in the descriptor says so.

### From SAO's derived history (the mod's own, with provenance)

- **Age** when the engine has none: deterministic per person from
  the identity hash, in the county's own bands (19-29, 30-39, 40-49,
  50-59, 60-68; no children); birth year = the world's start year
  minus age (`SAO_History.ageOf` / `birthYearOf`).
- **Age in any year** (`ageInYear`) - the reason to carry age at
  all: what a person can remember of a decade depends on how old
  they were during it.
- **Service:** which war a person's birth year and a service age of
  18-26 made them eligible for (Korea 1950-53, Vietnam 1965-73, the
  Gulf 1990-91), and whether their life actually put them there -
  only the census's military occupations (`servedIn`).
- **Occupation class** from the county census: the engine's
  profession registry plus the civil lives the engine has no
  profession for (clerks, teachers, and the rest), classed as
  carer, settled, trades, professional, military and so on
  (`SAO_Census`).
- **Origin region** and a one-line origin situation (`originRegion`,
  `Census.originNote`) on the identity record.
- **Lessons** with provenance (lived, seen, told) and an epistemic
  age (`SAO_Lessons`, `SAO_History`); the era per person - innocent
  or hardened - in the Day Zero mode.
- **Household and relations**, standing toward others, and what
  they have been told and by whom (`SAO_Perception`'s
  told-provenance).

Every derived item is itself a claim with provenance, never a bare
fact.

## The carrier tags, resolved per person

Every claim in the documents carries a "who carries it" tag. This is
what each tag means mechanically. All rules are deterministic from
the person's attributes and the identity hash, so two sessions agree
about the same person.

| Tag | Resolves to | Note |
|---|---|---|
| everyone | every adult in the county, gated by age at the date (below) | the floor is small: the fall, the President's name, the war, the prices of what they buy |
| adults | age at the claim's date of 18 or more | a person born in 1972 carries the Gulf War as an adult and 1979 as a child |
| followers | a per-topic draw from profession, traits and personality: politics and institutions favour police, fire, doctor, nurse, engineer, veteran, security guard and fast readers; science and space favour engineer, doctor, nurse and fast readers; sport favours athletic, baseball player, jogger, fitness instructor and the young; music and film favour the young and night owls; outdoors and weather favour farmer, rancher, park ranger, hunter, outdoorsman, fisherman | the draw is per person from these attributes, deterministic on the identity hash; the county's proportion is whatever the living add up to, not a fraction set in advance (ruled 2026-09-06) |
| service | `servedIn` non-nil, or the veteran profession | military.md reaches them whole; others get it only as followers |
| region:X | origin region X; the county itself for region:Kentucky | region claims are lived (provenance paid-for), not read |
| everyone under fifty | age at the date under 50 | sport, popular music, television for the young |
| trade:X | occupation class or profession X | work-and-money and the prices of the trade: a nurse knows hospital things, a mechanic car prices, a burger flipper fast-food wages |

## Age at the event

Knowledge of an event scales with the person's age when it happened:

- under 6: nothing.
- 6 to 12: a child's memory - the event as a household mood, no
  detail; the models learn the vagueness, not the facts.
- 13 to 17: a teenager's slice - music, film, television, school and
  sport strong; politics and money weak.
- 18 and over: the adult slice, per the tags.

## Provenance - the path a claim took to the person

A claim needs a path, and the path is taught with it:

- **read** (print): needs literacy. The illiterate trait removes
  every print-only claim; slow reader thins them; fast reader
  thickens them. In the Knox record, print stops July 6 for the
  county and July 16 for Louisville.
- **heard** (radio, television): the deaf trait removes radio and
  speech-only sources (print and people remain); hard of hearing
  thins them; favour-indoors and night owl thicken late television;
  nobody hears anything after the static of July 19-20 except the
  loop, the automated bulletins and the amateurs.
- **lived:** region, service, trade, and the county's own July 1993
  days (the local claims in knox-event.md).
- **told:** what another person in the county said - SAO's
  told-provenance, with the teller stamped, arriving after the fact
  and possibly wrong.

## Horizon per person

The save's horizon (PLAN.md) is cut again by the person: inside the
cordon from July 6 the papers of July 12-16 are outside knowledge
unless found; the broadcasts end for everyone on July 18-20; a later
arrival carries what their origin region knew.

## Decay per person (drafted 2026-09-06, after the catalogue)

What decays is a claim in a person, never a fact in the world. SAO
already runs the mechanism: beliefs age and are pruned in
`SAO_Perception`'s decay pass, lessons carry an epistemic age, and
the knowledge surface renders an age word with every claim. What was
missing was variation between people. The catalogue
(../people-mods.md, part 2) settles what exists to build on:

- No Build 42 mod removes knowledge a person already holds. The
  nearest things are Build 41: an Alzheimer's trait (each day, each
  skill has a 50 percent chance to lose 2.5 percent of its
  experience), a Dyslexia trait (reading a quarter slower, a tenth
  less taken in), and an ADHD trait whose forgetfulness is rendered
  as dropped items. Vanilla has no memory trait; its learning traits
  change the rate of taking in only.
- What Build 42 has bears on the forming of claims rather than their
  keeping: addiction and withdrawal (eight dependency traits gained
  by use and lost after eighteen to twenty clean days; a period drug
  set for 1993 with tolerance, withdrawal and relapse), psychiatric
  conditions (schizophrenia, anxiety, narcolepsy, Parkinson's; PTSD,
  insanity), sanity as a running value, sleep (the vanilla sleep
  traits; narcolepsy), and the senses (deaf, hard of hearing, short
  sighted; cannot read without glasses; a hearing aid).

The rule, per claim per person:

1. **A base rate** from the claim's provenance and age: lived
   slowest, read and heard faster, told fastest. This is SAO's
   existing decay.
2. **A person factor**, deterministic from attributes: age at the
   claim (what was learned young decays slowest; the elderly keep the
   old and lose the recent - a pattern to teach, not a number yet);
   a cognitive condition where a person has one (a dementia condition
   raises the rate on everything recent and, late, on names and
   places; ADHD raises the rate on told claims and lowers the rate at
   which read claims form; dyslexia thins read claims at the source);
   an attention condition (depression and anxiety narrow what forms;
   PTSD pins certain lived claims and does not let them decay).
3. **The state at the time**, of learning and since: drunk,
   withdrawing, feverish, sleepless, panicked - the claim forms weakly
   or with a gap. SAO holds the sleep and sickness states; the
   substance mods hold the rest.
4. **Mis-remembering, not only forgetting.** A decayed claim is
   rendered with its age word (the surface does this already), and a
   told claim can be wrong because the teller was; the models are
   taught both.

What the mod decisions settled (Crucible, 2026-09-06): the memory
conditions in item 2 are ported into SAO as its own (the Alzheimer's,
ADHD and Bipolar traits, Dyslexia, the six mental-health conditions,
the Build 42 ADHD trait), the Build 42 condition mods are required
at runtime for what players see, the age effects come in from
Getting Old's source, and the substance dependencies of item 3 come
into SAO's own habits. The rule therefore runs on SAO-native
conditions plus the required mods' traits where present.

## What this forbids

- **One shared fact list.** The training store samples attribute
  records across the county's own distribution (the census weights)
  and generates examples per record, so the models learn the
  differences, including not knowing.
- **A claim without a path.** "Everyone knows" is an age-gated
  floor, not a default.
- **Personality as knowledge.** The eight floats condition how a
  person speaks (the voice layer), not what they know. Traits and
  profession do both.
- **Derived history stated as fact.** Origin, service and lessons
  carry provenance and an age, and a person can be wrong about them
  the way people are.

## Ruled 2026-09-06 (Crucible)

1. **The trade tag is layered.** The census class decides which
   slice a person gets; the engine profession (the 25 shipped, plus
   mods) adds its specifics where a document has them; an unknown
   mod profession falls back to its class, so nothing is unmapped.
2. **The child's-memory band teaches vagueness** - the event as a
   household mood, no dates or numbers - and the county is to have
   children and elders at all: mods that add child and elder bodies
   are catalogued in ../people-mods.md (part 1, bodies and age)
   so that SAO can make them native requirements, after which the
   age bands extend below 19 and above 68. (The engine ships no
   child or elder bodies; SAO's bands stop where they do for that
   reason. The catalogue found one child-body mod, closed and
   patching the game directory by hand; the engine-native path for
   a child is a scaled adult mesh. Elders need no model at all - the
   operator ruled it the same day: an elderly person is the adult
   body with hair, condition, behavior and age.)
3. **The follower share is not a global number.** Who follows what
   depends on who survives, or is simulated to survive: the living
   are not a random sample of the county, and the census governs
   who they are. The follower draw is therefore computed per person
   from attributes, and the county's proportion is whatever the
   living add up to - never a fraction set in advance.
4. **Knowledge decays per person, not at one rate.** Traits and
   health - dementia, memory loss, chronic illness, age - set each
   person's rate of forgetting and mis-remembering. Vanilla carries
   no dementia; the traits and health mods that do are being
   catalogued in ../people-mods.md (part 2, traits and health
   conditions, in progress) with anything else that fleshes out a
   person, so that SAO can require them and the models can be
   taught the variation. A "Decay per person" section follows the
   catalogue.
