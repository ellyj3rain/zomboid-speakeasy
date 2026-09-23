"""Bounded compositional expression over subject-, source- and time-bound facts.

This is an offline construction experiment, not a free-text semantic verifier.
The source recognizer deliberately refuses report language outside its grammar.
"""
from __future__ import annotations

import copy
from datetime import date
import re

import decision_authoring as A
import speaker_tasks as S

REPORT = re.compile(
    r"(?P<provider>[A-Za-z][A-Za-z ]*)' (?P<services>telephone and Internet) networks "
    r"failed across the (?P<region>[A-Za-z][A-Za-z ]*) area for hours and were still "
    r"down at press time; businesses closed; the cause unannounced, with talk of "
    r"downed wires, lightning or sabotage\.")
ORDINALS = ("first second third fourth fifth sixth seventh eighth ninth tenth "
            "eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth "
            "eighteenth nineteenth twentieth twenty-first twenty-second twenty-third "
            "twenty-fourth twenty-fifth twenty-sixth twenty-seventh twenty-eighth "
            "twenty-ninth thirtieth thirty-first").split()
KINDS = ("outage", "duration", "press-status", "closures", "cause-status", "rumours")
# Supported source entities are part of this proof's finite grammar. New sources
# need an explicit extension; a phrase matching letters/spaces is not an entity.
REPORT_ENTITIES = {
    "validated-capture": {("Knox Telecommunications", "Knox")},
    "synthetic-authored": {("Valley Telecommunications", "Valley")}}


def from_target(target_hash, evidence):
    """Resolve names only from the same validated immutable owner capture."""
    _, _, imported = S.sources(target_hash, evidence)
    model = S.input_for(target_hash, evidence)["modelInput"]
    capture = imported["capture"]
    participants = {}
    for role in ("person", "listener"):
        person = capture["sourceState"][role]
        participants[person["id"]] = {
            "givenName": person.get("forename"),
            "surname": person.get("surname"),
            "source": "capture.sourceState." + role}
    return {
        "origin": {"kind": "validated-capture", "sha256": imported["contentSha256"]},
        "speakerRef": model["speakerRef"], "listenerRef": model["listenerRef"],
        "participants": participants, "reports": copy.deepcopy(model["reports"]),
        "locations": [], "voiceConditioning": copy.deepcopy(model["voiceConditioning"]),
        "unavailableInputs": list(model["unavailableInputs"])}


def compile_source(source):
    A.fields(source, {"origin", "speakerRef", "listenerRef", "participants", "reports",
                      "locations", "voiceConditioning", "unavailableInputs"}, "expression source")
    A.require(source["origin"].get("kind") in {"validated-capture", "synthetic-authored"},
              "source origin must be explicit")
    A.require(source["speakerRef"] in source["participants"]
              and source["listenerRef"] in source["participants"], "unknown participant")
    propositions, reports = {}, {}
    for report in source["reports"]:
        match = REPORT.fullmatch(report["summary"])
        A.require(match is not None, "report-source-language-outside-proof-grammar")
        A.require((match["provider"], match["region"])
                  in REPORT_ENTITIES[source["origin"]["kind"]],
                  "report-entities-outside-proof-grammar")
        A.require(report["knowledgeKind"] == "reported", "report-attribution-required")
        date.fromisoformat(report["publicationDate"])
        A.require(report["claimRef"] not in reports, "duplicate report reference")
        common = {
            "ownerRef": source["speakerRef"], "claimRef": report["claimRef"],
            "sourceClaimId": report["claimId"], "source": copy.deepcopy(report["source"]),
            "knowledgeKind": "reported", "at": report["publicationDate"],
            "timeMeaning": "publication", "acquiredHour": report["acquiredHour"],
            "receiptId": report["receiptId"]}
        subject = {"provider": match["provider"], "region": match["region"],
                   "services": ["telephone", "Internet"]}
        values = {"outage": "out", "duration": "hours", "press-status": "still-down",
                  "closures": "businesses-closed", "cause-status": "unannounced",
                  "rumours": ["downed wires", "lightning", "sabotage"]}
        refs = []
        for kind in KINDS:
            ref = report["claimRef"] + "/" + kind
            proposition = {**copy.deepcopy(common), "id": ref, "subject": copy.deepcopy(subject),
                           "relation": kind, "value": values[kind],
                           "certainty": "speculation" if kind == "rumours" else "reported"}
            propositions[ref] = proposition
            refs.append(ref)
        reports[report["claimRef"]] = {"refs": refs, "publicationDate": report["publicationDate"]}
    for location in source["locations"]:
        A.fields(location, {"id", "subjectRef", "place", "at", "knowledgeKind", "source"},
                 "location evidence")
        A.require(location["id"] not in propositions, "duplicate proposition")
        A.require(location["subjectRef"] in source["participants"], "unknown location subject")
        A.require(location["knowledgeKind"] in {"observed", "reported"}, "location attribution required")
        A.require(isinstance(location["at"], str)
                  and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", location["at"]),
                  "location-time-requires-HH-MM")
        if location["knowledgeKind"] == "reported":
            A.fields(location["source"], {"kind", "personRef"}, "location attribution")
            A.require(location["source"]["kind"] == "testimony"
                      and location["source"]["personRef"] in source["participants"],
                      "unknown-reporting-person")
        else:
            A.fields(location["source"], {"kind", "receiptRef"}, "location observation")
            A.require(location["source"]["kind"] == "sight", "location sight evidence required")
            A.identifier(location["source"]["receiptRef"], "location sight receipt")
        A.require(location["place"] in {"east", "west", "north", "south"}, "unsupported place")
        propositions[location["id"]] = {
            "id": location["id"], "ownerRef": source["speakerRef"], "subject": location["subjectRef"],
            "relation": "location", "value": location["place"], "at": location["at"],
            "knowledgeKind": location["knowledgeKind"], "source": location["source"]}
    return {"schema": "speakeasy-expression-input", "schemaVersion": 1,
            "sourceSha256": A.digest(source), "speakerRef": source["speakerRef"],
            "listenerRef": source["listenerRef"], "participants": copy.deepcopy(source["participants"]),
            "reports": reports, "propositions": propositions,
            "voiceConditioning": copy.deepcopy(source["voiceConditioning"]),
            "unavailableInputs": list(source["unavailableInputs"])}


def report_plan(model, report_ref, variants=None, *, channel="telephone", vocative=False):
    return {"kind": "report", "reportRef": report_ref, "channel": channel,
            "propositions": [copy.deepcopy(model["propositions"][ref])
                             for ref in model["reports"][report_ref]["refs"]],
            "variants": dict(variants or {kind: 0 for kind in KINDS}), "vocative": vocative}


def person_name(model, ref):
    A.require(ref in model["participants"], "unknown-participant")
    name = model["participants"][ref].get("givenName")
    A.require(isinstance(name, str) and re.fullmatch(r"[A-Za-z][A-Za-z'-]{0,39}", name),
              "participant-name-unavailable-or-outside-grammar")
    return name


def render(model, plan):
    """Every emitted factual term originates in one complete bound proposition."""
    A.require(isinstance(plan, dict), "expression plan must be an object")
    if plan.get("kind") == "location":
        A.fields(plan, {"kind", "proposition", "variant"}, "location expression")
        p = plan["proposition"]
        A.require(p.get("id") in model["propositions"]
                  and p == model["propositions"][p["id"]], "proposition-binding-differs")
        A.require(p["relation"] == "location", "location relation differs")
        A.require(type(plan["variant"]) is int and plan["variant"] in (0, 1), "unknown lexical variant")
        name = person_name(model, p["subject"])
        prefix = ("I saw" if p["knowledgeKind"] == "observed"
                  else person_name(model, p["source"]["personRef"]) + " reported")
        if plan["variant"] == 0:
            return f"{prefix} {name} to the {p['value']} at {p['at']}."
        return f"At {p['at']}, {prefix} {name} to the {p['value']}."
    A.fields(plan, {"kind", "reportRef", "channel", "propositions", "variants", "vocative"},
             "report expression")
    A.require(plan["kind"] == "report" and plan["reportRef"] in model["reports"], "unknown report")
    report = model["reports"][plan["reportRef"]]
    expected = [model["propositions"][ref] for ref in report["refs"]]
    A.require(plan["propositions"] == expected, "proposition-binding-differs")
    A.require(plan["channel"] in expected[0]["subject"]["services"], "unsupported service projection")
    variants = plan["variants"]
    A.fields(variants, set(KINDS), "lexical variants")
    A.require(all(type(value) is int and value in (0, 1) for value in variants.values()),
              "unknown lexical variant")
    A.require(type(plan["vocative"]) is bool, "vocative must be boolean")
    p = expected[0]
    day = date.fromisoformat(report["publicationDate"])
    spoken_date = day.strftime("%B") + " " + ORDINALS[day.day - 1]
    explicit_date = day.strftime("%B") + f" {day.day}, {day.year}"
    region = p["subject"]["region"]
    service = "phones" if plan["channel"] == "telephone" else "Internet networks"
    clauses = {
        "outage": [
            f"The {explicit_date} paper reported that the {service} were out across {region}.",
            f"The {spoken_date} paper said the {service} were out all over {region}."],
        "duration": ["The report said the outage lasted for hours.", "For hours."],
        "press-status": ["It said they were still down at press time.",
                         "Still down when it went to press, too."],
        "closures": ["It also reported that businesses closed.", "Businesses closed."],
        "cause-status": ["The cause had not been announced.",
                         "They hadn't announced a cause"],
        "rumours": ["Downed wires, lightning or sabotage were only speculation.",
                    "there was talk of wires down, lightning, sabotage... but that's all it was. Talk."]}
    selected = {kind: clauses[kind][variants[kind]] for kind in KINDS}
    if plan["vocative"]:
        selected["duration"] = selected["duration"][:-1] + ", " + person_name(model, model["listenerRef"]) + "."
    # The uncertain cause clause remains inside the introduced report's scope.
    if variants["cause-status"] == 1:
        tail = selected["cause-status"] + "—" + selected["rumours"]
    else:
        tail = selected["cause-status"] + " " + selected["rumours"][0].upper() + selected["rumours"][1:]
    return " ".join([selected[k] for k in KINDS[:4]] + [tail])


def produce(source, plan):
    model = compile_source(source)
    return {"sourceSha256": model["sourceSha256"], "plan": copy.deepcopy(plan),
            "text": render(model, plan)}


def validate_output(value, source):
    A.fields(value, {"sourceSha256", "plan", "text"}, "expression output")
    model = compile_source(source)
    A.require(value["sourceSha256"] == model["sourceSha256"], "expression-source-differs")
    A.require(value["text"] == render(model, value["plan"]), "expression-text-differs")
    return value
