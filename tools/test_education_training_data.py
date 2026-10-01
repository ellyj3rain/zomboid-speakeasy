"""Educational sequence release binds actual admitted bytes and a frozen tokenizer."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import byte_tokenizer as B
import decision_authoring as A
import education_corpus as C
import education_training_data as D
import training_evidence as E


class EducationTrainingDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.archive = self.root / 'archive'; self.prepared = self.root / 'prepared'
        self.dataset = self.root / 'dataset'; self.output = self.root / 'tokenized'
        self.evidence = self.root / 'evidence'; self.evidence.mkdir()
        self.store = E.Store(self.evidence)
        self.bodies = {i: (f'Source {i}. Zoë 李 🙂 e\u0301 é x² + ∑ Δ. <bos><eos><pad>\n'
                           f'Exercise {i}: count {i} objects.\n') * 7 for i in (1, 2, 3)}
        def fetch(url):
            identity = int(url.rstrip('/').split('/')[-1].split('.')[0])
            if '/ebooks/' in url:
                return (f'<title>Controlled text {identity}</title>Public domain in the USA '
                        f'<a href="/files/{identity}/{identity}.txt" type="text/plain">Text</a>').encode(), url
            return ('*** START OF THE PROJECT GUTENBERG EBOOK CONTROL ***\n'
                    + self.bodies[identity] + '\n*** END OF THE PROJECT GUTENBERG EBOOK CONTROL ***').encode(), url
        catalogue = {'schema': 'speakeasy-education-source-catalogue/1', 'standing': 'candidate-sources',
                     'sources': [{'id': f'book-{i}', 'provider': 'gutenberg', 'bookId': i,
                                  'stages': ['primary'], 'subjects': ['mathematics']} for i in (1, 2, 3)]}
        with patch.object(C, 'fetch', side_effect=fetch):
            C.acquire(catalogue, self.archive)
        self.proposal = C.prepare(self.archive, self.prepared, 256)
        self.approval = self.ruling(self.proposal['contentSha256'])
        C.admit(self.archive, self.prepared, self.dataset, self.approval, self.store)
        self.rows = [A.loads(line) for line in (self.dataset / 'texts.jsonl').read_text(encoding='utf-8').splitlines()]
        self.artifact = B.train([r['text'].encode() for r in self.rows if r['sourceId'] == 'book-1'], 8)
        self.request = {'schema': 'speakeasy-educational-source-splits', 'schemaVersion': 1,
                        'sourceFamilies': [{'id': f'family-{i}', 'sourceIds': [f'book-{i}']} for i in (1, 2, 3)],
                        'splits': {'train': ['family-1'], 'validation': ['family-2'], 'test': ['family-3']}}

    def tearDown(self):
        self.tmp.cleanup()

    def ruling(self, subject):
        lineage = {'evidenceRef': 'speakeasy:content-sha256:' + subject}
        value = {'schema': 'mousecat.skill-invocation/2', 'action': 'await', 'skillRef': 'crucible',
                 'status': 'answered', 'interactionId': 'controlled-educational-review',
                 'items': [{'id': 'controlled-item', 'shape': 'decision', 'lineage': lineage}],
                 'responses': [{'itemId': 'controlled-item', 'shape': 'decision', 'status': 'answered',
                                'value': 'approved', 'selectedOption': 'approved',
                                'selectedOptions': ['approved'], 'lineage': lineage, 'notes': None}]}
        digest = A.digest(value); C.write_json(self.evidence / (digest + '.json'), value)
        return digest

    def export(self, output=None, **kwargs):
        return D.export(self.archive, self.prepared, self.dataset, self.artifact, self.request,
                        output or self.output, block_tokens=32, store=self.store, **kwargs)

    def verify(self, **kwargs):
        return D.verify(self.archive, self.prepared, self.dataset, self.artifact, self.request,
                        self.output, store=self.store, **kwargs)

    def blocks(self, partition='train'):
        return [A.loads(line) for line in (self.output / (partition + '.jsonl')).read_text().splitlines()]

    def test_actual_approved_passages_export_and_reconstruct(self):
        result = self.export(require_ready=True)
        self.assertEqual(result['release']['status'], 'ready-for-reference-training')
        self.assertEqual(self.verify(require_ready=True), result)
        self.assertFalse(result['trainedWeights']); self.assertFalse(result['runtimeIntegration'])
        self.assertFalse(result['personalAcquisitionAuthority']); self.assertFalse(result['currentWorldAuthority'])
        self.assertFalse(result['nativeActionAuthority']); self.assertTrue(result['opposingAssociativeModelIndependent'])
        self.assertEqual(result['task'], 'shared-cognitive-base')

    def test_automatically_evaluated_sources_export_without_manual_ruling(self):
        self.dataset=self.root/'automatic-dataset'
        admission=C.admit(self.archive,self.prepared,self.dataset)
        with patch.object(E.Store,'decision',side_effect=AssertionError('unwanted academic review gate')):
            result=self.export(require_ready=True)
            self.assertEqual(self.verify(require_ready=True),result)
        self.assertEqual(result['sourceAdmissionKind'],'automated-prerequisite-material')
        self.assertEqual(result['sourceEvaluationReceiptSha256'],admission['evaluationReceiptSha256'])
        self.assertIsNone(result['approvalReceiptSha256'])

    def test_exact_next_token_shift_masks_and_lossless_unicode_reconstruction(self):
        self.export()
        tokenizer = B.Tokenizer(self.artifact)
        for row in self.rows:
            partition = {'book-1': 'train', 'book-2': 'validation', 'book-3': 'test'}[row['sourceId']]
            blocks = [b for b in self.blocks(partition) if b['rowSha256'] == row['contentSha256']]
            inputs = [i for b in blocks for i, mask in zip(b['inputIds'], b['lossMask']) if mask]
            targets = [i for b in blocks for i, mask in zip(b['targetIds'], b['lossMask']) if mask]
            payload = tokenizer.encode_text(row['text'])
            self.assertEqual(inputs, [B.SPECIAL_IDS['bos'], *payload])
            self.assertEqual(targets, [*payload, B.SPECIAL_IDS['eos']])
            self.assertEqual(tokenizer.decode_bytes(inputs[1:]), row['text'].encode())
            self.assertEqual(sum(sum(b['lossMask']) for b in blocks), len(payload) + 1)
            for block in blocks:
                self.assertEqual(len(block['inputIds']), 32); self.assertEqual(len(block['targetIds']), 32)
                self.assertTrue(all(i == B.SPECIAL_IDS['pad'] for i, m in zip(block['targetIds'], block['lossMask']) if not m))

    def test_literal_structural_strings_cannot_inject_reserved_tokens(self):
        self.export()
        for block in self.blocks():
            real = [v for v, mask in zip(block['targetIds'], block['lossMask']) if mask]
            self.assertFalse(set(real) & (set(B.SPECIAL_IDS.values()) - {B.SPECIAL_IDS['eos']}))

    def test_deterministic_ordering_and_saved_frozen_artifact(self):
        first = self.export(); original = (self.output / 'train.jsonl').read_bytes()
        self.request['sourceFamilies'].reverse()
        second_path = self.root / 'second'
        second = self.export(second_path)
        self.assertEqual(first, second); self.assertEqual(original, (second_path / 'train.jsonl').read_bytes())
        self.assertEqual((self.output / 'tokenizer.json').read_bytes(), A.encoded(self.artifact) + b'\n')

    def test_export_never_refits_tokenizer_on_any_partition(self):
        before = A.encoded(self.artifact)
        with patch.object(B, 'train', side_effect=AssertionError('export must not fit')):
            self.export()
        self.assertEqual(A.encoded(self.artifact), before)

    def test_known_validation_text_in_tokenizer_fitting_corpus_refuses(self):
        self.artifact = B.train([r['text'].encode() for r in self.rows if r['sourceId'] == 'book-2'], 4)
        with self.assertRaisesRegex(ValueError, 'held-out educational text'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_known_full_held_out_book_in_tokenizer_fitting_corpus_refuses(self):
        self.artifact = B.train([(self.archive / 'book-2/source.txt').read_bytes()], 4)
        with self.assertRaisesRegex(ValueError, 'held-out educational text'):
            self.export()

    def test_missing_actual_approval_refuses(self):
        (self.evidence / (self.approval + '.json')).unlink()
        with self.assertRaisesRegex(ValueError, 'missing evidence'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_wrong_exact_approval_refuses(self):
        value = A.read(self.dataset / 'manifest.json')
        value['approvalReceiptSha256'] = self.ruling('0' * 64)
        C.write_json(self.dataset / 'manifest.json', value)
        with self.assertRaisesRegex(ValueError, 'exact subject'):
            self.export()

    def test_unadmitted_preparation_refuses(self):
        with self.assertRaises(OSError):
            D.export(self.archive, self.prepared, self.prepared, self.artifact, self.request,
                     self.output, store=self.store)
        self.assertFalse(self.output.exists())

    def test_changed_source_and_dataset_bytes_refuse(self):
        path = self.archive / 'book-1/source.txt'
        path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'protected educational source changed'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_changed_admitted_dataset_refuses(self):
        with (self.dataset / 'texts.jsonl').open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'admitted educational texts differ'):
            self.export()

    def test_family_cross_partition_and_source_multiple_families_refuse(self):
        self.request['splits']['test'].append('family-1')
        with self.assertRaisesRegex(ValueError, 'crosses partitions'):
            self.export()
        self.request['splits']['test'].remove('family-1')
        self.request['sourceFamilies'][1]['sourceIds'].append('book-1')
        with self.assertRaisesRegex(ValueError, 'multiple families'):
            self.export()

    def test_shared_module_and_duplicate_passages_refuse_false_family_independence(self):
        rows = copy.deepcopy(self.rows)
        rows[-1]['extractionSha256'] = rows[0]['extractionSha256']
        sources = A.read(self.archive / 'acquisition.json')['sources']
        with self.assertRaisesRegex(ValueError, 'shared source module'):
            D.partition_plan(self.request, sources, rows)
        rows = copy.deepcopy(self.rows); rows[-1]['text'] = rows[0]['text']
        with self.assertRaisesRegex(ValueError, 'duplicate educational passage'):
            D.partition_plan(self.request, sources, rows)

    def test_same_publisher_book_lineage_must_share_family(self):
        sources = A.read(self.archive / 'acquisition.json')['sources']
        sources[1]['bookId'] = sources[0]['bookId']
        with self.assertRaisesRegex(ValueError, 'same book lineage'):
            D.partition_plan(self.request, sources, self.rows)

    def test_missing_partition_is_saved_unreleased_and_release_refuses(self):
        self.request['splits']['train'].append('family-3'); self.request['splits']['test'] = []
        result = self.export()
        self.assertEqual(result['release'], {'status': 'excluded', 'missingPartitions': ['test']})
        self.assertEqual(self.verify(), result)
        with self.assertRaisesRegex(ValueError, 'missing partitions test'):
            self.verify(require_ready=True)

    def test_require_ready_refuses_incomplete_partitions_before_output(self):
        self.request['splits']['train'].append('family-3'); self.request['splits']['test'] = []
        with self.assertRaisesRegex(ValueError, 'missing partitions'):
            self.export(require_ready=True)
        self.assertFalse(self.output.exists())

    def test_corrupted_tokens_rehashed_manifest_still_refuse_reconstruction(self):
        self.export(); path = self.output / 'train.jsonl'
        rows = [A.loads(line) for line in path.read_text().splitlines()]
        block = rows[0]; block.pop('contentSha256'); block['targetIds'][0] = 42; rows[0] = A.seal(block)
        data = b''.join(A.encoded(b) + b'\n' for b in rows); path.write_bytes(data)
        saved = A.read(self.output / 'manifest.json'); saved.pop('contentSha256')
        saved['partitions']['train']['sha256'] = C.sha(data)
        C.write_json(self.output / 'manifest.json', A.seal(saved))
        with self.assertRaisesRegex(ValueError, 'tokens or provenance differ'):
            self.verify()

    def test_corrupted_loss_mask_offsets_or_extra_blocks_refuse(self):
        self.export(); path = self.output / 'validation.jsonl'
        rows = [A.loads(line) for line in path.read_text().splitlines()]
        rows[0]['lossMask'][0] = False; rows[0]['rowByteEnd'] += 1
        path.write_bytes(b''.join(A.encoded(b) + b'\n' for b in rows))
        with self.assertRaisesRegex(ValueError, 'tokens or provenance differ'):
            self.verify()

    def test_unknown_extra_output_file_and_changed_saved_tokenizer_refuse(self):
        self.export(); extra = self.output / 'extra.json'; extra.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'file inventory'):
            self.verify()
        extra.unlink(); (self.output / 'tokenizer.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'saved frozen tokenizer differs'):
            self.verify()

    def test_token_bound_failure_leaves_excluded_manifest(self):
        with self.assertRaisesRegex(ValueError, 'declared total token bound'):
            self.export(max_tokens=10)
        saved = A.read(self.output / 'manifest.json')
        self.assertEqual(saved['release']['status'], 'excluded')

    def test_saved_reconstruction_failure_never_marks_release_ready(self):
        real = D.reconstructed
        def corrupt_after_write(*args, **kwargs):
            result = real(*args, **kwargs)
            if not kwargs.get('checking', False):
                with (self.output / 'train.jsonl').open('ab') as stream:
                    stream.write(b'changed')
            return result
        with patch.object(D, 'reconstructed', side_effect=corrupt_after_write):
            with self.assertRaisesRegex(ValueError, 'extra saved'):
                self.export()
        self.assertEqual(A.read(self.output / 'manifest.json')['release']['status'], 'excluded')

    def test_cli_export_and_verify_use_actual_approval_owner_and_frozen_artifact(self):
        tokenizer_path = self.root / 'frozen.json'; request_path = self.root / 'splits.json'
        C.write_json(tokenizer_path, self.artifact); C.write_json(request_path, self.request)
        options = ['--archive', str(self.archive), '--prepared', str(self.prepared),
                   '--dataset', str(self.dataset), '--tokenizer', str(tokenizer_path),
                   '--splits', str(request_path), '--output', str(self.output), '--require-ready']
        # Only the owner location points to this private fixture; its real decision
        # parser and exact reviewed-subject checks run unchanged.
        with patch.object(C.E, 'Store', return_value=self.store):
            self.assertEqual(D.main(['export', *options, '--block-tokens', '32']), 0)
            self.assertEqual(D.main(['verify', *options]), 0)


class EducationalFamilyClosureTests(unittest.TestCase):
    def test_training_refuses_renamed_question_answer_copy_in_another_family(self):
        import xml.etree.ElementTree as ET
        import test_education_assessment as source_fixture

        fixture = source_fixture.EducationAssessmentTests(methodName='runTest')
        fixture.setUp()
        try:
            original = 'controlled-assessment-a'
            renamed = 'controlled-assessment-b'
            third = copy.deepcopy(fixture.catalogue['sources'][0])
            third.update(id='independent-validation', repository='openstax/independent-validation', revision='c' * 40)
            fixture.catalogue['sources'].append(third)
            copied = ET.fromstring(source_fixture.MODULE)
            for element in copied.iter():
                if 'id' in element.attrib:
                    element.set('id', 'renamed-' + element.get('id'))
            independent = (b'<document xmlns="http://cnx.rice.edu/cnxml"><content><exercise id="independent">'
                           b'<problem id="independent-problem"><para>What is nine plus ten?</para></problem>'
                           b'<solution id="independent-solution"><para>19</para></solution>'
                           b'</exercise></content></document>')
            archive, prepared, dataset = (fixture.root / name for name in ('training-archive', 'prepared', 'dataset'))
            fixture.acquire_related(archive, {original: source_fixture.MODULE,
                                             renamed: ET.tostring(copied, encoding='utf-8'), third['id']: independent})
            C.prepare(archive, prepared, 16384)
            C.admit(archive, prepared, dataset)
            tokenizer = B.train([b'Private independent tokenizer fixture.'], 0)
            request = {'schema': 'speakeasy-educational-source-splits', 'schemaVersion': 1,
                       'sourceFamilies': [{'id': 'original', 'sourceIds': [original]},
                                          {'id': 'renamed', 'sourceIds': [renamed]},
                                          {'id': 'independent', 'sourceIds': [third['id']]}],
                       'splits': {'train': ['renamed'], 'validation': ['independent'], 'test': ['original']}}
            with self.assertRaisesRegex(ValueError, 'related source component crosses caller source families'):
                D.validated_inputs(archive, prepared, dataset, tokenizer, request)
            joined = {'schema': request['schema'], 'schemaVersion': 1,
                      'sourceFamilies': [{'id': 'related', 'sourceIds': [original, renamed]},
                                         {'id': 'independent', 'sourceIds': [third['id']]}],
                      'splits': {'train': ['related'], 'validation': ['independent'], 'test': []}}
            actual = D.validated_inputs(archive, prepared, dataset, tokenizer, joined)
            self.assertEqual(actual[4][original], actual[4][renamed])
            self.assertNotEqual(actual[4][original], actual[4][third['id']])
        finally:
            fixture.tearDown()


if __name__ == '__main__':
    unittest.main()
