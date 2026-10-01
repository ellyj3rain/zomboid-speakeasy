"""Source-owned TRAIN answer supervision and public held-out question coverage."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import byte_tokenizer as B
import decision_authoring as A
import education_assessment as G
import education_corpus as C
import education_training_data as D
import foundation_assessment as E
import foundation_pretraining as F

INPUT_FIELDS = {'archive', 'prepared', 'dataset', 'tokenizer', 'splits', 'foundationData',
                'baseRun', 'bank', 'baseRunSha256', 'bankSha256'}
SCHEMA = 'speakeasy-educational-answer-data/1'


def inputs(value):
    A.fields(value, INPUT_FIELDS, 'educational adapter inputs')
    for key in ('baseRunSha256', 'bankSha256'): A.hash_value(value[key], key)
    paths = {k: Path(value[k]) for k in INPUT_FIELDS - {'baseRunSha256', 'bankSha256'}}
    artifact, request = A.read(paths['tokenizer']), A.read(paths['splits'])
    admitted, _, tokenizer, normalized, _, _ = D.validated_inputs(
        paths['archive'], paths['prepared'], paths['dataset'], artifact, request)
    run = A.read(paths['baseRun'] / 'manifest.json'); A.unseal(run, F.RUN)
    data = A.read(paths['foundationData'] / 'manifest.json'); A.unseal(data, F.DATA)
    A.require(run['contentSha256'] == value['baseRunSha256'] and run['precision'] == 'FP32'
              and run['task'] == 'shared-cognitive-base' and run['schemaVersion'] == 1
              and run['architecture'] == 'pre-ln-causal-transformer-tied-output-gelu-no-dropout',
              'frozen shared base differs')
    A.require(run['implementationSha256'] == C.sha(Path(F.__file__).read_bytes()), 'frozen base implementation differs')
    A.require(run['dataManifestSha256'] == data['contentSha256']
              and run['admittedManifestSha256'] == data['admittedManifestSha256'] == A.digest(admitted)
              and data['sourceSplits'] == normalized
              and run['tokenizerSha256'] == data['tokenizerSha256'] == artifact['contentSha256'],
              'base training provenance differs from source-owned input partitions')
    A.require({p.name for p in paths['baseRun'].iterdir()} ==
              {'manifest.json', 'config.json', 'tokenizer.json', 'weights.pt', 'optimizer.pt', 'loss-trace.json'},
              'base run inventory differs')
    for name, key in [('weights.pt', 'weightsSha256'), ('optimizer.pt', 'optimizerSha256'),
                      ('loss-trace.json', 'lossTraceSha256')]:
        A.require(C.sha((paths['baseRun']/name).read_bytes()) == run[key], 'corrupt frozen base ' + name)
    A.require(A.read(paths['baseRun']/'config.json') == run['config']
              and A.digest(run['config']) == run['configSha256']
              and (paths['baseRun']/'tokenizer.json').read_bytes() == A.encoded(artifact)+b'\n',
              'base config or tokenizer changed')
    F.validate_config(run['config']); F.check_data_files(paths['foundationData'], data)
    manifest, items = G.validate_bank(paths['archive'], paths['bank'])
    A.require(manifest['contentSha256'] == value['bankSha256'], 'source assessment bank differs')
    proof = G.validate_training_isolation(manifest, request, archive=paths['archive'], bank=paths['bank'])
    return paths, artifact, tokenizer, run, data, manifest, items, proof


def supervised(public, target, tokenizer, sequence_length, maximum_answer_tokens):
    A.require(public['split'] == 'train', 'held-out answer cannot enter supervision')
    prompt, _ = E.public_prompt(public)
    ids = [B.SPECIAL_IDS['bos'], *tokenizer.encode_text(prompt)]
    answer = target['correctKey'] if target['kind'] == 'multiple-choice' else target['literal']
    tokens = tokenizer.encode_text(answer)
    A.require(tokenizer.decode_bytes(tokens) == answer.encode(), 'answer byte parity differs')
    if len(tokens)+1 > maximum_answer_tokens or len(ids)+len(tokens) > sequence_length:
        return None
    sequence = [*ids, *tokens, B.SPECIAL_IDS['eos']]
    count = len(sequence)-1; padding = sequence_length-count
    return A.seal({'schema': 'speakeasy-educational-answer-sequence/1',
                   'itemSha256': public['itemSha256'], 'familyId': public['familyId'], 'split': 'train',
                   'learner': public, 'promptSha256': C.sha(prompt.encode()), 'answer': answer,
                   'targetKind': target['kind'], 'promptTokenCount': len(ids),
                   'inputIds': sequence[:-1]+[B.SPECIAL_IDS['pad']]*padding,
                   'targetIds': sequence[1:]+[B.SPECIAL_IDS['pad']]*padding,
                   'lossMask': [i >= len(ids)-1 for i in range(count)]+[False]*padding})


def derive(value, maximum_answer_tokens=32):
    A.require(type(maximum_answer_tokens) is int and 1 <= maximum_answer_tokens <= 128, 'invalid answer bound')
    paths, artifact, tokenizer, run, data, bank, items, proof = inputs(value)
    length = data['sequenceLength']; settings = {**E.DEFAULT_POLICY, 'maximumNewTokens': maximum_answer_tokens}
    counts, sources = defaultdict(Counter), defaultdict(Counter)
    files = {'train.jsonl': [], 'heldout.jsonl': [], 'excluded.jsonl': []}
    for item in sorted(items, key=lambda x: (x['split'], x['familyId'], x['contentSha256'])):
        split = item['split']; counts[split]['sourceExercises'] += 1
        reason, row = None, None
        if item['gradingTarget'] is None: reason = 'unsupported-source-target'
        else:
            counts[split]['supportedTargets'] += 1
            public = G.learner_input(item); prompt, options = E.public_prompt(public)
            prompt_count = 1+len(tokenizer.encode_text(prompt))
            reserve = max([len(tokenizer.encode_text(x['key'])) for x in options] or [maximum_answer_tokens])
            if public['input']['coverage']['mediaReferencesPresent']: reason = 'required-source-media-not-provided'
            elif prompt_count+reserve > length: reason = 'complete-question-exceeds-context-budget'
            if split == 'train' and reason is None:
                row = supervised(public, item['gradingTarget'], tokenizer, length, maximum_answer_tokens)
                if row is None: reason = 'complete-answer-exceeds-budget'
                else:
                    row = A.seal({**{k: v for k, v in row.items() if k != 'contentSha256'},
                                  'source': item['source'], 'exercise': item['exercise'],
                                  'sourceItemSha256': item['contentSha256']})
                    files['train.jsonl'].append(row)
            if split != 'train':
                files['heldout.jsonl'].append(A.seal({'schema': 'speakeasy-educational-answer-public/1',
                    'learner': public, 'source': item['source'], 'reason': reason,
                    'supportedTargetKind': item['gradingTarget']['kind']}))
        counts[split][reason or 'available'] += 1
        if reason:
            files['excluded.jsonl'].append(A.seal({'schema': 'speakeasy-educational-answer-exclusion/1',
                'itemSha256': item['contentSha256'], 'source': item['source'], 'familyId': item['familyId'],
                'split': split, 'reason': reason}))
        else: sources[split][item['source']['id']] += 1
    serialized = {name: b''.join(A.encoded(x)+b'\n' for x in rows) for name, rows in files.items()}
    serialized['tokenizer.json'] = A.encoded(artifact)+b'\n'
    manifest = A.seal({'schema': SCHEMA, 'task': 'educational-answer', 'inputs': value,
        'baseRunSha256': run['contentSha256'], 'baseWeightsSha256': run['weightsSha256'],
        'tokenizerSha256': artifact['contentSha256'], 'assessmentBankSha256': bank['contentSha256'],
        'isolationProofSha256': proof['contentSha256'], 'sequenceLength': length,
        'maximumAnswerTokens': maximum_answer_tokens, 'coverage': dict(counts), 'availableBySource': dict(sources),
        'files': {name: {'sha256': C.sha(raw), 'bytes': len(raw)} for name, raw in serialized.items()},
        'release': 'ready-for-bounded-task-fit' if files['train.jsonl'] else 'no-train-answer-coverage',
        'loss': 'source-train-answer-and-eos-only-next-token-shift', **E.AUTHORITY})
    return manifest, serialized


def check_output(output):
    repository = Path(__file__).resolve().parents[1]
    A.require(not output.exists(), 'preserve existing adapter output')
    A.require(not output.resolve().is_relative_to(repository)
              or output.resolve().is_relative_to(repository/'runs'), 'repository-local adapter outputs belong in runs')


def prepare(value, output, maximum_answer_tokens=32):
    check_output(output)
    A.require(not output.exists(), 'preserve existing adapter data')
    A.require(not any(output.resolve().is_relative_to(Path(value[k]).resolve())
                      for k in INPUT_FIELDS-{'baseRunSha256', 'bankSha256'}), 'output overlaps source inputs')
    manifest, serialized = derive(value, maximum_answer_tokens)
    output.mkdir(parents=True)
    for name, raw in serialized.items(): (output/name).write_bytes(raw)
    C.write_json(output/'manifest.json', manifest)
    return manifest


def verify(output, expected_sha=None):
    saved = A.read(output/'manifest.json'); G.validate_seal(saved, 'adapter data')
    A.require(saved['schema'] == SCHEMA and (expected_sha is None or saved['contentSha256'] == expected_sha),
              'adapter data identity differs')
    expected, serialized = derive(saved['inputs'], saved['maximumAnswerTokens'])
    A.require(saved == expected and {p.name for p in output.iterdir()} == {'manifest.json', *serialized},
              'adapter data provenance or inventory differs')
    for name, raw in serialized.items(): A.require((output/name).read_bytes() == raw, 'adapter data differs: '+name)
    return saved


def check_files(output, manifest):
    """Refuse mutable input races after canonical reconstruction and before release."""
    A.require(A.read(output/'manifest.json') == manifest, 'adapter data manifest changed during operation')
    for name, entry in manifest['files'].items():
        raw = (output/name).read_bytes()
        A.require(len(raw) == entry['bytes'] and C.sha(raw) == entry['sha256'],
                  'adapter data bytes changed during operation: '+name)
    paths = {k: Path(v) for k, v in manifest['inputs'].items() if k not in {'baseRunSha256', 'bankSha256'}}
    C.verified_sources(paths['archive'])
    bank = A.read(paths['bank']/'manifest.json'); G.validate_seal(bank, 'assessment bank')
    A.require(bank['contentSha256'] == manifest['assessmentBankSha256'], 'source bank changed during operation')
    for name, key in [('assessments.jsonl', 'assessmentsSha256'), ('learner-items.jsonl', 'learnerItemsSha256')]:
        A.require(C.sha((paths['bank']/name).read_bytes()) == bank[key], 'source bank bytes changed during operation')
