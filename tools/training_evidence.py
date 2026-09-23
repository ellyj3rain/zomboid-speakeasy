"""Resolve saved training evidence by canonical JSON content hash.

These are evidence envelopes, not model inputs or proof of source authenticity.
Repository review owns the authenticity of imported Mousecat/source receipts.
"""
from pathlib import Path

import decision_authoring as A
import cross_module_rows as J

ROOT = J.ROOT / "training/evidence"


class Store:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else ROOT

    def read(self, digest):
        A.hash_value(digest, "evidence digest")
        path = self.root / (digest + ".json")
        A.require(path.is_file(), "missing evidence object: " + digest)
        value = A.read(path)
        A.require(isinstance(value, dict), "evidence object must be an object")
        # Sealed Speakeasy records hash their body. Native Mousecat receipts
        # have no seal and are hashed as complete JSON objects.
        body = dict(value)
        declared = body.pop("contentSha256", None)
        A.require(A.digest(body) == digest
                  and ("contentSha256" not in value or declared == digest),
                  "evidence content hash differs: " + digest)
        return value

    def decision(self, digest, subject_hash, *, interaction=None, item_id=None,
                 status="approved"):
        value = self.read(digest)
        A.require(value.get("schema") == "mousecat.skill-invocation/2"
                  and value.get("action") == "await"
                  and value.get("skillRef") in ("crucible", "mass-assault")
                  and value.get("status") in ("answered", "completed"),
                  "decision evidence is not a completed Mousecat result")
        A.identifier(value.get("interactionId"), "Mousecat interaction")
        if interaction is not None:
            A.require(value["interactionId"] == interaction, "Mousecat interaction differs")
        items, responses = value.get("items"), value.get("responses")
        A.require(isinstance(items, list) and isinstance(responses, list),
                  "Mousecat items/responses are absent")
        expected = "speakeasy:content-sha256:" + subject_hash
        matching = [entry for entry in items if isinstance(entry, dict)
                    and isinstance(entry.get("lineage"), dict)
                    and entry["lineage"].get("evidenceRef") == expected
                    and (item_id is None or entry.get("id") == item_id)]
        A.require(len(matching) == 1, "Mousecat result does not bind the exact subject")
        item = matching[0]
        A.identifier(item.get("id"), "Mousecat item")
        A.require(item.get("shape") == "decision", "Mousecat item is not a decision")
        answers = [entry for entry in responses if isinstance(entry, dict)
                   and entry.get("itemId") == item.get("id")]
        A.require(len(answers) == 1, "Mousecat decision response is missing or duplicate")
        answer = answers[0]
        A.require(answer.get("shape") == "decision"
                  and answer.get("status") == "answered"
                  and answer.get("value") == status
                  and answer.get("selectedOption") == status
                  and answer.get("selectedOptions") == [status]
                  and answer.get("lineage") == item["lineage"],
                  "Mousecat decision or lineage differs")
        # Freeform qualifications need interpretation and a new exact proposal;
        # an automatic admission cannot silently drop them.
        A.require(answer.get("notes") in (None, ""),
                  "qualified Mousecat answer requires a revised proposal")
        return value

    def task_anchor(self, anchor, catalogue):
        binding = anchor["taskExample"]
        snapshot = self.read(binding["datasetSnapshotSha256"])
        A.schema(snapshot, "speakeasy-task-evidence-snapshot")
        A.fields(snapshot, {"schema", "schemaVersion", "snapshotId", "task", "rows",
                            "contentSha256"}, "task evidence snapshot")
        A.require(snapshot["snapshotId"] == binding["datasetSnapshotRef"]
                  and snapshot["task"] == anchor["task"], "task snapshot identity differs")
        A.require(isinstance(snapshot["rows"], list), "task snapshot rows must be a list")
        rows = snapshot["rows"]
        for entry in rows:
            A.fields(entry, {"rowId", "rowContentSha256", "approvalReceiptSha256"},
                     "task snapshot row reference")
            A.identifier(entry["rowId"], "task rowId")
            A.hash_value(entry["rowContentSha256"], "task row hash")
            A.hash_value(entry["approvalReceiptSha256"], "task approval hash")
        A.require(len({entry["rowId"] for entry in rows}) == len(rows),
                  "task evidence snapshot has duplicate row IDs")
        matching = [entry for entry in rows if entry["rowId"] == binding["rowId"]]
        A.require(len(matching) == 1 and matching[0] == {
            key: binding[key] for key in ("rowId", "rowContentSha256", "approvalReceiptSha256")
        }, "task row is absent from the referenced snapshot")
        row = self.read(binding["rowContentSha256"])
        if row.get("schemaVersion") == 3:
            import speaker_tasks as S
            S.validate_task(row, self)
        elif row.get("schemaVersion") == 2:
            import conversation_tasks as C
            C.validate_task(row, self)
        else:
            A.schema(row, "speakeasy-task-evidence")
        A.fields(row, {"schema", "schemaVersion", "rowId", "task", "input", "output",
                       "requiredClaimRefs", "contentSha256"}, "task evidence")
        A.require(row["rowId"] == binding["rowId"] and row["task"] == anchor["task"],
                  "source task row identity differs")
        comparable = row["input"]
        if row.get("schemaVersion") in (2, 3):
            comparable = {key: comparable[key] for key in ("catalogue", "context")}
        A.require(A.digest(comparable) == A.digest({"catalogue": catalogue,
                                                 "context": anchor["context"]}),
                  "source task input differs from anchor")
        A.require(row["requiredClaimRefs"] == anchor["requiredClaimRefs"],
                  "source task required claims differ from anchor")
        A.require(isinstance(row["output"], dict) and row["output"],
                  "source task output is missing")
        self.decision(binding["approvalReceiptSha256"], binding["rowContentSha256"])
        return row

    def references(self, entries, name, row_hashes=None):
        for entry in entries:
            value = self.read(entry["evidenceSha256"])
            A.require(value.get("id") == entry["id"] and value.get("reason") == entry["reason"],
                      name + " evidence identity differs")
            if row_hashes is not None:
                A.require(value.get("rowContentSha256s") == sorted(row_hashes),
                          "evaluation receipt does not cover the exact dataset rows")
