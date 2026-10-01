#!/usr/bin/env python3
"""Export and reconstruct admitted educational next-token data with a frozen BPE."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

import byte_tokenizer as B
import decision_authoring as A
import education_corpus as C
import education_assessment as G

PARTITIONS = ('train', 'validation', 'test')
SCHEMA = 'speakeasy-educational-tokenized-data'
MAX_TOTAL_TOKENS = 200_000_000


def partition_plan(request, sources, rows):
    A.schema(request, 'speakeasy-educational-source-splits')
    A.fields(request, {'schema', 'schemaVersion', 'sourceFamilies', 'splits'}, 'source split request')
    A.fields(request['splits'], set(PARTITIONS), 'source partitions')
    A.require(isinstance(request['sourceFamilies'], list) and request['sourceFamilies'], 'source families required')
    families, source_family, family_partition = {}, {}, {}
    available = {r['sourceId'] for r in rows}
    for family in request['sourceFamilies']:
        A.fields(family, {'id', 'sourceIds'}, 'source family')
        A.identifier(family['id'], 'source family id')
        A.require(family['id'] not in families, 'duplicate source family')
        ids = family['sourceIds']
        A.require(isinstance(ids, list) and ids and len(ids) == len(set(ids)), 'unique family source IDs required')
        for identity in ids:
            A.identifier(identity, 'family source id')
            A.require(identity in available and identity not in source_family, 'source missing or assigned to multiple families')
            source_family[identity] = family['id']
        families[family['id']] = sorted(ids)
    A.require(set(source_family) == available, 'source family coverage differs from admitted passages')
    for partition in PARTITIONS:
        ids = request['splits'][partition]
        A.require(isinstance(ids, list) and len(ids) == len(set(ids)), 'partition family IDs must be unique')
        for identity in ids:
            A.identifier(identity, 'partition source family')
            A.require(identity in families and identity not in family_partition, 'source family is unknown or crosses partitions')
            family_partition[identity] = partition
    A.require(set(family_partition) == set(families), 'every source family needs an explicit partition')
    # Different revisions of a publisher book, and shared modules within bundles,
    # cannot be relabelled as independent families by the caller's split request.
    lineage = {}
    for source in sources:
        if source['id'] not in source_family:
            continue
        key = ('gutenberg', source['bookId']) if source['provider'] == 'gutenberg' else ('publisher-repository', source['repository'])
        prior = lineage.setdefault(key, source_family[source['id']])
        A.require(prior == source_family[source['id']], 'same book lineage crosses source families')
    shared = {}
    for row in rows:
        family = source_family[row['sourceId']]
        prior = shared.setdefault(row['extractionSha256'], family)
        A.require(prior == family, 'shared source module crosses families')
        # Exact duplicate passages can also cross different extraction boundaries.
        prior = shared.setdefault('passage:' + C.sha(row['text'].encode()), family)
        A.require(prior == family, 'duplicate educational passage crosses families')
    normalized = {**request, 'sourceFamilies': [{'id': f, 'sourceIds': families[f]} for f in sorted(families)],
                  'splits': {p: sorted(request['splits'][p]) for p in PARTITIONS}}
    return normalized, source_family, family_partition


def validated_inputs(archive, prepared, dataset, artifact, request, store=None):
    admitted = C.validate_admitted(archive, prepared, dataset, store)
    data = (dataset / 'texts.jsonl').read_bytes()
    A.require(C.sha(data) == admitted['textsSha256'], 'admitted text bytes changed after validation')
    rows = [A.loads(line.decode('utf-8')) for line in data.splitlines() if line]
    A.require(len(rows) == admitted['trainingRows'], 'admitted row count differs')
    proposal = A.read(prepared / 'review-proposal.json')
    body = dict(proposal); declared = body.pop('contentSha256', None)
    A.require(declared == admitted['sourceReviewSha256'] == A.digest(body), 'review changed after validation')
    acquisition_data = (archive / 'acquisition.json').read_bytes()
    A.require(C.sha(acquisition_data) == proposal['sourceArchiveSha256'], 'source archive changed after validation')
    sources = A.loads(acquisition_data.decode('utf-8'))['sources']
    tokenizer = B.Tokenizer(artifact)
    normalized, source_family, family_partition = partition_plan(request, sources, rows)
    # Use the assessment owner's reconstructed content closure as well as the
    # passage inventory. Renamed XML IDs cannot isolate copied question/answers.
    components = G.source_components(sources, archive)
    G.family_request(normalized, components)
    # This exporter never fits vocabulary. Refuse known held-out passage/module/book
    # fingerprints in the supplied tokenizer's original fitting-corpus metadata.
    fitting = set(artifact['corpus']['segmentSha256'])
    held_out = set()
    held_out_sources = {s for s, f in source_family.items() if family_partition[f] != 'train'}
    for row in rows:
        if row['sourceId'] in held_out_sources:
            held_out.update((C.sha(row['text'].encode()), row['extractionSha256']))
    for source in sources:
        if source['id'] in held_out_sources:
            held_out.update(f['sha256'] for f in source['files']
                            if f['path'].endswith('.cnxml')
                            or Path(f['path']).name in {'source.txt', 'source.tex', 'source.html'})
    A.require(not fitting.intersection(held_out), 'frozen tokenizer fitting corpus contains held-out educational text')
    rows.sort(key=lambda r: (r['sourceId'], r['sourcePath'], r['startCharacter'], r['contentSha256']))
    return admitted, rows, tokenizer, normalized, source_family, family_partition


def sequence_blocks(rows, tokenizer, source_family, family_partition, block_tokens, max_tokens):
    A.require(type(block_tokens) is int and 16 <= block_tokens <= 4096, 'invalid token block bound')
    A.require(type(max_tokens) is int and 1 <= max_tokens <= MAX_TOTAL_TOKENS, 'invalid total token bound')
    total = 0
    special = B.SPECIAL_IDS
    for row in rows:
        payload = tokenizer.encode_text(row['text'])
        raw = row['text'].encode('utf-8')
        A.require(tokenizer.decode_bytes(payload) == raw, 'educational tokenizer byte parity differs')
        total += len(payload) + 1  # Every real next-token target, including EOS, exactly once.
        A.require(total <= max_tokens, 'educational token export exceeds declared total token bound')
        byte_offsets = [0]
        for token in payload:
            byte_offsets.append(byte_offsets[-1] + len(tokenizer.vocabulary[token]))
        sequence = [special['bos'], *payload, special['eos']]
        family = source_family[row['sourceId']]
        for start in range(0, len(sequence) - 1, block_tokens):
            count = min(block_tokens, len(sequence) - 1 - start)
            end = start + count
            begin_byte = byte_offsets[max(0, min(len(payload), start - 1))]
            end_byte = byte_offsets[min(len(payload), end)]
            block = {'schema': 'speakeasy-educational-sequence-block', 'schemaVersion': 1,
                     'partition': family_partition[family], 'sourceFamilyId': family,
                     'sourceId': row['sourceId'], 'sourceVersion': row['sourceVersion'],
                     'sourcePath': row['sourcePath'], 'sourceSha256': row['sourceSha256'],
                     'extractionSha256': row['extractionSha256'], 'rowSha256': row['contentSha256'],
                     'rowTextSha256': C.sha(raw), 'sourceStartCharacter': row['startCharacter'],
                     'sourceEndCharacter': row['endCharacter'], 'rowByteStart': begin_byte, 'rowByteEnd': end_byte,
                     'sequenceStartToken': start, 'sequenceEndToken': end,
                     'inputIds': sequence[start:end] + [special['pad']] * (block_tokens - count),
                     'targetIds': sequence[start + 1:end + 1] + [special['pad']] * (block_tokens - count),
                     'lossMask': [True] * count + [False] * (block_tokens - count)}
            yield family_partition[family], A.seal(block)


def manifest(admitted, artifact, request, partitions, block_tokens, max_tokens):
    missing = [p for p in PARTITIONS if partitions[p]['blocks'] == 0]
    return A.seal({'schema': SCHEMA, 'schemaVersion': 1, 'task': 'shared-cognitive-base',
                  'objective': 'next-token-passage-bytes', 'sourceDatasetSha256': A.digest(admitted),
                  'sourceReviewSha256': admitted['sourceReviewSha256'],
                  'approvalReceiptSha256': admitted['approvalReceiptSha256'],
                  'sourceAdmissionKind': admitted.get('sourceAdmissionKind', 'reviewed'),
                  'sourceEvaluationReceiptSha256': admitted.get('evaluationReceiptSha256'),
                  'admittedTextsSha256': admitted['textsSha256'], 'tokenizerSha256': artifact['contentSha256'],
                  'request': request, 'blockTokens': block_tokens, 'maximumTotalTokens': max_tokens,
                  'serialization': 'canonical-jsonl-utf8-v1', 'envelope': ['bos', 'eos'],
                  'loss': 'next-token-shift-with-true-eos-and-masked-padding', 'partitions': partitions,
                  'release': {'status': 'excluded' if missing else 'ready-for-reference-training',
                              'missingPartitions': missing},
                  'personalAcquisitionAuthority': False, 'currentWorldAuthority': False,
                  'nativeActionAuthority': False, 'opposingAssociativeModelIndependent': True,
                  'runtimeIntegration': False, 'trainedWeights': False,
                  'limits': ['source-content-admission-does-not-authorize-person-knowledge',
                             'caller-supplied-tokenizer-is-frozen-and-never-refitted',
                             'original-fitting-exposure-checks-known-source-fingerprints',
                             'prepared-source-passages-have-independent-bos-eos-boundaries',
                             'no-trained-model-inference-or-java-parity-claim']})


def reconstructed(admitted, rows, tokenizer, artifact, request, source_family, family_partition,
                  block_tokens, max_tokens, output, checking=False):
    handles, hashes, counts = {}, {}, {}
    try:
        for partition in PARTITIONS:
            path = output / (partition + '.jsonl')
            handles[partition] = path.open('rb' if checking else 'xb')
            hashes[partition] = hashlib.sha256()
            counts[partition] = {'path': path.name, 'blocks': 0, 'lossTokens': 0}
        for partition, block in sequence_blocks(rows, tokenizer, source_family, family_partition, block_tokens, max_tokens):
            data = A.encoded(block) + b'\n'
            if checking:
                A.require(handles[partition].readline() == data, 'saved educational tokens or provenance differ')
            else:
                handles[partition].write(data)
            hashes[partition].update(data)
            counts[partition]['blocks'] += 1
            counts[partition]['lossTokens'] += sum(block['lossMask'])
        for partition in PARTITIONS:
            if checking:
                A.require(not handles[partition].read(1), 'extra saved educational sequence blocks')
            counts[partition]['sha256'] = hashes[partition].hexdigest()
    finally:
        for handle in handles.values():
            handle.close()
    return manifest(admitted, artifact, request, counts, block_tokens, max_tokens)


def require_release(value):
    A.require(value['release']['status'] == 'ready-for-reference-training',
              'educational dataset release refused: missing partitions ' + ', '.join(value['release']['missingPartitions']))


def export(archive, prepared, dataset, artifact, request, output, block_tokens=256,
           max_tokens=20_000_000, require_ready=False, store=None):
    inputs = validated_inputs(archive, prepared, dataset, artifact, request, store)
    admitted, rows, tokenizer, normalized, source_family, family_partition = inputs
    A.require(not output.exists(), 'preserve existing educational tokenization')
    A.require(not any(output.resolve().is_relative_to(p.resolve()) for p in (archive, prepared, dataset)),
              'output cannot modify an immutable educational input directory')
    if require_ready:
        A.require(all(normalized['splits'][p] for p in PARTITIONS), 'educational dataset release refused: missing partitions')
    output.mkdir(parents=True)
    C.write_json(output / 'manifest.json', {'schema': 'speakeasy-educational-tokenization-incomplete/1',
                                          'release': {'status': 'excluded'}, 'reason': 'export-in-progress'})
    C.write_json(output / 'tokenizer.json', artifact)
    value = reconstructed(admitted, rows, tokenizer, artifact, normalized, source_family, family_partition,
                          block_tokens, max_tokens, output)
    if require_ready:
        require_release(value)
    # Revalidate admission and reconstruct the saved bytes before replacing the
    # incomplete manifest. A failed reconstruction leaves an excluded output.
    checked = validated_inputs(archive, prepared, dataset, artifact, request, store)
    actual_admitted, actual_rows, actual_tokenizer, actual_request, actual_families, actual_partitions = checked
    actual = reconstructed(actual_admitted, actual_rows, actual_tokenizer, artifact, actual_request,
                           actual_families, actual_partitions, block_tokens, max_tokens, output, checking=True)
    A.require(value == actual, 'educational export changed during saved reconstruction')
    C.write_json(output / 'manifest.json', value)
    return value


def verify(archive, prepared, dataset, artifact, request, output, require_ready=False, store=None):
    value = A.read(output / 'manifest.json')
    A.unseal(value, SCHEMA)
    expected_files = {'manifest.json', 'tokenizer.json', *[p + '.jsonl' for p in PARTITIONS]}
    A.require({p.name for p in output.iterdir()} == expected_files, 'tokenization file inventory differs')
    A.require((output / 'tokenizer.json').read_bytes() == A.encoded(artifact) + b'\n', 'saved frozen tokenizer differs')
    admitted, rows, tokenizer, normalized, source_family, family_partition = validated_inputs(
        archive, prepared, dataset, artifact, request, store)
    expected = reconstructed(admitted, rows, tokenizer, artifact, normalized, source_family, family_partition,
                             value.get('blockTokens'), value.get('maximumTotalTokens'), output, checking=True)
    A.require(value == expected, 'saved tokenization manifest differs from source reconstruction')
    if require_ready:
        require_release(value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['export', 'verify'])
    for name in ('archive', 'prepared', 'dataset', 'tokenizer', 'splits', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--block-tokens', type=int, default=256)
    parser.add_argument('--maximum-total-tokens', type=int, default=20_000_000)
    parser.add_argument('--require-ready', action='store_true')
    args = parser.parse_args(argv)
    try:
        paths = (args.archive, args.prepared, args.dataset)
        values = (A.read(args.tokenizer), A.read(args.splits), args.output)
        if args.action == 'export':
            value = export(*paths, *values, args.block_tokens, args.maximum_total_tokens, args.require_ready)
        else:
            value = verify(*paths, *values, args.require_ready)
        print(value['contentSha256'], value['release']['status'],
              {p: value['partitions'][p]['blocks'] for p in PARTITIONS})
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
