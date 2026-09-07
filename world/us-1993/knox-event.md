# The Knox Event - the game's own record of the fall

| | |
|---|---|
| Status | DRAFT 2026-09-06 - not approved; nothing here teaches a model yet. Proposed for the floor (PLAN.md, document 8). |
| Scope | What the shipped game says happened, day by day, from July 1 to about July 21, 1993, and what it keeps saying after. |
| Primary sources | The installed Build 42.20 files: `media/radio/RadioData.xml` joined with `media/lua/shared/Translate/EN/RadioData.json` (broadcasts, line text keyed `RD_<LineEntry ID>`); `media/lua/shared/Translate/EN/Print_Text.json` (newspapers and flyers); `media/lua/shared/Translate/EN/DynamicRadio.json` (the automated broadcast lines); `media/scripts/generated/items/literature.txt`, `media/lua/server/Items/Distributions.lua` and the `Newspaper` / `RecipeCodeHelper.nameNewspaper` bytecode (how the papers reach the world). |
| Confidence | HIGH throughout unless marked: the shipped file says it. The developer's statements read through the search index are MEDIUM (index). |
| Keying | The newspapers carry absolute dates. The broadcasts are keyed by the engine to days since the save began. The two agree only on the shipped July 9 start; this document keys everything to the absolute date and shows the mapping (see "Two clocks"). |

Who carries it: `county` (anyone in the Knox area that week),
`louisville`, `national`, `radio` / `tv` / `ham` / `military`
(heard it on that band), `everyone` (any survivor).

## Two clocks (engine-verified 2026-09-06)

The record is kept on two different clocks, and that fact decides how
it can be used.

- **Print is dated absolutely.** Every issue's title carries its date
  (`Print_Text.json`, e.g. "The Kentucky Herald - July 16 1993"), and
  the stories date themselves internally by weekday, consistently
  with the real 1993 calendar (July 3 a Saturday, July 11 a Sunday,
  July 14 a Wednesday). Which issue a found newspaper shows is not
  on any calendar: `RecipeCodeHelper.nameNewspaper` picks one at
  random from the paper's fixed issue list, or the newest issue when
  the item carries the `NEWSPAPER_NEW` tag (`Newspaper_Herald_New`
  and its three siblings, placed by the `newspaper_herald`,
  `newspaper_dispatch`, ... lists in `Distributions.lua`). Nothing
  reads the game day. A July 16 Herald can lie on a table in a world
  that started July 1.
- **Broadcasts are relative.** `ZomboidRadio.daysSinceStart` is
  seeded from `GameTime.getNightsSurvived()`, saved with the radio
  state, and stepped once per in-game day; each script's clock is
  `stamp - startDayStamp`, and the start day is a public setter
  (`RadioScript.setStartDayStamp`, `RadioChannel.setActiveScript`).
  The engine re-keys its own schedule this way for its challenge
  modes (`ZomboidRadio.checkGameModeSpecificStart`: "Initial
  Infection" swaps every channel to its `init_infection` script;
  "Six Months Later" puts the military band on `numbers` and NNR on
  `pastor`).
- **So the mapping below is computed, not given.** With the shipped
  default start (July 9, 1993 = day 0) the broadcast days land on
  the newspaper dates and match them headline for headline from day
  3 on. The broadcasts' own day-counting is loose by a day or two
  before that (day 0 calls itself both "the second day of the Knox
  Event exclusion" and "48 hours since this all began"; day 1 calls
  it the fifth day; day 2 says five days into the exclusion) while
  the papers date the cordon to July 5-6. The absolute dates here
  follow the papers; the broadcast day is given beside each entry so
  any start date can be served.

The consequence for this project: every claim below carries an
absolute date. The consequence on the SAO side is recorded there
(DR-031): a living start drives when each part of this record
reaches the county - built as SAO's batch C36 on 2026-09-07: every
vanilla channel is re-keyed once per save to begin on the save day
July 9 falls on, and every paper a container is filled with shows
the newest issue printed by the county's date or is not on the
shelf yet. The mapping computed above is the one it runs on.

## The county before (July 1-5, 1993) - Knox Knews

Knox Knews is the county paper; its six issues are the only record
of the days before the illness. Editor-in-chief Ian J. McCarrock.

| Date | Claim | Source | Who carries it |
|---|---|---|---|
| 1993-07-01 | Governor Cal Fairweather, speaking in Frankfort, promised Brandenburg its federal rebuilding funds after the April 18 tornado (an F2 that killed three, injured dozens, and left hundreds homeless; up to 40 percent of homes uninsured). | Knox Knews, July 1, front page | county |
| 1993-07-01 | A West Point sports win ("Rangers triumph"); a local teacher's national award; a hunter attacked by a stag west of Riverside; Ekron's oldest resident, 103. | Knox Knews, July 1 | county |
| 1993-07-02 | Knox Telecommunications' telephone and Internet networks failed across the Knox area for hours and were still down at press time; businesses closed; the cause unannounced, with talk of downed wires, lightning or sabotage. | Knox Knews, July 2 | county |
| 1993-07-02 | The band Delilah was staying in Brandenburg "indefinitely"; Chapelmount Downs planned a Virginia track; the Mint Julep Prize was held in Brandenburg. | Knox Knews, July 2 | county |
| 1993-07-03 | The FBI's Operation Centaur - corruption in the Kentucky General Assembly, more than a dozen legislators indicted over toxic-waste dumping, extortion and racketeering; House Speaker Dan Dullford resigned - was "winding down," FBI Director Ian Clark said in Louisville. Two of the Governor's aides had been arrested in February. | Knox Knews, July 3 | county; followers |
| 1993-07-03 | Second day of phone outages; cell and car phones affected; the cause given as a local exchange. | Knox Knews, July 3 | county |
| 1993-07-03 (Sat.) | An Army truck carrying hazardous waste overturned on Route 60 just north of March Ridge at about 3:15 p.m.; the scene was sealed by soldiers; Col. Niall O'Malley said the secret materials posed "little danger." The paper tied it to a pattern of lax handling of hazardous materials in the area and to respiratory illness rates. | Knox Knews, July 4 | county |
| 1993-07-04 | Hot weather forecast to continue; Irvington Speedway in talks to host a 1996 Formula X Grand Prix; Independence Day greetings from the paper. | Knox Knews, July 4 | county |
| 1993-07-04 (Sun.) | The county's Independence Day: a twenty-float parade through Knox toward Louisville, brass bands from West Point, Riverside and Brandenburg, an event at the drag-racing circuit near West Point with driver Cruz Dylan present, fireworks in the evening - "America's 217th birthday." Flyers advertised block parties at 6 Spring Dr., Riverside, and at the Dixie Mobile Park northwest of Muldraugh. | Knox Knews, July 5; flyers `RiversideIndependenceDayPartyAllWelcome`, `FourthofJulyCelebrationDixieMobilePark` | county |
| 1993-07-05 | "No end in sight" for the phone outages. An "unusual illness" affecting Muldraugh residents was a page-6 item. A foul smell over the region was blamed on Ohio River algae by a local teacher. Sheriff John Carroll warned about a spate of dog attacks on farm animals and people. | Knox Knews, July 5 | county |
| 1993-06-30 to 07-09 | The ordinary commercial calendar the flyers carry: a bake sale at Holy Grace Church, Muldraugh, on July 2; a firearms-safety briefing at the Meade County police building in Riverside on July 3 at 6 p.m.; a drugs seminar at Louisville police headquarters on July 5 at 7 p.m.; a prayer meeting at Fallas Lake Church on 7/7/93 at 8 p.m. (Pastor Robert Clay) asking to be spared "His plague"; the Irvington 500 on July 7; a Louisville Music Festival July 15-17; store offers ending June 30 through July 9. | `Print_Text.json` flyers (`MuldraughBakeSale`, `RiversidePD`, `LVPDHQ`, `FallasLakeChurch`, `IrvingtonSpeedway`, `MusicFest93`, `UStoreIt*`, `Sammies`, `CarFixation`, `AmericanTire`, `KnoxPackKitchens`, `PizzaWhirledJobAdRosewood`) | county; louisville |

## The fall, day by day (July 5-21, 1993)

Broadcast day = days since the shipped July 9 start. Papers report
the previous day's events in the morning; where the broadcast and
the paper disagree by a day, both are given.

| Date | Bcast day | What reached people | Source | Who carries it |
|---|---|---|---|---|
| 1993-07-05 (Mon.) | - | The military blocked roads and highways into "Knox Country," the counties near Fort Knox, without giving a reason. | National Dispatch, July 7 ("on Monday blocked roads"); July 13 ("trapped ... since July 6") | national; county |
| 1993-07-06 (Tue.) | - | Hundreds of armed troops arrived early in the morning and encircled thousands of civilians; residents outside the line were ordered to move; a West Point nurse, Larry Stoddard, was turned back on his way home from a Louisville night shift. | National Dispatch, July 7 | national; county |
| 1993-07-06 | - | ILLNESS OUTBREAK IN MULDRAUGH: dozens of flu-like cases with severe nausea and fever; doctors looking at a chemical leak; outside authorities meeting calls with "obfuscation and denials"; the Army opened quarantine facilities at its Fort Knox hospital. Also in the paper: an art exhibition at the Art Gallery of Louisville; a local attorney's body identified; the President cancelled his G7 Tokyo trip. | Kentucky Herald, July 6 | louisville; county |
| 1993-07-06 | - | MYSTERY ILLNESS STRIKES LOCALS, OVERWHELMS AUTHORITIES: fevers and vomiting; the military hospital at Fort Knox opened to the public; CDC officials reportedly on the way; several of the sick had suffered bites, and Dr. Janine Cortman, out of rabies immunoglobulin, theorized a rabies outbreak; people were using short-range radios because the phones had been down almost a week. Also: a murdered local "part of criminal gang"; Spiffo's apologized for a hot-sauce mix-up. | Knox Knews, July 6 (its last issue) | county |
| 1993-07-06 | - | WHAT IS GOING ON IN MULDRAUGH? Mystery illness spreading; CDC silent as the military moves; "Could it be a LEAK from a MILITARY LAB?" | Louisville Sun Times, July 6 | louisville |
| 1993-07-06 | - | The national front page was still ordinary: Iraq threatening to stop cooperating with the UN over missile-site monitoring; a Paris hotel gem heist. The President's cancellation of the G7 in Tokyo, "scheduled to begin on Wednesday," was mentioned without a reason. | National Dispatch, July 6 | national |
| 1993-07-07 (Wed.) | - | BLOCKADE IN KENTUCKY: the cordon reported nationally; an op-ed warned the secrecy would feed paranoia and anti-federal movements. | National Dispatch, July 7 | national |
| 1993-07-09 (Fri.) | 0 | The exclusion is national news on every channel. LBMW's Jackie Jaye at the military blockade north of the Zone: recruits who days earlier were waiting to ship overseas now guard checkpoints; an influenza-like illness, "localized," a handful of strange-behavior reports; military scientists inside. WBLN: reporter Richard Gershwin held by the Army. Triple-N's Kirsty Cormick: a community laid low, a military perimeter overnight, helicopters and hazmat suits; Knox Telecommunications claims the lines are down for planned works. NNR: the President met the CDC; a statement expected tomorrow. Civilian Radio: a ham operator breaks his schedule because his co-host is inside the Zone. | RadioData day 0: LBMW `init_infection`/`main`; WBLN; Triple-N; NNR; Civilian Radio | radio; tv; ham |
| 1993-07-10 (Sat.) | 1 | NNR: General John McGrew apologized for a "lack of clarity"; NNR granted access to his operations at the primary military camp south of Louisville. WBLN: "the Knox event IS contained" - Washington's word; civilian fatalities "not an ongoing concern." Triple-N (Washington): Republicans in uproar, America demanding answers. LBMW's Frank Hemingway from the media camp on the boundary: the President gave full support to the agencies. Civilian Radio: every back road blocked, guns at each checkpoint; "reporters ... sitting in bed with the Army." | RadioData day 1 | radio; tv; ham |
| 1993-07-11 (Sun.) | 2 | A night of chaos in the cities: placards in Washington, firebombs in Detroit, a Greene's Grocery set ablaze in Los Angeles, looting and running battles with police; the President spoke. Triple-N: US forces repeated warnings to those on the Zone's edge; forced dispersal. Civilian Radio: Hal broadcasting nightly from the Nashville Air Guard Base - defenses, food, beds, water. | RadioData day 2 | radio; tv; ham |
| 1993-07-11 (Sun.) | - | The World Health Organization advised all flights except military and medical be grounded worldwide to stop the "Knox Virus"; airlines complied almost at once; the President called it "unwelcome and economically unsound"; the European Community advised closing borders. | National Dispatch, July 12 (dates it Sunday); July 14 ("advice on July 11") | national; everyone |
| 1993-07-12 (Mon.) | 3 | LBMW: the Exclusion Zone widened early this morning, camps along access roads moved back, a statement from General McGrew's office. A White House briefing on all channels: "It is time to face facts. It is time to settle down." Curfews announced for New York, Miami and Los Angeles, more to follow; a confirmed fatality in New York, many injured in Miami. WBLN's Dawn Stevenson interviewed Dr. Jack Galbraithe, former CDC chief scientist. Civilian Radio: a photograph out of West Point - a man, arm missing, still walking in a street. | RadioData day 3 | radio; tv; ham |
| 1993-07-12 (Mon.) | - | The leaked photograph (a dismembered, apparently living man in a street of bodies in West Point) emerged Monday; stock markets, already falling after the flight grounding, plunged; the Dow was suspended. Louisville stayed quiet and anxious; authorities were saying the virus spread only by fluid contact. An earthquake struck off Hokkaido, Japan, at about 10:15 p.m. local time Monday, magnitude 7.5, with a tsunami and hundreds feared dead on Okushiri. | National Dispatch, July 13; July 12 op-ed | national; louisville |
| 1993-07-13 (Tue.) | 4 | The outage night: every channel breaks to static at some point ("Our apologies for this morning's break in programming" - NNR; "After last night's outage" - WBLN). LBMW, "possibly our last broadcast from the journalist camp": infection confirmed to spread by fluid exchange, namely bites; the infected "shadows of human beings"; a witness, Joe, from inside the military base. NNR: conflict endemic throughout the Zone; those who suffer from the infection prey on the healthy; survivors let through the line. | RadioData day 4 | radio; tv |
| 1993-07-13 (Tue.) | - | "KNOX EVENT CONTAINED" - OFFICIALS, after the leaked photo; a drip of insider information and short-range radio from inside undermined the claim. Louisville's Mayor Terence Stahl refused a curfew: "Louisvillians are made of stronger stuff." Knox Zone not being supplied; the Hokkaido earthquake. The Sun Times: "ALIVE OR DEAD?" - the virus creates "WALKING CORPSES"; the Zone widened; nationwide curfew as riots continue. Nationally: the Army and National Guard deployed in major cities, tear gas, water cannon, live fire returned; residents trapped inside the cordon since July 6. | Kentucky Herald, July 13; Louisville Sun Times, July 13; National Dispatch, July 13 | louisville; national |
| 1993-07-14 (Wed.) | 5 | General John McGrew's statement, requested onto every embedded channel: "we are safe. America is safe"; the Knox Event confirmed degenerative. NNR: the President left the White House through angry crowds last night as protesters broke curfew and converged on the Mall. LBMW's Jackie Jaye: violence in the border camp, gunfire at dawn, armed personnel among civilians, unverified reports of dead. Triple-N's Kirsty Cormick allowed through the Event line - live pictures from inside. WBLN lost contact with Richard Gershwin on the boundary mid-broadcast. | RadioData day 5 | radio; tv |
| 1993-07-14 (Wed.) | - | "NO NEED FOR PANIC" - GEN. MCGREW: the general's statement dated Tuesday by the paper - the virus degenerative but contained within a boundary of hundreds of square miles; the CDC calling fluid transmission an inefficient spread; the President's departure from Washington called a private family matter. Vatican City and Mecca closed to pilgrims; Saudi Arabia's borders closed; Democrats joined Republican critics. The Sun Times: PRESIDENT LEAVES WASHINGTON - "YOU'RE ON YOUR OWN!"; fluid contact; the Zone military releasing held civilians; signals disrupted by interference. Nationally: thirty-eight nations denounced the U.S. response through the UN, China loudest; bomb and death threats against the WHO in Geneva. | Kentucky Herald, July 14; Louisville Sun Times, July 14; National Dispatch, July 14 | louisville; national |
| 1993-07-14 (Wed.), about 5 a.m. | - | The breach: hundreds of infected broke through the military barricades south of Louisville; heavy fire failed to stop them; up to 100 soldiers and civilians killed, many hundreds wounded; the noise drew more; military and refugees pulled back to Louisville; the infected moved north through the suburbs all day; bridges and roads out of Louisville jammed, traffic backed up toward Columbus and Indianapolis. | National Dispatch, July 15 (dates it Wednesday, 5 a.m.) | everyone |
| 1993-07-15 (Thu.) | 6 | LBMW's Jackie Jaye: the night from hell at the Louisville border camp - violence between military and civilians "attracted them," hundreds of infected; then: "If you're listening to this from Louisville. Get out." Bodies everywhere. NNR's reporter on Route 31W south of Louisville: unburied bodies, devastation to the south; pitched battles, tear gas, sporadic gunfire through yesterday afternoon. Triple-N's Judge Matt Hass, off his usual slot: a wave of "changed" people surged over the Event line hours ago. WBLN's boundary team lost; another crew stuck at a checkpoint in gridlock. | RadioData day 6 | radio; tv |
| 1993-07-15 (Thu.) | - | KNOX BOUNDARY BREACHED: dozens dead, the Army retreating, the Boundary Line moving north toward Louisville, a shoot-to-kill policy overwhelmed, infected attacking tents in the Boundary Camp. States debating "radical solutions": Tennessee voting free firearms for "steady-minded" residents, the California Supreme Court moving to Santa Catalina Island, Congress at 25 percent attendance; the Governor accepting the need for federal aid. The Sun Times: INFECTED BREACH KNOX ZONE BARRIER; panic as civilians flee Louisville and the state; the mayor: "We are STILL safe." Nationally: some outside the Zone falling ill without contact - a CDC official calling aerial transmission a greater threat than the Spanish Flu; the WHO saying the virus was likely already worldwide and the grounding came too late. | Kentucky Herald, July 15; Louisville Sun Times, July 15; National Dispatch, July 15 (its last issue) | louisville; national |
| 1993-07-16 (Fri.) | 7 | NNR: confirmation that the infection spreads without any contact with an infected body - flu-like symptoms, panic, confusion; how it enters the body unknown. Triple-N: the infection spreading throughout Kentucky and further north; huge numbers laid low. LBMW's Jackie Jaye: the camp empty, a battleground; national news reporting it is in Louisville; "Wherever you are: avoid other people." Not everyone gets the illness. WBLN's Dawn Stevenson with the Right Reverend Peter Watts. | RadioData day 7 | radio; tv |
| 1993-07-16 (Fri.) | - | KNOX VIRUS SPREADS THROUGH AIR - the CDC confirming rapid airborne spread; a small percentage immune to the "aerial variant"; a cure now "close to zero"; advice to help neighbors, share food, avoid crowds, keep a bat ready - gunfire attracts them. The Herald's final edition: the virus in Louisville, staff running fevers, hundreds of infected in the streets; a photograph of infected near downtown taken Thursday. Congress evacuated to Mount Weather; the virus "likely already global." The Sun Times' last: LOUISVILLE OVERRUN - PRAY FOR US; the military defeated; spreading without bites; barricade your house and load your guns. | Kentucky Herald, July 16 (final); Louisville Sun Times, July 16 (final) | louisville; everyone |
| 1993-07-17 (Sat.) | 8 | NNR: the infection confirmed in Louisville and surroundings; Cincinnati and Columbus, Ohio; Norfolk, London and Newcastle, England; Mogadishu ... A pre-recorded message from General McGrew "addressed to those unaffected by the second wave." Civilian Radio: Zach's group took over a fortification at the Air National Guard Base near Nashville, by the airport; he will broadcast nightly. Most other channels: static, test cards, reruns. | RadioData day 8 | radio; ham |
| 1993-07-18 (Sun.) | 9 | NNR, breaking up: New Orleans, New York, Los Angeles, Berlin, Tokyo ... McGrew's recording repeated. | RadioData day 9 | radio |
| 1993-07-19 to 07-20 | 10-11 | Static on every channel. Civilian Radio, day 11: Zach again from the Nashville base - "the Immune who were here" - his last regular broadcast. | RadioData days 10-11 | ham |
| 1993-07-21 (Wed.) | 12 | Triple-N's recorded loop, "set to repeat": an unknown plague, the Knox Infection, has taken hold of America; "If the fever didn't get to you ... Find a way to survive ... God Bless America." | RadioData day 12, Triple-N | tv; everyone |
| 1993-07-22 to 08-05 | 13-27 | TURBO's static is the only scheduled broadcast left; the schedule ends on day 27. | RadioData days 13-27 | tv |

### What airs after the schedule ends

- **The automated emergency broadcast** (`DynamicRadio.json`, the
  AEBS lines, "Fiver Zero Two ... Automated Broadcast System") is
  not scheduled at all: it reads the live world - the forecast for
  today, tomorrow and the day after (temperature, wind, cloud, fog,
  storms, blizzards), severe weather warnings with an ETA in days,
  "Air Activity detected," and the Knox Power Grid line that moves
  from "Power fluctuations detected" through "Systems failing.
  Network compromised" to "Blackout" as the county's mains fail.
  Everyone with a working radio carries it. HIGH.
- **The Six Months Later scripts** exist in the file for the
  engine's own later-start mode: the military band `Classified
  M1A1` on `numbers` (a numbers station: "Three. Seven. ... Eight.
  Nine. Two. ... Negative eight. Five. ..." on 95000), and NNR on
  `pastor` - Pastor James Hartnell, bitten, praying in "what was
  once a place for radio broadcast ... a walking mausoleum" until
  the door gives. HIGH as file content; when they air is the
  engine's (or the mod's) choice.
- **The Initial Infection scripts** (`init_infection`, one per news
  and entertainment channel) are the same day-0 material cut for
  the engine's earliest-start mode: a Kentucky radio still running
  1992 campaign spots on KnoxTalk (Governor Cal Fairweather, who
  "hunts, shoots, fishes," against Mahoney, over toxins in the
  fields and "military testing thirty long years ago"), Hitz FM's
  pop, PawsTV's cartoon, the Cook Show and Woodcraft on Life and
  Living, and the first Kentucky reports on the news channels.

## Names the record carries (game world - never history)

These are the game's own people and institutions. They are what a
survivor would say; they are not real, and the "real names as
history" rule (PLAN.md) does not apply to them - it applies to the
real world the record sits inside.

- **Government and military:** General John McGrew (military
  overseer of the Knox Containment Zone); Col. Niall O'Malley; the
  unnamed President (never named anywhere in the record); Governor
  Cal Fairweather of Kentucky (Republican; opponent Mahoney,
  Democrat, in the 1992 race); Louisville Mayor Terence Stahl;
  Sheriff John Carroll; FBI Director Ian Clark; House Speaker Dan
  Dullford (resigned); Louisville police Chief Graham.
- **Medicine and science:** Dr. Janine Cortman (Muldraugh); Dr.
  Jack Galbraithe (former CDC chief scientist); Professor Peter
  Endsleigh; Dr. Tara Handel.
- **Press:** LBMW - Kentucky Radio (93.2): Jackie Jaye, Frank
  Hemingway. WBLN News (TV): Diane, Richard Gershwin, Dawn Stevenson
  ("Talk the Night"), Phil Hartup. Triple-N (TV): Joan, Kirsty
  Cormick, Judge Matt Hass ("the voice of reason"), Daniel Sinclair,
  Mark Spedding. NNR ("What matters to you. What matters to
  America."): Al. Knox Knews: editor Ian J. McCarrock. The Kentucky
  Herald: John Barrister. The National Dispatch: Molly Aoide,
  Richard Carlson, Keith Haroldson, Jeff Franks, Doris Hunt.
- **Clergy:** the Right Reverend Peter Watts; Pastor Robert Clay
  (Fallas Lake Church); Pastor James Hartnell (NNR, after).
- **Ham operators:** Tim (inside the Zone), Hal and Zach (the Air
  National Guard base near Nashville).
- **Companies and places:** Knox Telecommunications (KT); Spiffo's;
  Greene's Grocery; Fossoil; U-Store It; Sammie's; Knox Pack
  Kitchens; Pizza Whirled; Irvington Speedway; Chapelmount Downs;
  the Art Gallery of Louisville; Holy Grace Church, Muldraugh;
  Fallas Lake Church; the Dixie Mobile Park; Route 60, Route 31W,
  the Dixie Highway. Towns named: Muldraugh, West Point, Fort Knox,
  March Ridge, Rosewood, Ekron, Riverside, Brandenburg, Irvington,
  Dixie, Louisville, and "Knox Country."
- **The vocabulary:** "the Knox Event," "the Knox Virus" / "the Knox
  Infection," "the Exclusion Zone" / "the Event Zone" / "the Knox
  Containment Zone," "the Event line" / "the Boundary Line," "the
  Boundary Camp," "the aerial strain" / "the aerial variant," "the
  second wave," "the Immune," "changed people," "walking corpses."

## Where the record touches the real world

The game's writers set the fall inside the real July 1993, and the
national paper keeps carrying real events after the divergence:

- The Iraq-UN standoff over missile-site monitoring (Dispatch, July
  6) and the G7 summit in Tokyo "scheduled to begin on Wednesday"
  July 7 (Dispatch, July 6; Herald, July 6) are real; the divergence
  is the President's cancellation - in history he went. The
  Hokkaido earthquake of the night of July 12 (Dispatch, July 13),
  with its tsunami, Okushiri, and the "last January" quake that
  killed two, is real to the hour. These three are confirmed from
  primary sources in timeline.md; here they are the game's claims.
- The record never names the President, the Vice President, or any
  real official; its governor, mayor, sheriff and general are its
  own. A survivor who names the real President is drawing on the
  real 1993 (timeline.md), not on this record.

## Horizon inside the record

- Anyone in the county carries July 1-6 as lived days: the phones
  out all week, the truck on Route 60, the parade, the smell, the
  dogs, then the illness. Knox Knews stops July 6.
- Inside the cordon from July 6, the news comes by radio and
  television only, and the Louisville and national papers of July
  12-16 are outside knowledge unless found later (the game spawns
  them anywhere; a person's knowledge should not).
- Everyone with a set heard the broadcasts through July 18; the
  static of July 19-20 is when the world stopped delivering news.
  From July 21 there is the loop, the automated weather and power
  bulletins, and whatever amateurs are still transmitting.
- Louisville carried its papers through July 16 and then ran.

## How the record was read

`RadioData.xml` (18 channel entries: 5 radio, 10 television, 2
amateur, 1 military; 905 broadcasts on days 0-27) was joined to
`RadioData.json` (13,166 lines) on `RD_<LineEntry ID>` and written
out day by day; `Print_Text.json` was indexed by title (22 dated
issues of four papers, and about 130 undated flyers, adverts and
notices); the item and distribution scripts and the `Newspaper` and
`RecipeCodeHelper` bytecode were read for how the papers are placed.
The developer's public statements (The Indie Stone's July 2023 post
dating the outbreak to July 6, 1993) were read through the search
index only and are MEDIUM; the shipped files are the primary source
and they say the same thing.
