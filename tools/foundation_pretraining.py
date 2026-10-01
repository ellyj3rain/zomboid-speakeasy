"""Source-bound FP32 causal-transformer reference; PyTorch is an optional runtime dependency."""
from __future__ import annotations

import argparse
import array
import hashlib
import importlib
import math
import mmap
import os
from pathlib import Path
import random
import sys
import time

import byte_tokenizer as B
import decision_authoring as A
import education_corpus as C
import education_training_data as D

DATA = 'speakeasy-foundation-token-data'
RUN = 'speakeasy-foundation-pretraining-run'
EXPORT = 'speakeasy-foundation-reference-export'
DEFAULT_CONFIG = {'seed': 81, 'layers': 4, 'hidden': 256, 'heads': 4, 'batch': 8,
                  'steps': 100, 'learningRate': 0.0003, 'evaluationBatches': 16,
                  'device': 'cpu', 'cpuThreads': 1}


def torch_owner():
    try:
        return importlib.import_module('torch')
    except ImportError as error:
        raise ValueError('FP32 reference needs PyTorch in an isolated training environment') from error


def validate_config(config):
    A.fields(config, set(DEFAULT_CONFIG), 'foundation run config')
    bounds = {'seed': (0, 2**32-1), 'layers': (1, 12), 'hidden': (16, 1024), 'heads': (1, 16),
              'batch': (1, 128), 'steps': (1, 100000), 'evaluationBatches': (1, 1024), 'cpuThreads': (1, 32)}
    for key, (low, high) in bounds.items():
        A.require(type(config[key]) is int and low <= config[key] <= high, 'invalid ' + key)
    A.require(config['hidden'] % config['heads'] == 0, 'hidden dimension must divide into heads')
    A.require(type(config['learningRate']) in (int, float) and math.isfinite(config['learningRate'])
              and 0 < config['learningRate'] <= 0.01, 'invalid learning rate')
    A.require(config['device'] in ('cpu', 'cuda'), 'unsupported reference device')
    return config


def configure(config):
    validate_config(config)
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
    torch = torch_owner()
    A.require(config['device'] != 'cuda' or torch.cuda.is_available(), 'requested CUDA device is unavailable')
    torch.set_num_threads(config['cpuThreads'])
    torch.manual_seed(config['seed'])
    torch.use_deterministic_algorithms(True)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    return torch


def make_model(config, vocabulary_size, sequence_length):
    torch = configure(config)
    A.require(type(sequence_length) is int and 16 <= sequence_length <= 1024, 'invalid context length')
    A.require(type(vocabulary_size) is int and B.FIRST_MERGE <= vocabulary_size <= B.FIRST_MERGE+8192,
              'invalid vocabulary size')
    nn = torch.nn; width = config['hidden']

    class Block(nn.Module):
        def __init__(self):
            super().__init__()
            self.norm1 = nn.LayerNorm(width)
            self.attention = nn.MultiheadAttention(width, config['heads'], dropout=0, batch_first=True)
            self.norm2 = nn.LayerNorm(width)
            self.feed = nn.Sequential(nn.Linear(width, 4*width), nn.GELU(), nn.Linear(4*width, width))

        def forward(self, x, causal, padding):
            normalized = self.norm1(x)
            x = x + self.attention(normalized, normalized, normalized, attn_mask=causal,
                                   key_padding_mask=padding, need_weights=False)[0]
            return x + self.feed(self.norm2(x))

    class CausalBase(nn.Module):
        def __init__(self):
            super().__init__()
            self.tokens = nn.Embedding(vocabulary_size, width, padding_idx=B.SPECIAL_IDS['pad'])
            self.positions = nn.Embedding(sequence_length, width)
            self.blocks = nn.ModuleList([Block() for _ in range(config['layers'])])
            self.final = nn.LayerNorm(width)
            self.output = nn.Linear(width, vocabulary_size, bias=False)
            self.output.weight = self.tokens.weight
            self.register_buffer('causal', torch.triu(torch.ones(sequence_length, sequence_length, dtype=torch.bool), 1))
            for module in self.modules():
                if isinstance(module, (nn.Linear, nn.Embedding)):
                    nn.init.normal_(module.weight, mean=0., std=0.02)
                    if isinstance(module, nn.Linear) and module.bias is not None: nn.init.zeros_(module.bias)
                if isinstance(module, nn.MultiheadAttention):
                    nn.init.normal_(module.in_proj_weight, mean=0., std=0.02)
                    nn.init.zeros_(module.in_proj_bias)
            with torch.no_grad(): self.tokens.weight[B.SPECIAL_IDS['pad']].zero_()

        def forward(self, ids):
            length = ids.shape[1]
            A.require(length <= sequence_length, 'input exceeds model context')
            x = self.tokens(ids) + self.positions(torch.arange(length, device=ids.device))
            for block in self.blocks:
                x = block(x, self.causal[:length, :length], ids == B.SPECIAL_IDS['pad'])
            return self.output(self.final(x))

    return CausalBase().to(device=config['device'], dtype=torch.float32)


def masked_loss(logits, targets, mask):
    torch = torch_owner()
    A.require(logits.dtype == torch.float32 and mask.dtype == torch.bool, 'loss requires FP32 logits and boolean masks')
    count = int(mask.sum().item())
    A.require(count > 0, 'batch has no real next-token targets')
    # Select active positions before evaluating cross entropy; padding labels have no influence.
    return torch.nn.functional.cross_entropy(logits[mask], targets[mask]), count


def token_bytes(block):
    chunks = []
    for key in ('inputIds', 'targetIds'):
        values = array.array('H', block[key])
        A.require(values.itemsize == 2, 'platform uint16 width differs')
        if sys.byteorder != 'little': values.byteswap()
        chunks.append(values.tobytes())
    return b''.join(chunks) + bytes(block['lossMask'])


def prepared_manifest(admitted, artifact, request, records, sequence_length, maximum_tokens):
    A.require(all(records[p]['blocks'] for p in D.PARTITIONS), 'foundation data requires train, validation and test')
    return A.seal({'schema': DATA, 'schemaVersion': 1, 'task': 'shared-cognitive-base',
                   'admittedManifestSha256': A.digest(admitted), 'tokenizerSha256': artifact['contentSha256'],
                   'admittedTextsSha256': admitted['textsSha256'], 'sourcePreparationSha256': admitted['sourceReviewSha256'],
                   'sourceEvaluationReceiptSha256': admitted.get('evaluationReceiptSha256'),
                   'sourceSplits': request, 'sequenceLength': sequence_length, 'maximumTotalTokens': maximum_tokens,
                   'layout': 'uint16-le-inputs,uint16-le-targets,uint8-mask', 'partitions': records,
                   'runtimeIntegration': False, 'personKnowledgeAuthority': False})


def materialize(inputs, artifact, output, sequence_length, maximum_tokens, checking=False):
    admitted, rows, tokenizer, request, families, partitions = inputs
    A.require(16 <= sequence_length <= 1024, 'invalid context length')
    handles, hashes, records = {}, {}, {}
    try:
        for p in D.PARTITIONS:
            handles[p] = [(output/(p+suffix)).open('rb' if checking else 'xb') for suffix in ('.bin', '.provenance.jsonl')]
            hashes[p] = [hashlib.sha256(), hashlib.sha256()]
            records[p] = {'blocks': 0, 'lossTokens': 0}
        for p, block in D.sequence_blocks(rows, tokenizer, families, partitions, sequence_length, maximum_tokens):
            provenance = {k: v for k, v in block.items() if k not in ('inputIds', 'targetIds', 'lossMask')}
            values = [token_bytes(block), A.encoded(provenance)+b'\n']
            for handle, digest, data in zip(handles[p], hashes[p], values):
                if checking: A.require(handle.read(len(data)) == data, 'saved foundation tokens or provenance differ')
                else: handle.write(data)
                digest.update(data)
            records[p]['blocks'] += 1; records[p]['lossTokens'] += sum(block['lossMask'])
        for p in D.PARTITIONS:
            if checking: A.require(all(not h.read(1) for h in handles[p]), 'extra foundation token data')
            records[p].update(binarySha256=hashes[p][0].hexdigest(), provenanceSha256=hashes[p][1].hexdigest())
    finally:
        for pair in handles.values():
            for handle in pair: handle.close()
    return prepared_manifest(admitted, artifact, request, records, sequence_length, maximum_tokens)


def verify_data(archive, prepared, dataset, artifact, request, output, store=None):
    value = A.read(output/'manifest.json'); A.unseal(value, DATA)
    expected_files = {'manifest.json', 'tokenizer.json', *[p+s for p in D.PARTITIONS for s in ('.bin', '.provenance.jsonl')]}
    A.require({p.name for p in output.iterdir()} == expected_files, 'foundation data inventory differs')
    A.require((output/'tokenizer.json').read_bytes() == A.encoded(artifact)+b'\n', 'frozen tokenizer differs')
    inputs = D.validated_inputs(archive, prepared, dataset, artifact, request, store)
    actual = materialize(inputs, artifact, output, value['sequenceLength'], value['maximumTotalTokens'], True)
    A.require(value == actual, 'foundation data manifest differs from actual sources')
    return value


def prepare_data(archive, prepared, dataset, artifact, request, output, sequence_length=256,
                 maximum_tokens=100_000_000, store=None):
    inputs = D.validated_inputs(archive, prepared, dataset, artifact, request, store)
    A.require(not output.exists(), 'preserve existing foundation data')
    A.require(not any(output.resolve().is_relative_to(p.resolve()) for p in (archive, prepared, dataset)),
              'foundation output cannot modify source inputs')
    output.mkdir(parents=True)
    C.write_json(output/'manifest.json', {'schema': DATA+'-incomplete', 'release': 'excluded'})
    C.write_json(output/'tokenizer.json', artifact)
    result = materialize(inputs, artifact, output, sequence_length, maximum_tokens)
    actual = materialize(D.validated_inputs(archive, prepared, dataset, artifact, request, store),
                         artifact, output, sequence_length, maximum_tokens, True)
    A.require(result == actual, 'foundation data changed during reconstruction')
    C.write_json(output/'manifest.json', result)
    return result


class Batches:
    def __init__(self, data, manifest, partition):
        self.length = manifest['sequenceLength']; self.count = manifest['partitions'][partition]['blocks']
        self.handle = (data/(partition+'.bin')).open('rb')
        self.mapping = mmap.mmap(self.handle.fileno(), 0, access=mmap.ACCESS_READ)
        A.require(len(self.mapping) == self.count*self.length*5, 'binary sequence length differs')

    def read(self, indices, device):
        torch = torch_owner(); inputs, targets, masks = [], [], []; n = self.length
        for index in indices:
            A.require(type(index) is int and 0 <= index < self.count, 'block index exceeds data')
            raw = self.mapping[index*n*5:(index+1)*n*5]
            pair = array.array('H'); pair.frombytes(raw[:4*n])
            if sys.byteorder != 'little': pair.byteswap()
            inputs.append(torch.tensor(pair[:n], dtype=torch.long))
            targets.append(torch.tensor(pair[n:], dtype=torch.long))
            masks.append(torch.tensor(list(raw[4*n:]), dtype=torch.bool))
        return tuple(torch.stack(v).to(device) for v in (inputs, targets, masks))

    def close(self):
        self.mapping.close(); self.handle.close()


def evaluation_indices(data, manifest, config, partition):
    """Balance a bounded, evenly spread sample across every declared held-out family."""
    families = {}
    with (data/(partition+'.provenance.jsonl')).open('r', encoding='utf-8') as handle:
        for index, line in enumerate(handle):
            family = A.loads(line)['sourceFamilyId']
            families.setdefault(family, []).append(index)
    A.require(set(families) == set(manifest['sourceSplits']['splits'][partition]),
              'held-out family coverage differs from declared source split')
    total = sum(map(len, families.values()))
    A.require(total == manifest['partitions'][partition]['blocks'], 'evaluation provenance block count differs')
    budget = min(total, config['batch']*config['evaluationBatches'])
    A.require(budget >= len(families), 'evaluation budget cannot cover every held-out family')
    quotas = {family: 0 for family in sorted(families)}
    remaining = budget
    while remaining:
        for family in quotas:
            if quotas[family] < len(families[family]) and remaining:
                quotas[family] += 1; remaining -= 1
    selected = {}
    for family, count in quotas.items():
        population = families[family]
        for i in range(count): selected[population[(2*i+1)*len(population)//(2*count)]] = family
    return sorted(selected), selected, {family: len(v) for family, v in families.items()}


def measure(model, data, manifest, config, partition):
    indices, assignments, populations = evaluation_indices(data, manifest, config, partition)
    torch = torch_owner(); batches = Batches(data, manifest, partition)
    per_family = {family: {'lossSum': 0., 'lossTokens': 0, 'blocks': 0} for family in sorted(populations)}
    was_training = model.training; model.eval()
    try:
        with torch.no_grad():
            for start in range(0, len(indices), config['batch']):
                chosen = indices[start:start+config['batch']]
                x, y, mask = batches.read(chosen, config['device']); logits = model(x)
                active_losses = torch.nn.functional.cross_entropy(logits[mask], y[mask], reduction='none')
                losses = torch.zeros_like(mask, dtype=torch.float32); losses[mask] = active_losses
                sums, counts = losses.sum(dim=1).tolist(), mask.sum(dim=1).tolist()
                for index, loss_sum, count in zip(chosen, sums, counts):
                    record = per_family[assignments[index]]
                    record['lossSum'] += loss_sum; record['lossTokens'] += count; record['blocks'] += 1
    finally:
        batches.close(); model.train(was_training)
    targets = sum(v['lossTokens'] for v in per_family.values())
    loss_sum = sum(v['lossSum'] for v in per_family.values())
    mean = loss_sum/targets
    A.require(math.isfinite(mean), 'nonfinite held-out loss')
    coverage = {family: {'evaluatedBlocks': v['blocks'], 'partitionBlocks': populations[family],
                         'evaluatedLossTokens': v['lossTokens'], 'nextTokenLoss': v['lossSum']/v['lossTokens']}
                for family, v in per_family.items()}
    return {'nextTokenLoss': mean, 'perplexity': math.exp(min(mean, 700)), 'evaluatedLossTokens': targets,
            'evaluatedBlocks': len(indices), 'partitionBlocks': batches.count,
            'sourceFamiliesEvaluated': sorted(populations), 'familyCoverage': coverage,
            'selection': 'source-family-balanced-evenly-spaced-v1', 'blockIndicesSha256': A.digest(indices)}


def load_weights(model, path, expected_sha):
    torch = torch_owner(); A.require(C.sha(path.read_bytes()) == expected_sha, 'saved weights differ')
    state = torch.load(path, map_location='cpu', weights_only=True)
    A.require(isinstance(state, dict) and set(state) == set(model.state_dict()), 'weight tensor inventory differs')
    for key, expected in model.state_dict().items():
        tensor = state[key]
        A.require(isinstance(tensor, torch.Tensor) and tensor.shape == expected.shape and tensor.dtype == expected.dtype,
                  'weight tensor shape or precision differs')
        A.require(not tensor.is_floating_point() or torch.isfinite(tensor).all().item(), 'nonfinite weight tensor')
        if not tensor.is_floating_point(): A.require(torch.equal(tensor, expected.cpu()), 'structural attention buffer differs')
    A.require(torch.equal(state['tokens.weight'], state['output.weight']), 'tied base/output weights differ')
    model.load_state_dict(state, strict=True)


def metrics(model, data, manifest, config):
    return {p: measure(model, data, manifest, config, p) for p in ('validation', 'test')}


def check_data_files(data, manifest):
    for p in D.PARTITIONS:
        for suffix, key in [('.bin', 'binarySha256'), ('.provenance.jsonl', 'provenanceSha256')]:
            digest = hashlib.sha256()
            with (data/(p+suffix)).open('rb') as handle:
                while chunk := handle.read(1024*1024): digest.update(chunk)
            A.require(digest.hexdigest() == manifest['partitions'][p][key], 'training data changed during run')


def progress_receipt(directory, value):
    staged = directory/'progress.tmp'
    C.write_json(staged, {'schema': RUN+'-progress', 'standing': 'observational', **value})
    staged.replace(directory/'progress.json')


def train(archive, prepared, dataset, artifact, request, data, config, output, store=None):
    total_start = time.perf_counter()
    implementation_sha = C.sha(Path(__file__).read_bytes())
    validate_config(config); A.require(not output.exists(), 'preserve existing foundation run')
    A.require(not any(output.resolve().is_relative_to(p.resolve()) for p in (archive, prepared, dataset, data)),
              'training output cannot modify source inputs')
    progress = output.with_name(output.name+'.progress')
    A.require(not progress.exists(), 'preserve existing run progress')
    progress.mkdir(parents=True)
    anchor = {'configSha256': A.digest(config), 'implementationSha256': implementation_sha,
              'plannedSteps': config['steps']}
    progress_receipt(progress, {**anchor, 'stage': 'source-and-token-reconstruction', 'completedSteps': 0})
    manifest = verify_data(archive, prepared, dataset, artifact, request, data, store)
    anchor['dataManifestSha256'] = manifest['contentSha256']
    torch = configure(config); model = make_model(config, B.FIRST_MERGE+len(artifact['merges']), manifest['sequenceLength'])
    output.mkdir(parents=True); C.write_json(output/'manifest.json', {'schema': RUN+'-incomplete', 'release': 'excluded'})
    C.write_json(output/'config.json', config); C.write_json(output/'tokenizer.json', artifact)
    progress_receipt(progress, {**anchor, 'stage': 'untrained-control-evaluation', 'completedSteps': 0})
    baseline = metrics(model, data, manifest, config)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config['learningRate'], weight_decay=0.01)
    generator = random.Random(config['seed']); batches = Batches(data, manifest, 'train'); trace = []
    if config['device'] == 'cuda': torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter(); model.train()
    observed_tokens = 0
    try:
        with (progress/'loss-trace.jsonl').open('xb') as live_trace:
            for step in range(config['steps']):
                indices = [generator.randrange(batches.count) for _ in range(config['batch'])]
                x, y, mask = batches.read(indices, config['device']); optimizer.zero_grad(set_to_none=True)
                loss, count = masked_loss(model(x), y, mask)
                A.require(torch.isfinite(loss).item(), 'nonfinite training loss')
                loss.backward(); gradient = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
                optimizer.step(); observed_tokens += count
                trace.append({'step': step+1, 'loss': float(loss.detach()), 'lossTokens': count,
                              'gradientNorm': float(gradient), 'blockIndicesSha256': A.digest(indices)})
                live_trace.write(A.encoded(trace[-1])+b'\n'); live_trace.flush()
                if step == 0 or (step+1) % 16 == 0 or step+1 == config['steps']:
                    progress_receipt(progress, {**anchor, 'stage': 'training', 'completedSteps': step+1,
                                               'lastLoss': trace[-1]['loss'], 'meanLast16Loss': sum(v['loss'] for v in trace[-16:])/len(trace[-16:]),
                                               'lossTokens': observed_tokens, 'trainingSeconds': time.perf_counter()-start})
                if (step+1) % 1024 == 0:
                    torch.save({'step': step+1, 'config': config, 'dataManifestSha256': manifest['contentSha256'],
                                'weights': {k: v.detach().cpu() for k,v in model.state_dict().items()},
                                'optimizer': optimizer.state_dict(), 'samplingState': generator.getstate()},
                               progress/f'checkpoint-{step+1:06d}.pt')
    finally: batches.close()
    if config['device'] == 'cuda': torch.cuda.synchronize()
    training_seconds = time.perf_counter()-start
    torch.save({k: v.detach().cpu() for k, v in model.state_dict().items()}, output/'weights.pt')
    torch.save(optimizer.state_dict(), output/'optimizer.pt')
    C.write_json(output/'loss-trace.json', trace)
    weights_sha = C.sha((output/'weights.pt').read_bytes())
    progress_receipt(progress, {**anchor, 'stage': 'saved-weight-evaluation', 'completedSteps': config['steps'],
                               'weightsSha256': weights_sha, 'lossTokens': observed_tokens})
    load_weights(model, output/'weights.pt', weights_sha)
    learned = metrics(model, data, manifest, config)
    check_data_files(data, manifest)
    current = D.validated_inputs(archive, prepared, dataset, artifact, request, store)[0]
    A.require(A.digest(current) == manifest['admittedManifestSha256'], 'source admission changed during training')
    A.require(C.sha(Path(__file__).read_bytes()) == implementation_sha, 'frozen training implementation changed during run')
    parameters = sum(p.numel() for p in model.parameters())
    receipt = A.seal({'schema': RUN, 'schemaVersion': 1, 'task': 'shared-cognitive-base',
                      'architecture': 'pre-ln-causal-transformer-tied-output-gelu-no-dropout', 'precision': 'FP32',
                      'implementationSha256': implementation_sha,
                      'config': config, 'configSha256': A.digest(config), 'dataManifestSha256': manifest['contentSha256'],
                      'admittedManifestSha256': manifest['admittedManifestSha256'], 'tokenizerSha256': artifact['contentSha256'],
                      'weightsSha256': weights_sha, 'optimizerSha256': C.sha((output/'optimizer.pt').read_bytes()),
                      'lossTraceSha256': C.sha((output/'loss-trace.json').read_bytes()), 'parameterCount': parameters,
                      'parameterBytes': parameters*4, 'trainingSeconds': training_seconds,
                      'totalRunSeconds': time.perf_counter()-total_start,
                      'trainingLossTokens': sum(v['lossTokens'] for v in trace),
                      'peakCudaAllocatedBytes': torch.cuda.max_memory_allocated() if config['device'] == 'cuda' else None,
                      'peakCudaReservedBytes': torch.cuda.max_memory_reserved() if config['device'] == 'cuda' else None,
                      'deviceName': torch.cuda.get_device_name() if config['device'] == 'cuda' else 'CPU',
                      'torchVersion': torch.__version__, 'untrainedSeedMetrics': baseline, 'savedWeightMetrics': learned,
                      'runtimeIntegration': False, 'nativeConsumerParity': False, 'personKnowledgeAuthority': False,
                      'limits': ['bounded-held-out-next-token-evaluation', 'no-curriculum-competence-or-person-retention-claim',
                                 'reference-shared-base-without-task-adapters', 'dimensions-remain-measured-pilot-candidates']})
    C.write_json(output/'manifest.json', receipt)
    progress_receipt(progress, {**anchor, 'stage': 'complete', 'completedSteps': config['steps'],
                               'runSha256': receipt['contentSha256'], 'weightsSha256': weights_sha,
                               'lossTokens': observed_tokens})
    return receipt


def equal_metric(actual, declared):
    if isinstance(actual, dict):
        return isinstance(declared, dict) and actual.keys() == declared.keys() and all(equal_metric(actual[k], declared[k]) for k in actual)
    return math.isclose(actual, declared, rel_tol=1e-6, abs_tol=1e-6) if type(actual) is float else actual == declared


def evaluate(archive, prepared, dataset, artifact, request, data, run, expected_sha=None, store=None):
    value = A.read(run/'manifest.json'); A.unseal(value, RUN)
    A.require(value['precision'] == 'FP32' and value['architecture'] == 'pre-ln-causal-transformer-tied-output-gelu-no-dropout'
              and value['task'] == 'shared-cognitive-base' and value['schemaVersion'] == 1,
              'reference architecture or precision differs')
    if expected_sha is not None: A.require(value['contentSha256'] == expected_sha, 'run identity differs')
    A.require({p.name for p in run.iterdir()} == {'manifest.json', 'config.json', 'tokenizer.json', 'weights.pt', 'optimizer.pt', 'loss-trace.json'}, 'run inventory differs')
    manifest = verify_data(archive, prepared, dataset, artifact, request, data, store)
    A.require(value['dataManifestSha256'] == manifest['contentSha256']
              and value['tokenizerSha256'] == artifact['contentSha256']
              and A.read(run/'config.json') == value['config'] and A.digest(value['config']) == value['configSha256']
              and (run/'tokenizer.json').read_bytes() == A.encoded(artifact)+b'\n', 'run inputs differ')
    for filename, key in [('optimizer.pt', 'optimizerSha256'), ('loss-trace.json', 'lossTraceSha256')]:
        A.require(C.sha((run/filename).read_bytes()) == value[key], 'saved '+filename+' differs')
    config = validate_config(value['config']); model = make_model(config, B.FIRST_MERGE+len(artifact['merges']), manifest['sequenceLength'])
    A.require(sum(p.numel() for p in model.parameters()) == value['parameterCount']
              and value['parameterBytes'] == value['parameterCount']*4, 'reference parameter measurements differ')
    baseline = metrics(model, data, manifest, config); load_weights(model, run/'weights.pt', value['weightsSha256'])
    learned = metrics(model, data, manifest, config)
    for actual, declared in [(baseline, value['untrainedSeedMetrics']), (learned, value['savedWeightMetrics'])]:
        for p in actual:
            A.require(equal_metric(actual[p], declared[p]), 'saved-weight or seed-control evaluation differs')
    check_data_files(data, manifest)
    return value, model


def export(archive, prepared, dataset, artifact, request, data, run, output, expected_sha, store=None):
    A.hash_value(expected_sha, 'expected run identity')
    value, model = evaluate(archive, prepared, dataset, artifact, request, data, run, expected_sha, store)
    A.require(not output.exists(), 'preserve existing reference export')
    A.require(not any(output.resolve().is_relative_to(p.resolve()) for p in (archive, prepared, dataset, data, run)), 'export cannot modify reference inputs')
    output.mkdir(parents=True); tensors = []; offset = 0
    with (output/'weights.fp32le').open('xb') as handle:
        for name, tensor in model.named_parameters():
            values = array.array('f', tensor.detach().cpu().reshape(-1).tolist())
            A.require(values.itemsize == 4, 'FP32 export width differs')
            if sys.byteorder != 'little': values.byteswap()
            raw = values.tobytes(); handle.write(raw)
            tensors.append({'name': name, 'shape': list(tensor.shape), 'offsetBytes': offset, 'lengthBytes': len(raw), 'sha256': C.sha(raw)})
            offset += len(raw)
    C.write_json(output/'tokenizer.json', artifact)
    with (output/'weights.fp32le').open('rb') as handle:
        for tensor in tensors:
            A.require(C.sha(handle.read(tensor['lengthBytes'])) == tensor['sha256'], 'saved FP32 tensor export differs')
        A.require(not handle.read(1), 'extra FP32 export bytes')
    receipt = A.seal({'schema': EXPORT, 'schemaVersion': 1, 'runSha256': expected_sha, 'config': value['config'],
                      'architecture': value['architecture'], 'sequenceLength': A.read(data/'manifest.json')['sequenceLength'],
                      'vocabularySize': B.FIRST_MERGE+len(artifact['merges']),
                      'precision': 'FP32-little-endian', 'tensorInventory': tensors, 'tiedOutput': 'tokens.weight',
                      'weightsSha256': C.sha((output/'weights.fp32le').read_bytes()), 'tokenizerSha256': artifact['contentSha256'],
                      'structuralTokenIds': B.SPECIAL_IDS, 'runtimeIntegration': False, 'nativeConsumerParity': False})
    C.write_json(output/'manifest.json', receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'train', 'evaluate', 'export'])
    for name in ('archive', 'prepared', 'dataset', 'tokenizer', 'splits', 'data'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--output', type=Path); parser.add_argument('--run', type=Path)
    parser.add_argument('--config', type=Path); parser.add_argument('--run-sha256')
    parser.add_argument('--sequence-length', type=int, default=256)
    parser.add_argument('--maximum-total-tokens', type=int, default=100_000_000)
    args = parser.parse_args(argv)
    try:
        artifact, request = A.read(args.tokenizer), A.read(args.splits)
        common = (args.archive, args.prepared, args.dataset, artifact, request)
        if args.action == 'prepare': result = prepare_data(*common, args.data, args.sequence_length, args.maximum_total_tokens)
        elif args.action == 'train':
            A.require(args.config is not None and args.output is not None, 'train requires exact config and output')
            result = train(*common, args.data, A.read(args.config), args.output)
        elif args.action == 'evaluate':
            A.require(args.run is not None, 'evaluate requires saved run')
            result = evaluate(*common, args.data, args.run, args.run_sha256)[0]
        else:
            A.require(args.run is not None and args.output is not None and args.run_sha256 is not None, 'export requires run, output and trusted run hash')
            result = export(*common, args.data, args.run, args.output, args.run_sha256)
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        print('REFUSED: '+str(error), file=sys.stderr); return 2
    print('WROTE/VERIFIED '+result['schema']+' '+result['contentSha256']); return 0


if __name__ == '__main__': raise SystemExit(main())
