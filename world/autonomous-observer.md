# Autonomous simulation observation

SAO owns the native engine run and its saved evidence. Speakeasy reads that
explicit run, selects camera views and publishes data to Mousecat. Mousecat
displays native pixels and offers camera, time and person-inspection controls.
The world runs without a participating player.

The independent God-view uses native fullbright rendering and a canopy cutaway
to make people visible beneath trees. These are display settings; NPCs retain
their own private awareness. The inspector exposes recorded person state
without switching the renderer into that person's visual experience.

Start the SAO observer, then run this from Speakeasy:

```powershell
python tools/world_watch.py --run <native-run-directory> `
  --package <native-package-directory> --out <new-feed-directory> `
  --registry <mousecat-native-view-registry> `
  --view-id survival-observatory --label "Survival simulation" `
  --project-ref project:survivor-awareness
```

For Mousecat Desktop, configure `nativeViews.registryPath` in the service's
configuration to name a local JSON registry. Each registry entry binds one
session to its explicit feed directory:

```json
[
  {
    "id": "survival-observatory",
    "label": "Survival simulation",
    "projectRef": "project:survivor-awareness",
    "sessionId": "<sessionId from run.json>",
    "directory": "<absolute-feed-directory>"
  }
]
```

The watcher publishes the successor's first complete frame, then atomically
rebinds that stable view ID to the new session. Mousecat refreshes the registry
and follows the displayable replacement, so a completed or disconnected attempt
cannot remain the propagated view after its successor is ready. Open the
installed Desktop's Simulation view. The
compatibility Unreal viewer accepts
`-MousecatNativeView="<absolute-feed-directory>"`. One bridge owns each attempt's
control writer; it can be reattached after a process exit without reusing native
command numbers.

Layouts with a sealed `subjectId` follow that exact person across the authored
world; missing or dead people receive no substitute. Manual browsing applies
to that view, and Follow returns to its assignment. Layouts without assignments
retain automatic activity viewing. It holds a scene for about three seconds,
tracks it at most twice a second, and frames one person with up to
four nearby people. Observed movement and changes in activity or awareness
influence selection. Recent-scene and recent-person cooldowns make room for
quieter people and different groups. Nearby framing does not assert a social
relationship. A recorded location can lead to a visit whose native region then
loads; the inspector identifies native-body and durable-record positions.

The bridge also retains up to four recent activity-camera frames with their
capture times and exact native image identities. Each retained frame carries a
bounded projection of that pictured person's source-reported activity,
attention, memory counts and survival needs, including the source sample time
available when that frame was published.
Mousecat presents the current frame and retained views as an equal-panel
observatory. Panel size, visible screens and the four overlay groups remain
independently adjustable while every panel retains its exact capture time; fresh captions remain quiet. Definition-owned legacy retained activity views are time-multiplexed samples.
Declared independent sites use distinct simultaneous pixels from one native
frame, with one world clock and save. Manual camera frames do not invent an activity subject or
reuse a later person's state, and people absent from the current source
projection are removed from the observatory.

| Control | Effect |
|---|---|
| Panel size | Changes every observatory screen together while preserving equal dimensions |
| View toggles | Hide or restore individual current and retained screens without changing the simulation |
| Activity / Attention / Memory / Needs | Show or hide the corresponding frame-aligned source facts on every screen |
| Arrows or direction buttons | Move the camera and take manual control |
| Follow | Resume the assigned subject, or legacy activity viewing |
| People search and selection | Inspect a person's recorded state |
| Show in world | Focus the selected person's observed location; manual control |
| Open / Close game panel | Control the native inspector for the selected person |
| Pause and speed buttons | Control native simulation time |
| Zoom buttons, wheel, or + / - with the view focused | Change native projection within the engine's reported range |
| End run | Request native stop and save |

These are the Desktop controls. The compatibility viewer retains its existing
keyboard mapping. Zoom preserves activity-camera ownership and simulation speed.
The reported zoom waits for the engine image acknowledging the exact command.

Person detail comes from SAO's cached scalar inspection producer. It retains its
own sample time, source and availability, including native action receipts,
reception and accepted work. The prominent recorded reason copies an available
Controller pressure detail; the bridge does not infer a motive from a person's
position. The selected person receives the bounded detail budget first. Invalid
optional inspection becomes an explicit failure while the core feed continues.

Automatic subject labels wait for a native image carrying the applied camera
command. During a move, the view shows a transition without claiming new
pictured subjects. Partial inspection writes retain the last complete data and
its observation time while camera/time/stop controls remain available. Failed
requests are explicit and cannot strand later requests.

Native physics follows the engine's loaded region. Moving residency changes
which region is physically represented; no camera request changes a person's
coordinates, goals, beliefs or preferred outcome. `camera.jsonl` records the
observer's requested framing as unreviewed evidence. Manual panning moves the
view within the current region; focusing a person or resuming automatic viewing
can visit another region.

`tools/world_study.py` separately imports a completed run through its explicitly
supplied SAO validator. Its geometry/position replay is a diagnostic projection
of recorded fields. Live observation uses the actual engine image.

```powershell
python tools/world_study.py --run <completed-native-run-directory> `
  --package <native-package-directory> `
  --sao-validator <path-to-SAO-tools-world_lab_run.py> `
  --out <new-preview-directory>
```

The importer retains exact source bytes and hashes alongside the validation
receipt and package, validator and projector provenance. Both commands require
fresh output directories. Observation manifests and projected positions do not
establish successful native save/reopen durability.

The Record 72 suite passes all 204 Python tests, including exact image/command
binding for zoom, inspection validation and budget, panel commands, and recorded
reason fidelity. Direct installed Desktop checks verified native pixels, a game
panel, and a 1.0 to 1.25 native zoom change in SAO C87's residential studies.
The Desktop source remains in its separately modified local checkout; this
record publishes the bridge and its contract.

The final Record 71 suite passed all 196 Python tests. Its retained receipt
matches all 44 current Python source hashes and covers intake, partial and stale
frames, exclusive control ownership, command sequencing and activity viewing.

Native27 completed both the first run and a continuation of save
`73517772808093796831`, with native save-return receipts, no runtime errors and
zero saved players. The first run stopped at world hour `2.389998435974121`;
the reopened run started at `2.3903684616088867` and stopped at
`4.684725761413574`. Observation sequence 2 continued at sequence 3, and all
32 identities persisted. The definition, package, engine, agent and copied mod
inventory remained identical across both attempts.

Fresh intake of completed attempt 2, using SAO's actual validator and
`starter-terrain-package-02`, retained ten exact frames in the ignored local
directory `runs/r71-native27-attempt2-intake`. Every retained source hash was
checked; the manifest reports zero training rows and teaching targets, with
all observations unreviewed. [Record 71](../RECORD.md#record-71---native-world-observation-and-activity-camera)
records the receipt seals.

One-minute measurements delivered 10.98 distinct engine images per second in
native24 and 8.04 in native27. Mousecat's 60 FPS display refresh can reuse the
last image; the native capture target remains 20 new images per second and was
not sustained. Short region-loading transitions remain visible. Native physics
and the captured geometry cover loaded regions. These checks establish this
bounded observer and save continuation, not long-horizon social consistency or
general gameplay acceptance.

The bridge and viewer emit zero training rows, teaching targets or approval
receipts. Every scenario requires operator evaluation and explicit ratification
before admission under the existing teaching contract. Watching, stopping,
saving or passing a mechanical check does not perform that ratification.


## Competing cognition

The selected person's inspection includes ordinary and associative model
beliefs, hypotheses, proposals and recorded outcomes. Each model predicts the
same candidate actions before deterministic balanced selection. The display
compares both predictions against the performed action; an unexecuted alternative
remains unobserved. Ordinary cognition has no veto over its competitor. Native
Standing, route and timed-action owners retain physical authority.

The competition controls set the opposing model's allocation share, bounded
deliberation opportunities per county hour and association depth. A complete
three-value command applies atomically, including while time is paused. Mousecat
distinguishes the draft request, native acknowledgement and newer source-observed
settings. Accelerating deliberation supplies opportunities, not knowledge or
success. Associations retain provenance and missing mechanisms; they grant no
recipes, skills or native effects.

Completed native runs can be preserved as aggregate-training candidates:

```powershell
python tools/cognition_episodes.py --run <native-run> --package <native-package> --sao-validator <absolute-path-to-SAO/tools/world_lab_run.py> --out <new-output-directory>
```

SAO's validator first verifies the native package and completed run. Intake
retains source frame hashes, private evidence snapshots, immutable predictions,
selected-action results, disagreements and model revisions. County time remains
distinct from engine world age. Allocation weights describe deterministic
selection and are not random policy propensities. Censored and missing results
never become negative labels. The result includes `episodes.jsonl`,
`snapshots.jsonl` and a hashed manifest with zero training rows and teaching
targets. Existing scenario evaluation governs later dataset admission.

Record 74 extends the same `simulation.cognition/1` envelope for native model
variants `/2`. Archived `/1` proposals retain their original versions and
predictions. Full snapshots can include three further private experiences:

| Experience | Preserved evidence |
|---|---|
| `medication-use` | The person's completed use of a concrete native item, including its signed item ID and type. |
| `physical-change` | Named, finite before/after Stats measurements personally felt by that person. |
| `preparation` | The concrete food item and appliance/source, observed heat and increasing native cooking time. |

The private acquisition clock is `worldHours`; `occurredAtHours` preserves the
earlier occurrence time. Both use county hours, which can include prior years.
Neither can exceed the source observation clock. Source-owned capability
context remains attached to the acquired experience. Medication family,
pharmacological profiles, hidden exposure attribution and efficacy labels are
rejected. Item use and later physical change remain distinct facts. Prepared
food establishes no consumption or hunger relief.

These experiences cannot settle a `food`, `water`, `inspect` or `continue`
episode, create an unexecuted outcome, or grant recipes or skills. Their producer
owns authentic native action completion; Speakeasy validates and preserves the
bounded projection. This extension adds no native model or gameplay code to
Speakeasy and creates no training admission.

## Durable study sessions

An optional SAO session supervisor can place several finite native attempts over
one verified save. The observer bridge projects only its session identifier,
attempt, bounded duration, simulated clocks, status, stop reason and currently
valid save/continue operations. Local paths, executables and arbitrary commands
never enter the native-view contract.

`checkpoint` uses the existing native stop and normal save route. `configure`
writes bounded duration and automatic-continuation settings for the supervisor.
`continue` is admitted only from a saved session. These lifecycle requests use
immutable exact-sequence files and cannot supply a behavior verdict, dataset
admission, teaching target or training row.

Current source `cameraControls` carry a native sample time and engine viewport
independent of pictured `viewport`. A rendered frame can precede a subsequent
camera command without disabling supported zoom. Image labels, overlays and
displayed projection continue to require the captured epoch. The client can
offer Wide, Square or Frame shape and Fit or Fill framing; Window opens a
resizable independent feed with source-routed camera and time controls.

## Continuous native video and observation graph

The optional native `sao-study-video/1` manifest publishes one H264 composite
stream and up to four camera rectangles. Speakeasy verifies immutable stream
identity, initialization format, fragment hashes, native clocks, frame counts,
MP4 sample timing, independent decoding and bounded geometry before relaying
`mousecat.native-video/1`. The source's `fps` is the configured capture ceiling.
It is separate from measured rendering and delivered playback rates. Retained
fragments preserve gaps in source acquisition rather than accelerating time.

Each fragment qualifies its camera pose only when every captured receipt has
the same command epoch and site metadata. Mixed pose fragments keep their
pixels with an empty site receipt. A compatible viewer can retain the last
verified crop while withholding picture-specific pose and person overlays.
Stable video camera acknowledgement uses the fragment's exact final native
clock. PNG `camera` and `viewport` retain their own original image clock;
`videoCamera` carries the separately acknowledged video identity. Current
`cameraControls` continue to describe source command availability.

Verified initialization and media files are source-bound and immutable. The
relay retains a short bounded predecessor window for requests already issued.
Missing, truncated, malformed or unsupported video leaves the ordinary PNG
path usable. A completed stream retains its final fragments for local browsing;
saved-pixel pan and zoom issue no native world or continuation command.

The optional `simulation.observation-graph/1` projection supplies at most 128
nodes and 256 edges from actual people and inspection records. Human labels and
units accompany machine values. Native body and durable record positions retain
their source and fractional floor. Every node and edge carries its own source
record, world time and acquisition time; zero wall time means unknown acquisition.
Graph sample time does not replace a missing source clock.

Explicit cognition episode and action identities connect selected actions and
reported results. Private beliefs and model predictions retain their perspective.
Unselected proposals remain proposals; missing receipts remain unknown. Temporal
and associated observations have their own edge types. Proximity, chronology and
later physical changes cannot manufacture a causal outcome or externality.
