#!/usr/bin/env python3
"""Produce immutable simulated schooling backgrounds; textbook rights are separate.

The explicit plan owns institutions and participation parameters. Its world identity
and seed reproducibly realize background bodies once, preserving authored optional
choices. The profile supplies birthplace and migrations, never a spawn-origin alias.
Verified deterministic reconstruction precedes the curriculum compiler boundary.
"""
from __future__ import annotations

import argparse
import copy
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import decision_authoring as A
import education_curriculum as K

PRODUCER = 'education-backgrounds-1'
PARTICIPATION = {'enrolmentProbability', 'attendanceProbability',
                 'interruptionProbability', 'completionProbability',
                 'minimumInterruptedExposureFraction'}
BOUNDARY = {'personalRetentionAuthority': False, 'nativeSkillAuthority': False,
            'currentWorldAuthority': False, 'peerAssentAuthority': False,
            'trainingApprovalAuthority': False}


def seal(body):
    return K.sealed(copy.deepcopy(body))


def checked(value, name):
    A.require(isinstance(value, dict), f'{name} must be an object')
    body = copy.deepcopy(value)
    digest = body.pop('contentSha256', None)
    A.hash_value(digest, f'{name} content hash')
    A.require(A.digest(body) == digest, f'{name} content hash differs')
    return body


def probability(value, name):
    A.require(type(value) in (int, float) and math.isfinite(value)
              and 0 <= value <= 1, f'{name} must be a probability')


def draw(world, *key):
    # Exactly representable 52-bit fraction, independent of Python random state.
    return int(A.digest([PRODUCER, world, list(key)])[:13], 16) / (1 << 52)


def registry(curricula, archive):
    A.require(isinstance(curricula, list) and curricula, 'missing exact curriculum registry')
    result, versions = {}, set()
    for curriculum in curricula:
        courses, _, _, coverage = K.resolve_units(curriculum, archive)
        ref = K.reference(curriculum)
        version = (ref['id'], ref['version'])
        A.require(ref['sha256'] not in result and version not in versions,
                  'duplicate or conflicting curriculum registry version')
        versions.add(version)
        result[ref['sha256']] = {'curriculum': curriculum, 'courses': courses,
                                'reference': ref, 'coverage': coverage}
    return result


def reference_row(value, registered):
    K.fields(value, {'id', 'version', 'sha256'}, 'source curriculum reference')
    A.hash_value(value['sha256'], 'source curriculum hash')
    A.require(value.get('sha256') in registered
              and value == registered[value['sha256']]['reference'],
              'source curriculum hash or version differs')
    return registered[value['sha256']]


def _backgrounds(plan, registered):
    K.fields(plan, {'schema', 'id', 'worldOwner', 'curriculumRef', 'regions'}, 'background plan')
    A.require(plan['schema'] == 'speakeasy-education-background-plan/1', 'unsupported background plan')
    A.identifier(plan['id'], 'background plan id')
    K.fields(plan['worldOwner'], {'id', 'seed'}, 'world owner')
    for key in ('id', 'seed'):
        A.identifier(plan['worldOwner'][key], 'explicit world ' + key)
    current = reference_row(plan['curriculumRef'], registered)
    A.require(isinstance(plan['regions'], list) and 0 < len(plan['regions']) <= 128,
              'missing or excessive simulated regions')
    bodies, projections, seen = [], [], set()
    for region in plan['regions']:
        K.fields(region, {'id', 'cohorts'}, 'planned region')
        A.identifier(region['id'], 'region id')
        A.require(region['id'] not in seen, 'duplicate simulated region')
        seen.add(region['id'])
        A.require(isinstance(region['cohorts'], list) and 0 < len(region['cohorts']) <= 128,
                  'region needs bounded cohorts')
        cohorts, cohort_views, cohort_ids = [], [], set()
        for cohort in region['cohorts']:
            K.fields(cohort, {'id', 'startYear', 'endYear', 'curriculumRef', 'institutions'}, 'planned cohort')
            A.identifier(cohort['id'], 'cohort id')
            K.year(cohort['startYear'], 'cohort start'); K.year(cohort['endYear'], 'cohort end')
            A.require(cohort['startYear'] < cohort['endYear'] <= 1993, 'invalid simulated cohort chronology')
            A.require(cohort['id'] not in cohort_ids, 'duplicate simulated cohort')
            cohort_ids.add(cohort['id'])
            local = reference_row(cohort['curriculumRef'], registered)
            A.require(isinstance(cohort['institutions'], list) and 0 < len(cohort['institutions']) <= 128,
                      'cohort needs bounded institutions')
            institutions, institution_views, institution_ids = [], [], set()
            for institution in cohort['institutions']:
                K.fields(institution, {'id', 'levelIds', 'offeredCourseIds', 'participation',
                                       'authoredOptionalUnits'}, 'planned institution')
                A.identifier(institution['id'], 'institution id')
                A.require(institution['id'] not in institution_ids, 'duplicate simulated institution')
                institution_ids.add(institution['id'])
                K.names(institution['levelIds'], 'institution levels')
                K.names(institution['offeredCourseIds'], 'institution courses')
                K.fields(institution['participation'], PARTICIPATION, 'institution participation')
                for key, value in institution['participation'].items():
                    probability(value, key)
                authored = institution['authoredOptionalUnits']
                A.require(isinstance(authored, dict), 'authored optional choices must be an object')
                A.require(set(authored) <= set(institution['offeredCourseIds']), 'authored choice names unoffered course')
                optional = {}
                for identity in institution['offeredCourseIds']:
                    A.require(identity in local['courses'], 'institution offers unknown course')
                    course = local['courses'][identity]
                    core = [u['id'] for u in course['units'] if u['id'] not in course['optionalUnitIds']]
                    policy = local['curriculum']['regionalPolicy']
                    limit = len(core) * policy['optionalUnitNumerator'] // policy['optionalUnitDenominator']
                    if identity in authored:
                        K.names(authored[identity], 'authored optional units', True)
                        choices = copy.deepcopy(authored[identity])
                    else:
                        # Same seed/region/cohort/course gives every school the same
                        # generated minor variant; explicit school overrides survive.
                        cap = min(limit, len(course['optionalUnitIds']))
                        count = (1 + math.floor(draw(plan['worldOwner'], 'optional-count', region['id'],
                                                    cohort['id'], identity) * cap)) if cap else 0
                        choices = sorted(course['optionalUnitIds'], key=lambda unit:
                                         (draw(plan['worldOwner'], 'optional', region['id'], cohort['id'], identity, unit), unit))[:count]
                    A.require(set(choices) <= set(course['optionalUnitIds']) and len(choices) <= limit,
                              'authored variation exceeds source curriculum bound')
                    optional[identity] = choices
                body = seal({'schema': 'speakeasy-simulated-education-institution/1',
                             'id': institution['id'], 'regionId': region['id'], 'cohortId': cohort['id'],
                             'worldOwner': plan['worldOwner'], 'curriculumRef': local['reference'],
                             'levelIds': institution['levelIds'], 'offeredCourseIds': institution['offeredCourseIds'],
                             'participation': institution['participation'], 'optionalUnits': optional,
                             'authoredOptionalUnits': authored, 'authoredStateSha256': A.digest(authored),
                             'inputInstitutionSha256': A.digest(institution), 'producer': PRODUCER,
                             'provenance': 'simulated-state-initialization', **BOUNDARY})
                institutions.append(body)
                institution_views.append({'id': body['id'], 'historyRef': body['contentSha256'],
                                          'levelIds': body['levelIds'], 'offeredCourseIds': body['offeredCourseIds'],
                                          'optionalUnits': body['optionalUnits']})
            body = seal({'schema': 'speakeasy-simulated-education-cohort/1', 'id': cohort['id'],
                         'regionId': region['id'], 'startYear': cohort['startYear'], 'endYear': cohort['endYear'],
                         'curriculumRef': local['reference'], 'institutions': institutions,
                         'inputCohortSha256': A.digest(cohort), 'producer': PRODUCER})
            cohorts.append(body)
            cohort_views.append({'id': body['id'], 'curriculumRef': body['curriculumRef'],
                                 'startYear': body['startYear'], 'endYear': body['endYear'],
                                 'historyRef': body['contentSha256'], 'institutions': institution_views})
        body = seal({'schema': 'speakeasy-simulated-state-education-background/1', 'id': region['id'],
                     'worldOwner': plan['worldOwner'], 'cohorts': cohorts,
                     'inputRegionSha256': A.digest(region), 'producer': PRODUCER,
                     'provenance': 'simulated-state-initialization', **BOUNDARY})
        bodies.append(body)
        projections.append({'id': body['id'], 'stateBackgroundRef': body['contentSha256'], 'cohorts': cohort_views})
    regional = {'schema': 'speakeasy-regional-education-history/1',
                'curriculumRef': current['reference'], 'regions': projections}
    # The existing compiler owns shared-core and exact course-level validation.
    K.regional_index(regional, current['curriculum'], current['courses'], registered)
    rows = [{'curriculumRef': item['reference'], 'coverageSha256': item['coverage']['contentSha256']}
            for _, item in sorted(registered.items())]
    receipt = seal({'schema': 'speakeasy-education-background-generation/1', 'producer': PRODUCER,
                    'worldOwner': plan['worldOwner'], 'inputPlanSha256': A.digest(plan),
                    'curriculumRegistrySha256': A.digest(rows), 'backgroundBodiesSha256': A.digest(bodies),
                    'regionalRecordsSha256': A.digest(regional),
                    'sourceArchiveSha256': current['coverage']['sourceArchiveSha256']})
    return seal({'schema': 'speakeasy-generated-education-backgrounds/1', 'producer': PRODUCER,
                 'inputPlan': plan, 'worldOwner': plan['worldOwner'], 'curriculumRegistry': rows,
                 'regions': bodies, 'regionalRecords': regional, 'generationReceipt': receipt,
                 'standing': 'simulated-education-background', **BOUNDARY})


def preserve(expected, existing, name):
    if existing is not None:
        checked(existing, name)
        A.require(existing == expected, f'{name} differs from owned inputs or deterministic generation receipt')
        return copy.deepcopy(existing)
    return expected


def generate_backgrounds(plan, curricula, archive, existing=None):
    return preserve(_backgrounds(plan, registry(curricula, archive)), existing, 'generated background')


def _profile(profile, backgrounds):
    K.fields(profile, {'schema', 'id', 'birthYear', 'asOfYear', 'birthRegionId', 'currentRegionId',
                       'migrations', 'collegeYears', 'electiveCourseIds'}, 'simulated education profile')
    A.require(profile['schema'] == 'speakeasy-simulated-education-profile/1', 'unsupported person profile')
    A.identifier(profile['id'], 'person id')
    K.year(profile['birthYear'], 'birth year'); K.year(profile['asOfYear'], 'as-of year')
    A.require(profile['birthYear'] <= profile['asOfYear'] <= 1993, 'invalid profile chronology or horizon')
    regions = {region['id'] for region in backgrounds['regions']}
    A.identifier(profile['birthRegionId'], 'explicit birth region')
    A.identifier(profile['currentRegionId'], 'explicit current region')
    A.require(profile['birthRegionId'] in regions and profile['currentRegionId'] in regions,
              'profile needs explicit registered birth and current regions')
    A.require(type(profile['collegeYears']) is int and 0 <= profile['collegeYears'] <= 6,
              'college years must be explicit and bounded')
    K.names(profile['electiveCourseIds'], 'profile elective courses', True)
    A.require(isinstance(profile['migrations'], list), 'profile migrations must be explicit')
    residence, earlier = profile['birthRegionId'], profile['birthYear'] - 1
    for migration in profile['migrations']:
        K.fields(migration, {'year', 'fromRegionId', 'toRegionId'}, 'profile migration')
        K.year(migration['year'], 'migration year')
        A.identifier(migration['fromRegionId'], 'migration source region')
        A.identifier(migration['toRegionId'], 'migration destination region')
        A.require(max(earlier + 1, profile['birthYear']) <= migration['year'] <= profile['asOfYear']
                  and migration['fromRegionId'] == residence and migration['toRegionId'] in regions
                  and migration['toRegionId'] != residence, 'profile migration chronology or chain differs')
        residence, earlier = migration['toRegionId'], migration['year']
    A.require(residence == profile['currentRegionId'], 'current region differs from explicit migration chain')


def _person(profile, backgrounds, registered):
    _profile(profile, backgrounds)
    world, profile_hash = backgrounds['worldOwner'], A.digest(profile)
    available_electives = {c['id'] for item in registered.values() for c in item['courses'].values()
                          if c['requirement'] == 'elective'}
    A.require(set(profile['electiveCourseIds']) <= available_electives, 'profile selects unknown elective course')
    person = {'schema': 'speakeasy-person-education-history/1', 'id': profile['id'],
              'birthYear': profile['birthYear'], 'asOfYear': profile['asOfYear'],
              'birthRegionId': profile['birthRegionId'], 'currentRegionId': profile['currentRegionId'],
              'migrations': [], 'educationHistory': []}
    receipts, gaps = [], []
    for migration in profile['migrations']:
        receipt = seal({'schema': 'speakeasy-simulated-education-migration/1', 'personId': profile['id'],
                        'profileSha256': profile_hash, 'worldOwner': world, 'migration': migration,
                        'producer': PRODUCER})
        receipts.append(receipt)
        person['migrations'].append({**migration, 'historyRef': receipt['contentSha256']})
    scheduled = [(profile['birthYear'] + 5 + i, level) for i, level in enumerate(K.LEVELS[:-1])]
    scheduled.extend((profile['birthYear'] + 18 + i, 'college-general') for i in range(profile['collegeYears']))
    scheduled_courses, completed_courses = {}, {}
    for start, level in scheduled:
        if start > profile['asOfYear']:
            continue
        end = min(start + 1, profile['asOfYear'])
        residence = profile['birthRegionId']
        for migration in profile['migrations']:
            if migration['year'] <= start:
                residence = migration['toRegionId']
        candidates = []
        for region in backgrounds['regions']:
            if region['id'] != residence:
                continue
            for cohort in region['cohorts']:
                if not cohort['startYear'] <= start <= end <= cohort['endYear']:
                    continue
                for institution in cohort['institutions']:
                    # Specializations are offered college study, selected as electives.
                    levels = institution['levelIds']
                    eligible = level in levels or level == 'college-general' and any(
                        registered[cohort['curriculumRef']['sha256']]['courses'][c]['level'].startswith('college-specialization:')
                        for c in institution['offeredCourseIds'] if c in profile['electiveCourseIds'])
                    if eligible:
                        candidates.append((cohort, institution))
        if not candidates:
            gaps.append({'regionId': residence, 'levelId': level, 'startYear': start,
                         'reason': 'no-dated-source-institution'})
            continue
        cohort, institution = min(candidates, key=lambda pair:
                                  (draw(world, 'institution', profile['id'], start, pair[0]['id'], pair[1]['id']),
                                   pair[0]['id'], pair[1]['id']))
        local = registered[cohort['curriculumRef']['sha256']]
        participation = institution['participation']
        samples = {key: draw(world, 'participation', profile['id'], residence, cohort['id'], institution['id'], start, key)
                   for key in PARTICIPATION}
        enrolled = samples['enrolmentProbability'] < participation['enrolmentProbability']
        attended = enrolled and samples['attendanceProbability'] < participation['attendanceProbability']
        interrupted = attended and samples['interruptionProbability'] < participation['interruptionProbability']
        fraction = (participation['minimumInterruptedExposureFraction']
                    + (1 - participation['minimumInterruptedExposureFraction'])
                    * samples['minimumInterruptedExposureFraction']) if interrupted else 1
        if not attended or end == start:
            fraction = 0
        completed = attended and not interrupted and end > start and (
            samples['completionProbability'] < participation['completionProbability'])
        for course_id in institution['offeredCourseIds']:
            course = local['courses'][course_id]
            collegiate = course['level'] == 'college-general' or course['level'].startswith('college-specialization:')
            if course['level'] != level and not (level == 'college-general' and collegiate):
                continue
            if course['requirement'] == 'elective' and course_id not in profile['electiveCourseIds']:
                continue
            course_key = (local['reference']['sha256'], course_id)
            if course_key in completed_courses or not collegiate and course_key in scheduled_courses:
                continue
            # College prerequisites must be scheduled earlier; missing completions
            # remain visible in the compiler, never fabricated here.
            if collegiate and any(completed_courses.get((local['reference']['sha256'], p), end + 1) > start
                                   for p in course['prerequisites'] if local['courses'][p]['level'].startswith('college')):
                gaps.append({'regionId': residence, 'courseId': course_id, 'startYear': start,
                             'reason': 'college-prerequisite-not-completed'})
                continue
            core = [u['id'] for u in course['units'] if u['id'] not in course['optionalUnitIds']]
            selected = core + institution['optionalUnits'][course_id]
            exposed = selected[:math.floor(len(selected) * fraction)]
            receipt = seal({'schema': 'speakeasy-simulated-schooling-result/1', 'producer': PRODUCER,
                            'personId': profile['id'], 'profileSha256': profile_hash, 'worldOwner': world,
                            'institutionBodySha256': institution['contentSha256'], 'curriculumRef': local['reference'],
                            'courseId': course_id, 'startYear': start, 'endYear': end,
                            'ageAtStart': start - profile['birthYear'], 'participation': participation,
                            'samples': samples, 'enrolled': enrolled, 'attended': attended,
                            'interrupted': interrupted, 'exposureFraction': fraction,
                            'completion': 'completed' if completed else 'not-completed',
                            'exposedUnitIds': exposed, 'provenance': 'simulated-person-history', **BOUNDARY})
            receipts.append(receipt)
            person['educationHistory'].append({'id': receipt['contentSha256'], 'regionId': residence,
                                              'cohortId': cohort['id'], 'institutionId': institution['id'],
                                              'curriculumRef': local['reference'], 'courseId': course_id,
                                              'startYear': start, 'endYear': end,
                                              'attendance': 'attended' if attended else 'not-attended',
                                              'completion': receipt['completion'],
                                              'evidenceRefs': [receipt['contentSha256']], 'exposedUnitIds': exposed})
            scheduled_courses[course_key] = start
            if completed:
                completed_courses[course_key] = end
    generation = seal({'schema': 'speakeasy-person-education-generation/1', 'producer': PRODUCER,
                       'profileSha256': profile_hash, 'worldOwner': world,
                       'backgroundsSha256': backgrounds['contentSha256'],
                       'personHistorySha256': A.digest(person), 'receiptsSha256': A.digest(receipts),
                       'coverageGapsSha256': A.digest(gaps)})
    return seal({'schema': 'speakeasy-generated-person-education/1', 'producer': PRODUCER,
                 'inputProfile': profile, 'personHistory': person, 'receipts': receipts,
                 'coverageGaps': gaps, 'generationReceipt': generation,
                 'standing': 'simulated-person-education', **BOUNDARY})


def generate_person(profile, backgrounds, plan, curricula, archive, existing=None):
    registered = registry(curricula, archive)
    verified = preserve(_backgrounds(plan, registered), backgrounds, 'generated background')
    return preserve(_person(profile, verified, registered), existing, 'generated person history')


def compile_generated(curriculum, archive, plan, backgrounds, profile, person, source_curricula=None):
    curricula = [curriculum, *(source_curricula or [])]
    verified = generate_person(profile, backgrounds, plan, curricula, archive, existing=person)
    K.match_reference(plan['curriculumRef'], curriculum)
    result = K.compile_history(curriculum, archive, backgrounds['regionalRecords'],
                               verified['personHistory'], source_curricula)
    body = checked(result, 'curriculum exposure output')
    body['generatedBackgroundsSha256'] = backgrounds['contentSha256']
    body['generatedPersonHistorySha256'] = verified['contentSha256']
    body['backgroundGenerationReceiptSha256'] = backgrounds['generationReceipt']['contentSha256']
    body['personGenerationReceiptSha256'] = verified['generationReceipt']['contentSha256']
    return seal(body)


def write_immutable(path, value):
    if path.exists():
        A.require(A.read(path) == value, 'existing immutable output differs')
        return 'REPLAYED'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as output:
        output.write(A.encoded(value) + b'\n')
    return 'WROTE'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['generate', 'person', 'compile'])
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--curriculum', type=Path, required=True)
    parser.add_argument('--source-curriculum', type=Path, action='append', default=[])
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--backgrounds', type=Path)
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--person', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        plan, curriculum = A.read(args.plan), A.read(args.curriculum)
        sources = [A.read(path) for path in args.source_curriculum]
        curricula = [curriculum, *sources]
        K.match_reference(plan['curriculumRef'], curriculum)
        if args.action == 'generate':
            result = generate_backgrounds(plan, curricula, args.archive)
        else:
            A.require(args.backgrounds is not None and args.profile is not None,
                      'person/compile needs owned backgrounds and explicit profile')
            backgrounds, profile = A.read(args.backgrounds), A.read(args.profile)
            if args.action == 'person':
                result = generate_person(profile, backgrounds, plan, curricula, args.archive)
            else:
                A.require(args.person is not None, 'compile needs generated person history')
                result = compile_generated(curriculum, args.archive, plan, backgrounds, profile,
                                           A.read(args.person), sources)
        outcome = write_immutable(args.out, result)
    except (ValueError, OSError, ET.ParseError, UnicodeError) as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        return 2
    print(f"{outcome} {result['schema']} {result['contentSha256']}; simulated provenance, zero training approval")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
