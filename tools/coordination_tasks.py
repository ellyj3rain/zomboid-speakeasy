#!/usr/bin/env python3
"""Compile enacted SAO/ZAO coordination evidence into private task views.

The source row remains a version 3, full-namespace SAO decision joined to the
same-moment ZAO state.  The model-facing decision horizon is rebuilt only from
the actor's acquired proposal and private appraisal.  Delivery, commitments,
native work receipts, and results remain in a separate later-outcome horizon.
This compiler validates candidate observations; it does not approve labels or
make them eligible for training.
"""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
import sys
from typing import Any

import cross_module_rows as J
import decision_authoring as A


SCHEMA = "speakeasy-enacted-coordination-task"
VERSION = 2
RESPONSES = {
    "accept", "qualify", "counter-propose", "decline", "defer", "contest",
    "withdraw",
}
CAPABILITIES = {"acquire", "carry", "deliver", "execute"}
OWNER_FIELDS = {
    "currentActivity", "capabilities", "ownNeed", "relationship", "interests",
    "constraints",
}
PRIVATE_FIELDS = {
    "owner", "executor", "bodyOwner", "currentActivity", "capabilities",
    "constraints", "interests", "inputOwners", "relationship", "ownNeed",
    "destinationKnown", "feasibleOptions", "choice", "reconsider",
}
HIDDEN_PRIVATE_CONSTRAINT_FIELDS = {
    "currentForm", "diagnosis", "diet", "dietKnown", "pathogen",
    "pathogenDiagnosis", "terminalState", "visibleForms",
}
DECISION_FIELDS = {
    "id", "kind", "organizationId", "originatorId", "createdAt", "revisedAt",
    "revision", "currentRevision", "status", "proposal", "reception",
    "response", "responseHistory", "privateInputs", "responses", "commitments",
    "asOfHour",
}
OUTCOME_FIELDS = {
    "id", "kind", "organizationId", "originatorId", "createdAt", "revisedAt",
    "revision", "currentRevision", "status", "response", "commitments",
    "asOfHour",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise J.ContractError(message)


def identifier(value: Any, where: str) -> str:
    require(J.nonempty_string(value), f"{where} must be a nonempty string")
    return value


def finite(value: Any, where: str) -> float:
    require(J.finite_number(value), f"{where} must be a finite number")
    return value


def fields(value: Any, required: set[str], allowed: set[str], where: str) -> None:
    require(isinstance(value, dict), f"{where} must be an object")
    missing = required - set(value)
    extra = set(value) - allowed
    require(not missing and not extra,
            f"{where} fields differ: missing={sorted(missing)} extra={sorted(extra)}")


def lua_sequence(value: Any, where: str) -> list[Any]:
    """Kahlua's empty table has no array/map tag; normalize only known lists."""
    if value == {}:
        return []
    require(isinstance(value, list), f"{where} must be a list")
    return value


def nested_field_names(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                result.add(key)
            result.update(nested_field_names(item))
    elif isinstance(value, list):
        for item in value:
            result.update(nested_field_names(item))
    return result


def joined_source(row: dict[str, Any]) -> None:
    """Revalidate a joined row without allowing its audit-only additions in input."""
    require(isinstance(row, dict), "joined coordination row must be an object")
    cross = row.get("crossModule")
    require(isinstance(cross, dict)
            and cross.get("schema") == "speakeasy-cross-module-join"
            and cross.get("schemaVersion") == J.VERSION,
            "coordination task requires a version 3 cross-module join")
    require(cross.get("namespace") == row.get("namespace"),
            "cross-module namespace differs from the source row")
    person, situation = row.get("person"), row.get("situation")
    require(isinstance(person, dict) and isinstance(person.get("pathogen"), dict),
            "joined row lacks ZAO pathogen audit state")
    require(isinstance(situation, dict)
            and isinstance(situation.get("visibleForms"), list),
            "joined row lacks ZAO visible-form audit state")
    original = copy.deepcopy(row)
    original.pop("crossModule")
    original["person"].pop("pathogen")
    original["situation"].pop("visibleForms")
    J.validate_sao_row(original, Path("joined-sao"), 1)


def private_appraisal(value: Any, proposal: dict[str, Any], actor: str) -> dict[str, Any]:
    fields(value, PRIVATE_FIELDS, PRIVATE_FIELDS, "decision privateInputs")
    for name in ("owner", "executor", "bodyOwner", "currentActivity"):
        identifier(value[name], f"privateInputs {name}")
    require(isinstance(value["reconsider"], bool)
            and isinstance(value["destinationKnown"], bool),
            "privateInputs reconsider/destinationKnown must be booleans")
    finite(value["relationship"], "privateInputs relationship")
    finite(value["ownNeed"], "privateInputs ownNeed")

    capabilities = value["capabilities"]
    fields(capabilities, CAPABILITIES, CAPABILITIES, "private capabilities")
    require(all(isinstance(capabilities[name], bool) for name in CAPABILITIES),
            "private capabilities must be booleans")

    constraints = value["constraints"]
    require(isinstance(constraints, dict), "private constraints must be an object")
    required_constraints = {
        "represented", "currentActivity", "executionOwnerAvailable",
        "ownNeedAvailable"}
    require(required_constraints <= set(constraints),
            "private constraints lack representation/activity/owner/need availability")
    require(all(isinstance(constraints[name], bool)
                for name in ("represented", "executionOwnerAvailable",
                             "ownNeedAvailable")),
            "representation and owner/need availability must be booleans")
    require(constraints["currentActivity"] == value["currentActivity"],
            "constraint activity differs from private current work")
    leaked = HIDDEN_PRIVATE_CONSTRAINT_FIELDS & nested_field_names(constraints)
    require(not leaked,
            f"private constraints contain hidden fields: {sorted(leaked)}")

    require(isinstance(value["interests"], dict),
            "private interests must be an object")

    owners = value["inputOwners"]
    fields(owners, OWNER_FIELDS, OWNER_FIELDS, "private inputOwners")
    for name in OWNER_FIELDS:
        identifier(owners[name], f"input owner for {name}")

    options = value["feasibleOptions"]
    require(isinstance(options, list) and options
            and all(option in RESPONSES for option in options)
            and len(options) == len(set(options)),
            "feasibleOptions must be unique supported responses")
    require(value["choice"] in options, "chosen response is not a feasible option")

    required = proposal.get("requiredCapabilities", {})
    require(isinstance(required, dict) and set(required) <= CAPABILITIES
            and all(isinstance(flag, bool) for flag in required.values()),
            "proposal requiredCapabilities are invalid")
    for name, needed in required.items():
        if needed:
            require(capabilities[name] or not any(option in {
                "accept", "qualify", "counter-propose"} for option in options),
                f"impossible option: required {name} capability is unavailable")
    if not constraints["executionOwnerAvailable"]:
        require(not any(capabilities.values()),
                "unavailable execution owner cannot publish capabilities")
        require(value["choice"] not in {"accept", "qualify", "counter-propose"},
                "unavailable execution owner cannot choose an executable response")
    require(actor != "", "private appraisal actor is absent")
    return value


def decision_horizon(evidence: dict[str, Any], namespace: dict[str, Any]) -> tuple[
        dict[str, Any], dict[str, Any], dict[str, Any]]:
    process_id = identifier(evidence.get("processId"), "processId")
    actor = identifier(evidence.get("actorId"), "actorId")
    revision = evidence.get("processRevision")
    require(type(revision) is int and revision >= 1,
            "processRevision must be a positive integer")
    require(actor == namespace["personId"], "coordination actor differs from namespace person")

    decision = evidence.get("decisionTime")
    fields(decision, DECISION_FIELDS - {"organizationId"}, DECISION_FIELDS,
           "decisionTime")
    require(decision["id"] == process_id, "decisionTime process differs")
    require(decision["revision"] == revision
            and decision["currentRevision"] == revision,
            "decisionTime carries a stale process revision")
    require(decision["status"] == "open", "decisionTime must retain open standing")
    require(decision["asOfHour"] == namespace["hour"],
            "decision-time horizon differs from namespace hour")
    hour = finite(decision["asOfHour"], "decisionTime asOfHour")
    for name in ("createdAt", "revisedAt"):
        require(finite(decision[name], f"decisionTime {name}") <= hour,
                f"decisionTime {name} is future evidence")
    identifier(decision["kind"], "decisionTime kind")
    originator = identifier(decision["originatorId"], "decisionTime originatorId")
    require(actor != originator, "originator proposal is not a recipient response task")
    require(decision["responses"] == {} and decision["commitments"] == {},
            "decision-time horizon contains other responses or later commitments")
    decision["responseHistory"] = lua_sequence(
        decision["responseHistory"], "decision responseHistory")

    proposal_record = decision["proposal"]
    fields(proposal_record, {"revision", "proposedAt", "proposedBy", "proposal"},
           {"revision", "proposedAt", "proposedBy", "proposal"}, "proposal revision")
    require(proposal_record["revision"] == revision
            and proposal_record["proposedBy"] == originator,
            "proposal revision or author differs")
    require(finite(proposal_record["proposedAt"], "proposal proposedAt") <= hour,
            "proposal is future to the decision")
    require(isinstance(proposal_record["proposal"], dict), "proposal body must be an object")

    reception = decision["reception"]
    fields(reception, {"at", "channel", "fromId"},
           {"at", "channel", "fromId", "evidence"}, "proposal reception")
    require(finite(reception["at"], "proposal reception at") <= hour
            and reception["fromId"] == originator,
            "proposal reception is future or from a different originator")
    identifier(reception["channel"], "proposal reception channel")
    if "evidence" in reception:
        require(isinstance(reception["evidence"], dict),
                "proposal reception evidence must be an object")

    response = decision["response"]
    fields(response,
           {"personId", "revision", "response", "terms", "responseRevision",
            "formedAt", "delivered"},
           {"personId", "revision", "response", "terms", "responseRevision",
            "formedAt", "delivered"}, "decision response")
    require(response["personId"] == actor and response["revision"] == revision,
            "response actor or revision differs")
    require(response["response"] in RESPONSES and isinstance(response["terms"], dict),
            "decision response is invalid")
    require(type(response["responseRevision"]) is int
            and response["responseRevision"] >= 1,
            "responseRevision must be a positive integer")
    require(response["formedAt"] == hour and response["delivered"] is False,
            "decision horizon contains a later response-delivery fact")

    private = private_appraisal(decision["privateInputs"],
                                proposal_record["proposal"], actor)
    require(private["choice"] == response["response"],
            "private choice differs from recorded response")
    return decision, response, private


def _outcome_times(value: Any, path: str = "laterOutcome") -> list[tuple[str, float]]:
    result: list[tuple[str, float]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if (key.endswith("At") or key.endswith("Hour") or key.endswith("Hours")) \
                    and J.finite_number(item):
                result.append((child, item))
            result.extend(_outcome_times(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.extend(_outcome_times(item, f"{path}[{index}]"))
    return result


def outcome_horizon(evidence: dict[str, Any], decision: dict[str, Any],
                    response: dict[str, Any]) -> dict[str, Any]:
    outcome = evidence.get("laterOutcome")
    fields(outcome, OUTCOME_FIELDS - {"organizationId"}, OUTCOME_FIELDS,
           "laterOutcome")
    require(outcome["id"] == evidence["processId"]
            and outcome["revision"] == evidence["processRevision"],
            "later outcome process or revision differs")
    require(type(outcome["currentRevision"]) is int
            and outcome["currentRevision"] >= outcome["revision"],
            "later outcome current revision predates its decision")
    as_of = finite(outcome["asOfHour"], "laterOutcome asOfHour")
    require(as_of >= decision["asOfHour"],
            "later-outcome horizon predates the decision")
    for where, value in _outcome_times(outcome):
        require(value <= as_of, f"{where} exceeds the later-outcome horizon")

    later_response = outcome.get("response")
    require(isinstance(later_response, dict)
            and later_response.get("personId") == evidence["actorId"]
            and later_response.get("revision") == evidence["processRevision"]
            and later_response.get("response") == response["response"],
            "later outcome response differs from the decision")
    delivered = later_response.get("delivered") is True
    if delivered:
        require(J.finite_number(later_response.get("deliveredAt"))
                and decision["asOfHour"] <= later_response["deliveredAt"] <= as_of
                and J.nonempty_string(later_response.get("channel")),
                "delivered response lacks a bounded return-channel receipt")
    commitments = outcome["commitments"]
    require(isinstance(commitments, dict), "laterOutcome commitments must be an object")
    normalized = []
    for commitment_id in sorted(commitments):
        commitment = commitments[commitment_id]
        require(isinstance(commitment, dict)
                and commitment.get("id") == commitment_id
                and commitment.get("processId") == evidence["processId"]
                and commitment.get("revision") == evidence["processRevision"]
                and commitment.get("actorId") == evidence["actorId"],
                "later outcome contains a foreign or stale commitment")
        work = commitment.get("work")
        require(isinstance(work, dict), "commitment work must be an object")
        owner = work.get("owner")
        if owner is not None:
            require(owner == decision["privateInputs"]["bodyOwner"],
                    "work owner differs from the decision-time body owner")
        native_owner = work.get("nativeOwner")
        if native_owner is not None:
            require(native_owner in {"SourceUse", "Handover"},
                    "work names an unsupported native owner")
        source_receipts = work.get("sourceReceipts", {})
        handover_receipts = work.get("handoverReceipts", {})
        routes = lua_sequence(work.get("routeAttempts", []), "work routeAttempts")
        work["routeAttempts"] = routes
        require(isinstance(source_receipts, dict)
                and all(isinstance(item, dict)
                        and item.get("owner") == "SourceUse"
                        for item in source_receipts.values()),
                "source receipt lost SourceUse ownership")
        require(isinstance(handover_receipts, dict)
                and all(isinstance(item, dict)
                        and item.get("owner") == "Handover"
                        for item in handover_receipts.values()),
                "handover receipt lost Handover ownership")
        require(all(isinstance(item, dict)
                    and item.get("owner") == "Locomotion" for item in routes),
                "route attempt lost Locomotion ownership")
        normalized.append(copy.deepcopy(commitment))
    require(not commitments or (response["response"] in {"accept", "withdraw"}
                                and delivered),
            "work exists without a delivered accept/withdraw response")
    return {"status": "observed", "asOfHour": as_of,
            "currentRevision": outcome["currentRevision"],
            "processStatus": outcome["status"],
            "responseDelivery": {
                "delivered": delivered,
                **({"deliveredAt": later_response["deliveredAt"],
                    "channel": later_response.get("channel")}
                   if delivered else {}),
            },
            "commitments": normalized}


def envelope_options(row: dict[str, Any], evidence: dict[str, Any],
                     private: dict[str, Any], response: dict[str, Any]) -> None:
    expected = {"coordination:" + option for option in private["feasibleOptions"]}
    actual: set[str] = set()
    for option in row["options"]:
        option_id = option["id"]
        require(option_id.startswith("coordination:"),
                "v3 option is not an enacted coordination response")
        require(option["owner"] == "SAO.Organization.respond",
                "v3 coordination option has the wrong execution owner")
        fields(option["parameters"],
               {"actorId", "processId", "processRevision", "response"},
               {"actorId", "processId", "processRevision", "response"},
               "v3 coordination option parameters")
        parameters = option["parameters"]
        require(parameters == {
            "actorId": evidence["actorId"],
            "processId": evidence["processId"],
            "processRevision": evidence["processRevision"],
            "response": option_id.removeprefix("coordination:"),
        }, "v3 coordination option differs from its actor/process/revision")
        actual.add(option_id)
    require(actual == expected,
            "v3 executable options differ from actor-private feasible options")
    require(row["choice"]["optionId"] == "coordination:" + response["response"],
            "v3 choice differs from enacted response")


def compile_task(row: dict[str, Any]) -> dict[str, Any]:
    joined_source(row)
    ns = row["namespace"]
    evidence = row.get("enactedProcess")
    require(isinstance(evidence, dict) and evidence.get("schema") == 1,
            "SAO row lacks enacted process evidence schema 1")
    allowed = {"schema", "processId", "processRevision", "actorId",
               "decisionTime", "laterOutcome"}
    fields(evidence, allowed, allowed, "enacted process evidence")
    decision, response, private = decision_horizon(evidence, ns)
    envelope_options(row, evidence, private, response)
    later = outcome_horizon(evidence, decision, response)

    owners = private["inputOwners"]
    result = {
        "schema": SCHEMA,
        "schemaVersion": VERSION,
        "namespace": copy.deepcopy(ns),
        "process": {
            "id": evidence["processId"], "revision": evidence["processRevision"],
            "kind": decision["kind"], "originatorId": decision["originatorId"],
            **({"organizationId": decision["organizationId"]}
               if "organizationId" in decision else {}),
        },
        "actor": {"id": evidence["actorId"], "executor": private["executor"],
                  "bodyOwner": private["bodyOwner"]},
        "decisionTime": {
            "asOfHour": decision["asOfHour"],
            "proposal": copy.deepcopy(decision["proposal"]["proposal"]),
            "reception": copy.deepcopy(decision["reception"]),
            "currentWork": {"activity": private["currentActivity"],
                            "owner": owners["currentActivity"]},
            "competingPriorities": {
                "competingPressure": {
                    "value": (private["ownNeed"] if private["constraints"]
                              ["ownNeedAvailable"] else None),
                    "available": private["constraints"]["ownNeedAvailable"],
                    "owner": owners["ownNeed"],
                },
                "relationship": private["relationship"],
                "interests": copy.deepcopy(private["interests"]),
                "constraints": copy.deepcopy(private["constraints"]),
                "owners": {name: owners[name] for name in
                           ("ownNeed", "relationship", "interests", "constraints")},
            },
            "capabilities": {"values": copy.deepcopy(private["capabilities"]),
                             "owner": owners["capabilities"],
                             "availability": ("available" if private["constraints"]
                                              ["executionOwnerAvailable"] else "unavailable")},
            "feasibleOptions": list(private["feasibleOptions"]),
        },
        "choice": {"response": response["response"],
                   "terms": copy.deepcopy(response["terms"]),
                   "responseRevision": response["responseRevision"]},
        "laterOutcome": later,
        "provenance": {
            "crossModule": copy.deepcopy(row["crossModule"]),
            "sourceEvidenceSchema": evidence["schema"],
            "sourceOwnership": copy.deepcopy(owners),
        },
        "admission": {
            "status": "candidate-observation",
            "exclusions": ["independent-task-review-not-recorded",
                           "learned-runtime-not-integrated"],
        },
    }
    # Pathogen truth and forms are audit-only join inputs.  Their behavioral
    # effects enter through the actor-owned activity/capability snapshot above.
    require("pathogen" not in result["decisionTime"]
            and "visibleForms" not in result["decisionTime"],
            "hidden ZAO truth entered the decision input")
    return A.seal(result)


def task_rows(sao_path: Path, zao_path: Path, out_path: Path) -> list[dict[str, Any]]:
    return [compile_task(row) for row in J.joined_rows(sao_path, zao_path, out_path)]


def export_tasks(sao_path: Path, zao_path: Path, out_path: Path) -> int:
    return J.atomic_write(out_path, task_rows(sao_path, zao_path, out_path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sao", type=Path, required=True)
    parser.add_argument("--zao", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        count = export_tasks(args.sao, args.zao, args.out)
    except (J.ContractError, OSError, KeyError, TypeError, ValueError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2
    print(f"wrote {count} enacted coordination task(s) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
