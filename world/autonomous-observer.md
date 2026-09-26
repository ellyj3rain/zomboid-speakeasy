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
  --package <native-package-directory> --out <new-feed-directory>
```

Launch Mousecat's native application with
`-MousecatNativeView="<absolute-feed-directory>"`. Each fresh feed is bound to
one native attempt. One bridge owns that attempt's control writer; it can be
reattached after a process exit without reusing native command numbers.

The camera defaults to automatic activity viewing. It holds a scene for about
22 seconds, tracks it at most once a second, and frames one person with up to
four nearby people. Observed movement and changes in activity or awareness
influence selection. Recent-scene and recent-person cooldowns make room for
quieter people and different groups. Nearby framing does not assert a social
relationship. A recorded location can lead to a visit whose native region then
loads; the inspector identifies native-body and durable-record positions.

| Control | Effect |
|---|---|
| WASD, arrows, drag image | Move the camera and take manual control |
| R | Resume automatic activity viewing |
| Tab / Shift+Tab | Inspect another person |
| F | Focus the selected person's observed location; manual control |
| Space | Pause or resume native time |
| 1 / 2 / 3 | Choose native simulation speed |
| Esc | Request native stop and save |

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

The final Record 71 suite passes all 196 Python tests. Its retained receipt
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
