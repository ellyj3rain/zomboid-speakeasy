# The 1993 world documents - research plan

| | |
|---|---|
| Status | APPROVED 2026-08-31 with the three decisions below settled. Research follows this plan. |
| First cut | The national frame: the United States as an ordinary person knew it in mid-1993. Kentucky and Knox County follow as the second cut. |

## The horizon (corrected 2026-08-31)

There is no single boundary date. The game's start date is a
sandbox option, and what each option does was read from the engine
itself, not assumed:

- **Start Year** is a hundred-value list whose first value is 1993
  (`SandboxOptions.getFirstYear()` returns 1993); the shipped
  presets select that first value. The chosen year feeds the game
  clock (`GameTime.getStartYear` / `getYear`), so a later value
  is a later calendar year on the clock - the engine attaches no
  history to it, and its broadcast scripts are keyed to days since
  the start, not to the year. (An earlier draft cited the radio
  scripts as naming 1993; that was a false match on identifier
  strings and is withdrawn.)
- **Start Month** (1-12) and **Start Day** (1-31) set the date; the
  presets say July 9, 1993 (the constructor default reads as July
  23).
- **Months since the Apocalypse** (0-12) is the separate option
  that sets how deep into the fall a world begins. The game's own
  tooltip: it affects starting erosion and food spoilage and does
  not affect the starting date.

Policy for this project, the operator's: the world is 1993. A
later Start Year value is treated as a calendar setting with no
history behind it - nothing past December 31, 1993 is researched,
and a survivor in a later-year world still carries 1993. (The
operator described the later years as the apocalypse-depth knob;
the engine gives that role to Months since the Apocalypse. The
policy stands either way; the description is corrected.)

So the documents are DATED, and the horizon is computed per save:

- Every claim carries the date it became knowable. The first cut
  covers January 1990 through December 31, 1993 - the whole of the
  year a 1993 start can reach.
- A survivor's horizon is the day the world stopped delivering
  news: the fall. Normally that is the save's start date (the
  engine exposes it). Where Months since the Apocalypse is set,
  the fall is that many months before the start date, and nothing
  from the gap is known.
- In SAO's day-zero mode the county starts BEFORE the fall - a
  living start. The calendar runs, and the horizon advances with it
  day by day until the first witnessed horror; a person's world
  keeps filling in from the dated documents until then.
- The game's own record of the fall is dated: its newspapers run
  from July 1 to July 16, 1993, and its broadcasts - keyed by the
  engine to days since the save began - line up with those dates
  only on the shipped July 9 start (knox-event.md lays the two
  side by side). The operator ruled on 2026-09-06 that this
  schedule is controllable: a living start drives when each part
  of the record reaches the county, so the shipped assets serve
  any 1993 start. The engine's re-keying surface was verified on
  the SAO side (its engine contract, Addendum E; ruling DR-031).
  This project's part is to key every event to its absolute date,
  which knox-event.md does.

And still: knowable by THAT person. A soldier out of Fort Knox, a
nurse in Muldraugh, and a teenager carry different slices of the
same year.

## What a document is

A world document is a set of claims, not prose to be admired. Each
claim carries:

- **the claim** - one fact, stated plainly
- **when** - the date or span it holds for
- **confidence** - HIGH (a primary source dates it exactly),
  MEDIUM (a primary source supports it with an approximate date or
  indirectly), LOW (no primary source yet). LOW claims never teach
  a model; they wait for an upgrade or are struck.
- **source** - the PRIMARY source consulted: a period newspaper,
  a broadcast record, a government record, a trade publication of
  the time. Secondary sources (encyclopedias, retrospectives) may
  locate a primary source; they are never the citation.
- **who carries it** - which kinds of people would plausibly hold
  it: everyone, adults, a trade, a region, an age band, a follower
  of the topic. This is the scoping the design requires.

No document teaches anything until it has been reviewed and
approved as a whole.

## The proposed document set, first cut

1. **timeline.md** - what happened, January 1990 to December 31,
   1993, as it reached ordinary people: the Gulf War, the Soviet collapse,
   the 1992 election and the new administration, the Los Angeles
   riots, Hurricane Andrew, the World Trade Center bombing, Waco,
   the Midwest flood beginning that summer. Each entry dated, each
   marked for who would have followed it.
2. **daily-life.md** - what a household had and what things cost:
   wages and prices, cars, phones (cordless, answering machines,
   pagers - and what did not yet exist for ordinary homes), television
   and cable, VCRs, music formats, groceries, gas, rent.
3. **media.md** - what people watched, heard, and read: television
   programs on the air, films in theaters that summer, the music on
   radio (and radio formats themselves), major news anchors and
   papers. Scoped by age and taste, because a fifty-year-old and a
   nineteen-year-old did not share a radio dial.
4. **institutions.md** - how the country was run as people
   experienced it: the new administration's early months and the
   debates of that spring, Congress, the military after the Gulf War
   drawdown, the National Guard and emergency management (the
   structures a quarantine would fall on), police, hospitals,
   schools. Drafted 2026-09-06.
5. **work-and-money.md** - the economy as lived: the early-90s
   recession and its slow recovery, unemployment, the kinds of work
   an ordinary town had, what a paycheck bought, who was hiring.
   Drafted 2026-09-06.
6. **military.md** - the Army of 1993 for the people who served in
   it: structure, the post-Gulf mood, Fort Knox as the Armor Center
   (the bridge to the Kentucky cut). Carried by soldiers and
   military families, not by everyone. Drafted 2026-09-06.
7. **who-knows-what.md** - the scoping index: an explicit map from
   kinds of people (age bands, trades, regions, service) to the
   sections above, so the models are taught differences in
   knowledge, not one shared encyclopedia. Direction of 2026-09-06,
   the operator's: the map keys on the attributes the game itself
   makes available per character (age, gender, profession, traits,
   personality, skills - verified against the installed build) and
   on SAO's derived history (birth year, service, occupation class,
   origin region, lessons), so that nobody knows everything and
   personal history decides. Drafted 2026-09-06 for review.
8. **knox-event.md** - the game's own record of the fall, added
   2026-09-06 on the operator's word and verified against the
   shipped files: the broadcast schedule (RadioData.xml, eighteen
   channel entries across the radio, television, amateur and
   military bands, 905 broadcasts on days 0 to 27 after the start,
   13,166 lines of text in RadioData.json), the dated in-game
   newspapers (Print_Text.json - twenty-two issues of four papers:
   Knox Knews July 1 to 6, and the Kentucky Herald, the Louisville
   Sun Times and the National Dispatch July 6 to 16, 1993, from
   "Illness outbreak in Muldraugh" to "Louisville overrun"), the
   automated emergency broadcast lines (DynamicRadio.json), and the
   developer's own statements (The Indie Stone's July 2023 post
   dating the outbreak to July 6, 1993, read through the search
   index). This is what survivors LIVE - the news that reaches them
   after the start - and the reason a living start has something to
   run on. The primary source is the game itself; community wikis
   are finding aids only. Part of the floor with the first three
   (ratified 2026-09-06), because a survivor knows the Knox Event
   before they know Jurassic Park. Drafted 2026-09-06.

## Decisions settled (2026-08-31)

1. **Size of the first cut: three as the floor.** Timeline, daily
   life, and media are researched and approved first; training may
   begin on those while institutions, work and money, the military,
   and the who-knows-what index follow. Amended 2026-09-06 via
   Crucible: the floor is four documents - knox-event.md joins
   timeline, daily life and media, so nothing trains on the national
   frame without the fall.
2. **Real names as history.** Survivors may name the president,
   the store, the band on the radio - the world as it was, in
   ordinary nominative use.
3. **Primary sources only.** Every claim traces to a period
   newspaper, broadcast record, government record, or trade
   publication of the time. Slower and thinner where nobody
   recorded daily life formally - and where that is so, the claim
   stays LOW and does not teach.

## What the plan does not do

- It invents nothing. Every claim in a document is researched and
  cited; anything uncited is LOW and never teaches.
- It does not reach past December 31, 1993, and it never decides
  what a save knows - the save's own dates do.
- It does not decide Kentucky. The second cut has its own plan.
