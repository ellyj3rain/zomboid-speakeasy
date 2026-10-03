"""Choose observer views from observations; never issue character commands."""
from __future__ import annotations

import math


class ActivityCamera:
    """Hold scenes long enough to read, then rotate with activity and fair coverage.

    Observed harm, danger and critical needs preempt ordinary activity. Movement
    relative to a known threat, consequential action changes and ordinary motion
    follow. Within the same urgency, primary views rotate fairly. Nearby people
    form a framing group, not an inferred relationship or a simulation target.
    """
    # One native renderer supplies every observatory tile. Rotate quickly
    # enough that four retained views behave as a near-live contact sheet while
    # still leaving several complete frames at each location.
    DWELL = 3.0
    FOLLOW = 0.5
    RADIUS = 10.0

    def __init__(self):
        self.automatic = True
        self.subjects = []
        self.next_cut = self.next_follow = 0.0
        self.history = []
        self.person_history = {}
        self.previous = {}
        self.activity = {}
        self.priority = {}
        self.last_hours = None
        self.description = "Waiting for observed people"
        self.shot = 0

    @staticmethod
    def eligible(person, bounds):
        return (not person.get("record", {}).get("dead")
                and all(type(person.get(k)) in (int, float) and math.isfinite(person[k]) for k in ("x", "y", "z"))
                and bounds[0] <= person["x"] <= bounds[2] and bounds[1] <= person["y"] <= bounds[3]
                and -32 <= person["z"] < 32)

    @staticmethod
    def distance(a, b):
        return math.hypot(a["x"] - b["x"], a["y"] - b["y"]) if int(a["z"]) == int(b["z"]) else math.inf

    @staticmethod
    def label(person):
        record = person.get("record", {})
        return " ".join(str(record.get(k, "")) for k in ("forename", "surname")).strip() or person["id"]

    @staticmethod
    def number(value, default=None):
        if type(value) in (int, float) and math.isfinite(value):
            return float(value)
        try:
            result = float(value)
            return result if math.isfinite(result) else default
        except (TypeError, ValueError):
            return default

    @classmethod
    def physical_state(cls, person):
        """Read only source-reported current physiology from the observation."""
        values = {}
        inspection = person.get("context", {}).get("inspection", {})
        for section in inspection.get("sections", []) if isinstance(inspection, dict) else []:
            if section.get("id") != "needs" or section.get("status") != "available":
                continue
            for row in section.get("rows", []):
                values[str(row.get("label", "")).strip().upper()] = cls.number(row.get("value"))
        recorded = person.get("record", {})
        native = recorded.get("pharmacology", {}).get("observed", {}).get("stats", {})
        for key, value in native.items() if isinstance(native, dict) else []:
            values.setdefault(str(key).upper(), cls.number(value))
        health = values.get("HEALTH (%)")
        if health is not None:
            health /= 100
        else:
            health = cls.number(recorded.get("lastLivingHealth"), 1)
            if health is not None and health > 1:
                health /= 100
        return {"health": max(0, min(1, health if health is not None else 1)),
                "hunger": max(0, min(1, values.get("HUNGER") or 0)),
                "thirst": max(0, min(1, values.get("THIRST") or 0)),
                "fatigue": max(0, min(1, values.get("FATIGUE") or 0)),
                "pain": max(0, min(1, values.get("PAIN") or 0)),
                "panic": max(0, min(1, values.get("PANIC") or 0)),
                "endurance": max(0, min(1, values.get("ENDURANCE") if values.get("ENDURANCE") is not None else 1)),
                "wounds": max(0, cls.number(recorded.get("woundCarried"), 0))}

    @classmethod
    def threats(cls, person):
        known = person.get("context", {}).get("beliefs", {}).get("zombies", {})
        if not isinstance(known, dict):
            return 0, math.inf
        distances = []
        for threat in known.values():
            if not isinstance(threat, dict):
                continue
            distance = cls.number(threat.get("dist"))
            x, y, z = (cls.number(threat.get(key)) for key in ("x", "y", "z"))
            if x is not None and y is not None and (z is None or int(z) == int(person["z"])):
                distance = math.hypot(person["x"] - x, person["y"] - y)
            if distance is not None and distance >= 0:
                distances.append(distance)
        return len(known), min(distances, default=math.inf)

    @staticmethod
    def survival_priority(signature, old, movement):
        body = signature["body"]
        health_drop = max(0, (old or {}).get("body", {}).get("health", body["health"]) - body["health"])
        need = max(body["hunger"], body["thirst"], body["fatigue"])
        threat_count, threat_distance = signature["threats"]
        old_distance = (old or {}).get("threats", (0, math.inf))[1]
        threat_motion = (abs(old_distance - threat_distance)
                         if math.isfinite(old_distance) and math.isfinite(threat_distance) else 0)
        if health_drop >= .005:
            return 6, 100 + health_drop * 100, "active health loss"
        if body["health"] < .55 or body["pain"] >= .65:
            return 5, (1-body["health"]) * 20 + body["pain"] * 10, "severe injury or pain"
        if threat_count and (threat_distance <= 12 or body["panic"] >= .35):
            return 5, max(0, 12-threat_distance) + body["panic"] * 10 + threat_count, "immediate known danger"
        if need >= .75 or body["endurance"] <= .2:
            return 4, need * 10 + (1-body["endurance"]) * 5, "critical survival need"
        if threat_count and threat_distance <= 30 and movement >= 1.5 and threat_motion >= .5:
            return 4, movement + threat_motion + max(0, 20-threat_distance) / 4, "rapid movement relative to danger"
        if body["health"] < .8 or body["wounds"] > 0 or need >= .5:
            return 3, (1-body["health"]) * 10 + body["wounds"] + need * 5, "elevated injury or survival pressure"
        state = str(signature.get("state") or "").upper()
        if any(token in state for token in ("ATTACK", "COMBAT", "FLEE", "ESCAPE", "TREAT", "BANDAGE", "EAT", "DRINK")):
            return 2, 1, "consequential survival action"
        if old and state != str(old.get("state") or "").upper():
            return 1, 1, "changed action"
        return 0, 0, ""

    def update(self, people, hours, bounds):
        if hours == self.last_hours:
            return
        self.last_hours = hours
        current = {}
        for p in people:
            if not self.eligible(p, bounds):
                continue
            context = p.get("context", {})
            signature = {"x": p["x"], "y": p["y"], "z": p["z"],
                         "state": context.get("controller", {}).get("state"),
                         "beliefs": tuple(sorted(context.get("beliefCounts", {}).items())),
                         "body": self.physical_state(p), "threats": self.threats(p)}
            old = self.previous.get(p["id"])
            value = self.activity.get(p["id"], 0) * 0.85
            movement = 0
            if old:
                movement = math.hypot(signature["x"]-old["x"], signature["y"]-old["y"])
                value += min(movement, 3)
                value += 2 if signature["state"] != old["state"] else 0
                value += 1 if signature["beliefs"] != old["beliefs"] else 0
            self.activity[p["id"]] = min(value, 6)
            self.priority[p["id"]] = self.survival_priority(signature, old, movement)
            current[p["id"]] = signature
        self.previous = current
        self.activity = {key: value for key, value in self.activity.items() if key in current}
        self.priority = {key: value for key, value in self.priority.items() if key in current}

    def manual(self):
        self.automatic = False
        self.subjects = []
        self.description = "Manual camera; R resumes activity viewing"

    def resume(self):
        self.automatic = True
        self.subjects = []
        self.next_cut = self.next_follow = 0.0
        self.description = "Finding an observed scene"

    def view(self, people):
        available = {p["id"] for p in people}
        return {"mode": "automatic" if self.automatic else "manual",
                "personIds": [key for key in self.subjects if key in available][:5],
                "summary": self.description[:512]}

    def plan(self, people, hours, state, bounds, now):
        self.update(people, hours, bounds)
        if not self.automatic or state["paused"] or state.get("failure") or now < self.next_follow:
            return None
        candidates = [p for p in people if self.eligible(p, bounds)]
        if not candidates:
            self.subjects = []
            self.description = "Waiting for observed people"
            return None
        by_id = {p["id"]: p for p in candidates}
        current = [by_id[key] for key in self.subjects if key in by_id]
        cut = not current or now >= self.next_cut
        if cut:
            self.history = [(point, when) for point, when in self.history if now-when < 180]

            def score(person):
                recent = max((max(0, 14-(now-when)/5) for point, when in self.history
                              if self.distance(person, point) < 24), default=0)
                represented = person.get("positionSource") == "native-body"
                last_primary = self.person_history.get(person["id"], -1e9)
                urgency, consequence, _reason = self.priority.get(person["id"], (0, 0, ""))
                # Survival urgency preempts ordinary rotation. Within the same
                # urgency, the oldest primary wins, so a close group still gives
                # each person an individual view instead of counting neighbours.
                return (urgency, -last_primary, consequence if urgency else 0,
                         self.activity.get(person["id"], 0) + int(represented) - recent,
                        person["id"])

            primary = max(candidates, key=score)
            nearby = sorted((p for p in candidates if p["id"] != primary["id"]
                             and self.distance(p, primary) <= self.RADIUS),
                            key=lambda p: (self.distance(p, primary), p["id"]))[:4]
            current = [primary, *nearby]
            self.subjects = [p["id"] for p in current]
            self.person_history[primary["id"]] = now
            self.history.append(({k: primary[k] for k in ("x", "y", "z")}, now))
            self.next_cut = now + self.DWELL
            self.shot += 1
        else:
            # A group can disperse; frame people still near the primary subject.
            current = [current[0], *(p for p in current[1:] if self.distance(p, current[0]) <= self.RADIUS)]
            self.subjects = [p["id"] for p in current]
        primary = current[0]
        activity = primary.get("context", {}).get("controller", {}).get("state")
        self.description = "Watching " + self.label(primary)
        if len(current) > 1:
            self.description += f" with {len(current)-1} nearby"
        self.description += "; " + (str(activity).lower() if activity else "visiting recorded location")
        reason = self.priority.get(primary["id"], (0, 0, ""))[2]
        if reason:
            self.description += "; priority: " + reason
        x, y = (sum(p[k] for p in current)/len(current) for k in ("x", "y"))
        z = primary["z"]
        self.next_follow = now + self.FOLLOW
        if not cut and math.hypot(x-state["viewX"], y-state["viewY"]) < 0.75 and z == state["viewZ"]:
            return None
        return dict(viewX=x, viewY=y, viewZ=z, residencyX=x, residencyY=y, residencyZ=z)


class SubjectCamera(ActivityCamera):
    """Follow one declared person without changing their assignment or state."""

    def __init__(self, subject_id, bounds):
        super().__init__()
        self.subject_id = subject_id
        self.bounds = bounds
        self.description = "Waiting for assigned subject"

    def subject(self, people):
        person = next((person for person in people if person["id"] == self.subject_id), None)
        if person is None:
            return None, "Assigned subject unavailable: not observed"
        if person.get("record", {}).get("dead"):
            return None, "Assigned subject unavailable: recorded dead"
        if not all(type(person.get(key)) in (int, float) and math.isfinite(person[key])
                   for key in ("x", "y", "z")):
            return None, "Assigned subject unavailable: position unavailable"
        if not self.eligible(person, self.bounds):
            return None, "Assigned subject unavailable: outside observed world"
        return person, None

    def manual(self):
        super().manual()
        self.description = "Manual camera; resume follows the assigned subject"

    def resume(self):
        super().resume()
        self.description = "Waiting for assigned subject image"

    def view(self, people):
        if not self.automatic:
            return super().view([])
        _person, unavailable = self.subject(people)
        if unavailable:
            return {"mode": "automatic", "personIds": [], "summary": unavailable}
        if not self.subjects:
            return {"mode": "automatic", "personIds": [], "summary": "Waiting for assigned subject image"}
        return super().view(people)

    def plan(self, people, hours, state, bounds, now):
        person, unavailable = self.subject(people)
        if unavailable:
            self.subjects = []
            self.next_follow = 0.0
            self.description = unavailable
            return None
        if not self.automatic or state["paused"] or state.get("failure") or now < self.next_follow:
            return None
        initial = not self.subjects
        x, y, z = (person[key] for key in ("x", "y", "z"))
        self.subjects = [self.subject_id]
        self.description = "Following " + self.label(person)
        self.next_follow = now + self.FOLLOW
        if not initial and math.hypot(x-state["viewX"], y-state["viewY"]) < .75 and z == state["viewZ"]:
            return None
        self.shot += 1
        return dict(viewX=x, viewY=y, viewZ=z, residencyX=x, residencyY=y, residencyZ=z)
