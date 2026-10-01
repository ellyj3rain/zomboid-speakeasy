"""Private automatic source fixtures and small actual gradient-learning references."""
import array
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import byte_tokenizer as B
import decision_authoring as A
import education_corpus as C
import education_training_data as D
import foundation_pretraining as F


class Fixture:
    book_count = 3
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.archive = self.root/'archive'; self.prepared = self.root/'prepared'
        self.dataset = self.root/'dataset'; self.data = self.root/'tokens'; self.run = self.root/'run'
        books = range(1, self.book_count+1)
        self.bodies = {i: (f'Book {i}: abc abc abc. Count one two three. x² + Δ. Zoë 李 🙂.\n')*12 for i in books}
        def fetch(url):
            n = int(url.rstrip('/').split('/')[-1].split('.')[0])
            if '/ebooks/' in url:
                return (f'<title>Fixture {n}</title>Public domain in the USA '
                        f'<a href="/files/{n}/{n}.txt" type="text/plain">Text</a>').encode(), url
            return ('*** START OF THE PROJECT GUTENBERG EBOOK CONTROL ***\n'+self.bodies[n]
                    +'\n*** END OF THE PROJECT GUTENBERG EBOOK CONTROL ***').encode(), url
        catalogue = {'schema': 'speakeasy-education-source-catalogue/1', 'standing': 'candidate-sources',
                     'sources': [{'id': f'book-{n}', 'provider': 'gutenberg', 'bookId': n,
                                  'stages': ['primary'], 'subjects': ['mathematics']} for n in books]}
        with patch.object(C, 'fetch', side_effect=fetch): C.acquire(catalogue, self.archive)
        C.prepare(self.archive, self.prepared, 256)
        self.admitted = C.admit(self.archive, self.prepared, self.dataset)
        self.artifact = B.train([b'Private frozen training-family tokenizer fitting fixture.'], 4)
        self.request = {'schema': 'speakeasy-educational-source-splits', 'schemaVersion': 1,
                        'sourceFamilies': [{'id': f'family-{n}', 'sourceIds': [f'book-{n}']} for n in books],
                        'splits': {'train': ['family-1'], 'validation': [f'family-{n}' for n in range(2,self.book_count)],
                                   'test': [f'family-{self.book_count}']}}
        self.config = {**F.DEFAULT_CONFIG, 'layers': 1, 'hidden': 32, 'heads': 2, 'batch': 4,
                       'steps': 20, 'learningRate': 0.005, 'evaluationBatches': 4}

    def tearDown(self): self.temp.cleanup()

    def common(self): return self.archive, self.prepared, self.dataset, self.artifact, self.request

    def prepare_tokens(self): return F.prepare_data(*self.common(), self.data, sequence_length=16)

    def fit(self, run=None): return F.train(*self.common(), self.data, self.config, run or self.run)

    def evaluate(self, run=None, digest=None): return F.evaluate(*self.common(), self.data, run or self.run, digest)

    def reseal_run(self, value):
        value.pop('contentSha256', None); C.write_json(self.run/'manifest.json', A.seal(value))


class FoundationDataTests(Fixture, unittest.TestCase):
    def test_import_and_prepare_require_no_torch_or_manual_review(self):
        code = "import sys;sys.modules['torch']=None;import foundation_pretraining;print('lazy-import-ok')"
        process = subprocess.run([sys.executable, '-c', code], cwd=Path(F.__file__).parent,
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        with patch.object(B, 'train', side_effect=AssertionError('no refitting')):
            manifest = self.prepare_tokens()
        self.assertEqual(manifest['sourceEvaluationReceiptSha256'], self.admitted['evaluationReceiptSha256'])
        self.assertFalse(manifest['runtimeIntegration']); self.assertFalse(manifest['personKnowledgeAuthority'])
        self.assertEqual(F.verify_data(*self.common(), self.data), manifest)

    def test_binary_reconstructs_exact_owner_shift_masks_unicode_and_provenance(self):
        manifest = self.prepare_tokens()
        inputs = D.validated_inputs(*self.common())
        handles = {p: (self.data/(p+'.bin')).open('rb') for p in D.PARTITIONS}
        try:
            for p, block in D.sequence_blocks(inputs[1], inputs[2], inputs[4], inputs[5], 16, 100_000_000):
                self.assertEqual(handles[p].read(80), F.token_bytes(block))
                self.assertTrue(block['sourceFamilyId'].startswith('family-'))
            self.assertTrue(all(not h.read(1) for h in handles.values()))
        finally:
            for h in handles.values(): h.close()
        self.assertEqual((self.data/'tokenizer.json').read_bytes(), A.encoded(self.artifact)+b'\n')
        self.assertEqual(manifest['sequenceLength'], 16)

    def test_deterministic_binary_and_provenance(self):
        first = self.prepare_tokens(); second = self.root/'second'
        self.request['sourceFamilies'].reverse()
        result = F.prepare_data(*self.common(), second, 16)
        self.assertEqual(result, first)
        for p in D.PARTITIONS:
            for suffix in ('.bin', '.provenance.jsonl'):
                self.assertEqual((self.data/(p+suffix)).read_bytes(), (second/(p+suffix)).read_bytes())

    def test_binary_and_rehashed_manifest_corruption_refuse(self):
        manifest = self.prepare_tokens(); path = self.data/'train.bin'
        raw = bytearray(path.read_bytes()); raw[0] ^= 1; path.write_bytes(raw)
        manifest['partitions']['train']['binarySha256'] = C.sha(raw)
        manifest.pop('contentSha256'); C.write_json(self.data/'manifest.json', A.seal(manifest))
        with self.assertRaisesRegex(ValueError, 'tokens or provenance differ'): F.verify_data(*self.common(), self.data)

    def test_changed_source_or_admitted_bytes_refuse(self):
        self.prepare_tokens(); path = self.dataset/'texts.jsonl'; path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError, 'admitted educational texts'): F.verify_data(*self.common(), self.data)

    def test_missing_partition_stays_incomplete(self):
        self.request['splits']['validation'].append('family-3'); self.request['splits']['test'] = []
        with self.assertRaisesRegex(ValueError, 'requires train, validation and test'): self.prepare_tokens()
        self.assertEqual(A.read(self.data/'manifest.json')['release'], 'excluded')

    def test_held_out_tokenizer_fitting_and_family_contradiction_refuse(self):
        rows = [A.loads(v) for v in (self.dataset/'texts.jsonl').read_text(encoding='utf-8').splitlines()]
        self.artifact = B.train([next(r['text'].encode() for r in rows if r['sourceId']=='book-2')], 4)
        with self.assertRaisesRegex(ValueError, 'held-out educational text'): self.prepare_tokens()
        self.artifact = B.train([b'Private training text.'], 4)
        self.request['splits']['test'].append('family-1')
        with self.assertRaisesRegex(ValueError, 'crosses partitions'): self.prepare_tokens()

    def test_run_config_bounds_and_old_output_preservation(self):
        for key, value in [('hidden', 33), ('heads', 0), ('steps', True), ('device', 'auto'), ('learningRate', float('nan'))]:
            with self.assertRaises(ValueError): F.validate_config({**self.config, key: value})
        self.prepare_tokens()
        with self.assertRaisesRegex(ValueError, 'preserve existing'): self.prepare_tokens()


@unittest.skipUnless(importlib.util.find_spec('torch'), 'PyTorch tests run in the isolated pretraining environment')
class FoundationModelTests(Fixture, unittest.TestCase):
    def model(self): return F.make_model(self.config, B.FIRST_MERGE+len(self.artifact['merges']), 16)

    def test_causal_mask_future_tokens_cannot_change_past_logits(self):
        torch = F.torch_owner(); model = self.model(); model.eval()
        x = torch.arange(16).reshape(1,16); changed = x.clone(); changed[:,8:] += 30
        with torch.no_grad(): first = model(x); second = model(changed)
        torch.testing.assert_close(first[:,:8], second[:,:8], rtol=0, atol=0)
        self.assertFalse(torch.equal(first[:,8:], second[:,8:]))
        self.assertTrue(all(p.dtype == torch.float32 for p in model.parameters()))

    def test_padding_has_no_loss_and_all_masked_batch_refuses(self):
        torch = F.torch_owner(); logits = torch.randn(2,16,300); target = torch.zeros((2,16), dtype=torch.long)
        mask = torch.zeros((2,16), dtype=torch.bool); mask[:,:7] = True
        first, count = F.masked_loss(logits,target,mask); target[:,7:] = 10000
        second, count2 = F.masked_loss(logits,target,mask)
        self.assertEqual(float(first), float(second)); self.assertEqual(count,count2); self.assertEqual(count,14)
        with self.assertRaisesRegex(ValueError,'no real next-token'): F.masked_loss(logits,target,torch.zeros_like(mask))

    def test_actual_gradient_learning_saved_weights_and_seed_negative_control(self):
        self.prepare_tokens(); result = self.fit()
        trace = A.read(self.run/'loss-trace.json')
        self.assertLess(sum(t['loss'] for t in trace[-3:])/3, sum(t['loss'] for t in trace[:3])/3)
        for p in ('validation','test'):
            self.assertLess(result['savedWeightMetrics'][p]['nextTokenLoss'], result['untrainedSeedMetrics'][p]['nextTokenLoss'])
            self.assertGreater(result['savedWeightMetrics'][p]['evaluatedLossTokens'],0)
        checked, model = self.evaluate(digest=result['contentSha256'])
        self.assertEqual(result, checked); self.assertGreater(result['trainingLossTokens'],0)
        initial = self.model(); self.assertTrue(any(not F.torch_owner().equal(a,b) for a,b in zip(model.parameters(),initial.parameters())))
        self.assertEqual(result['precision'],'FP32'); self.assertFalse(result['nativeConsumerParity'])

    def test_training_is_deterministic_without_tokenizer_refitting(self):
        self.prepare_tokens(); self.config['steps'] = 4
        with patch.object(B,'train',side_effect=AssertionError('no fitting held-out data')):
            first = self.fit(); second = self.fit(self.root/'other-run')
        self.assertEqual(first['savedWeightMetrics'], second['savedWeightMetrics'])
        self.assertEqual(A.read(self.run/'loss-trace.json'), A.read(self.root/'other-run/loss-trace.json'))
        left = F.torch_owner().load(self.run/'weights.pt',weights_only=True)
        right = F.torch_owner().load(self.root/'other-run/weights.pt',weights_only=True)
        self.assertTrue(all(F.torch_owner().equal(left[k],right[k]) for k in left))

    def test_loss_trace_and_progress_exist_during_fit_outside_final_inventory(self):
        self.prepare_tokens(); self.config['steps'] = 17
        original = F.progress_receipt; observed = []
        def capture(directory, value):
            original(directory, value)
            if value['stage'] == 'training':
                lines = (directory/'loss-trace.jsonl').read_text(encoding='utf-8').splitlines()
                self.assertEqual(len(lines), value['completedSteps'])
                self.assertFalse((self.run/'weights.pt').exists())
                observed.append(value['completedSteps'])
        with patch.object(F, 'progress_receipt', side_effect=capture): result = self.fit()
        progress = self.run.with_name(self.run.name+'.progress')
        self.assertEqual(observed, [1,16,17])
        self.assertEqual(A.read(progress/'progress.json')['runSha256'], result['contentSha256'])
        self.assertEqual({p.name for p in self.run.iterdir()},
                         {'manifest.json','config.json','tokenizer.json','weights.pt','optimizer.pt','loss-trace.json'})

    def test_saved_weight_tamper_refuses_even_when_rehashed(self):
        self.prepare_tokens(); self.config['steps'] = 2; value = self.fit()
        torch = F.torch_owner(); path = self.run/'weights.pt'; state = torch.load(path,weights_only=True)
        state['tokens.weight'][97].add_(2); state['output.weight'] = state['tokens.weight']
        torch.save(state,path); value['weightsSha256'] = C.sha(path.read_bytes()); self.reseal_run(value)
        with self.assertRaisesRegex(ValueError,'evaluation differs'): self.evaluate()

    def test_raw_weight_corruption_and_half_precision_refuse(self):
        self.prepare_tokens(); self.config['steps'] = 1; value = self.fit(); torch = F.torch_owner()
        path = self.run/'weights.pt'; original = path.read_bytes(); path.write_bytes(original+b'altered')
        with self.assertRaisesRegex(ValueError,'saved weights differ'): self.evaluate()
        path.write_bytes(original); state = torch.load(path,weights_only=True)
        state['tokens.weight'] = state['tokens.weight'].half(); torch.save(state,path)
        value['weightsSha256'] = C.sha(path.read_bytes()); self.reseal_run(value)
        with self.assertRaisesRegex(ValueError,'precision differs'): self.evaluate()

    def test_causal_buffer_and_config_tamper_refuse(self):
        self.prepare_tokens(); self.config['steps'] = 1; value = self.fit(); torch = F.torch_owner()
        path = self.run/'weights.pt'; state = torch.load(path,weights_only=True); state['causal'].zero_(); torch.save(state,path)
        value['weightsSha256'] = C.sha(path.read_bytes()); self.reseal_run(value)
        with self.assertRaisesRegex(ValueError,'structural attention buffer'): self.evaluate()
        C.write_json(self.run/'config.json',{**self.config,'seed':2})
        with self.assertRaisesRegex(ValueError,'run inputs differ'): self.evaluate()

    def test_export_has_exact_fp32_tensor_bytes_and_trusted_run_identity(self):
        self.prepare_tokens(); self.config['steps'] = 1; value = self.fit(); output = self.root/'export'
        with self.assertRaisesRegex(ValueError,'run identity differs'):
            F.export(*self.common(),self.data,self.run,output,'0'*64)
        exported = F.export(*self.common(),self.data,self.run,output,value['contentSha256'])
        _, model = self.evaluate(); parameters = dict(model.named_parameters()); torch = F.torch_owner()
        raw = (output/'weights.fp32le').read_bytes()
        for spec in exported['tensorInventory']:
            values = array.array('f'); values.frombytes(raw[spec['offsetBytes']:spec['offsetBytes']+spec['lengthBytes']])
            if sys.byteorder != 'little': values.byteswap()
            actual = torch.tensor(values,dtype=torch.float32).reshape(spec['shape'])
            torch.testing.assert_close(actual,parameters[spec['name']],rtol=0,atol=0)
        self.assertEqual(exported['structuralTokenIds'],B.SPECIAL_IDS)
        self.assertEqual(exported['sequenceLength'],16); self.assertFalse(exported['nativeConsumerParity'])

    def test_cli_prepare_train_evaluate_and_export_use_saved_weights(self):
        artifact = self.root/'tokenizer.json'; splits = self.root/'splits.json'; config = self.root/'config.json'
        self.config['steps'] = 1
        for p,v in [(artifact,self.artifact),(splits,self.request),(config,self.config)]: C.write_json(p,v)
        common = ['--archive',str(self.archive),'--prepared',str(self.prepared),'--dataset',str(self.dataset),
                  '--tokenizer',str(artifact),'--splits',str(splits),'--data',str(self.data)]
        self.assertEqual(F.main(['prepare',*common,'--sequence-length','16']),0)
        self.assertEqual(F.main(['train',*common,'--config',str(config),'--output',str(self.run)]),0)
        self.assertEqual(F.main(['evaluate',*common,'--run',str(self.run)]),0)
        self.assertEqual(F.main(['export',*common,'--run',str(self.run),'--output',str(self.root/'export'),
                                 '--run-sha256',A.read(self.run/'manifest.json')['contentSha256']]),0)


@unittest.skipUnless(importlib.util.find_spec('torch'), 'PyTorch tests run in the isolated pretraining environment')
class FoundationStratifiedEvaluationTests(Fixture, unittest.TestCase):
    book_count = 5

    def test_every_actual_held_out_family_is_sampled_across_its_book(self):
        manifest = self.prepare_tokens(); self.config.update(batch=2, evaluationBatches=3)
        indices, assignments, populations = F.evaluation_indices(self.data, manifest, self.config, 'validation')
        self.assertEqual(len(indices),6); self.assertEqual(len(set(indices)),6)
        self.assertEqual(set(assignments.values()),{'family-2','family-3','family-4'})
        self.assertTrue(all(sum(v==family for v in assignments.values()) == 2 for family in populations))
        self.assertEqual(indices,F.evaluation_indices(self.data,manifest,self.config,'validation')[0])
        first_six = [A.loads(v)['sourceFamilyId'] for v in (self.data/'validation.provenance.jsonl').read_text().splitlines()[:6]]
        self.assertEqual(len(set(first_six)),1)  # Negative control reproduces the earlier first-book bias.
        model=F.make_model(self.config,B.FIRST_MERGE+len(self.artifact['merges']),16)
        result=F.measure(model,self.data,manifest,self.config,'validation')
        self.assertEqual(result['sourceFamiliesEvaluated'],['family-2','family-3','family-4'])
        self.assertTrue(all(v['evaluatedLossTokens']>0 for v in result['familyCoverage'].values()))

    def test_insufficient_family_coverage_budget_refuses(self):
        manifest=self.prepare_tokens(); self.config.update(batch=1,evaluationBatches=1)
        with self.assertRaisesRegex(ValueError,'cannot cover every held-out family'):
            F.evaluation_indices(self.data,manifest,self.config,'validation')


if __name__ == '__main__': unittest.main()
