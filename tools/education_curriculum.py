#!/usr/bin/env python3
"""Resolve sourced curricula and explicit education histories into exposure candidates."""
from __future__ import annotations

import argparse
import copy
import re
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import decision_authoring as A
import education_corpus as C
import cross_module_rows as J

ROOT = Path(__file__).resolve().parents[1]
CURRICULUM = ROOT / 'corpus/education/curriculum.json'
LEVELS = ['kindergarten', *[f'grade-{n}' for n in range(1, 13)], 'college-general']
SCHOOL_DOMAINS = {'literacy', 'mathematics', 'science', 'social-studies', 'arts',
                  'health', 'languages', 'practical-arts'}
COLLEGE_DOMAINS = {'writing', 'quantitative', 'science', 'history-civics',
                   'social-science', 'arts-humanities', 'health', 'language'}
CNXML = '{http://cnx.rice.edu/cnxml}'


def fields(value, expected, name):
    A.require(isinstance(value, dict) and set(value) == set(expected), f'{name} fields differ')


def names(value, name, allow_empty=False):
    A.require(isinstance(value, list) and (allow_empty or value), f'{name} must be a list')
    for item in value:
        A.identifier(item, name)
    A.require(len(value) == len(set(value)), f'{name} contains duplicates')


def year(value, name, minimum=1700):
    A.require(type(value) is int and minimum <= value <= 2200, f'{name} is outside supported years')


def sealed(value):
    value['contentSha256'] = A.digest(value)
    return value


def reference(curriculum):
    return {'id': curriculum['id'], 'version': curriculum['version'],
            'sha256': A.digest(curriculum)}


def match_reference(value, curriculum):
    fields(value, {'id', 'version', 'sha256'}, 'curriculum reference')
    A.require(value == reference(curriculum), 'missing or mismatched curriculum version')


def source_edition_date(text, evidence):
    """Read the complete local printed notice, never a caller-selected year substring."""
    if evidence is None:
        return None, 'unestablished'
    literal = evidence['literal']
    matches = [v.start() for v in re.finditer(re.escape(literal), text)]
    A.require(matches, 'dated edition evidence is absent from actual source')
    notices = []
    for start in matches:
        if start > 32768:
            return None, 'unestablished'
        left = text.rfind('\n\n', 0, start)
        left = 0 if left < 0 else left + 2
        right = text.find('\n\n', start + len(literal))
        right = len(text) if right < 0 else right
        # Indeterminate or long prose context supplies no bibliographic date.
        if right - left > 4096:
            return None, 'unestablished'
        notices.append(text[left:right])
    # A repeated literal with different contexts is not one identified notice.
    if len(set(notices)) != 1:
        return None, 'unestablished'
    bibliographic = re.compile(r'\b(?:copyright|published\s+(?:in|at|by|for)|printed\s+(?:in|at|by|for)|'
                              r'(?:first|second|third|fourth|fifth|revised|new)\s+edition|'
                              r'edition\s+(?:of|published)|revised\s+to|university\s+press|'
                              r'american\s+book\s+company|publication\s+date)\b', re.I)
    if not bibliographic.search(notices[0]):
        return None, 'unestablished'
    years = set(int(v) for v in re.findall(r'(?<!\d)(\d{4})(?!\d)', notices[0]))
    # Separate copyright/imprint blocks can establish a later edition. A caller
    # cannot suppress those notices by selecting one old front-matter citation.
    for block in text[:32768].split('\n\n'):
        if len(block) <= 4096 and bibliographic.search(block):
            years.update(int(v) for v in re.findall(r'(?<!\d)(\d{4})(?!\d)', block))
    if len(years) > 1:
        return None, 'ambiguous'
    if len(years) != 1:
        return None, 'unestablished'
    return years.pop(), 'literal-year'


def validate(curriculum):
    fields(curriculum, {'schema', 'id', 'version', 'standing', 'title', 'levels',
                       'courses', 'specializations', 'regionalPolicy', 'knownCoverageGaps'},
           'curriculum')
    A.require(curriculum['schema'] == 'speakeasy-educational-curriculum/1'
              and curriculum['standing'] == 'candidate-curriculum', 'unsupported curriculum standing')
    for key in ('id', 'version', 'title'):
        A.identifier(curriculum[key], f'curriculum {key}')
    A.require(curriculum['levels'] == LEVELS, 'curriculum must preserve kindergarten through college levels')
    policy = curriculum['regionalPolicy']
    fields(policy, {'sharedCore', 'optionalUnitNumerator', 'optionalUnitDenominator',
                    'owner', 'migration'}, 'regional policy')
    A.require(policy['sharedCore'] == 'required-course-and-unit-identities'
              and policy['owner'] == 'explicit-region-cohort-institution-history'
              and policy['migration'] == 'preserve-source-education-history', 'regional policy differs')
    A.require(type(policy['optionalUnitNumerator']) is int and type(policy['optionalUnitDenominator']) is int
              and 0 <= policy['optionalUnitNumerator'] < policy['optionalUnitDenominator'] <= 1000,
              'invalid regional optional-unit proportion')
    A.require(isinstance(curriculum['courses'], list) and curriculum['courses'], 'empty course progression')
    courses, units = {}, {}
    for course in curriculum['courses']:
        fields(course, {'id', 'level', 'subject', 'title', 'requirement', 'prerequisites',
                        'units', 'optionalUnitIds', 'coverageNeeds'}, 'course')
        for key in ('id', 'subject', 'title'):
            A.identifier(course[key], f'course {key}')
        A.require(course['id'] not in courses, 'duplicate course')
        A.require(isinstance(course['level'], str)
                  and (course['level'] in LEVELS or course['level'].startswith('college-specialization:')),
                  'unknown course level')
        A.require(course['requirement'] in {'core', 'elective'}, 'unknown course requirement')
        names(course['prerequisites'], 'prerequisites', True)
        names(course['optionalUnitIds'], 'optional units', True)
        A.require(isinstance(course['coverageNeeds'], list)
                  and all(isinstance(x, str) and x for x in course['coverageNeeds']), 'invalid coverage needs')
        A.require(isinstance(course['units'], list), 'course units must be a list')
        for unit in course['units']:
            fields(unit, {'id', 'title', 'sourceId', 'sourceVersion', 'editionYear', 'editionEvidence',
                          'temporalStanding', 'selector', 'activities'}, 'unit')
            for key in ('id', 'title', 'sourceId', 'sourceVersion'):
                A.identifier(unit[key], f'unit {key}')
            if unit['editionYear'] is None:
                A.require(unit['editionEvidence'] is None, 'unknown edition year cannot claim dated evidence')
            else:
                year(unit['editionYear'], 'source edition year', 1400)
                fields(unit['editionEvidence'], {'basis', 'literal'}, 'edition evidence')
                A.identifier(unit['editionEvidence']['literal'], 'printed edition evidence')
                A.require(unit['editionEvidence']['basis'] == 'printed-source'
                          and str(unit['editionYear']) in unit['editionEvidence']['literal'],
                          'edition evidence does not bind declared year')
            A.require(unit['temporalStanding'] == 'source-period-review-required',
                      'candidate curriculum cannot approve historical equivalence')
            A.require(unit['id'] not in units, 'duplicate unit identity')
            fields(unit['selector'], {'sourcePath', 'sourceSha256', 'extractionSha256',
                                      'startCharacter', 'endCharacter', 'excerptSha256',
                                      'format'}, 'unit selector')
            selector = unit['selector']
            A.identifier(selector['sourcePath'], 'unit source path')
            for key in ('sourceSha256', 'extractionSha256', 'excerptSha256'):
                A.hash_value(selector[key], f'unit {key}')
            A.require(type(selector['startCharacter']) is int and type(selector['endCharacter']) is int
                      and 0 <= selector['startCharacter'] < selector['endCharacter'], 'invalid unit span')
            A.require(selector['format'] in {'plain-text', 'tex-source', 'cnxml', 'html-text-with-figure-references'},
                      'unsupported unit format')
            A.require(isinstance(unit['activities'], list) and unit['activities'], 'unit needs actual activities')
            for activity in unit['activities']:
                fields(activity, {'kind', 'literalEvidence'}, 'activity')
                A.require(activity['kind'] in {'instruction', 'reading-exercise', 'exercise', 'worked-example'},
                          'unsupported activity kind')
                A.identifier(activity['literalEvidence'], 'activity source evidence')
            units[unit['id']] = (course, unit)
        A.require(set(course['optionalUnitIds']) <= {u['id'] for u in course['units']}, 'unknown optional unit')
        courses[course['id']] = course
    for course in courses.values():
        A.require(set(course['prerequisites']) <= set(courses), 'unknown prerequisite course')
        A.require(course['id'] not in course['prerequisites'], 'course is its own prerequisite')
    # Cycles would make the claimed progression incoherent even when individual references resolve.
    def visit(identity, active, done):
        A.require(identity not in active, 'cyclic course progression')
        if identity in done:
            return
        for earlier in courses[identity]['prerequisites']:
            visit(earlier, active | {identity}, done)
        done.add(identity)
    completed = set()
    for identity in courses:
        visit(identity, set(), completed)
    for course in courses.values():
        if course['level'] in LEVELS:
            for earlier in course['prerequisites']:
                prior_level = courses[earlier]['level']
                A.require(prior_level in LEVELS and LEVELS.index(prior_level) <= LEVELS.index(course['level']),
                          'prerequisite course is later than its progression level')
    A.require(isinstance(curriculum['specializations'], list), 'specializations must be a list')
    spec_ids = set()
    for specialization in curriculum['specializations']:
        fields(specialization, {'id', 'title', 'courseIds', 'coverageNeeds'}, 'specialization')
        A.identifier(specialization['id'], 'specialization id')
        A.identifier(specialization['title'], 'specialization title')
        names(specialization['courseIds'], 'specialization courses')
        A.require(specialization['id'] not in spec_ids, 'duplicate specialization')
        A.require(set(specialization['courseIds']) <= set(courses), 'unknown specialization course')
        A.require(all(courses[c]['level'] == 'college-specialization:' + specialization['id']
                      for c in specialization['courseIds']), 'specialization course level differs')
        names(specialization['coverageNeeds'], 'specialization coverage needs', True)
        spec_ids.add(specialization['id'])
    A.require(all(c['level'] in LEVELS or c['level'].split(':', 1)[1] in spec_ids
                  for c in courses.values()), 'undeclared specialization')
    A.require(isinstance(curriculum['knownCoverageGaps'], list)
              and all(isinstance(v, str) and v for v in curriculum['knownCoverageGaps']), 'invalid curriculum gaps')
    A.require(all(any(c['level'] == level and c['requirement'] == 'core' for c in courses.values())
                  for level in LEVELS), 'missing required progression level')
    return courses, units


def resolve_units(curriculum, archive):
    """Validate immutable source selections; absent editions remain explicit coverage gaps."""
    J.protected_artifacts()
    courses, units = validate(curriculum)
    sources = {s['id']: s for s in C.verified_sources(archive)}
    text_cache, resolved, missing = {}, {}, []
    for identity, (course, unit) in units.items():
        source = sources.get(unit['sourceId'])
        if source is None:
            missing.append({'courseId': course['id'], 'unitId': identity,
                            'reason': 'source-not-acquired', 'sourceId': unit['sourceId']})
            continue
        if source['sourceVersion'] != unit['sourceVersion']:
            missing.append({'courseId': course['id'], 'unitId': identity,
                            'reason': 'source-version-mismatch', 'sourceId': unit['sourceId']})
            continue
        selector = unit['selector']
        entry = next((f for f in source['files'] if f['path'] == selector['sourcePath']), None)
        A.require(entry is not None and entry['sha256'] == selector['sourceSha256'], 'unit source binding differs')
        key = (source['id'], entry['path'])
        if key not in text_cache:
            # Filter the verified inventory before extraction. Scanning every earlier
            # module for every unit makes a real multi-book curriculum quadratic.
            selected = next(((text, coverage) for item, text, coverage in C.texts({**source, 'files': [entry]}, archive)
                             if item['path'] == entry['path']), None)
            A.require(selected is not None, 'unit does not select actual educational content')
            text_cache[key] = (*selected, C.sha(selected[0].encode()))
        text, coverage, extraction_sha = text_cache[key]
        edition_year, date_standing = source_edition_date(text, unit['editionEvidence'])
        if edition_year is not None:
            A.require(edition_year == unit['editionYear'], 'source notice date differs from declared edition')
        A.require(coverage['format'] == selector['format']
                  and extraction_sha == selector['extractionSha256'], 'unit extraction differs')
        start, end = selector['startCharacter'], selector['endCharacter']
        A.require(end <= len(text), 'unit span leaves source text')
        excerpt = text[start:end]
        A.require(C.sha(excerpt.encode()) == selector['excerptSha256'], 'unit excerpt differs')
        A.require(all(v['literalEvidence'] in excerpt for v in unit['activities']),
                  'activity evidence is absent from selected course material')
        # This notice is present in PG's diagram-only geometry text, which contains no course text.
        A.require('a text version was not prepared' not in excerpt.lower(), 'selected source omits its course text')
        resolved[identity] = {'courseId': course['id'], 'unitId': identity, 'title': unit['title'],
                              'sourceId': source['id'], 'sourceVersion': source['sourceVersion'],
                              'selector': copy.deepcopy(selector), 'activities': copy.deepcopy(unit['activities']),
                              'sourceStanding': source['standing'], 'sourceLicense': copy.deepcopy(source['license']),
                              'editionYear': edition_year, 'declaredEditionYear': unit['editionYear'],
                              'sourceEditionDateStanding': date_standing,
                              'temporalStanding': unit['temporalStanding'],
                              'editionEvidence': copy.deepcopy(unit['editionEvidence']),
                              'sourceCoverage': coverage}
    gaps = [*curriculum['knownCoverageGaps']]
    for level in LEVELS:
        expected = COLLEGE_DOMAINS if level == 'college-general' else SCHOOL_DOMAINS
        present = {c['subject'] for c in courses.values()
                   if c['level'] == level and c['requirement'] == 'core'}
        gaps.extend(f'{level}: required domain {subject} has no course'
                    for subject in sorted(expected - present))
    for course in courses.values():
        for need in course['coverageNeeds']:
            gaps.append(f"{course['id']}: {need}")
        if not course['units'] and not course['coverageNeeds']:
            gaps.append(f"{course['id']}: no sourced course units")
    for specialization in curriculum['specializations']:
        gaps.extend(f"{specialization['id']}: {need}" for need in specialization['coverageNeeds'])
    report = sealed({'schema': 'speakeasy-curriculum-coverage/1', 'curriculumRef': reference(curriculum),
                     'sourceArchiveSha256': C.sha((archive / 'acquisition.json').read_bytes()),
                     'resolvedUnits': list(resolved.values()), 'missingSelections': missing,
                     'coverageGaps': gaps, 'completeCurriculum': not missing and not gaps,
                     'curriculumStanding': 'candidate', 'trainingRows': 0,
                     'runtimeIntegration': False, 'personKnowledgeAuthority': False})
    return courses, units, resolved, report


def regional_index(records, curriculum, courses, registry=None):
    fields(records, {'schema', 'curriculumRef', 'regions'}, 'regional education records')
    A.require(records['schema'] == 'speakeasy-regional-education-history/1', 'unsupported regional history')
    match_reference(records['curriculumRef'], curriculum)
    registry = registry or {A.digest(curriculum): {'curriculum': curriculum, 'courses': courses,
                                                  'reference': reference(curriculum)}}
    A.require(isinstance(records['regions'], list) and records['regions'], 'missing explicit regions')
    regions, institutions = {}, {}
    for region in records['regions']:
        fields(region, {'id', 'stateBackgroundRef', 'cohorts'}, 'region')
        A.identifier(region['id'], 'region id')
        A.identifier(region['stateBackgroundRef'], 'owned simulated state background reference')
        A.require(region['id'] not in regions, 'duplicate region')
        A.require(isinstance(region['cohorts'], list) and region['cohorts'], 'region needs explicit cohorts')
        cohort_ids = set()
        for cohort in region['cohorts']:
            fields(cohort, {'id', 'curriculumRef', 'startYear', 'endYear', 'historyRef', 'institutions'}, 'cohort')
            A.identifier(cohort['id'], 'cohort id')
            A.identifier(cohort['historyRef'], 'cohort history reference')
            year(cohort['startYear'], 'cohort start year'); year(cohort['endYear'], 'cohort end year')
            A.require(cohort['startYear'] <= cohort['endYear'], 'reversed cohort years')
            A.require(cohort['id'] not in cohort_ids, 'duplicate cohort')
            fields(cohort['curriculumRef'], {'id', 'version', 'sha256'}, 'cohort source curriculum reference')
            local = registry.get(cohort['curriculumRef']['sha256'])
            A.require(local is not None, 'cohort source curriculum version is not registered')
            A.require(cohort['curriculumRef'] == local['reference'], 'missing or mismatched curriculum version')
            local_courses = local['courses']
            A.require(isinstance(cohort['institutions'], list) and cohort['institutions'], 'cohort needs institutions')
            for institution in cohort['institutions']:
                fields(institution, {'id', 'historyRef', 'levelIds', 'offeredCourseIds', 'optionalUnits'}, 'institution')
                A.identifier(institution['id'], 'institution id')
                A.identifier(institution['historyRef'], 'institution history reference')
                names(institution['levelIds'], 'institution levels')
                valid_levels = set(LEVELS) | {c['level'] for c in local_courses.values()}
                A.require(set(institution['levelIds']) <= valid_levels, 'institution names unknown educational level')
                names(institution['offeredCourseIds'], 'offered courses')
                A.require(set(institution['offeredCourseIds']) <= set(local_courses), 'institution offers unknown course')
                required = {c['id'] for c in local_courses.values()
                            if c['level'] in institution['levelIds'] and c['requirement'] == 'core'}
                A.require(required <= set(institution['offeredCourseIds']), 'regional propagation drops shared core')
                A.require(all(local_courses[c]['level'] in institution['levelIds'] for c in institution['offeredCourseIds']),
                          'institution course level differs')
                A.require(isinstance(institution['optionalUnits'], dict), 'optional variants must be explicit')
                selected = {}
                for course_id in institution['offeredCourseIds']:
                    course = local_courses[course_id]
                    optional = institution['optionalUnits'].get(course_id, [])
                    names(optional, 'regional optional unit choices', True)
                    A.require(set(optional) <= set(course['optionalUnitIds']), 'regional variant uses unauthorized unit')
                    core = [u['id'] for u in course['units'] if u['id'] not in course['optionalUnitIds']]
                    policy = local['curriculum']['regionalPolicy']
                    A.require(len(optional) * policy['optionalUnitDenominator']
                              <= len(core) * policy['optionalUnitNumerator'],
                              'regional variation exceeds declared optional-unit proportion')
                    selected[course_id] = core + optional
                A.require(set(institution['optionalUnits']) <= set(institution['offeredCourseIds']), 'variant names unoffered course')
                key = (region['id'], cohort['id'], institution['id'])
                A.require(key not in institutions, 'duplicate institution identity')
                institutions[key] = {'cohort': cohort, 'institution': institution, 'selectedUnits': selected,
                                     'stateBackgroundRef': region['stateBackgroundRef'], 'sourceCurriculum': local}
            cohort_ids.add(cohort['id'])
        regions[region['id']] = region
    return regions, institutions


def compile_history(curriculum, archive, regional_records, person, source_curricula=None):
    courses, units, resolved, coverage = resolve_units(curriculum, archive)
    registry = {coverage['curriculumRef']['sha256']: {'curriculum': curriculum, 'courses': courses, 'units': units,
                                                    'resolved': resolved, 'coverage': coverage,
                                                    'reference': coverage['curriculumRef']}}
    for source_curriculum in source_curricula or []:
        source_courses, source_units, source_resolved, source_coverage = resolve_units(source_curriculum, archive)
        identity = source_coverage['curriculumRef']['sha256']
        A.require(identity not in registry, 'duplicate registered source curriculum')
        A.require(not any(v['curriculum']['id'] == source_curriculum['id']
                          and v['curriculum']['version'] == source_curriculum['version']
                          for v in registry.values()), 'curriculum id/version has conflicting definitions')
        registry[identity] = {'curriculum': source_curriculum, 'courses': source_courses, 'units': source_units,
                              'resolved': source_resolved, 'coverage': source_coverage,
                              'reference': source_coverage['curriculumRef']}
    regions, institutions = regional_index(regional_records, curriculum, courses, registry)
    fields(person, {'schema', 'id', 'birthYear', 'asOfYear', 'birthRegionId', 'currentRegionId',
                    'migrations', 'educationHistory'}, 'person education history')
    A.require(person['schema'] == 'speakeasy-person-education-history/1', 'unsupported education history')
    A.identifier(person['id'], 'person id')
    year(person['birthYear'], 'birth year'); year(person['asOfYear'], 'as-of year')
    A.require(person['birthYear'] <= person['asOfYear'], 'education cutoff precedes birth')
    A.require(person['birthRegionId'] in regions and person['currentRegionId'] in regions, 'unknown person region')
    A.require(isinstance(person['migrations'], list), 'migrations must be explicit')
    residence, previous_year = person['birthRegionId'], person['birthYear']
    for migration in person['migrations']:
        fields(migration, {'year', 'fromRegionId', 'toRegionId', 'historyRef'}, 'migration')
        year(migration['year'], 'migration year'); A.identifier(migration['historyRef'], 'migration evidence')
        A.require(previous_year <= migration['year'] <= person['asOfYear'], 'migration chronology differs')
        A.require(migration['fromRegionId'] == residence and migration['toRegionId'] in regions
                  and migration['toRegionId'] != residence, 'migration chain differs')
        residence, previous_year = migration['toRegionId'], migration['year']
    A.require(residence == person['currentRegionId'], 'current region has no matching migration history')
    A.require(isinstance(person['educationHistory'], list), 'education history must be explicit')
    exposures, withheld, entries, seen, completed = [], [], [], set(), {}
    previous_start = person['birthYear']
    for entry in person['educationHistory']:
        fields(entry, {'id', 'regionId', 'cohortId', 'institutionId', 'curriculumRef', 'courseId',
                       'startYear', 'endYear', 'attendance', 'completion', 'evidenceRefs',
                       'exposedUnitIds'}, 'education entry')
        A.identifier(entry['id'], 'education entry id')
        A.require(entry['id'] not in seen, 'duplicate education entry'); seen.add(entry['id'])
        year(entry['startYear'], 'education start year'); year(entry['endYear'], 'education end year')
        A.require(previous_start <= entry['startYear'] <= entry['endYear'] <= person['asOfYear'],
                  'education history chronology or cutoff differs')
        previous_start = entry['startYear']
        key = (entry['regionId'], entry['cohortId'], entry['institutionId'])
        A.require(key in institutions, 'education entry has no source institution history')
        history = institutions[key]
        local = history['sourceCurriculum']
        fields(entry['curriculumRef'], {'id', 'version', 'sha256'}, 'entry source curriculum reference')
        A.require(entry['curriculumRef'] == local['reference'], 'missing or mismatched curriculum version')
        A.require(history['cohort']['startYear'] <= entry['startYear'] <= entry['endYear']
                  <= history['cohort']['endYear'], 'education falls outside source cohort')
        A.require(entry['courseId'] in history['selectedUnits'], 'course not offered by source institution')
        A.require(entry['attendance'] in {'attended', 'not-attended', 'unknown'}
                  and entry['completion'] in {'completed', 'not-completed', 'unknown'}, 'invalid attendance/completion')
        A.require(entry['attendance'] != 'not-attended' or entry['completion'] != 'completed', 'completion contradicts attendance')
        names(entry['evidenceRefs'], 'education evidence', True)
        names(entry['exposedUnitIds'], 'exposed units', True)
        A.require(set(entry['exposedUnitIds']) <= set(history['selectedUnits'][entry['courseId']]),
                  'exposure selects units absent from source institution curriculum')
        A.require(not entry['exposedUnitIds'] or entry['attendance'] == 'attended', 'exposure lacks attendance')
        prerequisites = local['courses'][entry['courseId']]['prerequisites']
        source_key = local['reference']['sha256']
        absent_prerequisites = [c for c in prerequisites
                                if (source_key, c) not in completed or completed[(source_key, c)] > entry['startYear']]
        if entry['completion'] == 'completed' and entry['evidenceRefs']:
            completion_key = (source_key, entry['courseId'])
            completed[completion_key] = min(entry['endYear'], completed.get(completion_key, entry['endYear']))
        entries.append({'educationEntryId': entry['id'], 'sourceRegionId': entry['regionId'],
                        'sourceStateBackgroundRef': history['stateBackgroundRef'],
                        'sourceCohortId': entry['cohortId'], 'sourceInstitutionId': entry['institutionId'],
                        'courseId': entry['courseId'], 'attendance': entry['attendance'],
                        'sourceCurriculumRef': copy.deepcopy(local['reference']),
                        'completion': entry['completion'], 'evidenceRefs': entry['evidenceRefs'],
                        'unestablishedPrerequisites': absent_prerequisites,
                        'exposedUnitsDeclared': len(entry['exposedUnitIds']),
                        'retention': 'not-established'})
        for identity in entry['exposedUnitIds']:
            reasons = []
            if identity not in local['resolved']:
                reasons.append('source-selection-unavailable')
            if not entry['evidenceRefs']:
                reasons.append('education-exposure-evidence-missing')
            selection = local['resolved'].get(identity)
            edition_year = selection['editionYear'] if selection is not None else None
            if selection is not None and selection['sourceEditionDateStanding'] == 'ambiguous':
                reasons.append('source-edition-year-ambiguous')
            if edition_year is None:
                reasons.append('source-edition-year-unestablished')
            elif edition_year > entry['startYear']:
                reasons.append('source-edition-postdates-education')
            provenance = {'personId': person['id'], 'educationEntryId': entry['id'],
                          'sourceRegionId': entry['regionId'], 'sourceCohortId': entry['cohortId'],
                          'sourceInstitutionId': entry['institutionId'], 'courseId': entry['courseId'],
                          'unitId': identity, 'startYear': entry['startYear'], 'endYear': entry['endYear'],
                          'attendance': entry['attendance'], 'completion': entry['completion'],
                          'evidenceRefs': copy.deepcopy(entry['evidenceRefs'])}
            provenance['sourceCurriculumRef'] = copy.deepcopy(local['reference'])
            if reasons:
                withheld.append({**provenance, 'reasons': reasons})
            else:
                exposures.append({**provenance, 'sourceSelection': copy.deepcopy(local['resolved'][identity]),
                                  'standing': 'exposure-candidate', 'retention': 'not-established',
                                  'personalAcquisitionAuthority': False, 'nativeSkillAuthority': False,
                                  'currentWorldAuthority': False, 'peerAssentAuthority': False})
    return sealed({'schema': 'speakeasy-person-educational-exposures/1', 'personId': person['id'],
                   'asOfYear': person['asOfYear'], 'currentRegionId': person['currentRegionId'],
                   'birthRegionId': person['birthRegionId'], 'migrations': copy.deepcopy(person['migrations']),
                   'curriculumRef': copy.deepcopy(coverage['curriculumRef']), 'educationEntries': entries,
                   'exposureCandidates': exposures, 'withheldExposures': withheld,
                   'coverageSha256': coverage['contentSha256'],
                   'sourceCurriculaCoverage': [{'curriculumRef': copy.deepcopy(v['reference']),
                                                'coverageSha256': v['coverage']['contentSha256']}
                                               for _, v in sorted(registry.items())],
                   'regionalHistorySha256': A.digest(regional_records), 'personHistorySha256': A.digest(person),
                   'sourceArchiveSha256': coverage['sourceArchiveSha256'],
                   'retentionOwner': 'SAO-person-owned-acquisition-and-retention',
                   'sourceTask': 'shared-cognitive-base', 'opposingAssociativeModelIndependent': True,
                   'runtimeIntegration': False, 'trainingRows': 0, 'knownConcepts': [], 'nativeSkills': [],
                   'currentWorldClaims': [], 'peerAssent': [], 'standing': 'candidate-education-history'})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['coverage', 'compile'])
    parser.add_argument('--curriculum', type=Path, default=CURRICULUM)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--regions', type=Path)
    parser.add_argument('--person', type=Path)
    parser.add_argument('--source-curriculum', type=Path, action='append', default=[],
                        help='Register exact prior or outsider source curricula; residence never replaces them')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        curriculum = A.read(args.curriculum)
        if args.action == 'coverage':
            result = resolve_units(curriculum, args.archive)[3]
        else:
            A.require(args.regions is not None and args.person is not None, 'compile needs region and person histories')
            result = compile_history(curriculum, args.archive, A.read(args.regions), A.read(args.person),
                                     [A.read(p) for p in args.source_curriculum])
        A.require(not args.out.exists(), 'preserve existing curriculum output')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(A.encoded(result) + b'\n')
    except (ValueError, OSError, ET.ParseError, UnicodeError) as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        return 2
    print(f"WROTE {result['schema']} {result['contentSha256']}; zero admitted training rows")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
