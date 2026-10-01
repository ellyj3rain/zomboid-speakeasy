#!/usr/bin/env python3
"""Derive textbook assessments and grade exact learner responses automatically.

``bank --archive ARCHIVE --out NEW_DIRECTORY [--curriculum JSON]`` preserves
every CNXML exercise, its original MathML, private solution and coverage reason.
``verify`` reconstructs the complete bank from the immutable publisher archive.
``grade --bank BANK --responses JSONL --out NEW_JSONL`` performs that verification
before grading. Learners receive only ``learner-items.jsonl``; ``assessments.jsonl``
contains answer evidence and stays on the evaluator side.

A response uses schema ``speakeasy-educational-assessment-response/1`` and names
itemSha256, learner {kind, id, version}, sessionId, asOfTime {clock, value},
learningMode, assistanceEvidenceRefs, evidenceRefs and response (a string).
Optional gradingPolicy is an explicit caller-owned numeric tolerance policy.
Absolute tolerance uses the versioned unit table's canonical base unit;
relative tolerance is a fraction of the absolute source value in that unit.
Grades describe a response at its recorded time; they do not confer native skill,
world knowledge or lasting mastery. Unknown prose is never scored as incorrect.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from datetime import datetime
from fractions import Fraction
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

import decision_authoring as A
import education_corpus as C
import education_curriculum as K

VERSION = 4
FAMILY_PASSAGE_CHARACTERS = 4096
CN = '{http://cnx.rice.edu/cnxml}'
MM = '{http://www.w3.org/1998/Math/MathML}'
SPLITS = {'train', 'validation', 'test'}
MODES = {'independent-retrieval', 'hinted-retrieval', 'tutoring',
         'passive-learning', 'cross-learning'}
# These exact conversion constants are a versioned grading rule, not an inferred
# source tolerance. Unsupported units and affine conversions remain ungradable.
UNITS = {
    '': ('dimensionless', Fraction(1)), '%': ('percent', Fraction(1)),
    '$': ('USD', Fraction(1)), 'USD': ('USD', Fraction(1)),
    'm': ('length', Fraction(1)), 'cm': ('length', Fraction(1, 100)),
    'mm': ('length', Fraction(1, 1000)), 'km': ('length', Fraction(1000)),
    's': ('time', Fraction(1)), 'sec': ('time', Fraction(1)),
    'min': ('time', Fraction(60)), 'h': ('time', Fraction(3600)),
    'kg': ('mass', Fraction(1)), 'g': ('mass', Fraction(1, 1000)),
    'mg': ('mass', Fraction(1, 1000000)),
    'L': ('volume', Fraction(1)), 'mL': ('volume', Fraction(1, 1000)),
    'm/s': ('speed', Fraction(1)), 'km/h': ('speed', Fraction(5, 18)),
    'm/s^2': ('acceleration', Fraction(1)),
    'N': ('force', Fraction(1)), 'J': ('energy', Fraction(1)),
    'W': ('power', Fraction(1)), 'Pa': ('pressure', Fraction(1)),
    'kPa': ('pressure', Fraction(1000)), 'Hz': ('frequency', Fraction(1)),
    'K': ('temperature-K', Fraction(1)), '°C': ('temperature-C', Fraction(1)),
}
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'


def normalized(text):
    return re.sub(r'\s+', ' ', text).strip()


def question_content(element):
    """Content identity ignores source element IDs and cosmetic XML whitespace.

    Original XML, IDs and hashes remain in the assessment provenance. MathML,
    semantic attributes, child order and text stay in this comparison identity.
    """
    attributes = {key: value for key, value in sorted(element.attrib.items())
                  if key.rsplit('}', 1)[-1] != 'id'}
    return {'tag': element.tag, 'attributes': attributes,
            'text': normalized(element.text or ''),
            'children': [{'content': question_content(child),
                          'tail': normalized(child.tail or '')} for child in element]}


def ratio(value):
    return {'numerator': value.numerator, 'denominator': value.denominator}


def fraction(value):
    A.require(isinstance(value, dict) and set(value) == {'numerator', 'denominator'}
              and type(value['numerator']) is int and type(value['denominator']) is int
              and value['denominator'] > 0, 'invalid exact numeric quantity')
    return Fraction(value['numerator'], value['denominator'])


def math_text(node):
    """Render only structurally understood MathML; unsupported algebra fails closed."""
    name = node.tag.removeprefix(MM)
    if name in {'mn', 'mo', 'mi', 'mtext'}:
        if len(node):
            raise ValueError('unsupported nested mathematical token')
        return node.text or ''
    if name == 'mspace':
        return ' '
    if name == 'mfrac' and len(node) == 2:
        left, right = (normalized(math_text(v)) for v in node)
        if re.fullmatch(NUMBER, left) and re.fullmatch(NUMBER, right):
            # Parentheses retain the fraction boundary. Concatenating a preceding
            # whole number with its numerator would invent a different answer.
            return '(' + left + '/' + right + ')'
        raise ValueError('fraction is not an explicit numeric scalar')
    if name == 'msup' and len(node) == 2:
        return math_text(node[0]) + '^' + math_text(node[1])
    if name in {'math', 'mrow', 'mstyle', 'semantics'}:
        if name == 'semantics' and len(node) != 1:
            raise ValueError('mathematics has multiple semantic representations')
        parts = [node.text or '']
        previous = None
        for child in node:
            if previous is not None and previous.tag == MM + 'mn' and child.tag == MM + 'mn':
                parts.append(' ')
            parts.extend((math_text(child), child.tail or ''))
            previous = child
        return ''.join(parts)
    raise ValueError('unsupported mathematical structure')


def answer_text(node):
    if node.tag.startswith(MM):
        return math_text(node)
    if node.tag in {CN + 'title', CN + 'label'}:
        return ''
    if node.tag in {CN + 'figure', CN + 'table', CN + 'media', CN + 'image', CN + 'list'}:
        raise ValueError('solution is not a single explicit scalar')
    parts = [node.text or '']
    for child in node:
        if child.tag.startswith(MM):
            parts.append(' ')
        parts.extend((answer_text(child), child.tail or ''))
        if child.tag == CN + 'para' or child.tag.startswith(MM):
            parts.append(' ')
    return ''.join(parts)


def quantity(text):
    text = normalized(text).replace('−', '-').replace('–', '-').replace('\u00a0', ' ')
    # An explicit terminal punctuation mark is not part of a number or unit.
    if text.endswith('.') and not re.fullmatch(NUMBER, text):
        text = text[:-1].rstrip()
    if text.startswith('$'):
        text = text[1:].strip() + ' $'
    parenthesized = re.fullmatch(r'([+-]?)\((' + NUMBER + r'\s*/\s*' + NUMBER + r')\)(.*)', text)
    if parenthesized:
        text = parenthesized[1] + parenthesized[2] + parenthesized[3]
    scientific = re.fullmatch(r'(' + NUMBER + r')\s*[×⋅·]\s*10\s*\^\s*([+-]?\d+)(.*)', text)
    if scientific:
        exponent = int(scientific[2])
        if abs(exponent) > 100:
            return None
        base = Fraction(scientific[1]) * Fraction(10) ** exponent
        text = str(base) + scientific[3]
    match = re.fullmatch(r'(' + NUMBER + r')(?:\s*/\s*(' + NUMBER + r'))?\s*(.*)', text)
    if not match:
        return None
    try:
        value = Fraction(match[1])
        if match[2] is not None:
            value /= Fraction(match[2])
    except (ValueError, ZeroDivisionError, OverflowError):
        return None
    unit = normalized(match[3]).replace('²', '^2')
    if unit not in UNITS:
        return None
    dimension, scale = UNITS[unit]
    return {'value': ratio(value), 'unit': unit, 'dimension': dimension,
            'baseValue': ratio(value * scale), 'literal': text,
            'unitPolicy': 'explicit-exact-unit-table/1'}


def choice_options(problem):
    lists = list(problem.iter(CN + 'list'))
    if len(lists) != 1:
        return None
    node = lists[0]
    if (node.get('list-type') != 'enumerated'
            or node.get('number-style') not in {'lower-alpha', 'upper-alpha'}):
        return None
    items = node.findall(CN + 'item')
    if not 2 <= len(items) <= 26:
        return None
    options = [{'key': chr(65 + i), 'xml': xml(item),
                'text': None if any(v.tag.startswith(MM) for v in item.iter())
                else normalized(''.join(item.itertext()))} for i, item in enumerate(items)]
    if len({v['xml'] if v['text'] is None else v['text'].casefold() for v in options}) != len(options):
        return None
    return options


def multipart(problems, solutions):
    if len(problems) != 1 or len(solutions) > 1:
        return True
    for node in [*problems, *solutions]:
        text = ''.join(node.itertext())
        if len({v[0] for v in re.finditer(r'[ⓐ-ⓩ]|\([a-z]\)', text)}) > 1:
            return True
        for listing in node.iter(CN + 'list'):
            if len(listing.findall(CN + 'item')) > 1 and (node in solutions
                    or listing.get('list-type') == 'labeled-item'):
                return True
    return False


def target(problems, solutions, identities_present=True):
    if not solutions:
        return None, 'missing-source-answer'
    if multipart(problems, solutions):
        return None, 'multipart-answer-ambiguous'
    if not identities_present:
        return None, 'missing-source-element-identity'
    if len(problems) != 1 or len(solutions) != 1:
        return None, 'source-answer-structure-ambiguous'
    options = choice_options(problems[0])
    raw = normalized(''.join(solutions[0].itertext()))
    try:
        rendered = normalized(answer_text(solutions[0]))
    except ValueError:
        rendered = None
    if options and rendered is not None:
        key = re.fullmatch(r'\(?([A-Za-z])\)?\.?', rendered)
        declaration = re.match(r'^The correct answer is \(?([A-Za-z])\)?[\s.].*$', rendered, re.I)
        key = (key or declaration)
        if key and key[1].upper() in {v['key'] for v in options}:
            return {'kind': 'multiple-choice', 'correctKey': key[1].upper(), 'options': options,
                    'sourceAnswerLiteral': rendered,
                    'derivation': 'single-source-choice-key'}, 'automatically-gradable'
    numeric = quantity(rendered) if rendered is not None else None
    if numeric is not None and not options:
        return {'kind': 'numeric', **numeric, 'derivation': 'single-source-numeric-scalar'}, 'automatically-gradable'
    return None, 'source-answer-not-automatically-gradable' if raw else 'empty-source-answer'


def xml(node):
    retained = copy.deepcopy(node)
    retained.tail = None
    return ET.tostring(retained, encoding='unicode')


def safe_context(node):
    return not any(v.tag in {CN + 'solution', CN + 'exercise', CN + 'problem'} for v in node.iter())


def context_for(exercise, parents):
    """Keep source instruction and section titles without other exercises or solutions."""
    context, parent = [], parents.get(exercise)
    ancestors = []
    while parent is not None:
        ancestors.append(parent)
        parent = parents.get(parent)
    for parent in reversed(ancestors):
        title = parent.find(CN + 'title')
        if title is not None and safe_context(title):
            context.append(xml(title))
    direct = parents.get(exercise)
    if direct is not None:
        siblings = list(direct)
        for previous in reversed(siblings[:siblings.index(exercise)]):
            if previous.tag == CN + 'para' and safe_context(previous):
                context.append(xml(previous))
                break
    for node in exercise:
        if node.tag in {CN + 'title', CN + 'label'} and safe_context(node):
            context.append(xml(node))
    return list(dict.fromkeys(context))


def source_components(sources, archive):
    """Join copies, revisions and shared teaching material before assigning splits."""
    ids = {source['id'] for source in sources}
    parent = {identity: identity for identity in ids}
    fingerprints, inventories = {}, []

    def root(identity):
        while parent[identity] != identity:
            parent[identity] = parent[parent[identity]]
            identity = parent[identity]
        return identity

    def bind(kind, digest, identity):
        owners = fingerprints.setdefault((kind, digest), set())
        if owners:
            first = next(iter(owners))
            left, right = sorted((root(identity), root(first)))
            parent[right] = left
        owners.add(identity)

    for source in sorted(sources, key=lambda s: s['id']):
        identity = source['id']
        lineage = ({'provider': 'gutenberg', 'bookId': source['bookId']}
                   if source['provider'] == 'gutenberg' else
                   {'provider': source['provider'], 'repository': source['repository']})
        bind('publisher-book-lineage', A.digest(lineage), identity)
        bind('publisher-revision', A.digest({'provider': source['provider'],
                                           'version': source['sourceVersion']}), identity)
        bodies, extractions, passages, exercise_pairs = [], [], [], []
        for entry, text, _ in C.texts(source, archive):
            bodies.append(entry['sha256'])
            extraction = C.sha(text.encode())
            extractions.append(extraction)
            bind('source-body', entry['sha256'], identity)
            bind('source-module-extraction', extraction, identity)
            for start in range(0, len(text), FAMILY_PASSAGE_CHARACTERS):
                passage = text[start:start + FAMILY_PASSAGE_CHARACTERS]
                if passage.strip():
                    digest = C.sha(passage.encode())
                    passages.append(digest)
                    bind('source-passage', digest, identity)
            if entry['path'].endswith('.cnxml'):
                content = ET.fromstring(C.local_path(archive, entry['path']).read_bytes()).find(CN + 'content')
                for exercise in content.iter(CN + 'exercise'):
                    problems, solutions = exercise.findall(CN + 'problem'), exercise.findall(CN + 'solution')
                    if problems and solutions:
                        # Bind the complete question/answer pair together. A bare
                        # answer such as "B" cannot merge unrelated textbooks.
                        digest = A.digest({'problems': [question_content(v) for v in problems],
                                           'solutions': [question_content(v) for v in solutions]})
                        exercise_pairs.append(digest)
                        bind('source-exercise-problem-solution', digest, identity)
        inventories.append({'sourceId': identity, 'sourceVersion': source['sourceVersion'],
                            'publisherBookLineage': lineage,
                            'sourceBodiesSha256': A.digest(sorted(bodies)),
                            'moduleExtractionsSha256': A.digest(sorted(extractions)),
                            'fullPassagesSha256': A.digest(sorted(passages)),
                            'problemSolutionPairsSha256': A.digest(sorted(exercise_pairs))})
    groups = {}
    for identity in sorted(ids):
        groups.setdefault(root(identity), []).append(identity)
    families = [{'id': 'family-' + A.digest(members)[:16], 'sourceIds': members}
                for members in groups.values()]
    families.sort(key=lambda family: family['id'])
    edges = [{'kind': kind, 'sha256': digest, 'sourceIds': sorted(owners)}
             for (kind, digest), owners in fingerprints.items() if len(owners) > 1]
    edges.sort(key=lambda edge: (edge['kind'], edge['sha256'], edge['sourceIds']))
    return A.seal({'schema': 'speakeasy-educational-source-family-components/1',
                   'passageCharacters': FAMILY_PASSAGE_CHARACTERS,
                   'sourceFamilies': families, 'sourceInventories': inventories, 'sharedEvidence': edges,
                   'derivation': 'publisher-lineage-revision-and-shared-source-content/2'})


def family_request(request, components):
    """Accept the foundation owner's source-family request and prove component closure."""
    A.require(isinstance(request, dict) and set(request) == {'schema', 'schemaVersion', 'sourceFamilies', 'splits'}
              and request['schema'] == 'speakeasy-educational-source-splits'
              and request['schemaVersion'] == 1, 'unsupported foundation source-family request')
    expected_ids = {identity for family in components['sourceFamilies'] for identity in family['sourceIds']}
    A.require(isinstance(request['sourceFamilies'], list) and request['sourceFamilies'], 'source families required')
    source_family, families = {}, {}
    for family in request['sourceFamilies']:
        A.require(isinstance(family, dict) and set(family) == {'id', 'sourceIds'}, 'source family fields differ')
        A.identifier(family['id'], 'source family id')
        A.require(family['id'] not in families and isinstance(family['sourceIds'], list) and family['sourceIds'],
                  'source family must have unique identity and members')
        for identity in family['sourceIds']:
            A.identifier(identity, 'family source id')
            A.require(identity in expected_ids and identity not in source_family, 'source family coverage differs')
            source_family[identity] = family['id']
        families[family['id']] = sorted(family['sourceIds'])
    A.require(set(source_family) == expected_ids, 'source family coverage differs')
    for component in components['sourceFamilies']:
        A.require(len({source_family[identity] for identity in component['sourceIds']}) == 1,
                  'related source component crosses caller source families')
    A.require(isinstance(request['splits'], dict) and set(request['splits']) == SPLITS,
              'source split partitions differ')
    family_partition = {}
    for split, selected in request['splits'].items():
        A.require(isinstance(selected, list), 'source split families must be a list')
        for identity in selected:
            A.identifier(identity, 'partition source family')
            A.require(identity in families and identity not in family_partition, 'source family crosses partitions')
            family_partition[identity] = split
    A.require(set(family_partition) == set(families), 'every source family needs an explicit partition')
    normalized_request = {'schema': request['schema'], 'schemaVersion': 1,
                          'sourceFamilies': [{'id': key, 'sourceIds': families[key]} for key in sorted(families)],
                          'splits': {key: sorted(request['splits'][key]) for key in sorted(SPLITS)}}
    assignments = {identity: family_partition[family] for identity, family in source_family.items()}
    return normalized_request, assignments


def source_splits(sources, policy=None, *, archive=None, components=None):
    A.require(archive is not None or components is not None, 'source splits need actual archived content')
    components = components or source_components(sources, archive)
    ids = {s['id'] for s in sources}
    # A preserved normalized policy always reconstructs its original caller request.
    declared = policy if isinstance(policy, dict) and policy.get('schema') == 'speakeasy-educational-source-splits/2' else None
    request = declared['request'] if declared is not None else policy
    A.require(request is None or isinstance(request, dict), 'source split policy must be an object')
    if request is None:
        assignments = {}
        for family in components['sourceFamilies']:
            bucket = int(A.digest(family['sourceIds'])[:8], 16) % 100
            split = 'train' if bucket < 80 else 'validation' if bucket < 90 else 'test'
            assignments.update({identity: split for identity in family['sourceIds']})
        owner = 'deterministic-source-family-components/1'
    elif request.get('schema') == 'speakeasy-educational-source-splits':
        request, assignments = family_request(request, components)
        owner = 'caller:foundation-source-family-request'
    else:
        A.require(isinstance(request, dict) and set(request) == {'schema', 'owner', 'assignments'}
                  and request['schema'] == 'speakeasy-educational-source-splits/1', 'unsupported source split policy')
        A.identifier(request['owner'], 'split policy owner')
        assignments, owner = request['assignments'], request['owner']
    A.require(isinstance(assignments, dict) and set(assignments) == ids
              and all(isinstance(v, str) and v in SPLITS for v in assignments.values()),
              'source splits must assign every whole source exactly once')
    for component in components['sourceFamilies']:
        A.require(len({assignments[identity] for identity in component['sourceIds']}) == 1,
                  'related source component crosses partitions')
    result = {'schema': 'speakeasy-educational-source-splits/2', 'owner': owner,
              'assignments': dict(sorted(assignments.items())), 'sourceFamilies': components['sourceFamilies'],
              'familyAssignments': {family['id']: assignments[family['sourceIds'][0]]
                                    for family in components['sourceFamilies']},
              'sourceFamilyComponentsSha256': components['contentSha256'], 'request': copy.deepcopy(request)}
    if declared is not None:
        A.require(declared == result, 'preserved source split policy differs from source components')
    return result


def exercise_spans(text):
    spans, active = {}, []
    for match in re.finditer(r'<(/?)([\w-]+:)?exercise\b[^>]*>', text):
        if match[1]:
            if active:
                identity, start = active.pop()
                spans.setdefault(identity, []).append((start, match.end()))
        else:
            identity = re.search(r'\bid="([^"]+)"', match[0])
            active.append((identity[1] if identity else None, match.start()))
    return spans


def derive(archive, curriculum=None, split_policy=None):
    archive = archive.resolve()
    sources = C.verified_sources(archive)
    components = source_components(sources, archive)
    splits = source_splits(sources, split_policy, components=components)
    source_family = {identity: family['id'] for family in components['sourceFamilies'] for identity in family['sourceIds']}
    resolved = {}
    curriculum_ref = coverage_hash = None
    if curriculum is not None:
        _, _, resolved, coverage = K.resolve_units(curriculum, archive)
        curriculum_ref, coverage_hash = K.reference(curriculum), coverage['contentSha256']
    bindings = {}
    for unit in resolved.values():
        bindings.setdefault((unit['sourceId'], unit['selector']['sourcePath']), []).append(unit)
    rows, source_coverage = [], []
    for source in sources:
        counts = Counter()
        for entry in source['files']:
            if not entry['path'].endswith('.cnxml'):
                continue
            counts['cnxmlFiles'] += 1
            root = ET.fromstring(C.local_path(archive, entry['path']).read_bytes())
            parents = {child: parent for parent in root.iter() for child in parent}
            content = root.find(CN + 'content')
            A.require(content is not None, 'assessment source content is absent')
            selected_units = bindings.get((source['id'], entry['path']), [])
            spans = exercise_spans(ET.tostring(content, encoding='unicode')) if selected_units else {}
            exercises = list(content.iter(CN + 'exercise'))
            id_counts = Counter(v.get('id') for v in exercises)
            span_offsets = Counter()
            for index, exercise in enumerate(exercises):
                problems, solutions = exercise.findall(CN + 'problem'), exercise.findall(CN + 'solution')
                identity = exercise.get('id')
                identifiers = bool(identity and id_counts[identity] == 1 and all(v.get('id') for v in [*problems, *solutions]))
                expected, reason = target(problems, solutions, identifiers)
                clean_problems = []
                for problem in problems:
                    A.require(not any(v.tag == CN + 'solution' for v in problem.iter()),
                              'source problem contains hidden solution markup')
                    clean_problems.append(xml(problem))
                media = any(v.tag in {CN + 'image', CN + 'video', CN + 'audio'}
                            for problem in problems for v in problem.iter())
                links, offset = [], span_offsets[identity]
                if offset < len(spans.get(identity, [])):
                    start, end = spans[identity][offset]
                    for unit in selected_units:
                        selector = unit['selector']
                        if selector['startCharacter'] <= start and end <= selector['endCharacter']:
                            links.append({'courseId': unit['courseId'], 'unitId': unit['unitId'],
                                          'curriculumRef': curriculum_ref, 'selector': copy.deepcopy(selector)})
                span_offsets[identity] += 1
                source_ref = {'id': source['id'], 'version': source['sourceVersion'],
                              'path': entry['path'], 'sha256': entry['sha256']}
                exercise_ref = {'id': identity, 'index': index, 'problemIds': [v.get('id') for v in problems],
                                'solutionIds': [v.get('id') for v in solutions]}
                public = A.seal({'schema': 'speakeasy-educational-learner-input/1',
                                 'source': source_ref, 'exerciseId': identity, 'exerciseIndex': index,
                                 'problemIds': exercise_ref['problemIds'], 'problemXml': clean_problems,
                                 'contextXml': context_for(exercise, parents), 'courseUnits': links,
                                 'coverage': {'format': 'cnxml-with-MathML', 'mediaReferencesPresent': media,
                                              'mediaBytesAcquired': False, 'solutionTextIncluded': False}})
                concept = {'source': copy.deepcopy(source_ref), 'exerciseId': identity,
                           'exerciseIndex': index, 'problemSha256': A.digest(clean_problems),
                           'solutionSha256': A.digest([xml(v) for v in solutions])}
                concept['id'] = 'source-exercise:' + A.digest(concept)
                row = A.seal({'schema': 'speakeasy-educational-assessment-item/1',
                              'itemId': source['id'] + ':' + A.digest({'path': entry['path'], 'index': index, 'id': identity}),
                              'familyId': source_family[source['id']], 'split': splits['assignments'][source['id']],
                              'source': source_ref, 'exercise': exercise_ref, 'conceptRef': concept,
                              'courseUnits': links,
                              'learnerInput': public, 'gradingTarget': expected,
                              'eligibility': reason, 'solutionXml': [xml(v) for v in solutions],
                              'sourceLicense': source['license'], 'subjects': source['subjects'],
                              'stages': source['stages'], 'nativeSkillAuthority': False,
                              'currentWorldAuthority': False})
                rows.append(row)
                counts['exercises'] += 1
                counts['directSolutions'] += len(solutions)
                counts['answered' if solutions else 'missingAnswer'] += 1
                counts[reason] += 1
                if expected:
                    counts['eligible'] += 1
                    counts[expected['kind']] += 1
                    if links:
                        counts['eligibleWithCourseUnit'] += 1
        source_coverage.append({'sourceId': source['id'], 'sourceVersion': source['sourceVersion'],
                                'familyId': source_family[source['id']],
                                'familySplit': splits['assignments'][source['id']],
                                'formatCoverage': 'cnxml-exercises' if counts['cnxmlFiles'] else 'exercise-parser-unavailable',
                                'counts': dict(sorted(counts.items()))})
    totals = Counter()
    for entry in source_coverage:
        totals.update(entry['counts'])
    metadata = {'schema': 'speakeasy-educational-assessment-bank/1', 'parserVersion': VERSION,
                'sourceArchiveSha256': C.sha((archive / 'acquisition.json').read_bytes()),
                'sourceCount': len(sources), 'preservedSourceFiles': sum(len(s['files']) for s in sources),
                'curriculumRef': curriculum_ref, 'curriculumCoverageSha256': coverage_hash,
                'splitPolicy': splits, 'sourceFamilyComponents': components,
                'sourceFamilyCount': len(components['sourceFamilies']),
                'counts': dict(sorted(totals.items())), 'sourceCoverage': source_coverage,
                'answerIsolation': 'private-evaluator-file-and-whole-source-family-splits',
                'nativeSkillAuthority': False, 'currentWorldAuthority': False,
                'personalRetentionAuthority': False, 'trainingRows': 0,
                'limits': ['prose-and-algebra-answers-not-semantically-graded',
                           'multipart-solutions-not-guessed', 'unacquired-media-remains-unavailable',
                           'whole-evaluation-source-families-must-be-excluded-from-pretraining']}
    return metadata, rows


def serialized(rows):
    return b''.join(A.encoded(v) + b'\n' for v in rows)


def build_bank(archive, output, curriculum=None, split_policy=None):
    A.require(not output.exists(), 'assessment bank already exists; preserve prior version')
    metadata, rows = derive(archive, curriculum, split_policy)
    private, public = serialized(rows), serialized([learner_input(v) for v in rows])
    manifest = A.seal({**metadata, 'assessmentsSha256': C.sha(private), 'learnerItemsSha256': C.sha(public)})
    output.mkdir(parents=True)
    (output / 'assessments.jsonl').write_bytes(private)
    (output / 'learner-items.jsonl').write_bytes(public)
    if curriculum is not None:
        C.write_json(output / 'curriculum.json', curriculum)
    C.write_json(output / 'manifest.json', manifest)
    return manifest


def validate_bank(archive, bank, curriculum=None):
    manifest = A.read(bank / 'manifest.json')
    validate_seal(manifest, 'bank')
    snapshot = A.read(bank / 'curriculum.json') if manifest.get('curriculumRef') is not None else None
    if curriculum is not None:
        A.require(snapshot == curriculum, 'assessment curriculum differs from preserved bank')
    metadata, rows = derive(archive, snapshot, manifest.get('splitPolicy'))
    private, public = serialized(rows), serialized([learner_input(v) for v in rows])
    expected = A.seal({**metadata, 'assessmentsSha256': C.sha(private), 'learnerItemsSha256': C.sha(public)})
    A.require(manifest == expected, 'assessment bank metadata differs from source reconstruction')
    A.require((bank / 'assessments.jsonl').read_bytes() == private,
              'assessment targets differ from source reconstruction')
    A.require((bank / 'learner-items.jsonl').read_bytes() == public,
              'learner inputs differ from source reconstruction')
    return manifest, rows


def validate_seal(value, name):
    A.require(isinstance(value, dict), name + ' must be an object')
    body = copy.deepcopy(value)
    digest = body.pop('contentSha256', None)
    A.require(digest == A.digest(body), name + ' content hash differs')


def learner_input(item):
    validate_seal(item, 'assessment item')
    public = copy.deepcopy(item['learnerInput'])
    validate_seal(public, 'learner input')
    # Answer IDs and grading eligibility stay with the evaluator as well.
    return A.seal({'schema': 'speakeasy-educational-learner-item/1', 'itemSha256': item['contentSha256'],
                   'familyId': item['familyId'], 'split': item['split'], 'input': public})


def validate_training_isolation(manifest, training_inventory, evaluation_splits=('validation', 'test'), *, archive, bank):
    """Reconstruct the bank and compare its family graph with the actual training inventory.

    ``training_inventory`` accepts the foundation source-family request or an
    explicit source-ID inventory. The proof binds that exact request; it says
    nothing about whether weights have been trained from those sources.
    """
    verified, _ = validate_bank(archive, bank)
    A.require(manifest == verified, 'isolation bank differs from actual source reconstruction')
    A.require(set(evaluation_splits) <= SPLITS, 'unsupported evaluation splits')
    graph = manifest['sourceFamilyComponents']
    if isinstance(training_inventory, dict):
        normalized_inventory, inventory_assignments = family_request(training_inventory, graph)
        training_source_ids = {identity for identity, split in inventory_assignments.items() if split == 'train'}
        inventory_kind = 'foundation-source-family-request'
    else:
        A.require(isinstance(training_inventory, (list, tuple, set))
                  and all(isinstance(v, str) for v in training_inventory), 'training source inventory differs')
        A.require(len(set(training_inventory)) == len(training_inventory), 'training source inventory contains duplicates')
        training_source_ids = set(training_inventory)
        normalized_inventory, inventory_kind = sorted(training_source_ids), 'explicit-source-id-inventory'
    known = set(manifest['splitPolicy']['assignments'])
    A.require(training_source_ids <= known, 'training references an unknown source family')
    family_sources = {family['id']: set(family['sourceIds']) for family in graph['sourceFamilies']}
    held_out_families = {family for family, split in manifest['splitPolicy']['familyAssignments'].items()
                         if split in evaluation_splits}
    training_families = {family for family, ids in family_sources.items() if ids.intersection(training_source_ids)}
    A.require(not held_out_families.intersection(training_families),
              'evaluation source solutions leaked into pretraining through related source component')
    held_out = set().union(*(family_sources[family] for family in held_out_families)) if held_out_families else set()
    return A.seal({'schema': 'speakeasy-educational-assessment-isolation/1',
                   'assessmentBankSha256': manifest['contentSha256'],
                   'sourceArchiveSha256': manifest['sourceArchiveSha256'],
                   'sourceFamilyComponentsSha256': graph['contentSha256'],
                   'trainingInventoryKind': inventory_kind,
                   'trainingInventorySha256': A.digest(normalized_inventory),
                   'trainingSourceIds': sorted(training_source_ids), 'trainingFamilyIds': sorted(training_families),
                   'evaluationSourceIds': sorted(held_out), 'evaluationSplits': sorted(set(evaluation_splits)),
                   'evaluationFamilyIds': sorted(held_out_families),
                   'status': 'source-family-components-disjoint'})


def grading_policy(value=None):
    if value is None:
        return {'schema': 'speakeasy-educational-grading-policy/1', 'owner': 'exact-source-value/1',
                'absoluteTolerance': '0', 'relativeTolerance': '0',
                'unitPolicy': 'explicit-exact-unit-table/1'}
    A.require(isinstance(value, dict) and set(value) == {'schema', 'owner', 'absoluteTolerance',
                                                       'relativeTolerance', 'unitPolicy'}
              and value['schema'] == 'speakeasy-educational-grading-policy/1'
              and value['unitPolicy'] == 'explicit-exact-unit-table/1', 'unsupported grading policy')
    A.identifier(value['owner'], 'caller-owned grading policy')
    A.require(value['owner'].startswith('caller:'), 'numeric tolerance requires an explicit caller owner')
    for key in ('absoluteTolerance', 'relativeTolerance'):
        A.require(isinstance(value[key], str) and re.fullmatch(NUMBER, value[key])
                  and Fraction(value[key]) >= 0, 'invalid explicit grading tolerance')
    return copy.deepcopy(value)


def validate_response(value):
    required = {'schema', 'itemSha256', 'learner', 'sessionId', 'asOfTime', 'learningMode',
                'assistanceEvidenceRefs', 'evidenceRefs', 'response'}
    A.require(isinstance(value, dict) and required <= set(value) <= required | {'gradingPolicy'},
              'assessment response fields differ')
    A.require(value['schema'] == 'speakeasy-educational-assessment-response/1', 'unsupported assessment response')
    A.hash_value(value['itemSha256'], 'assessment item')
    learner = value['learner']
    A.require(isinstance(learner, dict) and set(learner) == {'kind', 'id', 'version'}
              and learner['kind'] in {'model', 'person'}, 'response needs an exact model or person')
    for key in ('id', 'version'):
        A.identifier(learner[key], 'learner ' + key)
    A.identifier(value['sessionId'], 'assessment session')
    clock = value['asOfTime']
    A.require(isinstance(clock, dict) and set(clock) == {'clock', 'value'}, 'assessment time fields differ')
    if clock['clock'] == 'utc':
        A.require(isinstance(clock['value'], str), 'UTC assessment time must be a string')
        instant = datetime.fromisoformat(clock['value'].replace('Z', '+00:00'))
        A.require(instant.tzinfo is not None and instant.utcoffset().total_seconds() == 0,
                  'assessment UTC time must include UTC offset')
    else:
        A.require(clock['clock'] in {'county-day', 'county-tick'} and type(clock['value']) in {int, float}
                  and clock['value'] >= 0, 'unsupported assessment clock')
    A.require(value['learningMode'] in MODES, 'unsupported learning observation mode')
    for key in ('assistanceEvidenceRefs', 'evidenceRefs'):
        refs = value[key]
        A.require(isinstance(refs, list) and all(isinstance(v, str) for v in refs)
                  and len(set(refs)) == len(refs), 'assessment evidence must be unique')
        for ref in refs:
            A.identifier(ref, 'assessment evidence reference')
    A.require(value['evidenceRefs'], 'assessment response needs recorded evidence')
    A.require(value['learningMode'] != 'independent-retrieval' or not value['assistanceEvidenceRefs'],
              'assisted response cannot claim independent retrieval')
    A.require(value['learningMode'] not in {'hinted-retrieval', 'tutoring', 'cross-learning'}
              or value['assistanceEvidenceRefs'], 'assisted learning needs its assistance evidence')
    A.require(isinstance(value['response'], str) and len(value['response']) <= 32768,
              'assessment response must be bounded actual text')
    A.encoded(value)
    return grading_policy(value.get('gradingPolicy'))


def grade_item(item, response, bank_sha256=None):
    """Grade a source-rederived item; public callers should use grade or grade_many."""
    validate_seal(item, 'assessment item')
    policy = validate_response(response)
    A.require(response['itemSha256'] == item['contentSha256'], 'response references a different assessment')
    expected = item['gradingTarget']
    earned, status, confidence = None, 'ungradable-target', 0
    feedback = item['eligibility']
    interpreted = None
    if expected is not None:
        if expected['kind'] == 'numeric':
            interpreted = quantity(response['response'])
            if interpreted is not None:
                if interpreted['dimension'] != expected['dimension']:
                    correct = False
                    feedback = 'response-unit-dimension-differs'
                else:
                    source_value = fraction(expected['baseValue'])
                    distance = abs(fraction(interpreted['baseValue']) - source_value)
                    tolerance = max(Fraction(policy['absoluteTolerance']),
                                    abs(source_value) * Fraction(policy['relativeTolerance']))
                    correct = distance <= tolerance
                    feedback = 'numeric-source-comparison'
                status, earned, confidence = ('correct', 1, 1) if correct else ('incorrect', 0, 1)
        elif expected['kind'] == 'multiple-choice':
            text = normalized(response['response'])
            key = re.fullmatch(r'\(?([A-Za-z])\)?\.?', text)
            valid = {v['key'] for v in expected['options']}
            selected = key[1].upper() if key and key[1].upper() in valid else None
            if selected is None:
                matches = [v['key'] for v in expected['options']
                           if v['text'] is not None and text.casefold() == v['text'].casefold()]
                selected = matches[0] if len(matches) == 1 else None
            if selected is not None:
                interpreted = {'selectedKey': selected}
                correct = selected == expected['correctKey']
                status, earned, confidence = ('correct', 1, 1) if correct else ('incorrect', 0, 1)
                feedback = 'source-choice-key-comparison'
        if earned is None:
            status, feedback = 'unrecognized-response', 'response-does-not-use-supported-answer-form'
    independent = status in {'correct', 'incorrect'} and response['learningMode'] == 'independent-retrieval'
    return A.seal({'schema': 'speakeasy-educational-assessment-grade/1',
                   'assessmentSha256': item['contentSha256'], 'assessmentBankSha256': bank_sha256,
                   'responseSha256': A.digest(response), 'learner': copy.deepcopy(response['learner']),
                   'sessionId': response['sessionId'], 'asOfTime': copy.deepcopy(response['asOfTime']),
                   'learningMode': response['learningMode'],
                   'assistanceEvidenceRefs': copy.deepcopy(response['assistanceEvidenceRefs']),
                   'evidenceRefs': copy.deepcopy(response['evidenceRefs']),
                   'source': copy.deepcopy(item['source']), 'exercise': copy.deepcopy(item['exercise']),
                   'conceptRef': copy.deepcopy(item['conceptRef']),
                   'courseUnits': copy.deepcopy(item['courseUnits']), 'familyId': item['familyId'],
                   'split': item['split'], 'status': status, 'earnedPoints': earned,
                   'maxPoints': 1 if expected is not None else 0, 'confidence': confidence,
                   'confidenceMeaning': 'supported-source-answer-comparison', 'feedback': feedback,
                   'interpretedResponse': interpreted, 'gradingPolicy': policy,
                   'sourceAnswerEvidenceSha256': A.digest(item['solutionXml']),
                   'independentRetrievalEvidence': independent, 'independentMasteryAuthority': False,
                   'evaluationTrainingIsolation': 'requires-whole-source-training-inventory-check',
                   'personalRetentionAuthority': False, 'nativeSkillAuthority': False,
                   'currentWorldAuthority': False, 'trainingRows': 0})


def grade_many(archive, bank, responses):
    manifest, rows = validate_bank(archive, bank)
    items = {row['contentSha256']: row for row in rows}
    receipts = []
    for response in responses:
        validate_response(response)
        A.require(response.get('itemSha256') in items, 'assessment response references an unknown item')
        receipts.append(grade_item(items[response['itemSha256']], response, manifest['contentSha256']))
    return receipts


def grade(archive, bank, response):
    return grade_many(archive, bank, [response])[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['bank', 'verify', 'grade'])
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--bank', type=Path)
    parser.add_argument('--curriculum', type=Path)
    parser.add_argument('--split-policy', type=Path)
    parser.add_argument('--responses', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == 'bank':
            A.require(args.out is not None, 'bank needs a new output directory')
            manifest = build_bank(args.archive, args.out,
                                  A.read(args.curriculum) if args.curriculum else None,
                                  A.read(args.split_policy) if args.split_policy else None)
            print(f"BANK {manifest['counts'].get('exercises', 0)} exercises; "
                  f"{manifest['counts'].get('eligible', 0)} automatic targets; {manifest['contentSha256']}")
        elif args.action == 'verify':
            A.require(args.bank is not None, 'verify needs the preserved bank')
            manifest, _ = validate_bank(args.archive, args.bank)
            print(f"VERIFIED {manifest['counts'].get('exercises', 0)} source-derived assessments; {manifest['contentSha256']}")
        else:
            A.require(args.bank is not None and args.responses is not None and args.out is not None,
                      'grade needs bank, responses and a new receipt file')
            A.require(not args.out.exists(), 'grade output already exists; preserve prior receipts')
            responses = [A.loads(line) for line in args.responses.read_text(encoding='utf-8').splitlines() if line.strip()]
            receipts = grade_many(args.archive, args.bank, responses)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open('xb') as handle:
                handle.write(serialized(receipts))
            print(f"GRADED {len(receipts)} exact learner responses; {dict(Counter(v['status'] for v in receipts))}")
        return 0
    except (OSError, ValueError, UnicodeError, ET.ParseError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
