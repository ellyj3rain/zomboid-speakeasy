"""Source-bound reported answers for authored speaker examples.

This bounded data renderer checks dated report summaries. It is not the learned
free-composition decoder or a runtime register-floor implementation.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timedelta
import hashlib
from pathlib import Path

import cross_module_rows as J
import decision_authoring as A
import training_evidence as E
import retriever_targets as R
import conversation_tasks as C

VERSION = 3
BOUND_VERSION = 4
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")
EXCLUSIONS = ["speaker-free-composition-decoder-not-implemented",
              "speaker-register-floor-admission-not-implemented"]


def sources(target_hash, evidence):
    """Resolve both independent approvals and the exact underlying capture."""
    target = R.validate_target(evidence.read(target_hash), evidence)
    anchor = target["anchor"]
    A.require(anchor["task"] == "understander", "speaker requires an understander anchor")
    task = evidence.task_anchor(anchor, target["input"]["catalogue"])
    C.validate_task(task, evidence)
    A.require(task["output"]["speechAct"] == "question"
              and task["output"]["requestedAction"] is None,
              "reported answer requires a question without an executable action")
    imported = C.validate_import(evidence.read(task["input"]["sourceImportSha256"]))
    return target, task, imported


def report_content(claim, capture):
    """Resolve an entire protected summary cell, never an arbitrary substring.

    The source document is a curated account of the newspaper, not a verbatim
    native issue transcript. Rendering attributes it without quotation marks.
    """
    fact = claim["fact"]
    A.require(claim["topic"] == "world" and fact.get("knowledgeKind") == "reported"
              and fact.get("source") == "read" and fact.get("carrier") == "print",
              "reported answer requires personally read print knowledge")
    matching = [a for a in capture["sourceState"]["person"]["worldKnowledge"]["acquisitions"]
                if a["claimId"] == claim["sourceClaimId"] and a["receiptId"] == fact["receiptId"]]
    A.require(len(matching) == 1, "report acquisition is missing or ambiguous")
    acquisition = matching[0]
    source = acquisition["source"]
    path = (C.ROOT / source["path"]).resolve()
    A.require(path.is_relative_to(C.ROOT / "world"), "report source outside world")
    A.require(C.file_hash(path) == source["sha256"], "report source hash differs")
    line = path.read_text(encoding="utf-8").splitlines()[source["line"] - 1]
    A.require(hashlib.sha256(line.encode("utf-8")).hexdigest() == source["excerptSha256"],
              "report source line differs")
    columns = [part.strip() for part in line.split("|")]
    A.require(len(columns) == 6 and columns[0] == columns[-1] == ""
              and all(columns[1:5]), "unsupported report source layout")
    publication = (datetime.fromisoformat(capture["calendar"]["anchorInstant"])
                   + timedelta(hours=fact["reportHour"] - capture["calendar"]["anchorHour"]))
    A.require(columns[1] == publication.date().isoformat(), "source publication date differs")
    return {"claimRef": claim["ref"], "claimId": claim["sourceClaimId"],
            "source": copy.deepcopy(source), "publicationDate": columns[1],
            "summary": columns[2], "sourceLabel": columns[3],
            "knowledgeKind": "reported", "acquiredHour": fact["acquiredHour"],
            "receiptId": fact["receiptId"]}


def input_for(target_hash, evidence):
    target, task, imported = sources(target_hash, evidence)
    capture = imported["capture"]
    required = target["labels"]["requiredClaimRefs"]
    A.require(required, "reported answer has no required claims")
    selected = [claim for claim in capture["catalogue"]["claims"] if claim["ref"] in required]
    A.require([claim["ref"] for claim in selected] == required, "speaker selection differs")
    # Complete catalogue/context are evidence for resolver interoperability.
    # Only the explicit modelInput is intended as speaker conditioning.
    return {"catalogue": copy.deepcopy(capture["catalogue"]),
            "context": copy.deepcopy(capture["context"]),
            "sourceImportSha256": imported["contentSha256"],
            "retrieverTargetSha256": target_hash,
            "understanderTaskSha256": task["contentSha256"],
            "modelInput": {
                "schema": "speakeasy-reported-answer-input", "schemaVersion": 1,
                "speakerRef": capture["context"]["personId"],
                "listenerRef": capture["context"]["listenerRef"],
                "utterance": capture["context"]["utterance"],
                "semanticIntent": copy.deepcopy(task["output"]),
                "situation": copy.deepcopy(capture["context"]["situation"]),
                "voiceConditioning": copy.deepcopy(capture["catalogue"]["conditioning"]),
                "unavailableInputs": list(capture["coverage"]["unavailableInputs"]),
                "selectedClaims": copy.deepcopy(selected),
                "reports": [report_content(claim, capture) for claim in selected]}}


def render(parts, model_input):
    A.require(isinstance(parts, list) and parts, "answer parts must be a nonempty list")
    reports = {report["claimRef"]: report for report in model_input["reports"]}
    seen, lines = set(), []
    for part in parts:
        A.fields(part, {"kind", "claimRef", "publicationDate", "summary"}, "reported answer part")
        A.require(part["kind"] == "reported-source-summary", "unsupported answer part kind")
        ref = part["claimRef"]
        A.identifier(ref, "answer claimRef")
        A.require(ref in reports and ref not in seen, "unknown or duplicate answer claim")
        seen.add(ref)
        report = reports[ref]
        A.require(part["publicationDate"] == report["publicationDate"], "answer publication date differs")
        A.require(part["summary"] == report["summary"], "answer must preserve the complete report summary")
        day = datetime.fromisoformat(report["publicationDate"])
        date_text = f"{MONTHS[day.month - 1]} {day.day}, {day.year}"
        summary = report["summary"]
        lines.append(f"The {date_text} paper reported that {summary}")
    A.require(list(reports) == [part["claimRef"] for part in parts],
              "answer must cover the ordered selected reports")
    return " ".join(lines)


def bound_input_for(target_hash, evidence):
    """Use captured identities and selected propositions as the speaker input."""
    import expression_proof as P
    inputs = input_for(target_hash, evidence)
    previous = inputs["modelInput"]
    inputs["modelInput"] = {
        "schema": "speakeasy-bound-answer-input", "schemaVersion": 1,
        **{key: copy.deepcopy(previous[key]) for key in (
            "speakerRef", "listenerRef", "utterance", "semanticIntent", "situation")},
        "expressionInput": P.compile_source(P.from_target(target_hash, evidence))}
    return inputs


def render_bound(parts, source):
    import expression_proof as P
    A.require(isinstance(parts, list) and parts, "bound answer parts must be nonempty")
    refs, lines = [], []
    for part in parts:
        P.validate_output(part, source)
        A.require(part["plan"]["kind"] == "report", "speaker task requires selected reports")
        refs.append(part["plan"]["reportRef"])
        lines.append(part["text"])
    A.require(refs == [report["claimRef"] for report in source["reports"]],
              "bound answer must cover ordered selected reports once")
    return " ".join(lines)


def propose_bound(target_hash, row_id, plans, evidence=None):
    """Plans are explicit authored targets; no voice is selected on the user's behalf."""
    import expression_proof as P
    evidence = evidence or E.Store()
    inputs = bound_input_for(target_hash, evidence)
    source = P.from_target(target_hash, evidence)
    parts = [P.produce(source, plan) for plan in plans]
    model = inputs["modelInput"]
    row = A.seal({"schema": C.TASK_SCHEMA, "schemaVersion": BOUND_VERSION,
        "rowId": row_id, "task": "speaker", "input": inputs,
        "output": {"speechAct": "answer", "speakerRef": model["speakerRef"],
                   "listenerRef": model["listenerRef"], "parts": parts,
                   "text": render_bound(parts, source)},
        "requiredClaimRefs": [report["claimRef"] for report in source["reports"]]})
    validate_task(row, evidence)
    return row


def propose(target_hash, row_id, evidence=None):
    evidence = evidence or E.Store()
    inputs = input_for(target_hash, evidence)
    model = inputs["modelInput"]
    parts = [{"kind": "reported-source-summary", "claimRef": r["claimRef"],
              "publicationDate": r["publicationDate"], "summary": r["summary"]}
             for r in model["reports"]]
    row = A.seal({"schema": C.TASK_SCHEMA, "schemaVersion": VERSION, "rowId": row_id,
                  "task": "speaker", "input": inputs,
                  "output": {"speechAct": "answer", "speakerRef": model["speakerRef"],
                             "listenerRef": model["listenerRef"], "parts": parts,
                             "text": render(parts, model)},
                  "requiredClaimRefs": [r["claimRef"] for r in model["reports"]]})
    validate_task(row, evidence)
    return row


def validate_task(row, evidence=None):
    evidence = evidence or E.Store()
    A.fields(row, {"schema", "schemaVersion", "rowId", "task", "input", "output",
                   "requiredClaimRefs", "contentSha256"}, "speaker task")
    A.require(row["schema"] == C.TASK_SCHEMA and type(row["schemaVersion"]) is int
              and row["schemaVersion"] in (VERSION, BOUND_VERSION) and row["task"] == "speaker",
              "requires speaker task evidence version 3 or 4")
    body = dict(row)
    A.hash_value(body.pop("contentSha256"), "speaker task seal")
    A.require(A.digest(body) == row["contentSha256"], "speaker task content hash differs")
    A.identifier(row["rowId"], "speaker rowId")
    A.require(isinstance(row["input"], dict), "speaker input must be an object")
    target_hash = row["input"].get("retrieverTargetSha256")
    A.hash_value(target_hash, "speaker retriever target")
    bound = row["schemaVersion"] == BOUND_VERSION
    expected = bound_input_for(target_hash, evidence) if bound else input_for(target_hash, evidence)
    A.require(A.digest(row["input"]) == A.digest(expected), "speaker input differs from approved source chain")
    output, model = row["output"], expected["modelInput"]
    A.fields(output, {"speechAct", "speakerRef", "listenerRef", "parts", "text"}, "speaker output")
    A.require(output["speechAct"] == "answer" and output["speakerRef"] == model["speakerRef"]
              and output["listenerRef"] == model["listenerRef"], "answer participants or act differ")
    if bound:
        import expression_proof as P
        source = P.from_target(target_hash, evidence)
        required = [r["claimRef"] for r in source["reports"]]
        text = render_bound(output["parts"], source)
    else:
        required = [r["claimRef"] for r in model["reports"]]
        text = render(output["parts"], model)
    A.require(row["requiredClaimRefs"] == required,
              "speaker required claims differ")
    A.require(output["text"] == text, "answer text differs from factual rendering")
    return row


def conditioning(row, evidence=None, *, scope=None, approval=None):
    if scope is not None:
        import experimental_admission as X
        return X.inspect(row, scope=scope, approval=approval, evidence=evidence)
    evidence = evidence or E.Store()
    validate_task(row, evidence)
    target = evidence.read(row["input"]["retrieverTargetSha256"])
    return {"status": "ineligible", "exclusions": list(target["conditioning"]["exclusions"]) + EXCLUSIONS}


def approve(row, receipt_hash, snapshot_id, evidence=None):
    evidence = evidence or E.Store()
    validate_task(row, evidence)
    evidence.decision(receipt_hash, row["contentSha256"])
    A.identifier(snapshot_id, "speaker snapshot ID")
    return A.seal({"schema": "speakeasy-task-evidence-snapshot", "schemaVersion": 1,
                   "snapshotId": snapshot_id, "task": "speaker", "rows": [{
                       "rowId": row["rowId"], "rowContentSha256": row["contentSha256"],
                       "approvalReceiptSha256": receipt_hash}]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--propose", metavar="RETRIEVER_TARGET_HASH")
    mode.add_argument("--validate", type=Path)
    mode.add_argument("--approve", type=Path)
    parser.add_argument("--row-id")
    parser.add_argument("--bound-plans", type=Path,
                        help="JSON list of explicit expression-proof plans; proposes version 4")
    parser.add_argument("--receipt-hash")
    parser.add_argument("--snapshot-id")
    parser.add_argument("--evidence-root", type=Path, default=E.ROOT)
    args = parser.parse_args()
    try:
        evidence = E.Store(args.evidence_root)
        if args.propose:
            value = (propose_bound(args.propose, args.row_id, A.read(args.bound_plans), evidence)
                     if args.bound_plans else propose(args.propose, args.row_id, evidence))
            print("Proposed speaker: " + C.save_evidence(value, args.evidence_root))
            print(value["output"]["text"])
        elif args.approve:
            value = approve(A.read(args.approve), args.receipt_hash, args.snapshot_id, evidence)
            print("Approved speaker snapshot: " + C.save_evidence(value, args.evidence_root))
        else:
            row = validate_task(A.read(args.validate), evidence)
            print("Valid bounded speaker example: " + row["contentSha256"])
    except (J.ContractError, OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, "REFUSED: " + str(error) + "\n")


if __name__ == "__main__":
    main()
