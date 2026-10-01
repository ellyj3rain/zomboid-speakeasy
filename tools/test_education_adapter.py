"""Source producer controls, answer masks and actual frozen-base gradient tests."""
import copy
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import byte_tokenizer as B
import decision_authoring as A
import education_adapter as T
import education_adapter_data as D
import education_assessment as G
import education_corpus as C
import foundation_assessment as E
import foundation_pretraining as F
import test_education_assessment as Q


class PublicSupervisionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Q.EducationAssessmentTests('test_actual_producer_preserves_source_bound_bank')
        self.fixture.setUp(); self.tokenizer = B.Tokenizer(B.train([b'Private TRAIN fit only.'], 4))

    def tearDown(self): self.fixture.tearDown()

    def public(self, identity='fraction'):
        value = G.learner_input(self.fixture.item(identity)); value.pop('contentSha256')
        return A.seal({**value, 'split': 'train'})

    def test_lazy_optional_torch_import(self):
        code = "import sys;sys.modules['torch']=None;import education_adapter;import education_adapter_data"
        result = subprocess.run([sys.executable, '-c', code], cwd=Path(T.__file__).parent, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_source_answer_only_shift_eos_pad_loss_and_unicode_parity(self):
        target = self.fixture.item('fraction')['gradingTarget']
        row = D.supervised(self.public(), target, self.tokenizer, 256, 32)
        n = row['promptTokenCount']; active = [i for i, enabled in enumerate(row['lossMask']) if enabled]
        self.assertEqual(active, list(range(n-1, n+len(self.tokenizer.encode_text(row['answer'])))))
        self.assertEqual(row['targetIds'][active[-1]], B.SPECIAL_IDS['eos'])
        self.assertFalse(any(row['lossMask'][:n-1]))
        count = sum(x != B.SPECIAL_IDS['pad'] for x in row['inputIds'])
        self.assertEqual(row['inputIds'][1:count], row['targetIds'][:count-1])
        self.assertFalse(any(row['lossMask'][count:]))
        self.assertIn('mfrac', self.fixture.item('fraction')['solutionXml'][0])
        for answer in ['Zoë 李 🙂 Δ x²', '2.5e-3 m']:
            controlled = D.supervised(self.public(), {'kind': 'numeric', 'literal': answer}, self.tokenizer, 256, 64)
            tokens = [t for t, mask in zip(controlled['targetIds'], controlled['lossMask'])
                      if mask and t != B.SPECIAL_IDS['eos']]
            self.assertEqual(self.tokenizer.decode_bytes(tokens), answer.encode())

    def test_heldout_supervision_hidden_answers_and_complete_overflow_refuse(self):
        heldout = G.learner_input(self.fixture.item('fraction'))
        with self.assertRaisesRegex(ValueError, 'held-out answer'): D.supervised(
            heldout, self.fixture.item('fraction')['gradingTarget'], self.tokenizer, 256, 32)
        public = self.public(); inner = copy.deepcopy(public['input']); inner.pop('contentSha256')
        inner['problemXml'] = ['<problem><para>Question</para><solution>HIDDEN</solution></problem>']
        public.pop('contentSha256'); public['input'] = A.seal(inner); public = A.seal(public)
        with self.assertRaisesRegex(ValueError, 'hidden answer'): E.public_prompt(public)
        self.assertIsNone(D.supervised(self.public(), {'kind': 'numeric', 'literal': '1'*200}, self.tokenizer, 256, 32))
        self.assertIsNone(D.supervised(self.public(), self.fixture.item('fraction')['gradingTarget'], self.tokenizer, 16, 32))

    def test_no_scored_coverage_never_becomes_performance(self):
        value = T.statistics([{'generation': {'status': 'withheld', 'coverage': {
            'inputTokens': 0, 'originalPromptTokens': 17, 'truncatedTokens': 0}},
            'grade': {'status': 'unrecognized-response'}}])
        self.assertEqual(value['coverageStanding'], 'no-scored-coverage')
        self.assertIsNone(value['accuracyOnScoredResponses'])
        self.assertEqual(value['correctFractionOfSelectedSupportedTargets'], 0)

    def test_complete_input_with_incomplete_output_still_counts_inference_attempt(self):
        rows = []
        for reason in ('maximum-output-tokens', 'structural-token-stop', 'generated-bytes-not-valid-utf8'):
            generation = A.seal({'schema': 'speakeasy-foundation-generated-answer/1',
                'status': 'generated', 'reason': reason, 'response': '123',
                'coverage': {'inputTokens': 17, 'originalPromptTokens': 17, 'truncatedTokens': 0}})
            with patch.object(E, 'inference', return_value=generation):
                actual = T.complete_inference(None, self.public(), None, 256, E.DEFAULT_POLICY)
            self.assertEqual(actual['status'], 'withheld'); self.assertEqual(actual['response'], '')
            rows.append({'generation': actual, 'grade': {'status': 'unrecognized-response'}})
        for reason in ('complete-question-exceeds-context-budget', 'required-source-media-not-provided'):
            rows.append({'generation': {'status': 'withheld', 'reason': reason,
                'coverage': {'inputTokens': 0, 'originalPromptTokens': 17, 'truncatedTokens': 0}},
                'grade': {'status': 'unrecognized-response'}})
        value = T.statistics(rows)
        self.assertEqual(value['attemptedCompleteInputs'], 3)
        self.assertEqual(value['withheldBeforeInference'], 2); self.assertEqual(value['withheldAfterInference'], 3)
        self.assertEqual(value['scoredResponses'], 0); self.assertIsNone(value['accuracyOnScoredResponses'])
        bad = copy.deepcopy(rows); bad[0]['generation']['coverage']['inputTokens'] = 8
        with self.assertRaisesRegex(ValueError, 'partial-question'): T.statistics(bad)

    def test_config_bounds_and_arbitrary_world_fields_refuse(self):
        config = {'seed': 82, 'bottleneck': 8, 'steps': 2, 'batch': 2, 'learningRate': .001,
                  'device': 'cpu', 'cpuThreads': 1}
        for key, value in [('steps', True), ('bottleneck', 0), ('learningRate', float('nan')),
                           ('device', 'auto'), ('nativeSkill', 'expert')]:
            with self.assertRaises(ValueError): T.validate_config({**config, key: value})

    def test_new_repository_source_outputs_refuse_before_source_work(self):
        target = Path(T.__file__).parent/('blocked-output-'+self.fixture.root.name)
        with patch.object(D, 'derive', side_effect=AssertionError('no source work before output guard')):
            with self.assertRaisesRegex(ValueError, 'outputs belong in runs'):
                D.prepare({}, target)
        self.assertFalse(target.exists())

    def test_single_file_evaluation_preserves_output_created_during_work(self):
        data = self.fixture.root/'boundary-data'; data.mkdir()
        C.write_json(data/'manifest.json', {'inputs': {'archive': str(self.fixture.archive)}})
        at, policy, output = [self.fixture.root/name for name in ('at.json', 'policy.json', 'evaluation.json')]
        C.write_json(at, {'clock': 'county-tick', 'value': 0}); C.write_json(policy, E.DEFAULT_POLICY)
        def concurrent_writer(*args):
            output.write_bytes(b'previous independent evidence'); return A.seal({'schema': 'controlled-cli-result/1'})
        with patch.object(T, 'evaluate', side_effect=concurrent_writer), contextlib.redirect_stderr(io.StringIO()):
            code = T.main(['evaluate', '--data', str(data), '--run', str(self.fixture.root/'run'),
                '--expected-sha256', '0'*64, '--time', str(at), '--policy', str(policy),
                '--session-id', 'controlled-boundary-test', '--out', str(output)])
        self.assertEqual(code, 2); self.assertEqual(output.read_bytes(), b'previous independent evidence')


class SourceFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.archive, self.prepared, self.dataset = [self.root/x for x in ('archive', 'prepared', 'dataset')]
        self.base_data, self.base_run, self.bank = [self.root/x for x in ('base-data', 'base-run', 'bank')]
        self.data, self.run = self.root/'answer-data', self.root/'answer-run'
        catalogue = {'schema': 'speakeasy-education-source-catalogue/1', 'standing': 'candidate-sources', 'sources': [
            {'id': 'source-'+letter, 'provider': 'openstax-github', 'repository': 'openstax/controlled-'+letter,
             'revision': letter*40, 'stages': ['primary'], 'subjects': ['mathematics']} for letter in 'abc']}
        by_revision, trees = {}, {}
        for i, source in enumerate(catalogue['sources']):
            module = ('<document xmlns="http://cnx.rice.edu/cnxml" id="module-one"><title>Book '+str(i)+
                '</title><content><section id="section"><title>Actual controlled source</title><exercise id="choice">'
                '<problem id="problem"><para>Book '+str(i)+' selects which option?</para>'
                '<list list-type="enumerated" number-style="upper-alpha"><item>Option '+str(i)+' first</item>'
                '<item>Option '+str(i)+' second</item></list></problem>'
                '<solution id="solution"><para>'+('B' if i==0 else 'A')+'</para></solution></exercise>'
                '</section></content></document>').encode()
            files = {'LICENSE': b'Attribution 4.0 International\nPrivate controlled source fixture.',
                     'modules/module-one/index.cnxml': module}
            revision = source['revision']; by_revision[revision] = files
            entries = [{'path': p, 'type': 'blob', 'size': len(raw),
                        'sha': hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
                       for p, raw in files.items()]
            trees[revision] = A.encoded({'sha': revision, 'truncated': False, 'tree': entries})
        def fetch(url):
            if '/git/trees/' in url: return trees[url.split('/git/trees/')[1].split('?')[0]], url
            revision = url.split('/')[5]; path = url.split('/'+revision+'/', 1)[1]
            return by_revision[revision][path], url
        with patch.object(C, 'fetch', side_effect=fetch): C.acquire(catalogue, self.archive)
        C.prepare(self.archive, self.prepared, 256); C.admit(self.archive, self.prepared, self.dataset)
        self.artifact = B.train([b'Private frozen TRAIN-only tokenizer corpus.'], 4)
        self.request = {'schema': 'speakeasy-educational-source-splits', 'schemaVersion': 1,
            'sourceFamilies': [{'id': 'family-'+x, 'sourceIds': ['source-'+x]} for x in 'abc'],
            'splits': {'train': ['family-a'], 'validation': ['family-b'], 'test': ['family-c']}}
        F.prepare_data(self.archive, self.prepared, self.dataset, self.artifact, self.request, self.base_data, 256)
        base_config = {**F.DEFAULT_CONFIG, 'hidden': 16, 'layers': 1, 'heads': 2, 'steps': 2,
                       'batch': 2, 'evaluationBatches': 1}
        base = F.train(self.archive, self.prepared, self.dataset, self.artifact, self.request,
                       self.base_data, base_config, self.base_run)
        split = {'schema': 'speakeasy-educational-source-splits/1', 'owner': 'caller:private-control',
                 'assignments': {'source-a': 'train', 'source-b': 'validation', 'source-c': 'test'}}
        bank = G.build_bank(self.archive, self.bank, split_policy=split)
        for name, value in [('tokenizer', self.artifact), ('splits', self.request)]: C.write_json(self.root/(name+'.json'), value)
        self.inputs = {name: str(path) for name, path in [('archive', self.archive), ('prepared', self.prepared),
            ('dataset', self.dataset), ('foundationData', self.base_data), ('baseRun', self.base_run),
            ('bank', self.bank), ('tokenizer', self.root/'tokenizer.json'), ('splits', self.root/'splits.json')]}
        self.inputs.update(baseRunSha256=base['contentSha256'], bankSha256=bank['contentSha256'])
        self.config = {'seed': 82, 'bottleneck': 8, 'steps': 30, 'batch': 2, 'learningRate': .01,
                       'device': 'cpu', 'cpuThreads': 1}

    def tearDown(self): self.temp.cleanup()


@unittest.skipUnless(importlib.util.find_spec('torch'), 'actual gradient controls use the isolated Torch environment')
class AdapterTests(SourceFixture, unittest.TestCase):
    def prepare_answers(self): return D.prepare(self.inputs, self.data)

    def test_actual_source_reconstruction_answer_exclusion_no_refitting_and_corruption(self):
        with patch.object(B, 'train', side_effect=AssertionError('frozen tokenizer must not fit')):
            manifest = self.prepare_answers(); self.assertEqual(D.verify(self.data), manifest)
        rows = T.read_train(self.data); self.assertEqual(len(rows), 1); self.assertEqual(rows[0]['answer'], 'B')
        heldout = (self.data/'heldout.jsonl').read_text(encoding='utf-8')
        for forbidden in ['gradingTarget', 'solutionXml', 'correctKey', 'sourceAnswerLiteral', '"answer"']:
            self.assertNotIn(forbidden, heldout)
        saved = self.data/'train.jsonl'; raw = saved.read_bytes(); saved.write_bytes(raw.replace(b'"answer":"B"', b'"answer":"A"'))
        with self.assertRaisesRegex(ValueError, 'adapter data differs'): D.verify(self.data)

    def test_corrupt_base_and_renamed_duplicate_source_family_refuse(self):
        self.prepare_answers(); weights = self.base_run/'weights.pt'; original = weights.read_bytes()
        weights.write_bytes(original[:-1]+bytes([original[-1]^1]))
        with self.assertRaisesRegex(ValueError, 'corrupt frozen base'): D.verify(self.data)
        weights.write_bytes(original)
        request = copy.deepcopy(self.request); request['splits']['test'].append('family-a')
        C.write_json(self.root/'splits.json', request)
        with self.assertRaisesRegex(ValueError, 'crosses partitions'): D.verify(self.data)
        # Source-produced renamed question IDs are closed by G's canonical family graph.
        exercise = '<exercise id="a"><problem id="p"><para>Duplicate question?</para></problem><solution id="s"><para>2</para></solution></exercise>'
        import xml.etree.ElementTree as ET
        self.assertEqual(G.question_content(ET.fromstring(exercise)),
                         G.question_content(ET.fromstring(exercise.replace('id="a"', 'id="b"').replace('id="p"', 'id="q"').replace('id="s"', 'id="r"'))))

    def test_source_produced_renamed_duplicate_cannot_enter_separate_adapter_families(self):
        catalogue = A.read(self.archive/'catalogue.json')
        originals = {source['id']: {entry['path'].split('/source/', 1)[1]:
            C.local_path(self.archive, entry['path']).read_bytes() for entry in source['files'] if '/source/' in entry['path']}
            for source in C.verified_sources(self.archive)}
        originals['source-b']['modules/module-one/index.cnxml'] = originals['source-a']['modules/module-one/index.cnxml'].replace(
            b'id="choice"', b'id="renamed-choice"').replace(b'id="problem"', b'id="renamed-problem"').replace(
            b'id="solution"', b'id="renamed-solution"')
        revisions = {source['revision']: originals[source['id']] for source in catalogue['sources']}
        def fetch(url):
            if '/git/trees/' in url:
                revision = url.split('/git/trees/')[1].split('?')[0]
                entries = [{'path': name, 'type': 'blob', 'size': len(raw),
                    'sha': hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
                    for name, raw in revisions[revision].items()]
                return A.encoded({'sha': revision, 'truncated': False, 'tree': entries}), url
            revision = url.split('/')[5]
            return revisions[revision][url.split('/'+revision+'/', 1)[1]], url
        archive, prepared, dataset = [self.root/name for name in ('copied-archive', 'copied-prepared', 'copied-dataset')]
        with patch.object(C, 'fetch', side_effect=fetch): C.acquire(catalogue, archive)
        C.prepare(archive, prepared, 256); C.admit(archive, prepared, dataset)
        import education_training_data as canonical
        with self.assertRaisesRegex(ValueError, 'related source component crosses'):
            canonical.validated_inputs(archive, prepared, dataset, self.artifact, self.request)

    def test_zero_output_causal_padding_masks_and_actual_gradient_freeze(self):
        manifest = self.prepare_answers(); base, _, _ = T.load_base(self.data, self.config)
        model = T.make_adapter(base, self.config); torch = F.torch_owner()
        ids, target, mask = T.tensors(T.read_train(self.data), 'cpu')
        with torch.no_grad(): self.assertTrue(torch.equal(model(ids), base(ids)))
        changed = ids.clone(); changed[:,100:] = 43
        with torch.no_grad(): self.assertTrue(torch.equal(model(ids)[:,:100], model(changed)[:,:100]))
        logits = model(ids); first, _ = F.masked_loss(logits, target, mask)
        target[~mask] = 100000; second, _ = F.masked_loss(logits, target, mask)
        self.assertEqual(float(first.detach()), float(second.detach()))
        result = T.fit(self.data, self.run, self.config, manifest['contentSha256'])
        trace = A.read(self.run/'loss-trace.json')
        self.assertLess(sum(x['answerLoss'] for x in trace[-5:]), sum(x['answerLoss'] for x in trace[:5]))
        saved, _, trained, _ = T.verify_run(self.data, self.run, result['contentSha256'])
        self.assertEqual(saved['baseStateSha256'], E.state_digest(trained.base))
        self.assertTrue(all(not p.requires_grad and p.grad is None for p in trained.base.parameters()))
        self.assertTrue(all(p.dtype == torch.float32 for p in trained.adapter.parameters()))

    def test_saved_adapter_determinism_grading_tamper_and_fp32_export(self):
        manifest = self.prepare_answers(); result = T.fit(self.data, self.run, self.config, manifest['contentSha256'])
        second = self.root/'second'; repeat = T.fit(self.data, second, self.config, manifest['contentSha256'])
        self.assertEqual(result['adapterStateSha256'], repeat['adapterStateSha256'])
        settings = {**E.DEFAULT_POLICY, 'maximumItemsPerSplit': 16}
        evaluation = T.evaluate(self.data, self.run, result['contentSha256'], {'clock': 'county-tick', 'value': 0}, 'private-control', settings)
        self.assertEqual(set(evaluation['metrics']), {'savedAdapter', 'frozenBase', 'sameUntrainedSeed'})
        self.assertTrue(all(row['split'] in {'validation', 'test'} for row in evaluation['rows']))
        self.assertTrue(all(row['grade']['assessmentBankSha256'] == self.inputs['bankSha256'] for row in evaluation['rows']))
        exported = T.export(self.data, self.run, result['contentSha256'], self.root/'export')
        self.assertEqual(exported['weightBytes'], result['adapterParameters']*4)
        self.assertEqual(exported['precision'], 'FP32'); self.assertFalse(exported['runtimeIntegration'])
        torch = F.torch_owner(); state = T.adapter_state(T.verify_run(self.data, self.run, result['contentSha256'])[2])
        state['0.weight'] = state['0.weight'].double(); invalid = self.root/'invalid-state.pt'; torch.save(state, invalid)
        with self.assertRaisesRegex(ValueError, 'FP32 precision'):
            T.load_adapter(T.verify_run(self.data, self.run, result['contentSha256'])[2], invalid, C.sha(invalid.read_bytes()))
        with self.assertRaisesRegex(ValueError, 'output cannot modify'):
            T.export(self.data, self.run, result['contentSha256'], self.archive/'bad-export')
        path = self.run/'adapter.pt'; raw = path.read_bytes(); path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
        with self.assertRaisesRegex(ValueError, 'saved adapter.pt'): T.verify_run(self.data, self.run, result['contentSha256'])

    def test_output_truncation_is_unscored_and_no_partial_prompt_inference(self):
        public = G.learner_input(self.fixture.item('fraction')) if hasattr(self, 'fixture') else None
        # The actual controlled source book is MC; reuse the independently sourced numeric fixture.
        fixture = Q.EducationAssessmentTests('test_actual_producer_preserves_source_bound_bank'); fixture.setUp()
        try:
            public = G.learner_input(fixture.item('fraction')); tokenizer = B.Tokenizer(self.artifact)
            torch = F.torch_owner()
            class Repeater(torch.nn.Module):
                def __init__(self): super().__init__(); self.anchor = torch.nn.Parameter(torch.zeros(1))
                def forward(self, ids):
                    values = torch.zeros((1, ids.shape[1], B.FIRST_MERGE+len(self.artifact['merges'])))
                    values[:,:,ord('1')] = 10; return values
            repeater = Repeater(); repeater.artifact = self.artifact
            settings = {**E.DEFAULT_POLICY, 'maximumNewTokens': 2}
            generated = T.complete_inference(repeater, public, tokenizer, 256, settings)
            self.assertEqual(generated['status'], 'withheld'); self.assertEqual(generated['response'], '')
            self.assertEqual(generated['reason'], 'incomplete-output:maximum-output-tokens')
            with patch.object(repeater, 'forward', side_effect=AssertionError('no partial question')):
                overflow = T.complete_inference(repeater, public, tokenizer, 16, settings)
                self.assertEqual(overflow['reason'], 'complete-question-exceeds-context-budget')
        finally: fixture.tearDown()


if __name__ == '__main__': unittest.main()
