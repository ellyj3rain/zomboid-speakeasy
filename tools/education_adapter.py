"""FP32 educational-answer residual adapter on a byte-identical frozen shared base."""
from __future__ import annotations

import argparse
import array
import copy
import math
from pathlib import Path
import random
import sys
import time

import byte_tokenizer as B
import decision_authoring as A
import education_adapter_data as D
import education_assessment as G
import education_corpus as C
import foundation_assessment as E
import foundation_pretraining as F

RUN = 'speakeasy-educational-answer-adapter-run/1'
ARCHITECTURE = 'frozen-base-final-normalized-residual-down-gelu-up-v1'
CONFIG_FIELDS = {'seed', 'bottleneck', 'steps', 'batch', 'learningRate', 'device', 'cpuThreads'}
RUN_FILES = {'manifest.json', 'config.json', 'adapter.pt', 'optimizer.pt', 'loss-trace.json'}


def validate_config(value):
    A.fields(value, CONFIG_FIELDS, 'educational answer adapter config')
    for key, low, high in [('seed', 0, 2**32-1), ('bottleneck', 1, 256), ('steps', 1, 100000),
                         ('batch', 1, 128), ('cpuThreads', 1, 32)]:
        A.require(type(value[key]) is int and low <= value[key] <= high, 'invalid ' + key)
    A.require(type(value['learningRate']) in (float, int) and math.isfinite(value['learningRate'])
              and 0 < value['learningRate'] <= .01, 'invalid adapter learning rate')
    A.require(value['device'] in {'cpu', 'cuda'}, 'unsupported adapter device')
    return value


def make_adapter(base, config):
    """The final base hidden state is detached; only two residual matrices are fitted."""
    validate_config(config); torch = F.torch_owner(); nn = torch.nn
    width, length = base.tokens.embedding_dim, base.positions.num_embeddings
    torch.manual_seed(config['seed'])

    class AnswerAdapter(nn.Module):
        def __init__(self):
            super().__init__(); self.base = base
            for parameter in base.parameters(): parameter.requires_grad_(False)
            self.adapter = nn.Sequential(nn.Linear(width, config['bottleneck']), nn.GELU(),
                                         nn.Linear(config['bottleneck'], width))
            nn.init.normal_(self.adapter[0].weight, std=.02); nn.init.zeros_(self.adapter[0].bias)
            nn.init.zeros_(self.adapter[2].weight); nn.init.zeros_(self.adapter[2].bias)
            self.adapter.to(device=config['device'], dtype=torch.float32); base.eval()

        def train(self, mode=True):
            super().train(mode); self.base.eval(); return self

        def forward(self, ids):
            n = ids.shape[1]; A.require(n <= length, 'input exceeds frozen base context')
            with torch.no_grad():
                hidden = base.tokens(ids)+base.positions(torch.arange(n, device=ids.device))
                for block in base.blocks:
                    hidden = block(hidden, base.causal[:n, :n], ids == B.SPECIAL_IDS['pad'])
                hidden = base.final(hidden)
            return base.output(hidden + self.adapter(hidden))

    return AnswerAdapter()


def load_base(data, config, seed_control=False):
    artifact = A.read(data/'tokenizer.json'); manifest = A.read(data/'manifest.json')
    paths = manifest['inputs']; saved = A.read(Path(paths['baseRun'])/'manifest.json')
    base_config = {**saved['config'], 'device': config['device'], 'cpuThreads': config['cpuThreads']}
    base = F.make_model(base_config, B.FIRST_MERGE+len(artifact['merges']), manifest['sequenceLength'])
    if not seed_control: F.load_weights(base, Path(paths['baseRun'])/'weights.pt', saved['weightsSha256'])
    return base, saved, artifact


def adapter_state(model):
    return {name: tensor.detach().cpu().clone() for name, tensor in model.adapter.state_dict().items()}


def load_adapter(model, path, expected_sha):
    torch = F.torch_owner(); A.require(C.sha(path.read_bytes()) == expected_sha, 'saved adapter bytes differ')
    state = torch.load(path, map_location='cpu', weights_only=True)
    A.require(isinstance(state, dict) and set(state) == set(model.adapter.state_dict()), 'adapter tensor inventory differs')
    for key, expected in model.adapter.state_dict().items():
        actual = state[key]
        A.require(isinstance(actual, torch.Tensor) and actual.shape == expected.shape
                  and actual.dtype == torch.float32 and torch.isfinite(actual).all().item(),
                  'adapter shape, FP32 precision or finite values differ')
    model.adapter.load_state_dict(state, strict=True)


def read_train(data):
    rows = [A.loads(raw) for raw in (data/'train.jsonl').read_text(encoding='utf-8').splitlines()]
    A.require(rows and all(row['split'] == row['learner']['split'] == 'train' for row in rows),
              'no source-owned train answer rows')
    return rows


def tensors(rows, device):
    torch = F.torch_owner()
    return (torch.tensor([row['inputIds'] for row in rows], dtype=torch.long, device=device),
            torch.tensor([row['targetIds'] for row in rows], dtype=torch.long, device=device),
            torch.tensor([row['lossMask'] for row in rows], dtype=torch.bool, device=device))


def output_boundary(output, data, run=None):
    D.check_output(output)
    manifest = A.read(data/'manifest.json')
    owned = [data, *[Path(value) for key, value in manifest['inputs'].items()
                    if key not in {'baseRunSha256', 'bankSha256'}]]
    if run is not None: owned.append(run)
    A.require(not output.exists() and not any(output.resolve().is_relative_to(p.resolve()) for p in owned),
              'output cannot modify source, tokenizer, data or existing run inputs')


def progress(directory, value):
    staged = directory/'progress.tmp'; C.write_json(staged, A.seal(value)); staged.replace(directory/'progress.json')


def fit(data, output, config, expected_data_sha):
    validate_config(config); A.hash_value(expected_data_sha, 'trusted adapter data identity')
    output_boundary(output, data)
    implementations = {'implementationSha256': C.sha(Path(__file__).read_bytes()),
                       'dataImplementationSha256': C.sha(Path(D.__file__).read_bytes()),
                       'baseImplementationSha256': C.sha(Path(F.__file__).read_bytes())}
    manifest = D.verify(data, expected_data_sha)
    A.require(manifest['release'] == 'ready-for-bounded-task-fit', 'no train-answer coverage')
    base, saved, artifact = load_base(data, config); torch = F.torch_owner()
    base_sha = E.state_digest(base); model = make_adapter(base, config)
    rows = read_train(data); randomizer = random.Random(config['seed'])
    probe = tensors(rows[:min(config['batch'], len(rows))], config['device'])[0]
    with torch.no_grad(): A.require(torch.equal(model(probe), base(probe)), 'zero-output adapter differs from base')
    optimizer = torch.optim.AdamW(model.adapter.parameters(), lr=config['learningRate'], weight_decay=.01)
    if config['device'] == 'cuda': torch.cuda.reset_peak_memory_stats()
    output.mkdir(parents=True); C.write_json(output/'config.json', config)
    trace = []; started = time.perf_counter(); observed = 0
    progress_dir = output.parent/(output.name+'-progress')
    A.require(not progress_dir.exists(), 'preserve prior progress evidence'); progress_dir.mkdir()
    with (progress_dir/'loss-trace.jsonl').open('xb') as log:
        for step in range(1, config['steps']+1):
            chosen = [rows[randomizer.randrange(len(rows))] for _ in range(config['batch'])]
            ids, target, mask = tensors(chosen, config['device'])
            optimizer.zero_grad(set_to_none=True); loss, count = F.masked_loss(model(ids), target, mask)
            A.require(torch.isfinite(loss).item(), 'nonfinite adapter fit loss')
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.adapter.parameters(), 1.)
            optimizer.step(); observed += count
            point = {'step': step, 'answerLoss': float(loss.detach()), 'lossTokens': count}
            trace.append(point); log.write(A.encoded(point)+b'\n'); log.flush()
            if step == 1 or step % 128 == 0 or step == config['steps']:
                progress(progress_dir, {'schema': 'speakeasy-educational-answer-progress/1',
                    'status': 'fitting', 'step': step, 'plannedSteps': config['steps'],
                    'answerLoss': point['answerLoss'], 'elapsedSeconds': time.perf_counter()-started,
                    'dataSha256': expected_data_sha, 'baseRunSha256': saved['contentSha256']})
    A.require(E.state_digest(base) == base_sha and all(p.grad is None for p in base.parameters()),
              'frozen shared base changed or received gradients')
    torch.save(adapter_state(model), output/'adapter.pt'); torch.save(optimizer.state_dict(), output/'optimizer.pt')
    C.write_json(output/'loss-trace.json', trace)
    paths = manifest['inputs']
    A.require(C.sha((Path(paths['baseRun'])/'weights.pt').read_bytes()) == saved['weightsSha256']
              and A.read(Path(paths['tokenizer'])) == artifact, 'base/tokenizer changed during fit')
    A.require(implementations == {'implementationSha256': C.sha(Path(__file__).read_bytes()),
              'dataImplementationSha256': C.sha(Path(D.__file__).read_bytes()),
              'baseImplementationSha256': C.sha(Path(F.__file__).read_bytes())}, 'adapter owner changed during fit')
    D.check_files(data, manifest)
    result = A.seal({'schema': RUN, 'task': 'educational-answer', 'architecture': ARCHITECTURE, 'precision': 'FP32',
        'dataSha256': expected_data_sha, 'baseRunSha256': saved['contentSha256'],
        'baseWeightsSha256': saved['weightsSha256'], 'baseStateSha256': base_sha,
        'tokenizerSha256': artifact['contentSha256'], 'config': config, 'configSha256': A.digest(config),
        **implementations,
        'adapterWeightsSha256': C.sha((output/'adapter.pt').read_bytes()),
        'optimizerSha256': C.sha((output/'optimizer.pt').read_bytes()),
        'lossTraceSha256': C.sha((output/'loss-trace.json').read_bytes()),
        'adapterStateSha256': E.state_digest(model.adapter),
        'adapterParameters': sum(p.numel() for p in model.adapter.parameters()),
        'peakCudaAllocatedBytes': torch.cuda.max_memory_allocated() if config['device'] == 'cuda' else None,
        'trainedAnswerTokens': observed, 'trainingSeconds': time.perf_counter()-started,
        'zeroOutputParityVerified': True, 'frozenBaseVerified': True,
        'standing': 'bounded-source-train-answer-fit-awaiting-heldout-evaluation', **E.AUTHORITY})
    C.write_json(output/'manifest.json', result)
    progress(progress_dir, {'schema': 'speakeasy-educational-answer-progress/1',
        'status': 'fit-complete', 'step': config['steps'], 'runSha256': result['contentSha256']})
    return result


def verify_run(data, run, expected_sha):
    A.hash_value(expected_sha, 'trusted adapter run identity')
    saved = A.read(run/'manifest.json'); G.validate_seal(saved, 'adapter run')
    A.require(saved['schema'] == RUN and saved['contentSha256'] == expected_sha
              and saved['architecture'] == ARCHITECTURE and saved['precision'] == 'FP32'
              and saved['task'] == 'educational-answer', 'adapter run identity differs')
    A.require({p.name for p in run.iterdir()} == RUN_FILES, 'adapter run inventory differs')
    config = validate_config(saved['config'])
    A.require(A.read(run/'config.json') == config and A.digest(config) == saved['configSha256'], 'adapter config differs')
    for name, key in [('adapter.pt', 'adapterWeightsSha256'), ('optimizer.pt', 'optimizerSha256'),
                      ('loss-trace.json', 'lossTraceSha256')]:
        A.require(C.sha((run/name).read_bytes()) == saved[key], 'saved '+name+' differs')
    manifest = D.verify(data, saved['dataSha256'])
    A.require(saved['baseRunSha256'] == manifest['baseRunSha256']
              and saved['baseWeightsSha256'] == manifest['baseWeightsSha256']
              and saved['tokenizerSha256'] == manifest['tokenizerSha256']
              and saved['implementationSha256'] == C.sha(Path(__file__).read_bytes())
              and saved['dataImplementationSha256'] == C.sha(Path(D.__file__).read_bytes())
              and saved['baseImplementationSha256'] == C.sha(Path(F.__file__).read_bytes()), 'frozen adapter owners differ')
    base, _, artifact = load_base(data, config)
    A.require(E.state_digest(base) == saved['baseStateSha256'], 'saved base state differs')
    model = make_adapter(base, config); load_adapter(model, run/'adapter.pt', saved['adapterWeightsSha256'])
    A.require(E.state_digest(model.adapter) == saved['adapterStateSha256']
              and sum(p.numel() for p in model.adapter.parameters()) == saved['adapterParameters'], 'adapter state differs')
    return saved, manifest, model, artifact


def complete_inference(model, public, tokenizer, length, settings, evidence=None):
    generation = E.inference(model, public, tokenizer, length, settings, evidence)
    if generation['status'] == 'generated' and generation['reason'] not in {'source-eos', 'public-choice-scoring'}:
        generation = A.seal({**{k: v for k, v in generation.items() if k != 'contentSha256'},
                            'status': 'withheld', 'response': '', 'reason': 'incomplete-output:'+generation['reason']})
    return generation


def statistics(rows):
    value = E.statistics(rows)
    attempts, before, after = 0, 0, 0
    for row in rows:
        generation = row['generation']; coverage = generation['coverage']
        count, original = coverage['inputTokens'], coverage['originalPromptTokens']
        A.require(type(count) is int and type(original) is int and original > 0
                  and count in (0, original) and coverage['truncatedTokens'] == 0
                  and (count > 0 or generation['status'] == 'withheld'), 'invalid partial-question inference coverage')
        attempts += count > 0
        before += count == 0 and generation['status'] == 'withheld'
        after += count > 0 and generation['status'] == 'withheld'
    value.update(attemptedCompleteInputs=attempts, withheldBeforeInference=before, withheldAfterInference=after)
    if not value['scoredResponses']: value['coverageStanding'] = 'no-scored-coverage'
    return value


def evaluate(data, run, expected_sha, as_of_time, session_id, settings):
    settings = E.policy(settings); A.identifier(session_id, 'evaluation session')
    saved, manifest, model, artifact = verify_run(data, run, expected_sha)
    tokenizer = B.Tokenizer(artifact)
    seed, _, _ = load_base(data, saved['config'], seed_control=True)
    models = {'savedAdapter': model, 'frozenBase': model.base, 'sameUntrainedSeed': seed}
    before = {name: E.state_digest(m) for name, m in models.items()}
    public_rows = [A.loads(line) for line in (data/'heldout.jsonl').read_text(encoding='utf-8').splitlines()]
    selected, coverage = [], {}
    for split in settings['evaluationSplits']:
        candidates = [row for row in public_rows if row['learner']['split'] == split]
        indexed = [{**row, 'familyId': row['learner']['familyId'], 'contentSha256': row['learner']['itemSha256']}
                   for row in candidates]
        chosen = E.select_families(indexed, settings['maximumItemsPerSplit']); selected.extend(chosen)
        coverage[split] = {**manifest['coverage'].get(split, {}), 'selectedSupportedTargets': len(chosen),
            'omittedByBound': len(candidates)-len(chosen),
            'sourceFamiliesWithSupportedTargets': sorted({row['familyId'] for row in indexed})}
    generated, responses = [], []
    for name, current in models.items():
        learner = {'kind': 'model', 'id': 'educational-answer-'+name, 'version': before[name]}
        for row in selected:
            public = row['learner']
            generation = complete_inference(current, public, tokenizer, manifest['sequenceLength'], settings,
                {'model': name, 'runSha256': expected_sha, 'stateSha256': before[name]})
            response = {'schema': 'speakeasy-educational-assessment-response/1', 'itemSha256': public['itemSha256'],
                'learner': learner, 'sessionId': session_id, 'asOfTime': as_of_time,
                'learningMode': 'independent-retrieval', 'assistanceEvidenceRefs': [],
                'evidenceRefs': [generation['contentSha256'], manifest['isolationProofSha256']],
                'response': generation['response']}
            G.validate_response(response); responses.append(response)
            generated.append({'model': name, 'split': public['split'], 'familyId': public['familyId'],
                              'source': row['source'], 'generation': generation, 'response': response})
    paths = manifest['inputs']
    grades = G.grade_many(Path(paths['archive']), Path(paths['bank']), responses)
    A.require(len(grades) == len(generated), 'actual source grader count differs')
    rows = [A.seal({**row, 'grade': grade}) for row, grade in zip(generated, grades)]
    A.require(before == {name: E.state_digest(m) for name, m in models.items()}, 'evaluation changed weights')
    A.require(C.sha((run/'adapter.pt').read_bytes()) == saved['adapterWeightsSha256']
              and C.sha((Path(paths['baseRun'])/'weights.pt').read_bytes()) == saved['baseWeightsSha256'],
              'weights changed during evaluation')
    D.check_files(data, manifest)
    return A.seal({'schema': 'speakeasy-educational-answer-adapter-evaluation/1', 'runSha256': expected_sha,
        'dataSha256': manifest['contentSha256'], 'assessmentBankSha256': manifest['assessmentBankSha256'],
        'sourceIsolationProofSha256': manifest['isolationProofSha256'], 'stateSha256': before,
        'sessionId': session_id, 'asOfTime': as_of_time, 'policy': settings, 'sourceCoverage': coverage, 'rows': rows,
        'metrics': {name: {split: statistics([row for row in rows if row['model'] == name and row['split'] == split])
                          for split in settings['evaluationSplits']} for name in models},
        'standing': 'bounded-actual-heldout-source-question-performance', **E.AUTHORITY})


def export(data, run, expected_sha, output):
    output_boundary(output, data, run)
    saved, manifest, model, artifact = verify_run(data, run, expected_sha)
    output.mkdir(parents=True); entries = []; offset = 0
    with (output/'adapter.fp32le').open('xb') as handle:
        for name, tensor in sorted(adapter_state(model).items()):
            values = array.array('f', tensor.reshape(-1).tolist()); A.require(values.itemsize == 4, 'FP32 width differs')
            if sys.byteorder != 'little': values.byteswap()
            raw = values.tobytes(); handle.write(raw)
            entries.append({'name': name, 'shape': list(tensor.shape), 'offsetBytes': offset,
                            'lengthBytes': len(raw), 'sha256': C.sha(raw)})
            offset += len(raw)
    C.write_json(output/'tokenizer.json', artifact); C.write_json(output/'config.json', saved['config'])
    D.check_files(data, manifest)
    value = A.seal({'schema': 'speakeasy-educational-answer-adapter-export/1', 'task': 'educational-answer',
        'architecture': ARCHITECTURE, 'hiddenDimension': model.base.tokens.embedding_dim,
        'bottleneck': saved['config']['bottleneck'], 'sequenceLength': manifest['sequenceLength'],
        'vocabularySize': B.FIRST_MERGE+len(artifact['merges']),
        'precision': 'FP32', 'runSha256': expected_sha, 'dataSha256': manifest['contentSha256'],
        'baseRunSha256': saved['baseRunSha256'], 'baseWeightsSha256': saved['baseWeightsSha256'],
        'baseStateSha256': saved['baseStateSha256'], 'adapterStateSha256': saved['adapterStateSha256'],
        'assessmentBankSha256': manifest['assessmentBankSha256'],
        'sourceIsolationProofSha256': manifest['isolationProofSha256'],
        'tokenizerSha256': artifact['contentSha256'], 'tensors': entries, 'weightBytes': offset,
        'weightsSha256': C.sha((output/'adapter.fp32le').read_bytes()),
        'standing': 'typed-task-adapter-reference-native-consumer-unverified', **E.AUTHORITY})
    C.write_json(output/'manifest.json', value); return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'verify-data', 'train', 'evaluate', 'export'])
    for key in ('inputs', 'data', 'run', 'out', 'config', 'time', 'policy'): parser.add_argument('--'+key, type=Path)
    parser.add_argument('--expected-sha256'); parser.add_argument('--session-id')
    parser.add_argument('--maximum-answer-tokens', type=int, default=32)
    args = parser.parse_args(argv)
    try:
        if args.action == 'prepare': value = D.prepare(A.read(args.inputs), args.out, args.maximum_answer_tokens)
        elif args.action == 'verify-data': value = D.verify(args.data, args.expected_sha256)
        elif args.action == 'train': value = fit(args.data, args.out, A.read(args.config), args.expected_sha256)
        elif args.action == 'export': value = export(args.data, args.run, args.expected_sha256, args.out)
        else:
            output_boundary(args.out, args.data, args.run)
            value = evaluate(args.data, args.run, args.expected_sha256, A.read(args.time), args.session_id,
                             A.read(args.policy))
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open('xb') as handle: handle.write(A.encoded(value)+b'\n')
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
        print('REFUSED: '+str(error), file=sys.stderr); return 2
    print('VERIFIED '+value['contentSha256']); return 0


if __name__ == '__main__': raise SystemExit(main())
