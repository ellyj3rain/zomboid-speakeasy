"""Exercise generated bodies, schooling receipts and the real compiler boundary."""
import contextlib
import copy
import io
import unittest
from unittest.mock import patch

import decision_authoring as A
import education_backgrounds as B
import education_curriculum as K
import education_corpus as C
import test_education_curriculum as F


class EducationBackgroundTests(unittest.TestCase):
    def setUp(self):
        # Existing archive fixture preserves actual source selectors and extraction;
        # the producer and K.compile_history themselves are never mocked.
        self.fixture = F.EducationCurriculumTests('test_real_source_selectors_resolve_with_actual_examples')
        self.fixture.setUp()
        self.archive, self.root = self.fixture.archive, self.fixture.root
        self.curriculum = self.fixture.curriculum
        self.foreign = copy.deepcopy(self.curriculum)
        self.foreign.update(id='foreign-progression', version='foreign-1')
        for unit in self.foreign['courses'][0]['units']:
            unit['id'] = 'foreign-' + unit['id']
        self.foreign['courses'][0]['optionalUnitIds'] = ['foreign-unit-11', 'foreign-unit-12']
        self.curricula = [self.curriculum, self.foreign]
        participation = {'enrolmentProbability': 1, 'attendanceProbability': 1,
                         'interruptionProbability': 0, 'completionProbability': 1,
                         'minimumInterruptedExposureFraction': 0}
        def region(identity, curriculum):
            return {'id': identity, 'cohorts': [{'id': 'mid-century', 'startYear': 1950,
                    'endYear': 1993, 'curriculumRef': K.reference(curriculum),
                    'institutions': [{'id': identity + '-school', 'levelIds': K.LEVELS,
                    'offeredCourseIds': [c['id'] for c in curriculum['courses']],
                    'participation': copy.deepcopy(participation), 'authoredOptionalUnits': {}}]}]}
        self.plan = {'schema': 'speakeasy-education-background-plan/1', 'id': 'owned-schooling-plan',
                     'worldOwner': {'id': 'world-test', 'seed': 'explicit-world-seed'},
                     'curriculumRef': K.reference(self.curriculum),
                     'regions': [region('kentucky', self.curriculum), region('outside', self.foreign)]}
        self.profile = {'schema': 'speakeasy-simulated-education-profile/1', 'id': 'person-outsider',
                        'birthYear': 1960, 'asOfYear': 1993, 'birthRegionId': 'outside',
                        'currentRegionId': 'kentucky',
                        'migrations': [{'year': 1985, 'fromRegionId': 'outside', 'toRegionId': 'kentucky'}],
                        'collegeYears': 0, 'electiveCourseIds': []}

    def tearDown(self):
        self.fixture.tearDown()

    def generate(self):
        backgrounds = B.generate_backgrounds(self.plan, self.curricula, self.archive)
        person = B.generate_person(self.profile, backgrounds, self.plan, self.curricula, self.archive)
        return backgrounds, person

    def compile(self, backgrounds=None, person=None):
        if backgrounds is None:
            backgrounds, person = self.generate()
        return B.compile_generated(self.curriculum, self.archive, self.plan, backgrounds,
                                   self.profile, person, [self.foreign])

    def participation(self, **changes):
        for region in self.plan['regions']:
            for cohort in region['cohorts']:
                for school in cohort['institutions']:
                    school['participation'].update(changes)

    def replace_edition(self, notice, declared_year):
        self.archive = self.root / 'different-edition'
        raw = self.fixture.raw.replace(b'Copyright, 1900.', notice.encode())
        page = (b'<title>Controlled curriculum text</title>Public domain in the USA '
                b'<a href="/files/1/1.txt" type="text/plain">Text</a>')
        catalogue = {'schema': 'speakeasy-education-source-catalogue/1', 'standing': 'candidate-sources',
                     'sources': [{'id': 'controlled-reader', 'provider': 'gutenberg', 'bookId': 1,
                                  'stages': ['kindergarten'], 'subjects': ['literacy']}]}
        with patch.object(C, 'fetch', side_effect=lambda url: (page if '/ebooks/' in url else raw, url)):
            C.acquire(catalogue, self.archive)
        source = C.verified_sources(self.archive)[0]
        file, text, coverage = next(C.texts(source, self.archive))
        for curriculum in self.curricula:
            for i, unit in enumerate(curriculum['courses'][0]['units'], 1):
                start = text.index(f'LESSON {i}.')
                end = text.index(f'LESSON {i + 1}.') if i < 12 else len(text)
                unit.update(sourceVersion=source['sourceVersion'], editionYear=declared_year,
                            editionEvidence={'basis': 'printed-source', 'literal': notice})
                unit['selector'] = {'sourcePath': file['path'], 'sourceSha256': file['sha256'],
                                    'extractionSha256': C.sha(text.encode()), 'startCharacter': start,
                                    'endCharacter': end, 'excerptSha256': C.sha(text[start:end].encode()),
                                    'format': coverage['format']}
        self.plan['curriculumRef'] = K.reference(self.curriculum)
        for region, curriculum in zip(self.plan['regions'], self.curricula):
            region['cohorts'][0]['curriculumRef'] = K.reference(curriculum)

    def test_actual_producer_and_wrapper_preserve_foreign_source(self):
        backgrounds, person = self.generate()
        result = self.compile(backgrounds, person)
        self.assertIn(len(result['exposureCandidates']), (11, 12))
        self.assertEqual(result['currentRegionId'], 'kentucky')
        self.assertTrue(all(e['sourceRegionId'] == 'outside' for e in result['exposureCandidates']))
        self.assertTrue(all(e['sourceCurriculumRef'] == K.reference(self.foreign)
                            for e in result['educationEntries']))
        self.assertEqual(result['generatedBackgroundsSha256'], backgrounds['contentSha256'])
        self.assertEqual(result['personGenerationReceiptSha256'], person['generationReceipt']['contentSha256'])

    def test_school_schedule_has_explicit_age_five_then_grades(self):
        _, person = self.generate()
        entries = person['personHistory']['educationHistory']
        self.assertEqual(len(entries), 13)
        self.assertEqual([e['startYear'] for e in entries], list(range(1965, 1978)))
        receipts = [r for r in person['receipts'] if r['schema'] == 'speakeasy-simulated-schooling-result/1']
        self.assertEqual([r['ageAtStart'] for r in receipts], list(range(5, 18)))

    def test_younger_child_has_no_schooling_and_cutoff_cannot_complete_year(self):
        self.profile.update(birthYear=1990, birthRegionId='kentucky', migrations=[])
        _, person = self.generate()
        self.assertEqual(person['personHistory']['educationHistory'], [])
        self.profile['birthYear'] = 1988
        _, person = self.generate()
        entry = person['personHistory']['educationHistory'][0]
        self.assertEqual((entry['startYear'], entry['endYear']), (1993, 1993))
        self.assertEqual(entry['completion'], 'not-completed')
        self.assertEqual(entry['exposedUnitIds'], [])

    def test_optional_college_is_profile_owned_and_not_implicit(self):
        _, first = self.generate()
        self.assertFalse(any(e['courseId'].startswith('college') for e in first['personHistory']['educationHistory']))
        self.profile['collegeYears'] = 2
        _, second = self.generate()
        college = [e for e in second['personHistory']['educationHistory'] if e['courseId'].startswith('college')]
        self.assertEqual(len(college), 1)
        self.assertEqual(college[0]['startYear'], 1978)

    def test_college_retries_do_not_guarantee_completion(self):
        self.profile['collegeYears'] = 2
        self.participation(completionProbability=0)
        _, person = self.generate()
        college = [e for e in person['personHistory']['educationHistory'] if e['courseId'].startswith('college')]
        self.assertEqual([e['startYear'] for e in college], [1978, 1979])
        self.assertTrue(all(e['completion'] == 'not-completed' for e in college))

    def test_college_prerequisites_are_completed_in_an_earlier_year(self):
        for curriculum in self.curricula:
            course = copy.deepcopy(curriculum['courses'][-1])
            course.update(id='college-follow-on', prerequisites=[curriculum['courses'][-1]['id']])
            curriculum['courses'].append(course)
        self.plan['curriculumRef'] = K.reference(self.curriculum)
        for region, curriculum in zip(self.plan['regions'], self.curricula):
            region['cohorts'][0]['curriculumRef'] = K.reference(curriculum)
            region['cohorts'][0]['institutions'][0]['offeredCourseIds'].append('college-follow-on')
        self.profile['collegeYears'] = 2
        _, person = self.generate()
        follow = [e for e in person['personHistory']['educationHistory'] if e['courseId'] == 'college-follow-on']
        self.assertEqual([e['startYear'] for e in follow], [1979])
        self.participation(completionProbability=0)
        _, failed = self.generate()
        self.assertFalse(any(e['courseId'] == 'college-follow-on' for e in failed['personHistory']['educationHistory']))
        self.assertTrue(any(g['reason'] == 'college-prerequisite-not-completed' for g in failed['coverageGaps']))

    def test_migration_changes_later_institution_but_keeps_previous_curriculum(self):
        self.profile['migrations'][0]['year'] = 1970
        _, person = self.generate()
        entries = person['personHistory']['educationHistory']
        self.assertTrue(all(e['regionId'] == 'outside' and e['curriculumRef'] == K.reference(self.foreign)
                            for e in entries if e['startYear'] < 1970))
        self.assertTrue(all(e['regionId'] == 'kentucky' and e['curriculumRef'] == K.reference(self.curriculum)
                            for e in entries if e['startYear'] >= 1970))
        self.assertEqual(len(person['personHistory']['migrations'][0]['historyRef']), 64)

    def test_generated_optional_variation_keeps_core_and_same_cohort_school_choices(self):
        school = self.plan['regions'][0]['cohorts'][0]['institutions'][0]
        other = copy.deepcopy(school); other['id'] = 'second-school'
        self.plan['regions'][0]['cohorts'][0]['institutions'].append(other)
        backgrounds, _ = self.generate()
        schools = backgrounds['regions'][0]['cohorts'][0]['institutions']
        self.assertEqual(schools[0]['optionalUnits'], schools[1]['optionalUnits'])
        courses = K.validate(self.curriculum)[0]
        _, indexed = K.regional_index(backgrounds['regionalRecords'], self.curriculum, courses,
                                     B.registry(self.curricula, self.archive))
        for key in [('kentucky', 'mid-century', school['id']), ('kentucky', 'mid-century', other['id'])]:
            selected = indexed[key]['selectedUnits']['kindergarten-literacy']
            self.assertEqual(selected[:10], ['unit-' + str(i) for i in range(1, 11)])
            self.assertLessEqual(len(selected) - 10, 2)
        variants = set()
        for index in range(6):
            self.plan['worldOwner']['seed'] = 'owned-variant-' + str(index)
            variant = B.generate_backgrounds(self.plan, self.curricula, self.archive)
            variants.add(frozenset(variant['regions'][0]['cohorts'][0]['institutions'][0]
                               ['optionalUnits']['kindergarten-literacy']))
        self.assertGreater(len(variants), 1)

    def test_authored_optional_state_is_preserved_and_bound_to_hash(self):
        school = self.plan['regions'][0]['cohorts'][0]['institutions'][0]
        school['authoredOptionalUnits'] = {'kindergarten-literacy': ['unit-12']}
        backgrounds, _ = self.generate()
        generated = backgrounds['regions'][0]['cohorts'][0]['institutions'][0]
        self.assertEqual(generated['optionalUnits']['kindergarten-literacy'], ['unit-12'])
        self.assertEqual(generated['authoredOptionalUnits'], school['authoredOptionalUnits'])
        self.assertEqual(generated['authoredStateSha256'], A.digest(school['authoredOptionalUnits']))
        school['authoredOptionalUnits']['kindergarten-literacy'] = ['unit-11']
        with self.assertRaisesRegex(ValueError, 'owned inputs'):
            B.generate_backgrounds(self.plan, self.curricula, self.archive, existing=backgrounds)

    def test_authored_override_cannot_add_unknown_or_excess_units(self):
        school = self.plan['regions'][0]['cohorts'][0]['institutions'][0]
        school['authoredOptionalUnits'] = {'kindergarten-literacy': ['unit-1']}
        with self.assertRaisesRegex(ValueError, 'variation'):
            self.generate()

    def test_shared_core_cannot_be_dropped(self):
        self.plan['regions'][0]['cohorts'][0]['institutions'][0]['offeredCourseIds'].remove('grade-1-literacy')
        with self.assertRaisesRegex(ValueError, 'shared core'):
            self.generate()

    def test_interruption_reduces_exposure_and_prevents_completion(self):
        _, normal = self.generate()
        self.participation(interruptionProbability=1)
        _, interrupted = self.generate()
        first = normal['personHistory']['educationHistory'][0]
        second = interrupted['personHistory']['educationHistory'][0]
        self.assertLess(len(second['exposedUnitIds']), len(first['exposedUnitIds']))
        self.assertEqual(second['completion'], 'not-completed')
        self.assertTrue(all(r['interrupted'] for r in interrupted['receipts'] if 'interrupted' in r))
        result = self.compile()
        self.assertEqual(len(result['exposureCandidates']), len(second['exposedUnitIds']))

    def test_enrolment_attendance_and_completion_are_distinct_owned_parameters(self):
        for key in ('enrolmentProbability', 'attendanceProbability'):
            self.participation(**{key: 0})
            _, person = self.generate()
            self.assertTrue(all(e['attendance'] == 'not-attended' and not e['exposedUnitIds']
                                and e['completion'] == 'not-completed'
                                for e in person['personHistory']['educationHistory']))
            self.participation(**{key: 1})
        self.participation(completionProbability=0)
        _, person = self.generate()
        self.assertTrue(all(e['completion'] == 'not-completed' for e in person['personHistory']['educationHistory']))
        self.assertTrue(person['personHistory']['educationHistory'][0]['exposedUnitIds'])

    def test_missing_dated_institutions_remain_explicit_gaps(self):
        self.plan['regions'][1]['cohorts'][0]['startYear'] = 1970
        _, person = self.generate()
        self.assertEqual(len(person['coverageGaps']), 5)
        self.assertTrue(all(g['reason'] == 'no-dated-source-institution' for g in person['coverageGaps']))
        self.assertFalse(any(e['courseId'] == 'kindergarten-literacy' for e in person['personHistory']['educationHistory']))

    def test_replay_is_deterministic_detached_and_preserves_input_objects(self):
        plan, profile = copy.deepcopy(self.plan), copy.deepcopy(self.profile)
        backgrounds, person = self.generate()
        self.assertEqual((self.plan, self.profile), (plan, profile))
        again = B.generate_backgrounds(self.plan, self.curricula, self.archive, existing=backgrounds)
        replay = B.generate_person(self.profile, again, self.plan, self.curricula, self.archive, existing=person)
        self.assertEqual(A.encoded(person), A.encoded(replay))
        again['regions'][0]['id'] = 'mutated-detached-copy'
        self.assertEqual(backgrounds['regions'][0]['id'], 'kentucky')

    def test_profile_changes_refuse_previous_person_output(self):
        backgrounds, person = self.generate()
        self.profile['birthYear'] = 1961
        with self.assertRaisesRegex(ValueError, 'owned inputs'):
            self.compile(backgrounds, person)

    def test_full_background_body_tamper_and_resealed_tamper_refuse(self):
        backgrounds, person = self.generate()
        backgrounds['regions'][0]['cohorts'][0]['institutions'][0]['participation']['enrolmentProbability'] = 0
        with self.assertRaisesRegex(ValueError, 'content hash'):
            self.compile(backgrounds, person)
        backgrounds = B.seal(B.checked(self.generate()[0], 'fresh'))
        backgrounds['regions'][0]['cohorts'][0]['institutions'][0]['participation']['enrolmentProbability'] = 0
        backgrounds = B.seal({k: v for k, v in backgrounds.items() if k != 'contentSha256'})
        with self.assertRaisesRegex(ValueError, 'owned inputs'):
            self.compile(backgrounds, person)

    def test_resealed_person_exposure_forgery_refuses(self):
        backgrounds, person = self.generate()
        person['personHistory']['educationHistory'][0]['exposedUnitIds'] = []
        person = B.seal({k: v for k, v in person.items() if k != 'contentSha256'})
        with self.assertRaisesRegex(ValueError, 'owned inputs'):
            self.compile(backgrounds, person)

    def test_generation_receipt_and_registry_hash_tamper_refuse(self):
        backgrounds, person = self.generate()
        for path in ('generationReceipt', 'curriculumRegistry'):
            changed = copy.deepcopy(backgrounds)
            if path == 'generationReceipt':
                changed[path]['backgroundBodiesSha256'] = '0' * 64
            else:
                changed[path][0]['coverageSha256'] = '0' * 64
            changed = B.seal({k: v for k, v in changed.items() if k != 'contentSha256'})
            with self.assertRaisesRegex(ValueError, 'owned inputs'):
                self.compile(changed, person)
        person['generationReceipt']['receiptsSha256'] = '0' * 64
        person = B.seal({k: v for k, v in person.items() if k != 'contentSha256'})
        with self.assertRaisesRegex(ValueError, 'owned inputs'):
            self.compile(backgrounds, person)

    def test_plan_reference_source_selector_and_actual_archive_tamper_refuse(self):
        backgrounds, person = self.generate()
        self.plan['regions'][1]['cohorts'][0]['curriculumRef']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'hash or version'):
            self.compile(backgrounds, person)
        self.plan['regions'][1]['cohorts'][0]['curriculumRef'] = K.reference(self.foreign)
        original = self.foreign['courses'][0]['units'][0]['selector']['sourceSha256']
        self.foreign['courses'][0]['units'][0]['selector']['sourceSha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.compile(backgrounds, person)
        self.foreign['courses'][0]['units'][0]['selector']['sourceSha256'] = original
        actual = next(self.archive.glob('**/source.txt'))
        actual.write_bytes(actual.read_bytes() + b' corruption')
        with self.assertRaises(ValueError):
            self.compile(backgrounds, person)

    def test_invalid_profile_chronology_current_origin_alias_and_parameters_refuse(self):
        for change in ({'birthYear': 1994}, {'collegeYears': True}, {'asOfYear': 1994},
                       {'currentRegionId': 'outside'}, {'birthRegionId': 'spawn-origin'}):
            saved = copy.deepcopy(self.profile); self.profile.update(change)
            with self.assertRaises(ValueError):
                self.generate()
            self.profile = saved
        self.profile['migrations'][0]['year'] = 1959
        with self.assertRaisesRegex(ValueError, 'migration'):
            self.generate()
        self.profile['migrations'][0]['year'] = 1985
        for value in (True, float('nan'), 1.1, -0.1):
            self.participation(attendanceProbability=value)
            with self.assertRaises(ValueError):
                self.generate()

    def test_malformed_source_and_region_references_refuse_cleanly(self):
        self.plan['regions'][0]['cohorts'][0]['curriculumRef']['sha256'] = []
        with self.assertRaises(ValueError):
            self.generate()
        self.plan['regions'][0]['cohorts'][0]['curriculumRef'] = K.reference(self.curriculum)
        self.profile['birthRegionId'] = {}
        with self.assertRaises(ValueError):
            self.generate()

    def test_modern_and_ambiguous_editions_stay_withheld_by_real_compiler(self):
        for notice, year, reason in [('Copyright, 2022.', 2022, 'source-edition-postdates-education'),
                                     ('Copyright, 1900 and 2002.', 1900, 'source-edition-year-ambiguous')]:
            # Distinct acquisition directories keep each test archive immutable.
            self.root = self.fixture.root / str(year)
            self.replace_edition(notice, year)
            result = self.compile()
            self.assertEqual(result['exposureCandidates'], [])
            self.assertTrue(result['withheldExposures'])
            self.assertTrue(all(reason in e['reasons'] for e in result['withheldExposures']))

    def test_no_implicit_retention_native_world_peer_or_training_authority(self):
        backgrounds, person = self.generate()
        for body in (backgrounds, person, *person['receipts']):
            for key in B.BOUNDARY:
                if key in body:
                    self.assertFalse(body[key])
        result = self.compile(backgrounds, person)
        for key in ('knownConcepts', 'nativeSkills', 'currentWorldClaims', 'peerAssent'):
            self.assertEqual(result[key], [])
        self.assertEqual(result['trainingRows'], 0)
        self.assertFalse(result['runtimeIntegration'])

    def test_cli_generate_person_compile_and_immutable_replay(self):
        paths = {name: self.root / (name + '.json') for name in
                 ('plan', 'curriculum', 'foreign', 'profile', 'backgrounds', 'person', 'compiled')}
        for name, value in [('plan', self.plan), ('curriculum', self.curriculum),
                            ('foreign', self.foreign), ('profile', self.profile)]:
            paths[name].write_bytes(A.encoded(value))
        common = ['--plan', str(paths['plan']), '--curriculum', str(paths['curriculum']),
                  '--source-curriculum', str(paths['foreign']), '--archive', str(self.archive)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(B.main(['generate', *common, '--out', str(paths['backgrounds'])]), 0)
            original = paths['backgrounds'].read_bytes()
            self.assertEqual(B.main(['generate', *common, '--out', str(paths['backgrounds'])]), 0)
            self.assertEqual(paths['backgrounds'].read_bytes(), original)
            next_args = ['--backgrounds', str(paths['backgrounds']), '--profile', str(paths['profile'])]
            self.assertEqual(B.main(['person', *common, *next_args, '--out', str(paths['person'])]), 0)
            self.assertEqual(B.main(['compile', *common, *next_args, '--person', str(paths['person']),
                                     '--out', str(paths['compiled'])]), 0)
        self.assertEqual(A.read(paths['compiled'])['personId'], self.profile['id'])
        paths['backgrounds'].write_text('{}', encoding='utf8')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(B.main(['generate', *common, '--out', str(paths['backgrounds'])]), 2)


if __name__ == '__main__':
    unittest.main()
