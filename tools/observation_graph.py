"""Bounded observation graph from native records and independently timed receipts.

This projection describes observations and private reasoning. Its associations
are source references; spatial or temporal proximity never creates a cause.
"""
from __future__ import annotations

import hashlib
import json
import math

import cognition_contract as Cognition

SCHEMA = "simulation.observation-graph/1"
MAX_NODES, MAX_EDGES = 128, 256
KINDS = {"person", "belief", "hypothesis", "decision", "action", "outcome", "event",
         "need", "unknown", "externality"}
PERSPECTIVES = {"observed", "private", "predicted", "unknown"}
RELATIONS = {"reports", "considers", "selects", "predicts", "result", "supports",
             "refutes", "correlates", "observes", "precedes"}
ACTION_LABELS = {"food": "Seek food", "water": "Seek water", "inspect": "Inspect a place",
                 "continue": "Continue current activity"}
MODEL_LABELS = {"ordinary": "Ordinary model", "associative": "Associative model"}
SOURCE_FIELDS = {"name", "recordId", "worldHours", "capturedAtUnixMs"}


def _require(condition, message):
    if not condition:
        raise ValueError("observation graph: " + message)


def _finite(value, low=None, high=None):
    try:
        return (type(value) in (int, float) and math.isfinite(value)
                and (low is None or value >= low) and (high is None or value <= high))
    except OverflowError:
        return False


def _text(value, limit, empty=False):
    return (isinstance(value, str) and (empty or bool(value)) and len(value) <= limit
            and not any((ord(c) < 32 and c not in "\n\t") or ord(c) == 127 for c in value))


def _caption(value, limit):
    # This is presentation shortening. Native record IDs are never shortened.
    return value if len(value) <= limit else value[:limit - 1] + "…"


def _id(kind, *parts):
    identity = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return kind + ":" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:40]


def _source(name, record, hours=None, captured=0):
    return dict(name=_caption(name, 160), recordId=record, worldHours=hours,
                capturedAtUnixMs=captured)


def _metric(key, label, value, unit="", description=""):
    return dict(key=key, label=_caption(label, 160), value=value, unit=unit,
                description=_caption(description, 512))


def _metric_value(node, key):
    return next((m["value"] for m in node.get("metrics", []) if m["key"] == key), None)


def validate_observation_graph(value):
    """Validate the public graph contract; return value or raise ValueError."""
    required = {"schema", "status", "message", "capturedAtUnixMs", "worldHours",
                "nodes", "edges", "omittedNodes", "omittedEdges"}
    _require(isinstance(value, dict) and set(value) == required, "top-level fields differ")
    _require(value["schema"] == SCHEMA and value["status"] in {"available", "unavailable", "failed"},
             "schema or status differs")
    _require(_text(value["message"], 512, True), "invalid message")
    for key in ("capturedAtUnixMs", "omittedNodes", "omittedEdges"):
        _require(type(value[key]) is int and value[key] >= 0, "invalid " + key)
    available = value["status"] == "available"
    _require(_finite(value["worldHours"], 0) if available else value["worldHours"] is None,
             "invalid graph clock")
    _require(isinstance(value["nodes"], list) and len(value["nodes"]) <= MAX_NODES
             and isinstance(value["edges"], list) and len(value["edges"]) <= MAX_EDGES,
             "collection limit")
    _require(available or not value["nodes"] and not value["edges"], "unavailable graph has facts")

    def source(entry):
        _require(isinstance(entry, dict) and set(entry) == SOURCE_FIELDS, "source fields differ")
        _require(_text(entry["name"], 160) and _text(entry["recordId"], 180), "invalid source identity")
        hours, captured = entry["worldHours"], entry["capturedAtUnixMs"]
        _require(hours is None or _finite(hours, 0, value["worldHours"]), "future or invalid source hour")
        _require(type(captured) is int and 0 <= captured <= value["capturedAtUnixMs"],
                 "future or invalid source capture time")

    nodes = {}
    node_required = {"id", "kind", "label", "summary", "perspective", "actorId", "source", "status"}
    for node in value["nodes"]:
        _require(isinstance(node, dict) and node_required <= node.keys()
                 and set(node) <= node_required | {"position", "confidence", "metrics"}, "node fields differ")
        for key, limit in (("id", 180), ("label", 160), ("summary", 512), ("actorId", 128), ("status", 80)):
            _require(_text(node[key], limit, key == "summary"), "invalid node " + key)
        _require(node["kind"] in KINDS and node["perspective"] in PERSPECTIVES, "unknown node type")
        _require(node["id"] not in nodes, "duplicate node identity")
        nodes[node["id"]] = node
        source(node["source"])
        if "confidence" in node:
            _require(_finite(node["confidence"], 0, 1), "invalid node confidence")
        if "position" in node:
            p = node["position"]
            _require(isinstance(p, dict) and set(p) == {"x", "y", "z", "source"}
                     and _finite(p["x"]) and _finite(p["y"]) and _finite(p["z"], -32)
                     and p["z"] < 32 and _text(p["source"], 80), "invalid position")
            _require(node["kind"] == "person" and p["source"] in {"native-body", "durable-record"},
                     "position lacks native or durable provenance")
            _require((p["source"] == "native-body" and node["perspective"] == "observed")
                     or (p["source"] == "durable-record" and node["perspective"] == "unknown"),
                     "position perspective differs from provenance")
        metrics = node.get("metrics", [])
        _require(isinstance(metrics, list) and len(metrics) <= 16, "metric limit")
        seen = set()
        for metric in metrics:
            _require(isinstance(metric, dict) and set(metric) == {"key", "label", "value", "unit", "description"},
                     "metric fields differ")
            for key, limit in (("key", 80), ("label", 160), ("unit", 80), ("description", 512)):
                _require(_text(metric[key], limit, key in {"unit", "description"}), "invalid metric " + key)
            _require(metric["key"] not in seen, "duplicate metric key")
            seen.add(metric["key"])
            v = metric["value"]
            _require(type(v) is bool or _finite(v) or _text(v, 512, True), "invalid metric value")

    seen = set()
    edge_required = {"id", "from", "to", "relation", "label", "perspective", "source"}
    for edge in value["edges"]:
        _require(isinstance(edge, dict) and edge_required <= edge.keys()
                 and set(edge) <= edge_required | {"confidence"}, "edge fields differ")
        _require(_text(edge["id"], 180) and edge["id"] not in seen
                 and _text(edge["label"], 160), "invalid or duplicate edge identity")
        seen.add(edge["id"])
        _require(edge["from"] in nodes and edge["to"] in nodes, "missing edge endpoint")
        _require(edge["relation"] in RELATIONS and edge["perspective"] in PERSPECTIVES, "unknown edge type")
        source(edge["source"])
        if "confidence" in edge:
            _require(_finite(edge["confidence"], 0, 1), "invalid edge confidence")
        origin, target = nodes[edge["from"]], nodes[edge["to"]]
        if edge["relation"] == "selects":
            _require(origin["kind"] == "decision" and target["kind"] == "action"
                     and origin["actorId"] == target["actorId"]
                     and isinstance(_metric_value(origin, "selectedActionId"), str)
                     and isinstance(_metric_value(origin, "episodeId"), str)
                     and _metric_value(origin, "selectedActionId") == _metric_value(target, "actionId")
                     and _metric_value(origin, "episodeId") == _metric_value(target, "episodeId"),
                     "selected action differs from decision receipt")
        if edge["relation"] == "result":
            _require(origin["kind"] == "action" and target["kind"] == "outcome"
                     and origin["actorId"] == target["actorId"]
                     and isinstance(_metric_value(origin, "actionId"), str)
                     and isinstance(_metric_value(origin, "episodeId"), str)
                     and _metric_value(origin, "actionId") == _metric_value(target, "actionId")
                     and _metric_value(origin, "episodeId") == _metric_value(target, "episodeId")
                     and _metric_value(origin, "selected") is True,
                     "outcome attached to an unexecuted alternative")
    return value


class _Builder:
    def __init__(self, captured, hours):
        self.value = dict(schema=SCHEMA, status="available", message="", capturedAtUnixMs=captured,
                          worldHours=hours, nodes=[], edges=[], omittedNodes=0, omittedEdges=0)
        self.nodes = {}
        self.seen_nodes, self.seen_edges = set(), set()
        self.missing = 0
        self.future = 0
        self.invalid = 0
        self.inspected = 0
        self.cognitions = 0

    def node(self, kind, identity, actor, label, summary, perspective, source, status, **optional):
        ident = _id(kind, *identity)
        if ident in self.seen_nodes:
            return ident
        self.seen_nodes.add(ident)
        if len(self.nodes) == MAX_NODES:
            self.value["omittedNodes"] += 1
            return ident
        node = dict(id=ident, kind=kind, label=_caption(label, 160), summary=_caption(summary, 512),
                    perspective=perspective, actorId=actor, source=source, status=status, **optional)
        self.nodes[ident] = node
        self.value["nodes"].append(node)
        return ident

    def edge(self, origin, target, relation, label, perspective, source):
        ident = _id("edge", origin, target, relation, source["name"], source["recordId"])
        if ident in self.seen_edges:
            return
        self.seen_edges.add(ident)
        if origin not in self.nodes or target not in self.nodes or len(self.value["edges"]) == MAX_EDGES:
            self.value["omittedEdges"] += 1
            return
        self.value["edges"].append(dict(id=ident, **{"from": origin, "to": target}, relation=relation,
                                        label=_caption(label, 160), perspective=perspective, source=source))

    def in_time(self, hours=None, captured=0):
        if ((hours is not None and not _finite(hours, 0))
                or type(captured) is not int or captured < 0):
            self.invalid += 1
            return False
        if ((hours is not None and hours > self.value["worldHours"])
                or captured > self.value["capturedAtUnixMs"]):
            self.future += 1
            return False
        return True

    def unknown(self, actor, record, summary, label="Source unavailable"):
        return self.node("unknown", (actor, "unavailable", record), actor, label, summary,
                         "unknown", _source("Projection coverage", record), "unavailable")


def _empty(status, captured, message):
    return dict(schema=SCHEMA, status=status, message=message, capturedAtUnixMs=captured,
                worldHours=None, nodes=[], edges=[], omittedNodes=0, omittedEdges=0)


def _snapshot_clock(detail, builder):
    if "worldHours" not in detail and "capturedAtUnixMs" not in detail:
        return None, 0
    hours, captured = detail.get("worldHours"), detail.get("capturedAtUnixMs", 0)
    return (hours, captured) if builder.in_time(hours, captured) else None


def _section(builder, actor, person_node, section, clock):
    required = {"id", "label", "source", "perspective", "status", "message", "rows"}
    if not (isinstance(section, dict) and set(section) == required
            and all(_text(section.get(k), n, k == "message") for k, n in
                    (("id", 128), ("label", 160), ("source", 160), ("perspective", 160), ("message", 1024)))
            and section.get("status") in {"available", "unavailable", "failed"}
            and isinstance(section.get("rows"), list) and len(section["rows"]) <= 48
            and all(isinstance(r, dict) and set(r) == {"label", "value"}
                    and _text(r["label"], 160, True) and _text(r["value"], 384, True) for r in section["rows"])):
        builder.invalid += 1
        return
    source = _source(section["source"], section["id"], *clock)
    available = section["status"] == "available"
    # Section perspective is free text. Only verified physical owners become
    # observed; decision, plan and process summaries retain private attribution.
    physical = ((section["id"] in {"needs", "attention"} and section["source"] == "Native body")
                or (section["id"] == "inventory" and section["source"] == "Native inventory containers"))
    perspective = ("observed" if physical else "private") if available else "unknown"
    rows = section["rows"] if available else []
    metrics = []
    for index, row in enumerate(rows):
        unit = ""
        if section["id"] == "needs":
            unit = "%" if row["label"] == "Health (%)" else "native ratio"
        metrics.append(_metric("row-" + str(index), row["label"] or "Recorded value", row["value"], unit,
                               "Exact source row; " + section["perspective"]))
    # Split long source sections into bounded nodes without dropping rows.
    chunks = [metrics[i:i + 16] for i in range(0, len(metrics), 16)] or [[]]
    for index, chunk in enumerate(chunks):
        kind = "need" if physical and section["id"] == "needs" and available else "belief" if available else "unknown"
        summary = section["message"] or section["perspective"]
        node = builder.node(kind, (actor, "section", section["id"], index), actor, section["label"], summary,
                            perspective, source, section["status"], metrics=chunk)
        builder.edge(person_node, node, "reports", "Recorded state", perspective, source)
    if not available:
        builder.missing += 1


def _events(builder, actor, person_node, values, receipts):
    if not isinstance(values, list) or len(values) > 24:
        builder.invalid += 1
        return
    groups, seen = {}, set()
    for event in values:
        required = {"id", "capturedAtUnixMs", "worldHours", "source", "stage", "summary"}
        if not (isinstance(event, dict) and required <= event.keys()
                and set(event) <= required | {"actorId", "recipientId", "correlationId"}
                and all(_text(event.get(k), n) for k, n in
                        (("id", 128), ("source", 160), ("stage", 128), ("summary", 1024)))
                and all(_text(event[k], 128) for k in ("actorId", "recipientId", "correlationId") if k in event)
                and _finite(event.get("worldHours"), 0)
                and event["id"] not in seen):
            builder.invalid += 1
            continue
        seen.add(event["id"])
        if not builder.in_time(event["worldHours"], event["capturedAtUnixMs"]):
            continue
        source = _source(event["source"], event["id"], event["worldHours"], event["capturedAtUnixMs"])
        metrics = [_metric("stage", "Recorded stage", event["stage"])]
        for key, label in (("actorId", "Recorded actor"), ("recipientId", "Named recipient"),
                           ("correlationId", "Correlation receipt")):
            if key in event:
                metrics.append(_metric(key, label, event[key]))
        node = builder.node("event", (actor, "event", event["source"], event["id"]),
                            event.get("actorId", actor), _caption(event["summary"], 160), event["summary"],
                            "observed", source, _caption(event["stage"], 80), metrics=metrics)
        receipts.setdefault(event["id"], []).append(node)
        builder.edge(person_node, node, "reports", "Recorded event", "observed", source)
        if "correlationId" in event:
            key = (event["source"], event["correlationId"])
            if key in groups:
                builder.edge(groups[key], node, "correlates", "Shared correlation receipt", "observed", source)
            else:
                groups[key] = node


def _cognition(builder, actor, person_node, raw, clock, receipts):
    try:
        view = Cognition.projection(raw, actor, full=True)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        builder.invalid += 1
        builder.missing += 1
        unknown = builder.unknown(actor, "cognition", "Cognitive source failed validation; no predictions or outcomes were projected.")
        builder.edge(person_node, unknown, "reports", "Cognitive source unavailable", "unknown",
                     _source("Projection coverage", "cognition"))
        return
    builder.cognitions += 1
    hypothesis_nodes, parent_links, evidence_links = {}, [], []
    for model in sorted(view["models"], key=lambda v: v["id"]):
        name = MODEL_LABELS[model["id"]]
        for belief in model["beliefs"]:
            source = _source(name, belief["id"], *clock)
            node = builder.node("belief", (actor, model["id"], "belief", belief["id"]), actor,
                                belief["label"], "Private belief recorded by " + name.lower(), "private", source,
                                belief["status"], confidence=belief["confidence"],
                                metrics=[_metric("modelId", "Model", model["id"]),
                                         _metric("modelVersion", "Model version", model["version"])])
            builder.edge(person_node, node, "reports", "Private belief", "private", source)
        for hypothesis in model["hypotheses"]:
            source = _source(name, hypothesis["id"], *clock)
            metrics = [_metric("modelId", "Model", model["id"]), _metric("branch", "Reasoning branch", hypothesis["branch"]),
                       _metric("depth", "Reasoning depth", hypothesis["depth"], "steps")]
            metrics += [_metric("missing-" + str(i), "Unknown mechanism", item) for i, item in enumerate(hypothesis["missing"])]
            node = builder.node("hypothesis", (actor, model["id"], "hypothesis", hypothesis["id"]), actor,
                                hypothesis["label"], "Private hypothesis; status describes this model's evidence assessment.",
                                "private", source, hypothesis["status"], confidence=hypothesis["confidence"], metrics=metrics)
            hypothesis_nodes[(model["id"], hypothesis["id"])] = node
            builder.edge(person_node, node, "considers", "Private hypothesis", "private", source)
            parent_links += [(node, model["id"], ref, source) for ref in hypothesis["parentIds"]]
            evidence_links += [(node, ref, source) for ref in hypothesis["evidenceIds"]]
    proposals_to_hypotheses = []
    for episode in sorted(view["episodes"], key=lambda v: (v["worldHours"], v["id"]), reverse=True):
        if not builder.in_time(episode["worldHours"]):
            continue
        source = _source("Cognitive decision receipt", episode["id"], episode["worldHours"])
        decision = builder.node("decision", (actor, "decision", episode["id"]), actor,
                                "Decision: " + ACTION_LABELS[episode["selectedActionId"]].lower(),
                                episode.get("reason") or "Selected from two independently recorded model proposals.",
                                "private", source, episode.get("executionStatus", episode["status"]),
                                metrics=[_metric("episodeId", "Decision receipt", episode["id"]),
                                         _metric("selectedActionId", "Selected action", episode["selectedActionId"]),
                                         _metric("selectedModelId", "Selected model", episode["selectedModelId"]),
                                         _metric("selectionWeight", "Selection weight", episode["selectionWeight"], "ratio"),
                                         _metric("disagreement", "Models chose different actions", episode["disagreement"]),
                                         _metric("hunger", "Hunger at decision", episode["frame"]["hunger"], "native ratio"),
                                         _metric("thirst", "Thirst at decision", episode["frame"]["thirst"], "native ratio"),
                                         _metric("fatigue", "Fatigue at decision", episode["frame"]["fatigue"], "native ratio")])
        builder.edge(person_node, decision, "reports", "Private decision receipt", "private", source)
        actions = {}
        for action in sorted(Cognition.ACTIONS):
            selected = action == episode["selectedActionId"]
            node = builder.node("action", (actor, "action", episode["id"], action), actor, ACTION_LABELS[action],
                                "Selected action; execution status is recorded separately." if selected else "Unexecuted alternative; outcome unknown.",
                                "private" if selected else "predicted", source,
                                episode.get("executionStatus", episode["status"]) if selected else "alternative",
                                metrics=[_metric("episodeId", "Decision receipt", episode["id"]),
                                         _metric("actionId", "Action identifier", action),
                                         _metric("selected", "Selected", selected)])
            actions[action] = node
        builder.edge(decision, actions[episode["selectedActionId"]], "selects", "Selected action", "private", source)
        outcome = episode.get("outcome")
        if outcome and builder.in_time(outcome["worldHours"]):
            outcome_source = _source("Native outcome receipt", outcome["eventId"], outcome["worldHours"])
            qualified = episode["status"] == "observed" and outcome["status"] in {"completed", "no-effect"}
            metrics = [_metric("episodeId", "Decision receipt", episode["id"]),
                       _metric("actionId", "Executed action", outcome["actionId"])]
            if "success" in outcome:
                metrics.append(_metric("success", "Qualified outcome", outcome["success"]))
            node = builder.node("outcome", (actor, "outcome", episode["id"], outcome["eventId"]), actor,
                                ACTION_LABELS[outcome["actionId"]] + ": " + outcome["status"],
                                outcome.get("detail") or "Native receipt for the selected action.",
                                "observed" if qualified else "unknown", outcome_source, outcome["status"], metrics=metrics)
            receipts.setdefault(outcome["eventId"], []).append(node)
            builder.edge(actions[episode["selectedActionId"]], node, "result", "Recorded result", "observed" if qualified else "unknown",
                         outcome_source)
        for proposal in sorted(episode["proposals"], key=lambda v: v["modelId"]):
            for action in sorted(Cognition.ACTIONS):
                prediction = proposal["predictions"][action]
                prediction_source = _source(MODEL_LABELS[proposal["modelId"]] + " prediction", episode["id"], episode["worldHours"])
                node = builder.node("hypothesis", (actor, "prediction", episode["id"], proposal["modelId"], action), actor,
                                    MODEL_LABELS[proposal["modelId"]] + ": " + ACTION_LABELS[action].lower(), prediction["claim"],
                                    "predicted", prediction_source, "prediction", confidence=proposal["confidence"],
                                    metrics=[_metric("episodeId", "Decision receipt", episode["id"]),
                                             _metric("modelId", "Predicting model", proposal["modelId"]),
                                             _metric("modelVersion", "Model version", proposal["version"]),
                                             _metric("actionId", "Predicted action", action),
                                             _metric("probability", "Predicted probability", prediction["probability"], "probability"),
                                             _metric("interpretation", "Private interpretation", proposal["interpretation"])])
                builder.edge(node, actions[action], "predicts", "Prediction for this action", "predicted", prediction_source)
                if proposal["actionId"] == action:
                    builder.edge(decision, node, "considers", "Model's proposed action", "private", source)
                if proposal.get("hypothesisId"):
                    proposals_to_hypotheses.append((node, proposal["modelId"], proposal["hypothesisId"], prediction_source))
    for experience in view.get("experiences", []):
        if not builder.in_time(experience["worldHours"]):
            continue
        private = experience["kind"] in Cognition.PRIVATE_EXPERIENCES
        source = _source("Private native experience" if private else "Native experience", experience["id"], experience["worldHours"])
        metrics = [_metric("kind", "Recorded activity", experience["kind"]),
                   _metric("category", "Category", experience["category"]),
                   _metric("observerId", "Observer", actor)]
        for key, label in (("sourceId", "Recorded source"), ("itemType", "Item type"), ("episodeId", "Decision reference"),
                           ("foodPresent", "Food inspected"), ("waterPresent", "Water inspected"),
                           ("hungerDelta", "Measured hunger change"), ("thirstDelta", "Measured thirst change")):
            if key in experience:
                metrics.append(_metric(key, label, experience[key]))
        node = builder.node("event", (actor, "experience", experience["id"]), experience["actorId"],
                            experience["kind"].replace("-", " ").capitalize() + ": " + experience["status"],
                            experience.get("detail") or "Native experience acquired by this observer.",
                            "private" if private else "observed", source, experience["status"], metrics=metrics)
        receipts.setdefault(experience["id"], []).append(node)
        builder.edge(person_node, node, "observes", "Acquired personal experience", "private" if private else "observed", source)

    def missing_ref(ref, label):
        builder.missing += 1
        return builder.unknown(actor, ref, "The source names this receipt, but its contents are absent from this projection.", label)

    for origin, model, ref, source in parent_links + proposals_to_hypotheses:
        target = hypothesis_nodes.get((model, ref)) or missing_ref(ref, "Hypothesis reference unavailable")
        builder.edge(origin, target, "considers", "Recorded hypothesis reference", "private", source)
    for origin, ref, source in evidence_links:
        targets = list(dict.fromkeys(receipts.get(ref, [])))
        # Ambiguous references remain unknown; neither timing nor status chooses
        # one event and no evidence reference by itself asserts causation.
        target = targets[0] if len(targets) == 1 else missing_ref(ref, "Evidence reference unavailable")
        builder.edge(origin, target, "reports", "Recorded evidence reference", "private", source)
    omitted = {"episodes": view["omittedEpisodes"], "experiences": view["omittedExperiences"]}
    omitted["beliefs"] = sum(m.get("omittedBeliefs", 0) for m in view["models"])
    omitted["hypotheses"] = sum(m.get("omittedHypotheses", 0) for m in view["models"])
    if any(omitted.values()):
        node = builder.node("unknown", (actor, "cognitive-coverage"), actor, "Cognitive projection is partial",
                            "These counts belong to the source projection; missing content cannot be reconstructed.",
                            "unknown", _source("Cognitive projection coverage", actor, *clock), "partial",
                            metrics=[_metric(k, "Source omitted " + k, v, "records") for k, v in omitted.items()])
        builder.edge(person_node, node, "reports", "Source coverage", "unknown", _source("Cognitive projection coverage", actor, *clock))


def build_observation_graph(raw_people, inspections, *, captured_at_unix_ms, world_hours):
    """Project source facts without assigning world truth to private cognition.

    The publication clock belongs to this graph. Raw person acquisition wall
    time is unknown in the native archive and stays zero. Inspection headers
    supply snapshot clocks; episode/event clocks remain their own receipts.
    """
    captured = captured_at_unix_ms if type(captured_at_unix_ms) is int and captured_at_unix_ms >= 0 else 0
    if captured != captured_at_unix_ms or type(captured_at_unix_ms) is not int or not _finite(world_hours, 0):
        return _empty("failed", captured, "Observation graph clock is invalid.")
    if raw_people is None:
        return _empty("unavailable", captured, "Native people source is unavailable.")
    if not isinstance(raw_people, list) or len(raw_people) > 2048 or not isinstance(inspections, dict):
        return _empty("failed", captured, "Observation graph source shape or collection limit is invalid.")
    builder = _Builder(captured, world_hours)
    people, ids = [], set()
    for person in raw_people:
        if not isinstance(person, dict) or not _text(person.get("id"), 128):
            builder.invalid += 1
            builder.value["omittedNodes"] += 1
            continue
        if person["id"] in ids:
            return _empty("failed", captured, "Native people source repeats a person identity.")
        ids.add(person["id"])
        people.append(person)
    if raw_people and not people:
        return _empty("failed", captured, "Native people source has no valid person records.")
    people.sort(key=lambda p: (p["id"] not in inspections, p.get("positionSource") != "native-body", p["id"]))
    person_nodes = {}
    for person in people:
        actor = person["id"]
        record = person.get("record") if isinstance(person.get("record"), dict) else {}
        name = " ".join(record[k] for k in ("forename", "surname") if _text(record.get(k), 160)) or actor
        provenance = person.get("positionSource")
        valid_position = (provenance in {"native-body", "durable-record"}
                          and all(_finite(person.get(k)) for k in ("x", "y", "z")) and -32 <= person["z"] < 32)
        perspective = "observed" if valid_position and provenance == "native-body" else "unknown"
        summary = "Current native body position." if perspective == "observed" else "Recorded location; current native body was not sampled." if valid_position else "Person record is available; position provenance is unavailable."
        metrics = []
        if _text(record.get("occupation"), 160):
            metrics.append(_metric("occupation", "Recorded occupation", record["occupation"]))
        if type(record.get("dead")) is bool:
            metrics.append(_metric("dead", "Recorded deceased", record["dead"]))
        context = person.get("context") if isinstance(person.get("context"), dict) else {}
        controller = context.get("controller") if isinstance(context.get("controller"), dict) else {}
        if _text(controller.get("state"), 128):
            metrics.append(_metric("activity", "Recorded controller activity", controller["state"], description="Controller state, not a claim about completed work."))
        optional = {"metrics": metrics}
        if valid_position:
            optional["position"] = {k: person[k] for k in ("x", "y", "z")} | {"source": provenance}
        else:
            builder.missing += 1
        person_nodes[actor] = builder.node("person", (actor,), actor, name, summary, perspective,
                                           _source("Native people observation", actor, world_hours),
                                           "native-body" if perspective == "observed" else "recorded" if valid_position else "unavailable",
                                           **optional)
    for person in people:
        actor, person_node = person["id"], person_nodes[person["id"]]
        if person_node not in builder.nodes:
            continue
        context = person.get("context") if isinstance(person.get("context"), dict) else {}
        detail = inspections.get(actor)
        if detail is None:
            builder.missing += 1
            unknown = builder.unknown(actor, "inspection", "Detailed state was not sampled for this person.", "Inspection unavailable")
            builder.edge(person_node, unknown, "reports", "Inspection coverage", "unknown", _source("Projection coverage", "inspection"))
            detail = {}
        if not isinstance(detail, dict):
            builder.invalid += 1
            continue
        clock = _snapshot_clock(detail, builder)
        if clock is None:
            unknown = builder.unknown(actor, "inspection-clock", "Inspection source is newer than this observation or its clock is invalid.", "Inspection awaits aligned observation")
            builder.edge(person_node, unknown, "reports", "Inspection clock coverage", "unknown", _source("Projection coverage", "inspection-clock"))
            continue
        if "sections" in detail:
            sections = detail["sections"]
            if isinstance(sections, list) and len(sections) <= 16:
                builder.inspected += 1
                seen = set()
                for section in sections:
                    sid = section.get("id") if isinstance(section, dict) else None
                    if not _text(sid, 128) or sid in seen:
                        builder.invalid += 1
                        continue
                    seen.add(sid)
                    _section(builder, actor, person_node, section, clock)
            else:
                builder.invalid += 1
        receipts = {}
        if "events" in detail:
            _events(builder, actor, person_node, detail["events"], receipts)
        raw_cognition = detail if detail.get("schema") == "simulation.cognition/1" else detail.get("cognition", context.get("cognition"))
        if raw_cognition is not None:
            # Header fields wrap normalized cognition, and are not cognition
            # contract fields themselves.
            if raw_cognition is detail:
                raw_cognition = {k: v for k, v in detail.items() if k not in {"worldHours", "capturedAtUnixMs"}}
            _cognition(builder, actor, person_node, raw_cognition, clock, receipts)
        else:
            builder.missing += 1
        counts = context.get("beliefCounts")
        if context.get("perceptionAvailable") is True and isinstance(counts, dict):
            metrics = [_metric(key, label, counts[key], "entries") for key, label in
                       (("people", "Remembered person locations"), ("zombies", "Stored threat memories"), ("sounds", "Unclassified sounds"))
                       if type(counts.get(key)) is int and 0 <= counts[key] <= 1000000]
            if metrics:
                source = _source("Personal perception snapshot", actor, world_hours)
                node = builder.node("belief", (actor, "perception-counts"), actor, "Personal awareness",
                                    "Counts of private stored observations; contents and current accuracy are not established.",
                                    "private", source, "recorded", metrics=metrics)
                builder.edge(person_node, node, "reports", "Private awareness counts", "private", source)
    value = builder.value
    value["message"] = _caption(f"{len(people)} people; {builder.inspected} detailed inspections; "
                                f"{builder.cognitions} cognitive sources. Coverage: {builder.missing} unavailable sources or references, "
                                f"{builder.future} newer receipts withheld, {builder.invalid} invalid records withheld. "
                                "Causal effects and externalities require explicit receipts.", 512)
    return validate_observation_graph(value)
