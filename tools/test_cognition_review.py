import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cross_module_rows as Join
import cognition_review as R


def row(actor, number, ordinary, associative, success=True):
    selected = associative
    predictions = lambda probability: {selected: {"probability": probability, "claim": "bounded"}}
    episode = {"id": f"episode/{number}", "worldHours": 2 + number / 10,
        "status": "observed", "disagreement": ordinary != associative,
        "selectedActionId": selected, "selectedModelId": "associative",
        "proposals": [
            {"modelId": "ordinary", "actionId": ordinary, "predictions": predictions(.4)},
            {"modelId": "associative", "actionId": associative, "predictions": predictions(.7)}],
        "outcome": {"eventId": f"event/{number}", "worldHours": 2.01 + number / 10,
                    "success": success}}
    return {"schema": "speakeasy-cognition-episode/1", "datasetAdmission": "unreviewed",
            "actorId": actor, "episode": episode,
            "selectedActionComparison": [
                {"modelId": "ordinary", "probability": .4, "squaredError": .36},
                {"modelId": "associative", "probability": .7, "squaredError": .09}]}


def fixture(root, rows):
    raw = b"".join(R.encoded(value) for value in rows)
    (root / "episodes.jsonl").write_bytes(raw)
    manifest = {"schema": "speakeasy-cognition-trajectories/1",
        "datasetAdmission": "unreviewed", "trainingRows": 0, "teachingTargets": 0,
        "episodes": len(rows), "files": {"episodes.jsonl": R.digest(raw)}}
    (root / "manifest.json").write_bytes(R.encoded(manifest))


class CognitionReview(unittest.TestCase):
    def test_completed_disagreements_collapse_to_actor_trajectories(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            rows = [row("sao-1", i, "continue", "inspect") for i in range(1, 5)]
            rows += [row("sao-2", 5, "continue", "food")]
            fixture(root, rows)
            compiled = R.review_invocation(root, "session", "invocation")
            self.assertEqual(compiled["observedDisagreements"], 5)
            self.assertEqual(compiled["actorTrajectories"], 2)
            self.assertEqual(compiled["trainingRows"], 0)
            self.assertEqual(compiled["invocation"]["skillRef"], "mass-assault")
            seams = compiled["invocation"]["intake"]["seams"]
            self.assertEqual([seam["order"] for seam in seams], [1, 2])
            first = seams[0]
            self.assertTrue(first["options"][0]["recommended"])
            self.assertIn("does not ratify a rule", first["mlReview"]["decisionPrecedent"])
            evidence = {item["label"]: json.loads(item["value"])
                        for item in first["mlReview"]["actualInput"]}
            self.assertEqual(evidence["Ordinary cognition model"]["proposals"], {"continue": 4})
            self.assertEqual(evidence["Ordinary cognition model"]["selected"], 0)
            self.assertEqual(evidence["Associative discovery model"]["proposals"], {"inspect": 4})
            self.assertEqual(evidence["Associative discovery model"]["selected"], 4)

    def test_unobserved_rows_remain_sequestered_without_review_spam(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            value = row("sao-1", 1, "continue", "inspect")
            value["episode"]["status"] = "censored"
            value["episode"].pop("outcome")
            fixture(root, [value])
            compiled = R.review_invocation(root, "session", "invocation")
            self.assertIsNone(compiled["invocation"])
            self.assertEqual(compiled["sequesteredWithoutObservedOutcome"], 1)

    def test_queue_is_durable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "evidence"; root.mkdir()
            outbox = Path(name) / "outbox"
            fixture(root, [row("sao-1", 1, "continue", "food")])
            result = {"schema": "speakeasy-mousecat-review-queue/1",
                      "status": "queued", "interactionId": "skill-example"}
            with patch.object(R.Mousecat, "invoke_skill", return_value=result) as invoke:
                first = R.queue(root, outbox, "http://localhost:4317/mcp", "session")
            second = R.queue(root, outbox, "http://localhost:4317/mcp", "session")
            self.assertEqual(first, second)
            invoke.assert_called_once()
            self.assertEqual(json.loads((outbox / "queued.json").read_text())["trainingRows"], 0)
            manifest = json.loads((root / "manifest.json").read_text())
            manifest["episodes"] += 1
            (root / "manifest.json").write_bytes(R.encoded(manifest))
            with self.assertRaisesRegex(Join.ContractError, "different evidence"):
                R.queue(root, outbox, "http://localhost:4317/mcp", "session")


if __name__ == "__main__":
    unittest.main()
