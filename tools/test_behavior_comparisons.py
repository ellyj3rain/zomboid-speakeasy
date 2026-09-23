"""Behavioral comparison boundaries; synthetic inputs never become approvals."""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import behavior_comparisons as B
import conversation_tasks as C
import cross_module_rows as J
import decision_authoring as A
import training_evidence as E


class BehaviorTests(unittest.TestCase):
    def setUp(self):
        self.capture = copy.deepcopy(E.Store().read(
            'f71389f06f52f44372a27850b9eddf9a43ccecdf14e826f6b5624b539bd1ed26')['capture'])
        self.capture['schemaVersion'] = 2
        conditioning = self.capture['catalogue']['conditioning']
        channels = {name: {'owner': owner, 'status': 'unavailable', 'reason': 'body-not-loaded'}
                    for name, owner in B.OWNERS.items()}
        values = {
            'temperament': {key: {'base': v, 'history': 0, 'lesson': 0, 'condition': 0, 'effective': v}
                            for key, v in conditioning['traits'].items()},
            'conditions': {'carried': ['anxiety'], 'fearContribution': .25},
            'relationship': {'trust': 0, 'debt': 0, 'hostile': False},
            'threat': {'pressure': 0, 'scope': 'retained-zombie-beliefs'},
            'cognition': {'observedAtHour': 48, 'enabled': True, 'load': 0, 'clarity': 1,
                          'affectiveVolatility': 0, 'baseDecisionTicks': 16, 'decisionTicks': 16},
            'experience': {'known': {}, 'provenance': {}, 'legacy': {}}}
        for name, value in values.items():
            channels[name] = {'owner': B.OWNERS[name], 'status': 'available', 'value': value}
        self.capture['behavior'] = {'schema': 'sao-behavior-evidence', 'schemaVersion': 1,
            'personId': self.capture['context']['personId'], 'listenerRef': self.capture['context']['listenerRef'],
            'atTick': 432000, 'atHour': 48, 'channels': channels}

    def test_exact_channel_axes_owner_and_time(self):
        B.validate_behavior(self.capture)
        for edit in [
            lambda v: v['behavior'].update(personId='foreign'),
            lambda v: v['behavior']['channels']['temperament'].update(value={}),
            lambda v: v['behavior']['channels']['cognition']['value'].update(observedAtHour=47),
            lambda v: v['behavior']['channels']['relationship'].update(owner='unrelated'),
            lambda v: v['behavior']['channels']['threat']['value'].update(nearest={'at': 999999}),
            lambda v: v['behavior']['channels']['temperament']['value']['nerve'].update(condition=.8),
            lambda v: v['behavior']['channels']['needs'].update(status='available', value={'fatigue': 0}),
        ]:
            value = copy.deepcopy(self.capture)
            edit(value)
            with self.assertRaises((J.ContractError, KeyError)): B.validate_behavior(value)

    def test_model_input_excludes_owner_state_and_medical_causes_but_has_report(self):
        self.capture['sourceState']['auditOnly'] = {'wound': True, 'futureEvent': 'hidden'}
        view = B.model_view(self.capture)
        text = A.encoded(view).decode()
        for word in ('ownerStateBytes', 'auditOnly', 'futureEvent', 'neuroState'):
            self.assertNotIn(word, text)
        self.assertEqual(len(view['reports']), 1)
        self.assertEqual(view['utteranceRoles'], {'speakerRef': self.capture['context']['listenerRef'],
                                                'listenerRef': self.capture['context']['personId']})
        self.assertIn('at press time', view['reports'][0]['summary'])
        self.assertEqual(view['behavior']['needs']['status'], 'unavailable')
        broken = copy.deepcopy(self.capture)
        broken['behavior']['channels']['cognition']['value']['hiddenCause'] = 'wound'
        with self.assertRaises(J.ContractError): B.model_view(broken)

    def test_prepared_comparison_rebuilds_changes_and_never_admits_text(self):
        baseline = {'capture': self.capture, 'manifest': {'scenario': {'behaviorIntervention': {'id': 'test-only'}}}}
        changed = copy.deepcopy(baseline)
        changed['capture']['behavior']['channels']['relationship']['value']['trust'] = .6
        changed['capture']['catalogue']['conditioning'].update(trust=.6, trusted=True)
        objects = {'0'*64: baseline, '1'*64: changed}
        class SyntheticStore:
            def read(self, digest): return copy.deepcopy(objects[digest])
        request = {'schema': 'speakeasy-behavior-comparison-request', 'schemaVersion': 1,
            'familyId': 'test-only-family', 'baselineImportSha256': '0'*64, 'cases': [
                {'id': 'test-only-case', 'importSha256': '1'*64, 'question': 'Which delivery?',
                 'learningConsequence': 'Test only; no training.', 'candidates': [
                     {'id': 'a', 'act': 'answer', 'text': 'First authored text.', 'emphasis': 'First'},
                     {'id': 'b', 'act': 'answer', 'text': 'Second authored text.', 'emphasis': 'Second'}]}]}
        # Source authenticity has its own exact-commit import tests. This isolates
        # preparation over a deliberately synthetic, unregistered capture pair.
        with patch.object(C, 'validate_import', side_effect=lambda value: value):
            result = B.prepare(request, SyntheticStore())
            B.validate(result, SyntheticStore())
            self.assertEqual(result['cases'][0]['changedChannels'], ['relationship'])
            self.assertFalse(result['trainingEligible'])
            for mutation in ('input', 'standing', 'changedChannels', 'text'):
                value = copy.deepcopy(result)
                if mutation == 'input': value['cases'][0]['modelInput']['behavior']['relationship']['value']['trust'] = 1
                elif mutation == 'standing': value['trainingEligible'] = True
                elif mutation == 'changedChannels': value['cases'][0]['changedChannels'] = []
                else: value['cases'][0]['candidates'][0]['text'] = 'Unbound replacement'
                value.pop('contentSha256')
                with self.assertRaisesRegex(J.ContractError, 'comparison differs'):
                    B.validate(A.seal(value), SyntheticStore())
        with self.assertRaises((J.ContractError, KeyError)):
            C.validate_import(baseline)

    def test_published_family_and_literal_review_agree(self):
        folder = Path(__file__).resolve().parents[1] / 'training/behavior/c78'
        result = B.validate(A.read(folder / 'comparison.json'))
        invocation = A.read(folder / 'review-invocation.json')
        evidence = E.Store()
        self.assertEqual(len(result['cases']), 4)
        for case, seam in zip(result['cases'], invocation['intake']['seams'], strict=True):
            imported = C.validate_import(evidence.read(case['importSha256']))
            self.assertEqual(seam['id'], 'c78-behavior-' + case['id'])
            self.assertEqual(seam['prompt'], case['question'])
            self.assertEqual([v['value'] for v in seam['mlReview']['proposedLearning']],
                             [v['text'] for v in case['candidates']])
            self.assertEqual(seam['mlReview']['decisionPrecedent'], case['learningConsequence'])
            seals = {v['label']: v['value'] for v in seam['mlReview']['evidence']}
            self.assertEqual(seals['Exact source capture'], imported['manifest']['captureSha256'])
            self.assertEqual(seals['Producer manifest'], imported['manifest']['contentSha256'])
            self.assertFalse(case['trainingEligible'])
        indexed = {c['id']: c for c in result['cases']}
        self.assertEqual(indexed['trusted']['changedChannels'], ['relationship'])
        self.assertEqual(indexed['threat']['changedChannels'], ['threat'])
        self.assertEqual(indexed['strain']['modelInput']['behavior']['cognition']['value']['decisionTicks'], 18)
        self.assertEqual(result['baselineInput']['behavior']['cognition']['value']['decisionTicks'], 16)
        lesson_claims = indexed['learned']['modelInput']['catalogue']['claims']
        self.assertTrue(any(c['fact'].get('key') == 'measure-the-danger' and c['fact'].get('source') == 'told'
                            for c in lesson_claims))
        # Existing task admission cannot turn this reviewed comparison schema
        # into a trained speaker example.
        import experimental_admission as X
        admission = X.inspect(result, scope='offline-authored-conversation-v1')
        self.assertEqual(admission['status'], 'excluded')
        self.assertIn('source-and-task-contract:unsupported-task-contract', admission['exclusions'])


if __name__ == '__main__':
    unittest.main()
