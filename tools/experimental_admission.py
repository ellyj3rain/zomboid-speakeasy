"""Explicit admission for offline authored conversation evaluation.

Sample admission, dataset separation and runtime readiness have separate results.
Historical conditioning declarations remain immutable.
"""
from __future__ import annotations

import copy

import decision_authoring as A
import cross_module_rows as J
import conversation_tasks as C
import retriever_targets as R
import speaker_tasks as S
import training_evidence as E

SCOPE = "offline-authored-conversation-v1"
REQUIREMENTS = {
    "understander": ["exact-source-capture", "utterance", "participant-ids", "owned-claim-refs",
                    "exact-task-label-approval"],
    "retriever": ["exact-source-capture", "utterance", "complete-claim-catalogue",
                 "approved-task-anchor", "independent-retrieval-label-approval"],
    "speaker": ["exact-source-capture", "approved-task-anchor", "selected-claims",
                "validated-expression", "exact-task-label-approval"]}


def inspect(row, *, scope, approval=None, evidence=None):
    evidence = evidence or E.Store()
    A.require(scope == SCOPE, "unknown experimental task scope")
    task = row.get("task", "retriever" if row.get("schema") == R.TARGET_SCHEMA
                   else "speaker-wording" if row.get("schema") == "speakeasy-speaker-wording-proposal"
                   else "unknown")
    checks = []
    def check(name, action):
        try:
            value = action()
            checks.append({"check": name, "status": "passed"})
            return value
        except (J.ContractError, KeyError, TypeError, ValueError, OSError) as error:
            checks.append({"check": name, "status": "refused", "reason": str(error)})
            return None

    validated = None
    if task == "understander":
        validated = check("source-and-task-contract", lambda: C.validate_task(row, evidence))
    elif task == "retriever":
        validated = check("source-and-task-contract", lambda: R.validate_target(row, evidence))
    elif task == "speaker":
        validated = check("source-and-task-contract", lambda: S.validate_task(row, evidence))
    else:
        checks.append({"check": "source-and-task-contract", "status": "refused",
                       "reason": "wording-approval-is-not-task-admission" if task == "speaker-wording"
                       else "unsupported-task-contract"})
    source_keys, unavailable = [], []
    if validated is not None:
        context = row["input"]["context"]
        def required_input():
            A.require(isinstance(context.get("utterance"), str) and context["utterance"].strip(),
                      "required-utterance-missing")
            A.require(context.get("personId") and context.get("listenerRef"),
                      "required-participant-identity-missing")
            A.require(isinstance(row["input"]["catalogue"].get("claims"), list),
                      "required-claim-catalogue-missing")
            return True
        check("required-offline-inputs", required_input)
        if task == "retriever":
            # validate_target already verifies the independent retrieval ruling.
            checks.append({"check": "exact-task-label-approval", "status": "passed"})
            anchor = evidence.task_anchor(row["anchor"], row["input"]["catalogue"])
            import_hash = anchor["input"].get("sourceImportSha256")
        else:
            check("exact-task-label-approval",
                  lambda: evidence.decision(approval, row["contentSha256"]))
            import_hash = row["input"].get("sourceImportSha256")
        imported = check("exact-source-capture",
                         lambda: C.validate_import(evidence.read(import_hash)))
        if imported is not None:
            capture = imported["capture"]
            unavailable = list(capture["coverage"]["unavailableInputs"])
            source_keys.append("capture:" + A.digest(capture))
            for claim in capture["sourceState"]["person"]["worldKnowledge"]["acquisitions"]:
                source_keys.append("document:" + claim["source"]["sha256"])
        source_keys.append("catalogue:" + A.digest(row["input"]["catalogue"]))
    reasons = [c["check"] + ":" + c["reason"] for c in checks if c["status"] == "refused"]
    return {
        "rowId": row.get("rowId", row.get("proposalId")), "rowSha256": row.get("contentSha256"), "task": task,
        "scope": scope, "requirements": REQUIREMENTS.get(task, []), "checks": checks,
        "status": "excluded" if reasons else "admitted-to-offline-evaluation",
        "exclusions": reasons, "sourceGroups": sorted(set(source_keys)),
        "unavailableNativeInputs": unavailable,
        "scopeLimits": ["authored-capture", "no-live-game-generalization",
                        "no-model-quality-measurement"],
        "runtime": {"ready": False, "reasons": [
            "no-trained-task-bundle", "native-consumer-not-integrated",
            *["unavailable:" + name for name in unavailable]]}}


def compile_dataset(requests, splits, *, scope, evidence=None):
    """Report all row refusals; prevent leakage before any learning dataset use."""
    evidence = evidence or E.Store()
    A.require(isinstance(requests, list) and requests, "dataset requires requests")
    A.fields(splits, {"train", "validation", "test"}, "experimental splits")
    for values in splits.values():
        A.require(isinstance(values, list), "split must be a list of exact row hashes")
        for value in values:
            A.hash_value(value, "split row hash")
    rows = [inspect(evidence.read(request["rowSha256"]), scope=scope,
                    approval=request.get("approvalReceiptSha256"), evidence=evidence)
            for request in requests]
    ids = [row["rowSha256"] for row in rows]
    A.require(len(set(ids)) == len(ids), "duplicate dataset row")
    assigned = [digest for values in splits.values() for digest in values]
    A.require(len(assigned) == len(set(assigned)) and set(assigned) == set(ids),
              "splits must assign every exact row once")
    groups, leakage = {}, []
    for split, digests in splits.items():
        for row in rows:
            if row["rowSha256"] not in digests:
                continue
            for group in row["sourceGroups"]:
                if group in groups and groups[group] != split:
                    leakage.append({"sourceGroup": group, "splits": sorted([groups[group], split])})
                groups[group] = split
    reasons = (["excluded-rows-present"] if any(r["status"] == "excluded" for r in rows) else [])
    if leakage:
        reasons.append("shared-source-split-leakage")
    empty = [name for name, digests in splits.items() if not digests]
    if empty:
        reasons.append("independent-evaluation-partitions-missing")
    return A.seal({
        "schema": "speakeasy-experimental-admission", "schemaVersion": 1, "scope": scope,
        "rows": rows, "splits": copy.deepcopy(splits), "leakage": leakage,
        "dataset": {"status": "excluded" if reasons else "admitted-for-offline-experiment",
                    "exclusions": reasons, "emptyPartitions": empty},
        "evaluation": {"status": "not-run", "reason": "no-trained-model-or-evaluation-results"},
        "runtime": {"ready": False, "reason": "offline-data-report-only"}})
