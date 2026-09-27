"""Data-only boundary for independently authored native cognition evidence.

This module validates projections, never implements either native model. A
projection and its predictions confer no approval or admission to training.
"""
from __future__ import annotations

import copy
import json
import math

ACTIONS = {"food", "water", "inspect", "continue"}
MODELS = {"ordinary", "associative"}
HYPOTHESIS_STATES = {"hypothesis", "supported", "refined", "falsified"}


def require(condition, message):
    if not condition:
        raise ValueError("cognition: " + message)


def fields(value, required, optional=()):
    require(isinstance(value, dict) and set(required) <= value.keys()
            and set(value) <= set(required) | set(optional), "fields differ")


def number(value, low=0, high=2**53 - 1, integer=False):
    require(type(value) in (int, float) and math.isfinite(value)
            and low <= value <= high and (not integer or int(value) == value), "invalid number")
    return value


def text(value, limit=128, empty=False):
    require(isinstance(value, str) and (empty or value) and len(value) <= limit
            and not any((ord(c) < 32 and c not in "\n\t") or ord(c) == 127 for c in value), "invalid text")
    return value


def array(value, limit):
    # Empty Lua tables encode as objects; this is the sole normalized ambiguity.
    if value == {}:
        value = []
    require(isinstance(value, list) and len(value) <= limit, "collection limit")
    return value


def settings(value):
    fields(value, {"enabled", "opponentShare", "opportunitiesPerHour", "maxDepth"})
    require(type(value["enabled"]) is bool, "enabled must be Boolean")
    number(value["opponentShare"], 0, 1)
    number(value["opportunitiesPerHour"], 1, 60, True)
    number(value["maxDepth"], 1, 4, True)


def frame(value, actor):
    fields(value, {"id", "actorId", "worldHours", "hunger", "thirst", "fatigue",
                   "eatAt", "drinkAt", "foodAllowed", "waterAllowed", "inspectionAllowed",
                   "knownFood", "knownWater", "knownPlaces", "capabilities"}, {"priorIntent"})
    text(value["id"])
    require(value["actorId"] == actor, "frame actor differs")
    number(value["worldHours"])
    for key in ("hunger", "thirst", "fatigue", "eatAt", "drinkAt"):
        number(value[key], 0, 1)
    for key in ("foodAllowed", "waterAllowed", "inspectionAllowed"):
        require(type(value[key]) is bool, "admission must be Boolean")
    for key in ("knownFood", "knownWater", "knownPlaces"):
        number(value[key], 0, 100000, True)
    fields(value["capabilities"], {"cook", "forage", "treat"})
    require(all(type(v) is bool for v in value["capabilities"].values()), "capability must be Boolean")
    if "priorIntent" in value:
        text(value["priorIntent"])


def proposal(value):
    fields(value, {"modelId", "version", "actionId", "interpretation", "confidence", "predictions"},
           {"hypothesisId"})
    require(value["modelId"] in MODELS and value["actionId"] in ACTIONS, "unknown model or action")
    text(value["version"]); text(value["interpretation"], 512)
    number(value["confidence"], 0, 1)
    fields(value["predictions"], ACTIONS)
    for predicted in value["predictions"].values():
        fields(predicted, {"probability", "claim"})
        number(predicted["probability"], 0, 1); text(predicted["claim"], 512)
    if "hypothesisId" in value:
        text(value["hypothesisId"])


def episode(value, actor):
    fields(value, {"id", "worldHours", "status", "frame", "proposals", "selectedModelId",
                   "selectedActionId", "selectionWeight", "selectionPolicy", "disagreement"},
           {"reason", "outcome", "executionStatus"})
    text(value["id"]); number(value["worldHours"])
    require(value["status"] in {"proposed", "attempted", "observed", "censored"}, "invalid episode status")
    if "executionStatus" in value:
        require(value["executionStatus"] in {"queued", "attempted", "observed", "censored"}, "invalid execution status")
    frame(value["frame"], actor)
    require(value["frame"]["worldHours"] == value["worldHours"], "decision clocks differ")
    proposals = array(value["proposals"], 2)
    require(len(proposals) == 2, "two independent proposals required")
    for entry in proposals:
        proposal(entry)
    by_model = {p["modelId"]: p for p in proposals}
    require(set(by_model) == MODELS, "model identities differ or repeat")
    selected = value["selectedModelId"]
    require(selected in by_model and value["selectedActionId"] == by_model[selected]["actionId"],
            "selected proposal differs")
    number(value["selectionWeight"], math.nextafter(0, math.inf), 1)
    require(value["selectionPolicy"] == "deterministic-balanced", "selection policy differs")
    require(type(value["disagreement"]) is bool and value["disagreement"] ==
            (proposals[0]["actionId"] != proposals[1]["actionId"]), "disagreement differs")
    if "reason" in value:
        text(value["reason"], 512, True)
    outcome = value.get("outcome")
    if outcome is not None:
        fields(outcome, {"eventId", "worldHours", "actionId", "status"}, {"detail", "success", "revisions", "predictions"})
        text(outcome["eventId"]); number(outcome["worldHours"], value["worldHours"])
        require(outcome["actionId"] == value["selectedActionId"], "outcome is for an unexecuted action")
        require(outcome["status"] in {"completed", "no-effect", "interrupted", "unavailable"}, "outcome status differs")
        if "success" in outcome:
            require(type(outcome["success"]) is bool and value["status"] == "observed"
                    and outcome["status"] in {"completed", "no-effect"}, "censored outcome cannot become a target")
        if "detail" in outcome:
            text(outcome["detail"], 512, True)
        if "revisions" in outcome:
            fields(outcome["revisions"], MODELS)
            for revision in outcome["revisions"].values():
                text(revision, 512, True)
        if "predictions" in outcome:
            fields(outcome["predictions"], MODELS)
            require(type(outcome.get("success")) is bool, "scored predictions require an observed target")
            for model, prediction in outcome["predictions"].items():
                fields(prediction, {"probability", "claim", "squaredError"})
                prior = by_model[model]["predictions"][value["selectedActionId"]]
                require(prediction["probability"] == prior["probability"] and prediction["claim"] == prior["claim"],
                        "outcome rewrites a pre-outcome prediction")
                number(prediction["squaredError"], 0, 1)
                require(abs(prediction["squaredError"] - (prior["probability"] - int(outcome["success"]))**2) < 1e-9,
                        "selected-action prediction score differs")
    require(value["status"] != "observed" or outcome is not None, "observed episode lacks its native outcome")


def projection(value, actor, full=False, max_hours=None):
    """Return a detached, validated projection with normalized empty arrays."""
    if max_hours is not None: number(max_hours, 0, 1e9)
    value = copy.deepcopy(value)
    fields(value, {"schema", "settings", "actorId", "sequence", "omittedEpisodes", "omittedExperiences",
                   "episodes", "models"}, {"rejectedExperiences", "experiences"} if full else {"rejectedExperiences"})
    require(value["schema"] == "simulation.cognition/1" and value["actorId"] == actor, "schema or actor differs")
    text(actor); settings(value["settings"])
    for key in ("sequence", "omittedEpisodes", "omittedExperiences"):
        number(value[key], integer=True)
    if "rejectedExperiences" in value:
        number(value["rejectedExperiences"], integer=True)
    if "experiences" in value:
        value["experiences"] = array(value["experiences"], 256)
        seen_experiences = set()
        for experience in value["experiences"]:
            fields(experience, {"id", "actorId", "observerId", "worldHours", "kind", "category", "perspective", "status"},
                   {"sourceId", "itemType", "episodeId", "detail", "foodPresent", "waterPresent",
                    "hungerDelta", "thirstDelta", "capabilities"})
            text(experience["id"]); text(experience["actorId"])
            require(experience["observerId"] == actor, "experience belongs to another observer")
            require(experience["id"] not in seen_experiences, "duplicate experience")
            seen_experiences.add(experience["id"]); number(experience["worldHours"], 0, 1e9)
            if max_hours is not None: require(experience["worldHours"] <= max_hours, "future experience")
            require(experience["kind"] in {"inspection", "acquire", "store", "consume"}
                    and experience["category"] in {"food", "water", "container"}
                    and experience["status"] in {"completed", "no-effect", "interrupted", "unavailable"},
                    "experience kind/category/status differs")
            for key in ("foodPresent", "waterPresent"):
                if key in experience:
                    require(type(experience[key]) is bool and experience["kind"] == "inspection", "uninspected contents")
            for key in ("hungerDelta", "thirstDelta"):
                if key in experience:
                    number(experience[key], -1, 1)
                    require(experience["kind"] == "consume", "need delta without use")
            if experience["perspective"] == "performed":
                require(experience["actorId"] == actor, "performed event belongs to someone else")
            else:
                require(experience["perspective"] == "observed" and experience["actorId"] != actor
                        and experience["kind"] in {"acquire", "store"}
                        and not {"episodeId", "foodPresent", "waterPresent", "hungerDelta", "thirstDelta"} & experience.keys(),
                        "unobserved private experience fields")
            for key, limit in (("sourceId", 160), ("itemType", 160), ("episodeId", 128), ("detail", 512)):
                if key in experience:
                    text(experience[key], limit, key == "detail")
            if "capabilities" in experience:
                fields(experience["capabilities"], {"cook", "forage", "treat"})
                require(all(type(v) is bool for v in experience["capabilities"].values()), "invalid experience capabilities")
    value["episodes"] = array(value["episodes"], 64 if full else 8)
    seen = set()
    for item in value["episodes"]:
        episode(item, actor)
        if max_hours is not None:
            require(item["worldHours"] <= max_hours and item["frame"]["worldHours"] <= max_hours,
                    "future cognitive decision")
            if item.get("outcome"): require(item["outcome"]["worldHours"] <= max_hours, "future cognitive outcome")
        require(item["id"] not in seen, "duplicate episode"); seen.add(item["id"])
    value["models"] = array(value["models"], 2)
    seen = set()
    for model in value["models"]:
        fields(model, {"id", "version", "beliefs", "hypotheses"}, {"omittedBeliefs", "omittedHypotheses"})
        require(model["id"] in MODELS and model["id"] not in seen, "duplicate or unknown model")
        seen.add(model["id"]); text(model["version"])
        for key in ("omittedBeliefs", "omittedHypotheses"):
            if key in model:
                number(model[key], integer=True)
        model["beliefs"] = array(model["beliefs"], 64)
        belief_ids = set()
        for belief in model["beliefs"]:
            fields(belief, {"id", "label", "confidence", "status"})
            text(belief["id"]); text(belief["label"], 512); text(belief["status"], 64)
            number(belief["confidence"], 0, 1)
            require(belief["id"] not in belief_ids, "duplicate belief"); belief_ids.add(belief["id"])
        model["hypotheses"] = array(model["hypotheses"], 64 if full else 12)
        hypothesis_ids = set()
        for hypothesis in model["hypotheses"]:
            fields(hypothesis, {"id", "label", "branch", "depth", "confidence", "status",
                                "evidenceIds", "parentIds", "missing"})
            for key, limit in (("id", 128), ("label", 512), ("branch", 160)):
                text(hypothesis[key], limit)
            number(hypothesis["depth"], 1, 4, True); number(hypothesis["confidence"], 0, 1)
            require(hypothesis["status"] in HYPOTHESIS_STATES, "hypothesis status differs")
            require(hypothesis["id"] not in hypothesis_ids, "duplicate hypothesis")
            hypothesis_ids.add(hypothesis["id"])
            for key, count, limit in (("evidenceIds", 8, 128), ("parentIds", 4, 128), ("missing", 8, 256)):
                hypothesis[key] = array(hypothesis[key], count)
                for entry in hypothesis[key]:
                    text(entry, limit)
                require(len(set(hypothesis[key])) == len(hypothesis[key]), "duplicate hypothesis reference")
    require(not value["episodes"] or seen == MODELS, "episode model summaries missing")
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    require(len(raw) <= (512 if full else 64) * 1024, "projection byte budget")
    return value
