"""Controls for dated-report speaker evidence and factual rendering."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import conversation_tasks as C
import speaker_tasks as S
import cross_module_rows as J
import decision_authoring as A
import retriever_targets as R
import training_evidence as E
import test_retriever_targets as F


def reseal(value):
    value = copy.deepcopy(value)
    value.pop("contentSha256", None)
    return A.seal(value)


class SpeakerTests(unittest.TestCase):
    def setUp(self):
        self.index = A.read(C.ROOT / "training/speaker/c77-example.json")
        self.row = E.Store().read(self.index["taskSha256"])
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for path in E.ROOT.glob("*.json"):
            C.save_evidence(A.read(path), self.root)
        self.store = E.Store(self.root)

    def test_complete_approved_chain_and_bounded_model_input(self):
        row = S.propose(self.index["retrieverTargetSha256"], self.row["rowId"], self.store)
        self.assertEqual(row, self.row)
        model = row["input"]["modelInput"]
        self.assertEqual(len(model["selectedClaims"]), 1)
        self.assertNotIn("catalogue", model)
        self.assertNotIn("sourceState", model)
        self.assertEqual(row["output"]["speakerRef"], "sao-1")
        self.assertEqual(row["output"]["listenerRef"], "sao-2")
        self.assertIn("July 2, 1993 paper reported", row["output"]["text"])
        self.assertEqual(model["reports"][0]["acquiredHour"],24)
        self.assertEqual(len(model["unavailableInputs"]), 3)
        self.assertEqual(S.conditioning(row,self.store)["status"], "ineligible")

    def test_resealed_text_cannot_assert_current_service_or_personal_use(self):
        for text in ("The phones are still down today.", "I used the Internet before the outage.",
                     "Service returned after a few hours.", "Everyone had Internet access.",
                     self.row["output"]["text"] + " I checked today."):
            row = copy.deepcopy(self.row)
            row["output"]["text"] = text
            with self.subTest(text=text), self.assertRaisesRegex(J.ContractError,"factual rendering"):
                S.validate_task(reseal(row),self.store)

    def test_source_summary_cannot_be_replaced_or_selectively_clipped(self):
        for summary in ("Phones work now.", self.row["output"]["parts"][0]["summary"].split(';')[0],
                        "lightning or sabotage."):
            row = copy.deepcopy(self.row)
            row["output"]["parts"][0]["summary"] = summary
            row["output"]["text"] = "The July 2, 1993 paper reported that " + summary
            with self.subTest(summary=summary), self.assertRaisesRegex(J.ContractError,"complete report"):
                S.validate_task(reseal(row),self.store)

    def test_publication_cannot_be_replaced_by_reading_or_question_date(self):
        for date in ("1993-07-10", "1993-07-11"):
            row = copy.deepcopy(self.row)
            row["output"]["parts"][0]["publicationDate"] = date
            with self.subTest(date=date), self.assertRaisesRegex(J.ContractError,"publication date"):
                S.validate_task(reseal(row),self.store)

    def test_foreign_unselected_duplicate_empty_or_freeform_parts_refuse(self):
        for defect in ("foreign","unselected","duplicate","empty","literal","extra"):
            row=copy.deepcopy(self.row);parts=row["output"]["parts"]
            if defect=="foreign": parts[0]["claimRef"]="unknown"
            elif defect=="unselected": parts[0]["claimRef"]=row["input"]["catalogue"]["claims"][0]["ref"]
            elif defect=="duplicate": parts.append(copy.deepcopy(parts[0]))
            elif defect=="empty": parts.clear()
            elif defect=="literal": parts[0]["kind"]="free-text"
            else: parts[0]["newFact"]="Phones are working"
            with self.subTest(defect=defect),self.assertRaises(J.ContractError):
                S.validate_task(reseal(row),self.store)

    def test_voice_context_energy_and_selected_facts_are_source_bound(self):
        for defect in ("voice","energy","fact","intent","utterance","context","extra"):
            row=copy.deepcopy(self.row);model=row["input"]["modelInput"]
            if defect=="voice": model["voiceConditioning"]["trust"]=100
            elif defect=="energy": model["unavailableInputs"]=[]
            elif defect=="fact": model["selectedClaims"].append(row["input"]["catalogue"]["claims"][0])
            elif defect=="intent": model["semanticIntent"]["speechAct"]="threat"
            elif defect=="utterance": model["utterance"]="Are the phones working?"
            elif defect=="context": row["input"]["context"]["atTick"]+=9000
            else: model["omniscientFact"]="power is restored"
            with self.subTest(defect=defect),self.assertRaisesRegex(J.ContractError,"approved source chain"):
                S.validate_task(reseal(row),self.store)

    def test_roles_required_refs_and_output_extensions_refuse(self):
        for defect in ("speaker","listener","refs","extra","act"):
            row=copy.deepcopy(self.row)
            if defect=="speaker": row["output"]["speakerRef"]="sao-2"
            elif defect=="listener": row["output"]["listenerRef"]="sao-1"
            elif defect=="refs": row["requiredClaimRefs"]=[]
            elif defect=="extra": row["output"]["extra"]="true"
            else: row["output"]["speechAct"]="request"
            with self.subTest(defect=defect),self.assertRaises(J.ContractError):
                S.validate_task(reseal(row),self.store)

    def test_missing_retrieval_approval_or_source_refuses(self):
        target=self.store.read(self.index["retrieverTargetSha256"])
        imports=self.row["input"]["sourceImportSha256"]
        for digest in (target["review"]["decision"]["resultSha256"],imports):
            path=self.root/(digest+".json");data=path.read_bytes();path.unlink()
            try:
                with self.assertRaisesRegex(J.ContractError,"missing evidence"):
                    S.validate_task(self.row,self.store)
            finally:path.write_bytes(data)

    def test_changed_protected_source_refuses_before_rendering(self):
        with patch.object(C,"file_hash",return_value="0"*64):
            with self.assertRaisesRegex(J.ContractError,"source hash differs"):
                S.validate_task(self.row,self.store)

    def fixture_approval(self):
        fixture=F.RetrieverTargetTests();fixture.evidence_root=self.root
        return fixture.mousecat(self.row["contentSha256"],interaction="speaker-test-only")

    def test_speaker_approval_is_independent_of_both_prior_rulings(self):
        index=A.read(C.ROOT/"training/understander/c77-example.json")
        for digest in (index["approvalReceiptSha256"],index["retrieverResultSha256"]):
            with self.assertRaisesRegex(J.ContractError,"exact subject"):
                S.approve(self.row,digest,"fixture-only",self.store)

    def test_qualified_rejected_and_pending_speaker_results_refuse(self):
        original=self.store.read(self.fixture_approval())
        for defect in ("notes","pending","rejected"):
            value=copy.deepcopy(original)
            if defect=="notes":value["responses"][0]["notes"]="Make it shorter."
            elif defect=="pending":value["status"]="pending"
            else:value["responses"][0]["value"]="rejected"
            digest=C.save_evidence(value,self.root)
            with self.subTest(defect=defect),self.assertRaises(J.ContractError):
                S.approve(self.row,digest,"fixture-only",self.store)

    def test_speaker_resolves_through_shared_evidence_and_keeps_exclusions(self):
        receipt=self.fixture_approval()
        snapshot=S.approve(self.row,receipt,"speaker-fixture-only",self.store)
        C.save_evidence(snapshot,self.root)
        catalogue=self.row["input"]["catalogue"]
        anchor=A.seal({"schema":R.ANCHOR_SCHEMA,"schemaVersion":2,"anchorId":"speaker-fixture-anchor",
            "task":"speaker","catalogue":{"snapshotRef":catalogue["snapshotRef"],"contentSha256":A.digest(catalogue)},
            "context":self.row["input"]["context"],"taskExample":{"datasetSnapshotRef":snapshot["snapshotId"],
            "datasetSnapshotSha256":snapshot["contentSha256"],**snapshot["rows"][0],"standing":"approved"},
            "requiredClaimRefs":self.row["requiredClaimRefs"]})
        self.assertEqual(self.store.task_anchor(anchor,catalogue),self.row)
        self.assertEqual(R.task_conditioning(anchor,catalogue,self.store),S.conditioning(self.row,self.store))
        self.assertIn("speaker-free-composition-decoder-not-implemented",R.task_conditioning(anchor,catalogue,self.store)["exclusions"])


if __name__=="__main__": unittest.main()
