#!/usr/bin/env python3
"""Replay source-graded, person-owned educational memory without native authority.

Inputs are explicit simulated histories, a verified source assessment bank, actual
learner responses and a recorded learning policy. Observation projects time decay
on a detached copy; only received learning events alter the immutable ledger.
"""
from __future__ import annotations

import argparse
import copy
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import decision_authoring as A
import education_assessment as G
import education_backgrounds as B
import education_curriculum as K

PRODUCER = 'educational-memory-1'
AUTHORITY = {'nativeSkillAuthority': False, 'recipeAuthority': False,
             'currentWorldAuthority': False, 'peerAssentAuthority': False,
             'modelTrainingAuthority': False, 'runtimeIntegration': False}
POLICY_FIELDS = {'schema', 'owner', 'version', 'clock', 'ticksPerDay', 'rates',
                 'familiarityRate', 'baseHalfLifeDays', 'familiarityHalfLifeMultiplier',
                 'ageDecayPerYear', 'ageLearningPerYear', 'interestLearningBoost',
                 'interestDecayProtection', 'practiceProtection', 'successfulRetrievalProtection',
                 'maximumProtection', 'wrongRecallPenalty', 'unknownRecallPenalty',
                 'assistedRetentionCap', 'crossPrimingRate', 'maximumPriming',
                 'teacherRetentionThreshold', 'interests', 'eventLimit'}


def validate_policy(policy):
    K.fields(policy, POLICY_FIELDS, 'learning policy')
    A.require(policy['schema'] == 'speakeasy-person-learning-policy/1', 'unsupported learning policy')
    A.identifier(policy['owner'], 'explicit learning policy owner')
    A.identifier(policy['version'], 'learning policy version')
    A.require(policy['clock'] in {'county-day', 'county-tick'}, 'person learning needs county time')
    for key in ('ticksPerDay', 'baseHalfLifeDays', 'familiarityHalfLifeMultiplier', 'maximumProtection'):
        A.require(type(policy[key]) in (int, float) and math.isfinite(policy[key])
                  and 0 < policy[key] <= 1e9, 'invalid positive policy ' + key)
    A.require(policy['maximumProtection'] >= 1, 'maximum protection cannot weaken the unpracticed baseline')
    K.fields(policy['rates'], G.MODES, 'learning rates')
    for key, value in policy['rates'].items():
        B.probability(value, 'learning rate ' + key)
    A.require(all(policy['rates']['independent-retrieval'] > policy['rates'][mode]
                  for mode in G.MODES - {'independent-retrieval'}),
              'independent recall must be stronger than assisted learning')
    for key in POLICY_FIELDS - {'schema', 'owner', 'version', 'clock', 'rates', 'interests', 'eventLimit',
                               'ticksPerDay', 'baseHalfLifeDays', 'familiarityHalfLifeMultiplier', 'maximumProtection'}:
        B.probability(policy[key], 'policy ' + key)
    A.require(isinstance(policy['interests'], dict), 'interests must be an explicit course policy')
    for key, value in policy['interests'].items():
        A.identifier(key, 'interest course'); B.probability(value, 'interest strength')
    A.require(type(policy['eventLimit']) is int and 1 <= policy['eventLimit'] <= 4096, 'invalid ledger bound')


def moment(value, policy):
    K.fields(value, {'clock', 'value'}, 'learning time')
    A.require(value['clock'] == policy['clock'] and type(value['value']) in (int, float)
              and math.isfinite(value['value']) and value['value'] >= 0, 'learning time or clock differs')
    return value['value'] / (policy['ticksPerDay'] if value['clock'] == 'county-tick' else 1)


def verified_context(context):
    K.fields(context, {'archive', 'curriculum', 'sourceCurricula', 'plan', 'backgrounds',
                       'profile', 'person', 'education'}, 'owned learning context')
    expected = B.compile_generated(context['curriculum'], context['archive'], context['plan'],
                                   context['backgrounds'], context['profile'], context['person'],
                                   context['sourceCurricula'])
    B.checked(context['education'], 'educational exposures')
    A.require(context['education'] == expected, 'learning education differs from reconstructed history')
    return {'profileSha256': A.digest(context['profile']),
            'backgroundsSha256': context['backgrounds']['contentSha256'],
            'personEducationSha256': context['person']['contentSha256'],
            'educationalExposuresSha256': expected['contentSha256'],
            'sourceArchiveSha256': expected['sourceArchiveSha256']}


def owner(context):
    return {'kind': 'person', 'id': context['profile']['id'], 'version': A.digest(context['profile'])}


def interest(state, policy):
    return max([policy['interests'].get(link['courseId'], 0) for link in state['courseUnits']] or [0])


def decay(state, at, epoch, age, policy):
    elapsed = at - state['lastDay']
    A.require(elapsed >= 0, 'memory cannot be observed before its last event')
    person_age = age + max(0, at - epoch) / 365.2425
    protection = min(policy['maximumProtection'], 1
                     + policy['practiceProtection'] * state['usageCount']
                     + policy['successfulRetrievalProtection'] * state['independentSuccesses']
                     + policy['interestDecayProtection'] * interest(state, policy))
    half_life = policy['baseHalfLifeDays'] * protection / (1 + policy['ageDecayPerYear'] * person_age)
    factor = 2 ** (-elapsed / half_life)
    state['retention'] *= factor
    state['priming'] *= factor
    state['familiarity'] *= 2 ** (-elapsed / (half_life * policy['familiarityHalfLifeMultiplier']))
    state['lastDay'] = at


def concept_state(item, at):
    return {'conceptRef': copy.deepcopy(item['conceptRef']), 'courseUnits': copy.deepcopy(item['courseUnits']),
            'familiarity': 0.0, 'retention': 0.0, 'priming': 0.0,
            'calibration': {'correct': 0, 'incorrect': 0, 'unknown': 0, 'estimatedCorrectness': 0.5},
            'independentSuccesses': 0, 'assistedSuccesses': 0, 'usageCount': 0, 'lastDay': at}


def assessment_event(identity, response, archive, bank, received=None, kind='assessment'):
    A.require(kind in {'assessment', 'practice'}, 'unsupported graded event kind')
    return B.seal({'schema': 'speakeasy-person-learning-event/1', 'id': identity, 'kind': kind,
                   'asOfTime': response['asOfTime'], 'response': response,
                   'grade': G.grade(archive, bank, response), 'receivedEvidence': received})


def passive_event(identity, item_sha256, receipt_sha256, at):
    return B.seal({'schema': 'speakeasy-person-learning-event/1', 'id': identity, 'kind': 'passive',
                   'asOfTime': at, 'itemSha256': item_sha256, 'exposureReceiptSha256': receipt_sha256})


def transfer_event(identity, source_event_id, item_sha256, at):
    return B.seal({'schema': 'speakeasy-person-learning-event/1', 'id': identity, 'kind': 'transfer',
                   'asOfTime': at, 'sourceEventId': source_event_id, 'itemSha256': item_sha256})


def reception(identity, teacher_sha256, recipient, concept_id, source_evidence_ref, at, session_id):
    """Encode an explicitly received simulated lesson; this never observes proximity."""
    for value in (identity, concept_id, source_evidence_ref, session_id):
        A.identifier(value, 'received learning evidence')
    A.hash_value(teacher_sha256, 'teacher snapshot')
    return B.seal({'schema': 'speakeasy-simulated-teaching-reception/1', 'id': identity,
                   'sourceOwner': 'explicit-simulated-reception', 'sourceEvidenceRef': source_evidence_ref,
                   'teacherSnapshotSha256': teacher_sha256, 'recipient': recipient,
                   'conceptId': concept_id, 'receivedAt': at, 'sessionId': session_id,
                   **AUTHORITY})


def cross_link(source, target, curricula):
    for earlier in source['courseUnits']:
        for later in target['courseUnits']:
            if earlier['curriculumRef'] != later['curriculumRef']:
                continue
            curriculum = next((c for c in curricula if K.reference(c) == earlier['curriculumRef']), None)
            A.require(curriculum is not None, 'cross-learning curriculum is absent')
            courses, units = K.validate(curriculum)
            A.require(earlier['unitId'] in units and later['unitId'] in units,
                      'cross-learning unit is absent')
            a, b = courses[earlier['courseId']], courses[later['courseId']]
            relation = ('course-prerequisite' if a['id'] in b['prerequisites'] else
                        'shared-course' if a['id'] == b['id'] else
                        'shared-subject' if a['subject'] == b['subject'] else None)
            if relation:
                return {'curriculumRef': earlier['curriculumRef'], 'sourceUnitId': earlier['unitId'],
                        'targetUnitId': later['unitId'], 'sourceCourseId': a['id'], 'targetCourseId': b['id'],
                        'relation': relation, 'sourceSelectorSha256': A.digest(earlier['selector']),
                        'targetSelectorSha256': A.digest(later['selector'])}
    raise ValueError('no exact source curriculum link for cross-learning')


def replay(context, policy, bank, started_at, events, teachers=None, _active=None):
    validate_policy(policy)
    binding = verified_context(context)
    manifest, items = G.validate_bank(context['archive'], bank)
    A.require(manifest['sourceArchiveSha256'] == binding['sourceArchiveSha256'],
              'learning bank source archive differs from person history')
    if manifest.get('curriculumRef') is not None:
        A.require(any(K.reference(c) == manifest['curriculumRef']
                      for c in [context['curriculum'], *context['sourceCurricula']]),
                  'learning bank curriculum is not registered to this person')
    A.require(type(events) is list and len(events) <= policy['eventLimit'], 'learning ledger exceeds its bound')
    epoch = last = moment(started_at, policy)
    age = context['profile']['asOfYear'] - context['profile']['birthYear']
    indexed = {item['contentSha256']: item for item in items}
    for event in events:
        A.require(isinstance(event, dict), 'learning event must be an object')
        B.checked(event, 'learning event')
        if event.get('kind') in {'assessment', 'practice'}:
            A.require('response' in event and 'grade' in event, 'graded event lacks actual response')
    concepts, identifiers, used_responses, grades_by_event, links, history = {}, set(), set(), {}, [], []
    used_passive, used_transfer = set(), set()
    graded_events = [event for event in events if event.get('kind') in {'assessment', 'practice'}]
    grades = G.grade_many(context['archive'], bank, [event['response'] for event in graded_events])
    grade_index = iter(grades)
    for event in events:
        body = B.checked(event, 'learning event')
        A.require({'schema', 'id', 'kind', 'asOfTime'} <= set(body), 'learning event lacks required fields')
        A.require(body.get('schema') == 'speakeasy-person-learning-event/1', 'unsupported learning event')
        A.identifier(body.get('id'), 'learning event id')
        A.require(body['id'] not in identifiers, 'duplicate learning event in replay')
        identifiers.add(body['id'])
        at = moment(body['asOfTime'], policy)
        A.require(at >= last, 'learning event chronology differs')
        last = at
        kind = body['kind']
        historical_days, transfer_strength = 0, 0
        if kind in {'assessment', 'practice'}:
            K.fields(body, {'schema', 'id', 'kind', 'asOfTime', 'response', 'grade', 'receivedEvidence'}, 'graded learning event')
            grade = next(grade_index)
            A.require(body['grade'] == grade, 'learning grade differs from actual source grader')
            response = body['response']
            A.require(response['learner'] == owner(context) and response['asOfTime'] == body['asOfTime'],
                      'graded learner or event time differs from person owner')
            A.require(grade['responseSha256'] not in used_responses, 'assessment response already applied')
            used_responses.add(grade['responseSha256'])
            item = indexed[response['itemSha256']]
            mode = grade['learningMode']
            A.require(mode not in {'passive-learning', 'cross-learning'},
                      'passive and cross-learning need their source-bound event producers')
            if kind == 'practice':
                A.require(mode == 'independent-retrieval' and grade['status'] == 'correct',
                          'usage stabilization needs a successful independent response')
            if mode == 'tutoring':
                received = body['receivedEvidence']
                received_body = B.checked(received, 'received teaching')
                K.fields(received_body, {'schema', 'id', 'sourceOwner', 'sourceEvidenceRef', 'teacherSnapshotSha256',
                                         'recipient', 'conceptId', 'receivedAt', 'sessionId', *AUTHORITY}, 'teaching reception')
                A.require(received_body['schema'] == 'speakeasy-simulated-teaching-reception/1'
                          and received_body['sourceOwner'] == 'explicit-simulated-reception'
                          and all(received_body[key] is False for key in AUTHORITY), 'invalid simulated reception owner')
                for value in (received_body['id'], received_body['sourceEvidenceRef']):
                    A.identifier(value, 'received source evidence')
                teacher_sha = received_body['teacherSnapshotSha256']
                A.require(received['contentSha256'] in grade['evidenceRefs']
                          and teacher_sha in grade['assistanceEvidenceRefs']
                          and received_body['recipient'] == owner(context)
                          and received_body['conceptId'] == item['conceptRef']['id']
                          and received_body['sessionId'] == grade['sessionId']
                          and moment(received_body['receivedAt'], policy) <= at,
                          'tutoring lacks exact recipient reception evidence')
                A.require(teachers is not None and teacher_sha in teachers, 'teacher retained-state evidence is absent')
                teacher = teachers[teacher_sha]
                A.require(teacher['ledger']['contentSha256'] == teacher_sha, 'teacher snapshot differs')
                active = set(_active or ())
                A.require(teacher_sha not in active and len(active) < 8, 'cyclic or excessive tutoring lineage')
                view = observe(teacher['ledger'], received_body['receivedAt'], teacher['context'], teacher['policy'], bank,
                               teachers, _active=active | {teacher_sha})
                A.require(view['owner']['id'] != owner(context)['id'], 'person cannot provide their own tutoring evidence')
                retained = view['concepts'].get(item['conceptRef']['id'])
                A.require(retained is not None and retained['independentSuccesses'] > 0
                          and retained['retention'] > 0
                          and retained['retention'] >= policy['teacherRetentionThreshold'],
                          'teacher does not retain the shared concept')
            else:
                A.require(body['receivedEvidence'] is None, 'non-tutoring event cannot carry teaching reception')
            grades_by_event[body['id']] = grade
        elif kind == 'passive':
            K.fields(body, {'schema', 'id', 'kind', 'asOfTime', 'itemSha256', 'exposureReceiptSha256'}, 'passive event')
            A.require(body['itemSha256'] in indexed, 'passive assessment source is absent')
            item = indexed[body['itemSha256']]
            receipt = next((r for r in context['person']['receipts']
                            if r['contentSha256'] == body['exposureReceiptSha256']), None)
            A.require(receipt is not None and receipt.get('personId') == owner(context)['id']
                      and receipt.get('attended') is True, 'passive exposure needs an actual schooling receipt')
            A.require(any(link['unitId'] in receipt['exposedUnitIds']
                          and link['curriculumRef'] == receipt['curriculumRef']
                          and any(e['unitId'] == link['unitId'] and e['educationEntryId'] == receipt['contentSha256']
                                  and e['sourceCurriculumRef'] == link['curriculumRef']
                                  for e in context['education']['exposureCandidates'])
                          for link in item['courseUnits']), 'passive exposure lacks source-backed available unit')
            passive_key = (item['conceptRef']['id'], receipt['contentSha256'])
            A.require(passive_key not in used_passive, 'passive source receipt already applied to concept')
            used_passive.add(passive_key)
            historical_days = (context['profile']['asOfYear'] - receipt['endYear']) * 365.2425 + at - epoch
            A.require(historical_days >= 0, 'historical exposure postdates person learning time')
            mode, grade = 'passive-learning', None
        elif kind == 'transfer':
            K.fields(body, {'schema', 'id', 'kind', 'asOfTime', 'sourceEventId', 'itemSha256'}, 'cross-learning event')
            A.require(body['sourceEventId'] in grades_by_event and body['itemSha256'] in indexed,
                      'cross-learning needs earlier graded source evidence')
            source_grade = grades_by_event[body['sourceEventId']]
            A.require(source_grade['independentRetrievalEvidence'] and source_grade['status'] == 'correct',
                      'cross-learning source is not independent successful retrieval')
            item = indexed[body['itemSha256']]
            source_item = indexed[source_grade['assessmentSha256']]
            A.require(source_item['conceptRef']['id'] != item['conceptRef']['id'], 'cross-learning target is the source concept')
            retained_source = copy.deepcopy(concepts[source_item['conceptRef']['id']])
            decay(retained_source, at, epoch, age, policy)
            transfer_strength = retained_source['retention']
            A.require(transfer_strength > 0, 'cross-learning source is no longer retained')
            link = cross_link(source_item, item, [context['curriculum'], *context['sourceCurricula']])
            transfer_key = (body['sourceEventId'], item['conceptRef']['id'])
            A.require(transfer_key not in used_transfer, 'cross-learning source receipt already applied to target')
            used_transfer.add(transfer_key)
            links.append({'eventId': body['id'], 'sourceEventId': body['sourceEventId'],
                          'sourceGradeSha256': source_grade['contentSha256'],
                          'sourceRetention': transfer_strength, 'evidence': link})
            mode, grade = 'cross-learning', None
        else:
            raise ValueError('unsupported learning event kind')
        identity = item['conceptRef']['id']
        state = concepts.setdefault(identity, concept_state(item, at))
        decay(state, at, epoch, age, policy)
        person_age = age + (at - epoch - historical_days) / 365.2425
        rate = min(1, policy['rates'][mode] * (1 + state['priming'])
                   * (1 + policy['interestLearningBoost'] * interest(state, policy))
                   / (1 + policy['ageLearningPerYear'] * person_age))
        historical = concept_state(item, at - historical_days)
        historical['familiarity'], historical['retention'] = policy['familiarityRate'], rate
        decay(historical, at, epoch, age, policy)
        state['familiarity'] += historical['familiarity'] * (1 - state['familiarity'])
        if mode == 'cross-learning':
            state['priming'] = min(policy['maximumPriming'], state['priming']
                                   + policy['crossPrimingRate'] * rate * transfer_strength)
        elif grade is None or grade['status'] == 'correct':
            if mode == 'independent-retrieval':
                state['independentSuccesses'] += 1
                state['calibration']['correct'] += 1
                state['retention'] += rate * (1 - state['retention'])
                if kind == 'practice':
                    state['usageCount'] += 1
            else:
                state['assistedSuccesses'] += grade is not None
                state['retention'] = max(state['retention'], min(policy['assistedRetentionCap'],
                                        state['retention'] + historical['retention'] * (1 - state['retention'])))
        elif grade['status'] == 'incorrect':
            if grade['independentRetrievalEvidence']:
                state['calibration']['incorrect'] += 1
            state['retention'] = max(0, state['retention'] - policy['wrongRecallPenalty'])
        else:
            state['calibration']['unknown'] += 1
            state['retention'] = max(0, state['retention'] - policy['unknownRecallPenalty'])
        calibration = state['calibration']
        calibration['estimatedCorrectness'] = (1 + calibration['correct']) / (2 + calibration['correct'] + calibration['incorrect'])
        history.append(copy.deepcopy(event))
    return B.seal({'schema': 'speakeasy-person-educational-memory/1', 'producer': PRODUCER,
                   'owner': owner(context), 'contextRefs': binding, 'policySha256': A.digest(policy),
                   'assessmentBankSha256': manifest['contentSha256'], 'startedAt': started_at,
                   'lastDay': last, 'ageAtEpoch': age, 'events': history, 'concepts': concepts,
                   'crossLearningLinks': links, 'standing': 'simulated-person-memory', **AUTHORITY})


def initialize(context, policy, bank, started_at):
    return replay(context, policy, bank, started_at, [])


def verify(ledger, context, policy, bank, teachers=None, _active=None):
    body = B.checked(ledger, 'learning ledger')
    A.require({'startedAt', 'events'} <= set(body), 'learning ledger lacks replay inputs')
    expected = replay(context, policy, bank, ledger['startedAt'], ledger['events'], teachers, _active)
    A.require(ledger == expected, 'learning ledger differs from source/event reconstruction')
    return copy.deepcopy(expected)


def apply_event(ledger, event, context, policy, bank, teachers=None):
    A.require(isinstance(event, dict), 'learning event must be an object')
    verified = verify(ledger, context, policy, bank, teachers)
    for previous in verified['events']:
        if previous['id'] == event.get('id'):
            A.require(previous == event, 'learning event identity conflicts with prior receipt')
            return verified
    return replay(context, policy, bank, verified['startedAt'], [*verified['events'], event], teachers)


def observe(ledger, as_of, context, policy, bank, teachers=None, _active=None):
    verified = verify(ledger, context, policy, bank, teachers, _active)
    at, epoch = moment(as_of, policy), moment(verified['startedAt'], policy)
    A.require(at >= verified['lastDay'], 'observation precedes recorded learning')
    concepts = copy.deepcopy(verified['concepts'])
    for state in concepts.values():
        decay(state, at, epoch, verified['ageAtEpoch'], policy)
    return B.seal({'schema': 'speakeasy-person-educational-memory-view/1', 'owner': verified['owner'],
                   'ledgerSha256': ledger['contentSha256'], 'asOfTime': as_of, 'concepts': concepts,
                   'standing': 'read-only-person-memory-projection', **AUTHORITY})


def export_prior(ledger, as_of, context, policy, bank, teachers=None, maximum_concepts=128):
    A.require(type(maximum_concepts) is int and 1 <= maximum_concepts <= 128, 'invalid bounded prior size')
    view = observe(ledger, as_of, context, policy, bank, teachers)
    selected = sorted(view['concepts'].values(), key=lambda item: (-item['retention'], item['conceptRef']['id']))[:maximum_concepts]
    return B.seal({'schema': 'speakeasy-person-educational-prior/1', 'owner': view['owner'],
                   'ledgerSha256': ledger['contentSha256'], 'asOfTime': as_of,
                   'concepts': selected, 'omittedConcepts': len(view['concepts']) - len(selected),
                   'sourceBankSha256': ledger['assessmentBankSha256'],
                   'contextRefs': ledger['contextRefs'], 'standing': 'future-sao-person-prior', **AUTHORITY})


def read_context(path):
    paths = A.read(path)
    K.fields(paths, {'archive', 'curriculum', 'sourceCurricula', 'plan', 'backgrounds', 'profile', 'person', 'education'}, 'context paths')
    context = {key: A.read(Path(value)) for key, value in paths.items() if key not in {'archive', 'sourceCurricula'}}
    context['archive'] = Path(paths['archive'])
    context['sourceCurricula'] = [A.read(Path(item)) for item in paths['sourceCurricula']]
    return context


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['replay', 'observe', 'export'])
    parser.add_argument('--context', type=Path, required=True, help='Explicit paths to all owned background/compiler inputs')
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--bank', type=Path, required=True)
    parser.add_argument('--started-at', type=Path)
    parser.add_argument('--events', type=Path)
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--as-of', type=Path)
    parser.add_argument('--teachers', type=Path, help='Exact teacher snapshot hashes with ledger/context/policy paths')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        context = read_context(args.context)
        policy = A.read(args.policy)
        teachers = None
        if args.teachers is not None:
            paths = A.read(args.teachers)
            A.require(isinstance(paths, dict), 'teacher paths must be keyed by exact snapshot hashes')
            teachers = {}
            for digest, entry in paths.items():
                A.hash_value(digest, 'teacher snapshot hash')
                K.fields(entry, {'ledger', 'context', 'policy'}, 'teacher paths')
                teachers[digest] = {'ledger': A.read(Path(entry['ledger'])),
                                   'context': read_context(Path(entry['context'])),
                                   'policy': A.read(Path(entry['policy']))}
        if args.action == 'replay':
            A.require(args.started_at is not None and args.events is not None, 'replay needs start and events')
            result = replay(context, policy, args.bank, A.read(args.started_at), A.read(args.events), teachers)
        else:
            A.require(args.ledger is not None and args.as_of is not None, 'observation needs ledger and time')
            method = observe if args.action == 'observe' else export_prior
            result = method(A.read(args.ledger), A.read(args.as_of), context, policy, args.bank, teachers)
        status = B.write_immutable(args.out, result)
    except (ValueError, OSError, ET.ParseError, UnicodeError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        return 2
    print(f"{status} {result['schema']} {result['contentSha256']}; person memory, no native authority")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
