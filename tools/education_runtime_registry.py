#!/usr/bin/env python3
"""Package reconstructed person education for explicit native world admission.

The caller supplies actual world-definition bytes, an explicit world owner, and
each person's independently reconstructible context/ledger/policy/source bank.
This packages those records; it does not generate people, profiles or competence.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import decision_authoring as A
import education_backgrounds as B
import education_curriculum as K
import education_learning as L

MAX_BYTES = 16 * 1024 * 1024
MAX_ROWS = 128
TICKS_PER_DAY = 216000
PRODUCER = 'education-runtime-registry-1'
ENTRY_FIELDS = {'context', 'ledger', 'policy', 'bank', 'asOfTime', 'teachers', 'maximumConcepts'}


def definition_bytes(raw, world_owner=None):
    A.require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, 'world definition bytes exceed bound')
    value = A.loads(raw.decode('utf-8'))
    A.require(isinstance(value, dict), 'world definition must be a JSON object')
    if 'worldOwner' in value:
        A.require(value['worldOwner'] == world_owner, 'world definition differs from explicit source owner')
    # Config.definitionSha256 uses tools/world_lab.py's canonical body, including ASCII escapes.
    canonical=json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',', ':'),allow_nan=False).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()


def build_registry(world_definition, world_owner, entries):
    world_sha = definition_bytes(world_definition, world_owner)
    K.fields(world_owner, {'id', 'seed'}, 'explicit world owner')
    for key in ('id', 'seed'): A.identifier(world_owner[key], 'explicit world ' + key)
    A.require(type(entries) is list and 1 <= len(entries) <= MAX_ROWS, 'registry requires bounded explicit people')
    rows, identifiers, bank_sha, archive_sha = [], set(), None, None
    for entry in entries:
        K.fields(entry, ENTRY_FIELDS, 'runtime person inputs')
        context, policy = entry['context'], entry['policy']
        # Export verifies the archive, bank, profile, schooling and every received ledger event.
        prior = L.export_runtime(entry['ledger'], entry['asOfTime'], context, policy, entry['bank'],
                                 entry['teachers'], entry['maximumConcepts'])
        A.require(policy['ticksPerDay'] == TICKS_PER_DAY, 'native county clock differs from History')
        A.require(context['plan']['worldOwner'] == world_owner
                  and context['backgrounds']['worldOwner'] == world_owner,
                  'source person belongs to a different world owner')
        person_id = prior['owner']['id']
        A.require(person_id not in identifiers, 'duplicate source person id in registry')
        identifiers.add(person_id)
        if bank_sha is None:
            bank_sha, archive_sha = prior['sourceBankSha256'], prior['contextRefs']['sourceArchiveSha256']
        A.require(prior['sourceBankSha256'] == bank_sha and prior['contextRefs']['sourceArchiveSha256'] == archive_sha,
                  'registry source bank or archive differs between people')
        refs = prior['contextRefs']
        bindings = {'worldSha256': world_sha, 'profileSha256': refs['profileSha256'],
                    'sourceBankSha256': bank_sha, 'backgroundsSha256': refs['backgroundsSha256'],
                    'personEducationSha256': refs['personEducationSha256'],
                    'educationalExposuresSha256': refs['educationalExposuresSha256'],
                    'sourceArchiveSha256': archive_sha}
        row = B.seal({'schema': 'speakeasy-person-education-runtime-registry-row/1', 'personId': person_id,
                      'sourceProfile': copy.deepcopy(context['profile']), 'sourceProfileSha256': A.digest(context['profile']),
                      'birthProfileProvenance': {'owner': 'speakeasy-source-reconstructed-person-history',
                          'worldOwner': copy.deepcopy(world_owner), 'profileSha256': refs['profileSha256'],
                          'backgroundsSha256': refs['backgroundsSha256'], 'personEducationSha256': refs['personEducationSha256']},
                      'bindings': bindings, 'prior': prior, 'rawPriorSha256': A.digest(prior)})
        A.require(row['sourceProfileSha256'] == prior['owner']['version'], 'source birth profile differs from prior owner')
        rows.append(row)
    rows.sort(key=lambda row: row['personId'])
    result = B.seal({'schema': 'speakeasy-person-education-runtime-registry/1', 'producer': PRODUCER,
                     'worldOwner': copy.deepcopy(world_owner), 'worldDefinitionSha256': world_sha,
                     'sourceBankSha256': bank_sha, 'sourceArchiveSha256': archive_sha, 'rows': rows,
                     'standing': 'source-reconstructed-explicit-person-registry', **L.AUTHORITY})
    A.require(len(A.encoded(result)) <= MAX_BYTES, 'runtime registry exceeds byte bound')
    return result


def verify_registry(registry, world_definition, world_owner, entries):
    B.checked(registry, 'runtime registry')
    expected = build_registry(world_definition, world_owner, entries)
    A.require(registry == expected, 'runtime registry differs from independent source reconstruction')
    return copy.deepcopy(expected)


def read_entries(path):
    rows = A.read(path)
    A.require(type(rows) is list and 1 <= len(rows) <= MAX_ROWS, 'explicit person input paths must be bounded')
    result = []
    for row in rows:
        K.fields(row, ENTRY_FIELDS, 'runtime person paths')
        teachers = None
        if row['teachers'] is not None:
            teacher_paths = A.read(Path(row['teachers']))
            A.require(isinstance(teacher_paths, dict), 'teacher paths must be hash keyed')
            teachers = {}
            for digest, paths in teacher_paths.items():
                A.hash_value(digest, 'teacher snapshot hash')
                K.fields(paths, {'ledger', 'context', 'policy'}, 'teacher paths')
                teachers[digest] = {'ledger': A.read(Path(paths['ledger'])),
                    'context': L.read_context(Path(paths['context'])), 'policy': A.read(Path(paths['policy']))}
        result.append({'context': L.read_context(Path(row['context'])), 'ledger': A.read(Path(row['ledger'])),
                       'policy': A.read(Path(row['policy'])), 'bank': Path(row['bank']),
                       'asOfTime': A.read(Path(row['asOfTime'])), 'teachers': teachers,
                       'maximumConcepts': row['maximumConcepts']})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'verify'])
    parser.add_argument('--world-definition', type=Path, required=True)
    parser.add_argument('--world-owner', type=Path, required=True)
    parser.add_argument('--persons', type=Path, required=True)
    parser.add_argument('--registry', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        raw, owner, entries = args.world_definition.read_bytes(), A.read(args.world_owner), read_entries(args.persons)
        if args.action == 'verify':
            A.require(args.registry is not None, 'verify requires registry path')
            value = verify_registry(A.read(args.registry), raw, owner, entries)
        else: value = build_registry(raw, owner, entries)
        status = B.write_immutable(args.out, value)
    except (ValueError, OSError, UnicodeError, ET.ParseError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr); return 2
    print(status + ' ' + str(args.out) + ' ' + value['contentSha256']); return 0


if __name__ == '__main__': raise SystemExit(main())
