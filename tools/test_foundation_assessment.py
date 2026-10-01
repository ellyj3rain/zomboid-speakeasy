"""Controlled producer/inference integrity tests; fixture scores are never model ability evidence."""
import contextlib
import copy
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import byte_tokenizer as B
import decision_authoring as A
import education_assessment as G
import education_corpus as C
import foundation_assessment as E
import foundation_pretraining as F
import test_education_assessment as Q


class PublicInputTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Q.EducationAssessmentTests('test_actual_producer_preserves_source_bound_bank')
        with contextlib.redirect_stdout(io.StringIO()): self.fixture.setUp()
        self.rows = self.fixture.rows
        self.tokenizer = B.Tokenizer(B.train([b'Private training only tokenizer bytes.'], 0))

    def tearDown(self): self.fixture.tearDown()

    def item(self, identity):
        return next(row for row in self.rows if row['source']['id'] == 'controlled-assessment-a'
                    and row['exercise']['id'] == identity)

    def test_only_source_public_problem_and_instruction_reach_the_prompt(self):
        item = self.item('prose')
        public = G.learner_input(item)
        text, options = E.public_prompt(public)
        self.assertIn('Explain the reasoning.', text)
        self.assertNotIn('PRIVATE_SOURCE_SOLUTION', text)
        self.assertNotIn('prose-solution', text)
        self.assertNotIn('gradingTarget', text)
        self.assertNotIn('sourceAnswerLiteral', text)
        self.assertEqual(options, [])
        body = copy.deepcopy(public); body.pop('contentSha256')
        body['solutionXml'] = ['INVENTED_ORACLE_ANSWER']
        modified, _ = E.public_prompt(A.seal(body))
        self.assertEqual(text, modified)

    def test_mathml_structure_is_preserved_instead_of_flattened(self):
        public = G.learner_input(self.item('fraction'))
        body = copy.deepcopy(public); body.pop('contentSha256')
        input_body = copy.deepcopy(body['input']); input_body.pop('contentSha256')
        input_body['problemXml'] = ['<problem xmlns:m="http://www.w3.org/1998/Math/MathML">'
                                    '<m:math><m:msup><m:mn>2</m:mn><m:mn>3</m:mn></m:msup></m:math> metres.</problem>']
        body['input'] = A.seal(input_body)
        text, _ = E.public_prompt(A.seal(body))
        self.assertIn('msup', text)
        self.assertEqual(text.count('metres.'), 1)
        self.assertNotIn('23 metres.', text)

    def test_hidden_solution_markup_refuses_even_if_public_bytes_are_resealed(self):
        public = G.learner_input(self.item('fraction'))
        public.pop('contentSha256'); source = public['input']; source.pop('contentSha256')
        source['problemXml'] = ['<problem>Question<solution>Hidden answer</solution></problem>']
        public['input'] = A.seal(source)
        with self.assertRaisesRegex(ValueError, 'hidden answer'):
            E.public_prompt(A.seal(public))

    def test_public_choice_titles_and_tails_preserve_option_identity(self):
        node = E.ET.fromstring('<list list-type="enumerated" number-style="lower-alpha">'
                              '<title>Choices</title><item>First</item> separating text '
                              '<item>Second</item></list>')
        text = E.source_text(node)
        self.assertIn('Choices', text)
        self.assertIn('(A) First', text)
        self.assertIn('(B) Second', text)
        self.assertIn('separating text', text)
        self.assertNotIn('(A) Choices', text)

    def test_context_overflow_and_missing_media_are_explicit_and_do_not_call_model(self):
        public = G.learner_input(self.item('fraction'))
        receipt = E.inference(None, public, self.tokenizer, 16, E.DEFAULT_POLICY)
        self.assertEqual(receipt['response'], '')
        self.assertEqual(receipt['status'], 'withheld')
        self.assertGreater(receipt['coverage']['contextOverflowTokens'], 0)
        self.assertEqual(receipt['coverage']['truncatedTokens'], 0)
        self.assertEqual(receipt['coverage']['inputTokens'], 0)
        self.assertEqual(receipt['inputTokenIds'], [])
        public.pop('contentSha256'); source = public['input']; source.pop('contentSha256')
        source['coverage']['mediaReferencesPresent'] = True
        public['input'] = A.seal(source)
        receipt = E.inference(None, A.seal(public), self.tokenizer, 1024, E.DEFAULT_POLICY)
        self.assertEqual(receipt['reason'], 'required-source-media-not-provided')
        self.assertIsNone(receipt['modelConfidence'])

    def test_true_zero_and_unknown_coverage_do_not_become_accuracy_or_mastery(self):
        result = E.statistics([])
        self.assertIsNone(result['accuracyOnScoredResponses'])
        self.assertIsNone(result['correctFractionOfSelectedSupportedTargets'])
        self.assertEqual(result['coverageStanding'], 'no-supported-targets')
        result = E.statistics([{'generation': {'status': 'generated'}, 'grade': {'status': 'unrecognized-response'}}])
        self.assertEqual(result['unscored'], 1)
        self.assertEqual(result['incorrect'], 0)
        self.assertIsNone(result['accuracyOnScoredResponses'])

    def test_training_source_evaluation_and_unbounded_generation_refuse(self):
        for field, value in [('evaluationSplits', ['train']), ('maximumNewTokens', 10000),
                             ('contextOverflow', 'silently-truncate')]:
            settings = {**E.DEFAULT_POLICY, field: value}
            with self.assertRaises(ValueError): E.policy(settings)

    def test_bounded_selection_preserves_source_families(self):
        rows = [{'familyId': 'a', 'contentSha256': str(n)} for n in range(10)]
        rows += [{'familyId': 'b', 'contentSha256': str(n)} for n in range(3)]
        selected = E.select_families(rows, 4)
        self.assertEqual([r['familyId'] for r in selected], ['a', 'b', 'a', 'b'])
        with self.assertRaisesRegex(ValueError, 'supported source families'): E.select_families(rows, 1)


@unittest.skipUnless(importlib.util.find_spec('torch'), 'Run actual model controls in isolated PyTorch environment')
class SavedModelControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.archive, self.prepared, self.dataset = [self.root / name for name in ('archive', 'prepared', 'dataset')]
        self.data, self.run, self.bank = [self.root / name for name in ('data', 'run', 'bank')]
        bodies = {1: 'Timber shelters hold beams above dry earth. A roof keeps the rain outside.\n' * 12,
                  2: 'Ocean currents flow around coastal harbours. Salt water carries drifting boats.\n' * 12,
                  3: 'Bird feathers provide insulation while wings propel flight. Nests hold small eggs.\n' * 12}
        catalogue = {'schema': 'speakeasy-education-source-catalogue/1', 'standing': 'candidate-sources',
                     'sources': [{'id': 'book-' + str(n), 'provider': 'gutenberg', 'bookId': n,
                                  'stages': ['primary'], 'subjects': ['mathematics']} for n in (1, 2, 3)] +
                     [{'id': 'controlled-assessment-' + name, 'provider': 'openstax-github',
                       'repository': 'openstax/controlled-' + name, 'revision': name * 40,
                       'stages': ['primary'], 'subjects': ['mathematics']} for name in ('a', 'b')]}
        files = {'LICENSE': b'Attribution 4.0 International\nControlled fixture license.',
                 'modules/module-one/index.cnxml': Q.MODULE}
        entries = [{'path': path, 'type': 'blob', 'size': len(raw),
                    'sha': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()}
                   for path, raw in files.items()]
        def fetch(url):
            if '/git/trees/' in url:
                revision = url.split('/git/trees/')[1].split('?')[0]
                return A.encoded({'sha': revision, 'truncated': False, 'tree': entries}), url
            for path, raw in files.items():
                if url.endswith('/' + path): return raw, url
            n = int(url.rstrip('/').split('/')[-1].split('.')[0])
            if '/ebooks/' in url:
                return (f'<title>Control {n}</title>Public domain in the USA '
                        f'<a href="/files/{n}/{n}.txt" type="text/plain">Text</a>').encode(), url
            return ('*** START OF THE PROJECT GUTENBERG EBOOK CONTROL ***\n' + bodies[n]
                    + '\n*** END OF THE PROJECT GUTENBERG EBOOK CONTROL ***').encode(), url
        with patch.object(C, 'fetch', side_effect=fetch), contextlib.redirect_stdout(io.StringIO()):
            C.acquire(catalogue, self.archive); C.prepare(self.archive, self.prepared, 256)
            C.admit(self.archive, self.prepared, self.dataset)
        rows = [A.loads(line) for line in (self.dataset / 'texts.jsonl').read_text(encoding='utf-8').splitlines()]
        self.artifact = B.train([row['text'].encode() for row in rows if row['sourceId'] == 'book-1'], 8)
        self.request = {'schema': 'speakeasy-educational-source-splits', 'schemaVersion': 1,
                        'sourceFamilies': [{'id': 'family-' + str(n), 'sourceIds': ['book-' + str(n)]} for n in (1, 2, 3)] +
                                          [{'id': 'shared-assessment-source', 'sourceIds': ['controlled-assessment-a', 'controlled-assessment-b']}],
                        'splits': {'train': ['family-1'], 'validation': ['family-2', 'shared-assessment-source'], 'test': ['family-3']}}
        self.config = {**F.DEFAULT_CONFIG, 'layers': 1, 'hidden': 16, 'heads': 2, 'batch': 2,
                       'steps': 2, 'learningRate': 0.001, 'evaluationBatches': 4}
        with contextlib.redirect_stdout(io.StringIO()):
            self.data_manifest = F.prepare_data(*self.common(), self.data, sequence_length=256)
            self.saved = F.train(*self.common(), self.data, self.config, self.run)
            self.bank_manifest = G.build_bank(self.archive, self.bank, split_policy=self.request)
        self.settings = {**E.DEFAULT_POLICY, 'maximumNewTokens': 4}
        self.time = {'clock': 'utc', 'value': '2026-10-01T00:00:00Z'}

    def tearDown(self): self.temp.cleanup()

    def common(self): return self.archive, self.prepared, self.dataset, self.artifact, self.request

    def evaluate(self, **kwargs):
        return E.evaluate(*self.common(), self.data, self.run, self.bank,
                          kwargs.pop('run_sha', self.saved['contentSha256']),
                          kwargs.pop('bank_sha', self.bank_manifest['contentSha256']), self.time,
                          'controlled-model-integrity-test-not-ability', kwargs.pop('settings', self.settings), **kwargs)

    def test_actual_saved_weights_seed_and_grader_pipeline_preserve_zero_supported_test(self):
        result = self.evaluate()
        self.assertEqual(result['runSha256'], self.saved['contentSha256'])
        self.assertNotEqual(result['savedStateSha256'], result['untrainedStateSha256'])
        self.assertEqual(result['sourceCoverage']['test']['supportedTargets'], 0)
        for name in ('savedWeights', 'sameUntrainedSeed'):
            self.assertEqual(result['metrics'][name]['test']['coverageStanding'], 'no-supported-targets')
            self.assertIsNone(result['metrics'][name]['test']['accuracyOnScoredResponses'])
        self.assertTrue(result['rows'])
        for row in result['rows']:
            self.assertEqual(row['response']['learner']['kind'], 'model')
            self.assertEqual(row['response']['learningMode'], 'independent-retrieval')
            self.assertEqual(row['generation']['modelEvidence']['learner'], row['response']['learner'])
            self.assertEqual(row['generation']['modelEvidence']['comparisonRunSha256'], self.saved['contentSha256'])
            self.assertNotIn('PRIVATE_SOURCE_SOLUTION', row['generation']['prompt'])
            self.assertEqual(row['grade']['responseSha256'], A.digest(row['response']))
            self.assertFalse(row['grade']['independentMasteryAuthority'])
        for key in E.AUTHORITY: self.assertFalse(result[key])

    def test_same_initial_seed_and_outputs_replay_deterministically_without_training(self):
        before = C.sha((self.run / 'weights.pt').read_bytes())
        first, second = self.evaluate(), self.evaluate()
        self.assertEqual(first, second)
        self.assertEqual(C.sha((self.run / 'weights.pt').read_bytes()), before)

    def test_changed_saved_weights_refuse_before_benchmark_results(self):
        path = self.run / 'weights.pt'; path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'saved weights differ'): self.evaluate()

    def test_changed_training_data_refuses_even_when_binary_hash_is_resealed(self):
        path = self.data / 'train.bin'; raw = bytearray(path.read_bytes()); raw[0] ^= 1; path.write_bytes(raw)
        value = A.read(self.data / 'manifest.json'); value.pop('contentSha256')
        value['partitions']['train']['binarySha256'] = C.sha(raw)
        C.write_json(self.data / 'manifest.json', A.seal(value))
        with self.assertRaisesRegex(ValueError, 'tokens or provenance differ'): self.evaluate()

    def test_changed_bank_refuses_even_after_row_hashes_are_resealed(self):
        path = self.bank / 'assessments.jsonl'
        rows = [A.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        body = copy.deepcopy(rows[0]); body.pop('contentSha256'); body['solutionXml'] = ['Invented answer']
        rows[0] = A.seal(body); path.write_bytes(G.serialized(rows))
        manifest = A.read(self.bank / 'manifest.json'); manifest.pop('contentSha256')
        manifest['assessmentsSha256'] = C.sha(path.read_bytes()); C.write_json(self.bank / 'manifest.json', A.seal(manifest))
        with self.assertRaisesRegex(ValueError, 'source reconstruction'): self.evaluate()

    def test_trusted_run_and_bank_identity_cannot_be_changed(self):
        with self.assertRaisesRegex(ValueError, 'run identity differs'): self.evaluate(run_sha='0' * 64)
        with self.assertRaisesRegex(ValueError, 'bank identity differs'): self.evaluate(bank_sha='0' * 64)

    def test_empty_supported_split_still_requires_valid_evaluation_attribution(self):
        self.time = {'clock': 'utc', 'value': 'invented-time'}
        with self.assertRaises(ValueError):
            self.evaluate(settings={**self.settings, 'evaluationSplits': ['test']})

    def test_runtime_receiver_sees_only_public_choice_candidates(self):
        _, items = G.validate_bank(self.archive, self.bank)
        item = next(item for item in items if item['exercise']['id'] == 'choice')
        public = G.learner_input(item)
        _, options = E.public_prompt(public)
        self.assertEqual([option['key'] for option in options], ['A', 'B'])
        self.assertIn('(A) First option', E.public_prompt(public)[0])
        self.assertIn('(B) Second option', E.public_prompt(public)[0])
        model = F.make_model(self.config, B.FIRST_MERGE + len(self.artifact['merges']), 256)
        result = E.inference(model, public, B.Tokenizer(self.artifact), 256, self.settings)
        self.assertEqual(result['reason'], 'public-choice-scoring')
        self.assertIn(result['response'], ['A', 'B'])
        self.assertGreaterEqual(result['modelConfidence'], 0)
        self.assertLessEqual(result['modelConfidence'], 1)
        self.assertTrue(all(set(candidate) == {'key', 'tokenIds', 'logLikelihood'} for candidate in result['candidateScores']))


if __name__ == '__main__': unittest.main()
