"""Curriculum histories preserve actual source selections and person-owned boundaries."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import decision_authoring as A
import education_corpus as C
import education_curriculum as K


class EducationCurriculumTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.archive = self.root / 'archive'
        body = 'Copyright, 1900.\n' + '\n'.join(f'LESSON {i}.\nWorked example {i}.\nExercise {i}: count objects.'
                         for i in range(1, 13))
        self.raw = ('*** START OF THE PROJECT GUTENBERG EBOOK CONTROL ***\n'
                    + body + '\n*** END OF THE PROJECT GUTENBERG EBOOK CONTROL ***').encode()
        page = (b'<title>Controlled curriculum text</title>Public domain in the USA '
                b'<a href="/files/1/1.txt" type="text/plain">Text</a>')
        catalogue = {'schema': 'speakeasy-education-source-catalogue/1', 'standing': 'candidate-sources',
                     'sources': [{'id': 'controlled-reader', 'provider': 'gutenberg', 'bookId': 1,
                                  'stages': ['kindergarten'], 'subjects': ['literacy']}]}
        with patch.object(C, 'fetch', side_effect=lambda url: (page if '/ebooks/' in url else self.raw, url)):
            C.acquire(catalogue, self.archive)
        source = C.verified_sources(self.archive)[0]
        file, text, coverage = next(C.texts(source, self.archive))
        units = []
        for i in range(1, 13):
            start = text.index(f'LESSON {i}.')
            end = text.index(f'LESSON {i + 1}.') if i < 12 else len(text)
            units.append({'id': f'unit-{i}', 'title': f'Lesson {i}', 'sourceId': source['id'],
                          'sourceVersion': source['sourceVersion'], 'editionYear': 1900,
                          'editionEvidence': {'basis': 'printed-source', 'literal': 'Copyright, 1900.'},
                          'temporalStanding': 'source-period-review-required',
                          'selector': {'sourcePath': file['path'], 'sourceSha256': file['sha256'],
                                       'extractionSha256': C.sha(text.encode()), 'startCharacter': start,
                                       'endCharacter': end, 'excerptSha256': C.sha(text[start:end].encode()),
                                       'format': coverage['format']},
                          'activities': [{'kind': 'worked-example', 'literalEvidence': f'Worked example {i}.'},
                                         {'kind': 'exercise', 'literalEvidence': f'Exercise {i}:'}]})
        courses = [{'id': level + '-literacy', 'level': level, 'subject': 'literacy',
                    'title': 'Controlled literacy progression', 'requirement': 'core',
                    'prerequisites': [] if i == 0 else [K.LEVELS[i - 1] + '-literacy'],
                    'units': units if i == 0 else [], 'optionalUnitIds': ['unit-11', 'unit-12'] if i == 0 else [],
                    'coverageNeeds': [] if i == 0 else ['Actual higher-level course material absent']}
                   for i, level in enumerate(K.LEVELS)]
        self.curriculum = {'schema': 'speakeasy-educational-curriculum/1', 'id': 'controlled-progression',
                           'version': 'test-1', 'standing': 'candidate-curriculum',
                           'title': 'Controlled source curriculum', 'levels': K.LEVELS,
                           'courses': courses, 'specializations': [],
                           'regionalPolicy': {'sharedCore': 'required-course-and-unit-identities',
                                              'optionalUnitNumerator': 1, 'optionalUnitDenominator': 5,
                                              'owner': 'explicit-region-cohort-institution-history',
                                              'migration': 'preserve-source-education-history'},
                           'knownCoverageGaps': ['Controlled fixture has no complete curriculum']}
        ref = K.reference(self.curriculum)
        def region(identity, optional):
            institution = {'id': 'school', 'historyRef': identity + '-school-history',
                           'levelIds': ['kindergarten'], 'offeredCourseIds': ['kindergarten-literacy'],
                           'optionalUnits': {'kindergarten-literacy': optional}}
            return {'id': identity, 'stateBackgroundRef': identity + '-owned-state-background',
                    'cohorts': [{'id': '1960s', 'curriculumRef': copy.deepcopy(ref), 'startYear': 1960, 'endYear': 1970,
                                 'historyRef': identity + '-cohort-history', 'institutions': [institution]}]}
        self.regions = {'schema': 'speakeasy-regional-education-history/1', 'curriculumRef': ref,
                        'regions': [region('kentucky', ['unit-11']), region('ohio', ['unit-12'])]}
        self.person = {'schema': 'speakeasy-person-education-history/1', 'id': 'controlled-person',
                       'birthYear': 1960, 'asOfYear': 1993, 'birthRegionId': 'ohio',
                       'currentRegionId': 'kentucky',
                       'migrations': [{'year': 1985, 'fromRegionId': 'ohio', 'toRegionId': 'kentucky',
                                       'historyRef': 'controlled-migration-history'}],
                       'educationHistory': [{'id': 'schooling-1', 'regionId': 'ohio', 'cohortId': '1960s',
                                             'institutionId': 'school', 'curriculumRef': ref,
                                             'courseId': 'kindergarten-literacy', 'startYear': 1965, 'endYear': 1966,
                                             'attendance': 'attended', 'completion': 'completed',
                                             'evidenceRefs': ['controlled-school-record'],
                                             'exposedUnitIds': ['unit-1', 'unit-12']}]}

    def tearDown(self):
        self.tmp.cleanup()

    def compile(self):
        return K.compile_history(self.curriculum, self.archive, self.regions, self.person)

    def refresh_refs(self):
        ref = K.reference(self.curriculum)
        self.regions['curriculumRef'] = ref
        for region in self.regions['regions']:
            for cohort in region['cohorts']:
                cohort['curriculumRef'] = ref
        for entry in self.person['educationHistory']:
            entry['curriculumRef'] = ref

    def test_real_source_selectors_resolve_with_actual_examples(self):
        result = K.resolve_units(self.curriculum, self.archive)[3]
        self.assertEqual(len(result['resolvedUnits']), 12)
        self.assertEqual(result['missingSelections'], [])
        self.assertFalse(result['completeCurriculum'])
        self.assertEqual(result['resolvedUnits'][0]['activities'][0]['literalEvidence'], 'Worked example 1.')

    def test_migration_preserves_outsider_source_curriculum(self):
        result = self.compile()
        self.assertEqual(result['currentRegionId'], 'kentucky')
        self.assertEqual([e['sourceRegionId'] for e in result['exposureCandidates']], ['ohio', 'ohio'])
        self.assertEqual(result['exposureCandidates'][1]['unitId'], 'unit-12')
        self.assertEqual(result['educationEntries'][0]['sourceStateBackgroundRef'], 'ohio-owned-state-background')

    def test_same_region_keeps_core_with_small_owned_optional_variation(self):
        courses, _ = K.validate(self.curriculum)
        _, records = K.regional_index(self.regions, self.curriculum, courses)
        ky = records[('kentucky', '1960s', 'school')]['selectedUnits']['kindergarten-literacy']
        oh = records[('ohio', '1960s', 'school')]['selectedUnits']['kindergarten-literacy']
        self.assertEqual(ky[:10], oh[:10])
        self.assertEqual(ky[-1], 'unit-11'); self.assertEqual(oh[-1], 'unit-12')

    def test_completed_course_does_not_invent_exposures_or_retention(self):
        self.person['educationHistory'][0]['exposedUnitIds'] = []
        result = self.compile()
        self.assertEqual(result['exposureCandidates'], [])
        self.assertEqual(result['educationEntries'][0]['completion'], 'completed')
        self.assertEqual(result['knownConcepts'], []); self.assertEqual(result['nativeSkills'], [])
        self.assertEqual(result['currentWorldClaims'], []); self.assertEqual(result['peerAssent'], [])

    def test_exposure_preserves_authority_boundaries_and_independent_opponent(self):
        result = self.compile()
        row = result['exposureCandidates'][0]
        self.assertEqual(row['retention'], 'not-established')
        for name in ('personalAcquisitionAuthority', 'nativeSkillAuthority', 'currentWorldAuthority', 'peerAssentAuthority'):
            self.assertFalse(row[name])
        self.assertFalse(result['runtimeIntegration']); self.assertTrue(result['opposingAssociativeModelIndependent'])
        self.assertEqual(result['sourceTask'], 'shared-cognitive-base')
        self.assertEqual(result['trainingRows'], 0)

    def test_attendance_without_completion_remains_candidate(self):
        self.person['educationHistory'][0]['completion'] = 'not-completed'
        result = self.compile()
        self.assertEqual(len(result['exposureCandidates']), 2)
        self.assertEqual(result['exposureCandidates'][0]['completion'], 'not-completed')

    def test_missing_exposure_evidence_is_withheld(self):
        self.person['educationHistory'][0]['evidenceRefs'] = []
        result = self.compile()
        self.assertFalse(result['exposureCandidates'])
        self.assertIn('education-exposure-evidence-missing', result['withheldExposures'][0]['reasons'])

    def test_modern_source_cannot_be_backdated_into_schooling(self):
        # Change the supported attendance years instead of inventing a printed future year.
        self.person['birthYear'] = 1860
        self.person['migrations'][0]['year'] = 1885
        self.person['educationHistory'][0].update(startYear=1865, endYear=1866)
        self.regions['regions'][1]['cohorts'][0].update(startYear=1860, endYear=1870)
        self.refresh_refs()
        result = self.compile()
        self.assertEqual(len(result['exposureCandidates']), 0)
        self.assertEqual(result['withheldExposures'][0]['unitId'], 'unit-1')
        self.assertIn('source-edition-postdates-education', result['withheldExposures'][0]['reasons'])

    def test_unknown_source_year_is_withheld(self):
        unit = self.curriculum['courses'][0]['units'][0]
        unit.update(editionYear=None, editionEvidence=None)
        self.refresh_refs()
        result = self.compile()
        self.assertIn('source-edition-year-unestablished', result['withheldExposures'][0]['reasons'])

    def test_invented_source_year_refuses(self):
        unit = self.curriculum['courses'][0]['units'][0]
        unit.update(editionYear=1800, editionEvidence={'basis': 'printed-source', 'literal': 'Copyright, 1800.'})
        with self.assertRaisesRegex(ValueError, 'dated edition evidence is absent'):
            K.resolve_units(self.curriculum, self.archive)

    def test_multiple_printed_years_do_not_backdate_an_edition(self):
        literal = 'Copyright, 1800 and 1900.'
        raw = self.raw.replace(b'Copyright, 1900.', literal.encode())
        self.archive = self.root / 'ambiguous-archive'
        catalogue = {'schema': 'speakeasy-education-source-catalogue/1', 'standing': 'candidate-sources',
                     'sources': [{'id': 'controlled-reader', 'provider': 'gutenberg', 'bookId': 1,
                                  'stages': ['kindergarten'], 'subjects': ['literacy']}]}
        page = (b'<title>Controlled curriculum text</title>Public domain in the USA '
                b'<a href="/files/1/1.txt" type="text/plain">Text</a>')
        with patch.object(C, 'fetch', side_effect=lambda url: (page if '/ebooks/' in url else raw, url)):
            C.acquire(catalogue, self.archive)
        source = C.verified_sources(self.archive)[0]
        file, text, coverage = next(C.texts(source, self.archive))
        for i, unit in enumerate(self.curriculum['courses'][0]['units'], 1):
            start = text.index(f'LESSON {i}.')
            end = text.index(f'LESSON {i + 1}.') if i < 12 else len(text)
            unit.update(sourceVersion=source['sourceVersion'], editionYear=1800,
                        editionEvidence={'basis': 'printed-source', 'literal': literal})
            unit['selector'].update(sourcePath=file['path'], sourceSha256=file['sha256'],
                                    extractionSha256=C.sha(text.encode()), startCharacter=start,
                                    endCharacter=end, excerptSha256=C.sha(text[start:end].encode()),
                                    format=coverage['format'])
        self.person['birthYear'] = 1860
        self.person['migrations'][0]['year'] = 1885
        self.person['educationHistory'][0].update(startYear=1865, endYear=1866)
        self.regions['regions'][1]['cohorts'][0].update(startYear=1860, endYear=1870)
        self.refresh_refs()
        result = self.compile()
        self.assertFalse(result['exposureCandidates'])
        self.assertIn('source-edition-year-ambiguous', result['withheldExposures'][0]['reasons'])
        for unit in self.curriculum['courses'][0]['units']:
            unit['editionEvidence']['literal'] = 'Copyright, 1800'
        self.refresh_refs()
        shortened = self.compile()
        self.assertFalse(shortened['exposureCandidates'])
        self.assertIn('source-edition-year-ambiguous', shortened['withheldExposures'][0]['reasons'])

    def test_later_date_on_notice_continuation_is_withheld(self):
        evidence = {'basis': 'printed-source', 'literal': 'Copyright, 1800'}
        text = 'Title\n\nCopyright, 1800\nand 1900.\nPublished by Control.\n\nLESSON 1.'
        self.assertEqual(K.source_edition_date(text, evidence), (None, 'ambiguous'))
        uncertain = 'Copyright, 1800 ' + 'x' * 4096
        self.assertEqual(K.source_edition_date(uncertain, evidence), (None, 'unestablished'))

    def test_historical_prose_is_not_an_edition_notice(self):
        text = 'Copyright, 2001.\n\nPublished in 2001.\n\nThe winter of 1800 was cold.'
        self.assertEqual(K.source_edition_date(text, {'basis':'printed-source','literal':'1800'}),
                         (None,'unestablished'))
        text = 'Published in 1800.\n\nCopyright, 2001.'
        self.assertEqual(K.source_edition_date(text, {'basis':'printed-source','literal':'Published in 1800.'}),
                         (None,'ambiguous'))

    def test_electives_do_not_complete_missing_shared_core_domains(self):
        self.curriculum['knownCoverageGaps'] = []
        for course in list(self.curriculum['courses']):
            course['coverageNeeds'] = []
            expected = K.COLLEGE_DOMAINS if course['level'] == 'college-general' else K.SCHOOL_DOMAINS
            course['subject'] = sorted(expected)[0]
            if not course['units']:
                unit = copy.deepcopy(self.curriculum['courses'][0]['units'][0])
                unit['id'] = course['id'] + '-unit'
                course['units'] = [unit]
            for subject in sorted(expected - {course['subject']}):
                elective = copy.deepcopy(course)
                elective.update(id=course['level'] + '-elective-' + subject, subject=subject, requirement='elective',
                                prerequisites=[], optionalUnitIds=[])
                elective['units'] = [copy.deepcopy(elective['units'][0])]
                elective['units'][0]['id'] = elective['id'] + '-unit'
                self.curriculum['courses'].append(elective)
        report = K.resolve_units(self.curriculum, self.archive)[3]
        self.assertFalse(report['completeCurriculum'])
        self.assertIn('kindergarten: required domain languages has no course', report['coverageGaps'])

    def test_outsider_can_retain_distinct_registered_curriculum_version(self):
        foreign = copy.deepcopy(self.curriculum)
        foreign.update(id='ohio-source-curriculum', version='prior-distinct-version')
        # Distinct source sequences can differ substantially between regions; each
        # region still preserves its own stable institution core.
        foreign['courses'][0]['units'] = foreign['courses'][0]['units'][1:]
        foreign['courses'][0]['optionalUnitIds'] = ['unit-12']
        ref = K.reference(foreign)
        self.regions['regions'][1]['cohorts'][0]['curriculumRef'] = ref
        self.person['educationHistory'][0]['curriculumRef'] = ref
        self.person['educationHistory'][0]['exposedUnitIds'] = ['unit-2', 'unit-12']
        result = K.compile_history(self.curriculum, self.archive, self.regions, self.person, [foreign])
        self.assertEqual(result['exposureCandidates'][0]['sourceCurriculumRef'], ref)
        self.assertEqual(result['currentRegionId'], 'kentucky')
        with self.assertRaisesRegex(ValueError, 'not registered'):
            self.compile()

    def test_current_residence_does_not_replace_optional_source_unit(self):
        self.person['educationHistory'][0]['exposedUnitIds'] = ['unit-11']
        with self.assertRaisesRegex(ValueError, 'absent from source institution'):
            self.compile()

    def test_broad_regional_variation_refuses(self):
        self.curriculum['courses'][0]['optionalUnitIds'] = ['unit-10', 'unit-11', 'unit-12']
        self.regions['regions'][0]['cohorts'][0]['institutions'][0]['optionalUnits'] = {
            'kindergarten-literacy': ['unit-10', 'unit-11', 'unit-12']}
        self.refresh_refs()
        with self.assertRaisesRegex(ValueError, 'exceeds declared optional-unit proportion'):
            self.compile()

    def test_optional_variation_proportion_is_owned_curriculum_parameter(self):
        self.curriculum['regionalPolicy'].update(optionalUnitNumerator=1, optionalUnitDenominator=10)
        self.refresh_refs()
        self.assertEqual(len(self.compile()['exposureCandidates']), 2)
        self.curriculum['regionalPolicy']['optionalUnitDenominator'] = 0
        with self.assertRaisesRegex(ValueError, 'invalid regional optional-unit proportion'):
            K.validate(self.curriculum)

    def test_regional_core_removal_refuses(self):
        self.regions['regions'][0]['cohorts'][0]['institutions'][0]['offeredCourseIds'] = ['grade-1-literacy']
        with self.assertRaisesRegex(ValueError, 'drops shared core'):
            self.compile()

    def test_missing_curriculum_version_refuses(self):
        self.person['educationHistory'][0]['curriculumRef']['version'] = 'foreign-version'
        with self.assertRaisesRegex(ValueError, 'mismatched curriculum'):
            self.compile()

    def test_missing_source_reports_coverage_without_inventing_text(self):
        self.curriculum['courses'][0]['units'][0]['sourceId'] = 'not-acquired'
        self.refresh_refs()
        report = K.resolve_units(self.curriculum, self.archive)[3]
        self.assertEqual(report['missingSelections'][0]['reason'], 'source-not-acquired')
        result = self.compile()
        self.assertEqual(len(result['exposureCandidates']), 1)
        self.assertIn('source-selection-unavailable', result['withheldExposures'][0]['reasons'])

    def test_mismatched_source_version_reports_coverage_gap(self):
        self.curriculum['courses'][0]['units'][0]['sourceVersion'] = 'foreign-version'
        report = K.resolve_units(self.curriculum, self.archive)[3]
        self.assertEqual(report['missingSelections'][0]['reason'], 'source-version-mismatch')

    def test_wrong_unit_bytes_refuse(self):
        self.curriculum['courses'][0]['units'][0]['selector']['excerptSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'excerpt differs'):
            K.resolve_units(self.curriculum, self.archive)

    def test_fabricated_activity_refuses(self):
        self.curriculum['courses'][0]['units'][0]['activities'][0]['literalEvidence'] = 'Imagined example'
        with self.assertRaisesRegex(ValueError, 'activity evidence is absent'):
            K.resolve_units(self.curriculum, self.archive)

    def test_future_education_refuses(self):
        self.person['educationHistory'][0]['endYear'] = 1994
        with self.assertRaisesRegex(ValueError, 'chronology or cutoff'):
            self.compile()

    def test_unsorted_history_refuses(self):
        first = self.person['educationHistory'][0]
        second = copy.deepcopy(first); second['id'] = 'schooling-2'; second['startYear'] = 1964
        self.person['educationHistory'].append(second)
        with self.assertRaisesRegex(ValueError, 'chronology or cutoff'):
            self.compile()

    def test_migration_without_history_chain_refuses(self):
        self.person['migrations'][0]['fromRegionId'] = 'kentucky'
        with self.assertRaisesRegex(ValueError, 'migration chain'):
            self.compile()

    def test_unknown_institution_and_cohort_refuse(self):
        self.person['educationHistory'][0]['institutionId'] = 'imagined-school'
        with self.assertRaisesRegex(ValueError, 'no source institution history'):
            self.compile()

    def test_absent_attendance_cannot_supply_exposure(self):
        self.person['educationHistory'][0]['attendance'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'exposure lacks attendance'):
            self.compile()

    def test_no_unseen_world_or_persona_authority_fields(self):
        self.person['countyThreats'] = ['secret future event']
        with self.assertRaisesRegex(ValueError, 'person education history fields differ'):
            self.compile()

    def test_curriculum_cycle_refuses(self):
        self.curriculum['courses'][0]['prerequisites'] = ['grade-1-literacy']
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            K.validate(self.curriculum)

    def test_declared_specialization_only_institution_can_supply_exact_course_exposure(self):
        specialized = copy.deepcopy(self.curriculum['courses'][0])
        specialized.update(id='college-specialization:mathematics-analysis',
                           level='college-specialization:mathematics', subject='analysis',
                           requirement='elective', optionalUnitIds=[])
        specialized['units'] = [copy.deepcopy(specialized['units'][0])]
        specialized['units'][0]['id'] = 'specialization-unit'
        self.curriculum['courses'].append(specialized)
        self.curriculum['specializations'] = [{'id': 'mathematics', 'title': 'Controlled mathematics',
                                              'courseIds': [specialized['id']], 'coverageNeeds': []}]
        self.refresh_refs()
        school = self.regions['regions'][1]['cohorts'][0]['institutions'][0]
        school.update(levelIds=[specialized['level']], offeredCourseIds=[specialized['id']], optionalUnits={})
        self.person['educationHistory'][0].update(courseId=specialized['id'], exposedUnitIds=['specialization-unit'])
        result = self.compile()
        self.assertEqual(result['exposureCandidates'][0]['unitId'], 'specialization-unit')

    def test_deterministic_output_and_hash_bind_person_history(self):
        first = self.compile(); self.assertEqual(first, self.compile())
        self.person['educationHistory'][0]['completion'] = 'not-completed'
        second = self.compile()
        self.assertNotEqual(first['personHistorySha256'], second['personHistorySha256'])
        self.assertNotEqual(first['contentSha256'], second['contentSha256'])

    def test_duplicate_version_with_different_curriculum_content_refuses(self):
        foreign = copy.deepcopy(self.curriculum)
        foreign['title'] = 'Conflicting same-version source definition'
        with self.assertRaisesRegex(ValueError, 'conflicting definitions'):
            K.compile_history(self.curriculum, self.archive, self.regions, self.person, [foreign])

    def test_repeated_course_does_not_erase_earlier_completion_evidence(self):
        school = self.regions['regions'][1]['cohorts'][0]['institutions'][0]
        school['levelIds'].append('grade-1')
        school['offeredCourseIds'].append('grade-1-literacy')
        first = self.person['educationHistory'][0]
        second = copy.deepcopy(first)
        second.update(id='retake', startYear=1967, endYear=1970, exposedUnitIds=[])
        third = copy.deepcopy(first)
        third.update(id='next-course', courseId='grade-1-literacy', startYear=1968, endYear=1969, exposedUnitIds=[])
        self.person['educationHistory'].extend([second, third])
        self.assertEqual(self.compile()['educationEntries'][-1]['unestablishedPrerequisites'], [])


if __name__ == '__main__':
    unittest.main()
