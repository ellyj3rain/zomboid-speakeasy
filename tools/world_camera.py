"""Choose observer views from observations; never issue character commands."""
from __future__ import annotations

import math


class ActivityCamera:
    """Hold scenes long enough to read, then rotate with activity and fair coverage.

    Movement and changes in recorded activity/awareness attract attention. Recent
    scenes receive a cooldown, so quiet people also get visits. Nearby people
    form a framing group, not an inferred relationship or a simulation target.
    """
    DWELL = 22.0
    RADIUS = 10.0

    def __init__(self):
        self.automatic = True
        self.subjects = []
        self.next_cut = self.next_follow = 0.0
        self.history = []
        self.person_history = {}
        self.previous = {}
        self.activity = {}
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

    def update(self, people, hours, bounds):
        if hours == self.last_hours:
            return
        self.last_hours = hours
        current = {}
        for p in people:
            if not self.eligible(p, bounds):
                continue
            context = p.get("context", {})
            signature = (p["x"], p["y"], p["z"], context.get("controller", {}).get("state"),
                         tuple(sorted(context.get("beliefCounts", {}).items())))
            old = self.previous.get(p["id"])
            value = self.activity.get(p["id"], 0) * 0.85
            if old:
                value += min(math.hypot(signature[0]-old[0], signature[1]-old[1]), 3)
                value += 2 if signature[3] != old[3] else 0
                value += 1 if signature[4] != old[4] else 0
            self.activity[p["id"]] = min(value, 6)
            current[p["id"]] = signature
        self.previous = current
        self.activity = {key: value for key, value in self.activity.items() if key in current}

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
                person_recent = max(0, 8-(now-self.person_history.get(person["id"], -1e9))/20)
                return (self.activity.get(person["id"], 0) + int(represented) - recent - person_recent, person["id"])

            primary = max(candidates, key=score)
            nearby = sorted((p for p in candidates if p["id"] != primary["id"]
                             and self.distance(p, primary) <= self.RADIUS),
                            key=lambda p: (self.distance(p, primary), p["id"]))[:4]
            current = [primary, *nearby]
            self.subjects = [p["id"] for p in current]
            self.person_history.update({p["id"]: now for p in current})
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
        x, y = (sum(p[k] for p in current)/len(current) for k in ("x", "y"))
        z = primary["z"]
        self.next_follow = now + 1.0
        if not cut and math.hypot(x-state["viewX"], y-state["viewY"]) < 0.75 and z == state["viewZ"]:
            return None
        return dict(viewX=x, viewY=y, viewZ=z, residencyX=x, residencyY=y, residencyZ=z)
