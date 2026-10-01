"""Real archive/grader/history joins and replay controls for personal memory."""
import contextlib
import copy
import io
import unittest
from unittest.mock import patch

import decision_authoring as A
import education_assessment as G
import education_backgrounds as B
import education_corpus as C
import education_curriculum as K
import education_learning as L
import test_education_assessment as F


class EducationLearningTests(unittest.TestCase):
    def setUp(self):
        self.fixture = F.EducationAssessmentTests('test_actual_producer_preserves_source_bound_bank')
        module = F.MODULE.replace(b'<content>', b'<content>\n\n<para id="edition">Copyright, 1900.</para>\n\n')
        with patch.object(F, 'MODULE', module), contextlib.redirect_stdout(io.StringIO()):
            self.fixture.setUp()
        self.root, self.archive = self.fixture.root, self.fixture.archive
        source = C.verified_sources(self.archive)[0]
        file, text, coverage = next(C.texts(source, self.archive))
        unit = {'id': 'actual-arithmetic-unit', 'title': 'Sourced arithmetic', 'sourceId': source['id'],
                'sourceVersion': source['sourceVersion'], 'editionYear': 1900,
                'editionEvidence': {'basis': 'printed-source', 'literal': 'Copyright, 1900.'},
                'temporalStanding': 'source-period-review-required',
                'selector': {'sourcePath': file['path'], 'sourceSha256': file['sha256'],
                             'extractionSha256': C.sha(text.encode()), 'startCharacter': 0,
                             'endCharacter': len(text), 'excerptSha256': C.sha(text.encode()),
                             'format': coverage['format']},
                'activities': [{'kind': 'exercise', 'literalEvidence': 'What is one divided by two?'}]}
        courses = [{'id': level + '-arithmetic', 'level': level, 'subject': 'mathematics',
                    'title': 'Controlled arithmetic', 'requirement': 'core', 'prerequisites': [],
                    'units': [unit] if i == 0 else [], 'optionalUnitIds': [],
                    'coverageNeeds': [] if i == 0 else ['Later source units absent']}
                   for i, level in enumerate(K.LEVELS)]
        curriculum = {'schema': 'speakeasy-educational-curriculum/1', 'id': 'learning-test-curriculum',
                      'version': 'controlled-1', 'standing': 'candidate-curriculum', 'title': 'Source learning control',
                      'levels': K.LEVELS, 'courses': courses, 'specializations': [],
                      'regionalPolicy': {'sharedCore': 'required-course-and-unit-identities',
                                         'optionalUnitNumerator': 1, 'optionalUnitDenominator': 5,
                                         'owner': 'explicit-region-cohort-institution-history',
                                         'migration': 'preserve-source-education-history'},
                      'knownCoverageGaps': ['Controlled source only']}
        plan = {'schema': 'speakeasy-education-background-plan/1', 'id': 'controlled-schooling',
                'worldOwner': {'id': 'explicit-world', 'seed': 'explicit-seed'}, 'curriculumRef': K.reference(curriculum),
                'regions': [{'id': 'kentucky', 'cohorts': [{'id': 'source-cohort', 'startYear': 1930, 'endYear': 1993,
                            'curriculumRef': K.reference(curriculum), 'institutions': [{'id': 'source-school',
                            'levelIds': K.LEVELS, 'offeredCourseIds': [c['id'] for c in courses],
                            'authoredOptionalUnits': {}, 'participation': {'enrolmentProbability': 1,
                            'attendanceProbability': 1, 'interruptionProbability': 0, 'completionProbability': 1,
                            'minimumInterruptedExposureFraction': 0}}]}]}]}
        backgrounds = B.generate_backgrounds(plan, [curriculum], self.archive)
        self.base = {'archive': self.archive, 'curriculum': curriculum, 'sourceCurricula': [],
                     'plan': plan, 'backgrounds': backgrounds}
        self.context = self.person_context('learner-one')
        self.bank = self.root / 'linked-source-bank'
        G.build_bank(self.archive, self.bank, curriculum, self.fixture.split_policy)
        _, self.items = G.validate_bank(self.archive, self.bank)
        self.policy = {'schema': 'speakeasy-person-learning-policy/1', 'owner': 'caller:controlled-simulation',
                       'version': 'test-1', 'clock': 'county-day', 'ticksPerDay': 60000,
                       'rates': {'independent-retrieval': 0.4, 'hinted-retrieval': 0.08, 'tutoring': 0.1,
                                 'passive-learning': 0.02, 'cross-learning': 0.01},
                       'familiarityRate': 0.1, 'baseHalfLifeDays': 30, 'familiarityHalfLifeMultiplier': 4,
                       'ageDecayPerYear': 0.005, 'ageLearningPerYear': 0.003, 'interestLearningBoost': 0.5,
                       'interestDecayProtection': 0.4, 'practiceProtection': 0.5,
                       'successfulRetrievalProtection': 0.4, 'maximumProtection': 10,
                       'wrongRecallPenalty': 0.15, 'unknownRecallPenalty': 0.01, 'assistedRetentionCap': 0.3,
                       'crossPrimingRate': 0.05, 'maximumPriming': 0.2, 'teacherRetentionThreshold': 0.2,
                       'interests': {}, 'eventLimit': 512}
        self.start = {'clock': 'county-day', 'value': 0}
        self.ledger = L.initialize(self.context, self.policy, self.bank, self.start)
        self.sequence = 0

    def tearDown(self):
        self.fixture.tearDown()

    def person_context(self, identity, birth=1960):
        profile = {'schema': 'speakeasy-simulated-education-profile/1', 'id': identity, 'birthYear': birth,
                   'asOfYear': 1993, 'birthRegionId': 'kentucky', 'currentRegionId': 'kentucky',
                   'migrations': [], 'collegeYears': 0, 'electiveCourseIds': []}
        context = {**self.base, 'profile': profile}
        context['person'] = B.generate_person(profile, context['backgrounds'], context['plan'],
                                              [context['curriculum']], self.archive)
        context['education'] = B.compile_generated(context['curriculum'], self.archive, context['plan'],
                                                   context['backgrounds'], profile, context['person'])
        return context

    def item(self, identity='fraction'):
        return next(i for i in self.items if i['source']['id'] == 'controlled-assessment-a'
                    and i['exercise']['id'] == identity)

    def response(self, identity='fraction', text='0.5', day=1, mode='independent-retrieval', context=None, **changes):
        self.sequence += 1
        response = {'schema': 'speakeasy-educational-assessment-response/1',
                    'itemSha256': self.item(identity)['contentSha256'], 'learner': L.owner(context or self.context),
                    'sessionId': 'actual-response-session-' + str(self.sequence),
                    'asOfTime': {'clock': 'county-day', 'value': day}, 'learningMode': mode,
                    'assistanceEvidenceRefs': ['recorded-hint'] if mode != 'independent-retrieval' else [],
                    'evidenceRefs': ['actual-response-record-' + str(self.sequence)], 'response': text}
        response.update(changes)
        return response

    def event(self, response=None, **changes):
        response = response or self.response()
        return L.assessment_event('event-' + str(self.sequence), response, self.archive, self.bank, **changes)

    def apply(self, event, ledger=None, policy=None, context=None, teachers=None):
        return L.apply_event(ledger or self.ledger, event, context or self.context,
                             policy or self.policy, self.bank, teachers)

    def state(self, ledger, identity='fraction'):
        return ledger['concepts'][self.item(identity)['conceptRef']['id']]

    def test_actual_grader_receipt_changes_person_memory_and_is_attributable(self):
        event = self.event()
        ledger = self.apply(event)
        state = self.state(ledger)
        self.assertGreater(state['retention'], 0)
        self.assertEqual(state['independentSuccesses'], 1)
        self.assertEqual(state['calibration']['correct'], 1)
        self.assertEqual(ledger['owner'], L.owner(self.context))
        self.assertEqual(event['grade'], G.grade(self.archive, self.bank, event['response']))
        self.assertNotEqual(ledger['contextRefs']['personEducationSha256'], ledger['owner']['version'])

    def test_wrong_and_unknown_are_different_without_invented_correctness(self):
        correct = self.apply(self.event())
        wrong = self.apply(self.event(self.response(text='0.7', day=2)), correct)
        unknown = self.apply(self.event(self.response(text='I do not know', day=2)), correct)
        self.assertEqual(self.state(wrong)['calibration']['incorrect'], 1)
        self.assertEqual(self.state(unknown)['calibration']['unknown'], 1)
        self.assertGreater(self.state(unknown)['retention'], self.state(wrong)['retention'])
        self.assertEqual(self.state(unknown)['calibration']['correct'], 1)

    def test_assisted_correctness_is_weaker_and_cannot_be_independent_mastery(self):
        independent = self.apply(self.event())
        hinted = self.apply(self.event(self.response(mode='hinted-retrieval')))
        self.assertGreater(self.state(independent)['retention'], self.state(hinted)['retention'])
        self.assertEqual(self.state(hinted)['independentSuccesses'], 0)
        self.assertEqual(self.state(hinted)['calibration']['correct'], 0)
        self.assertEqual(self.state(hinted)['assistedSuccesses'], 1)

    def test_saved_grade_and_response_tampering_fail_even_after_resealing(self):
        for field in ('grade', 'response'):
            event = self.event()
            body = B.checked(event, 'event')
            if field == 'grade':
                grade = B.checked(body['grade'], 'grade'); grade['earnedPoints'] = 0
                body['grade'] = B.seal(grade)
            else:
                body['response']['response'] = '0.7'
            with self.assertRaisesRegex(ValueError, 'actual source grader'):
                self.apply(B.seal(body))

    def test_replay_idempotence_and_conflicting_or_reused_receipts_refuse(self):
        event = self.event()
        ledger = self.apply(event)
        self.assertEqual(ledger, self.apply(event, ledger))
        self.assertEqual(ledger, L.replay(self.context, self.policy, self.bank, self.start, [event]))
        changed = B.checked(event, 'event'); changed['id'] = 'different-event-id'
        with self.assertRaisesRegex(ValueError, 'already applied'):
            self.apply(B.seal(changed), ledger)
        changed['id'] = event['id']; changed['kind'] = 'practice'
        with self.assertRaisesRegex(ValueError, 'identity conflicts'):
            self.apply(B.seal(changed), ledger)

    def test_ledger_state_and_policy_and_profile_hash_corruption_refuse(self):
        ledger = self.apply(self.event())
        body = B.checked(ledger, 'ledger'); self.state(body)['retention'] = 1
        with self.assertRaisesRegex(ValueError, 'reconstruction'):
            L.verify(B.seal(body), self.context, self.policy, self.bank)
        changed = copy.deepcopy(self.policy); changed['baseHalfLifeDays'] = 60
        with self.assertRaises(ValueError):
            L.verify(ledger, self.context, changed, self.bank)
        context = copy.deepcopy(self.context); context['profile']['birthYear'] = 1961
        with self.assertRaises(ValueError):
            L.verify(ledger, context, self.policy, self.bank)

    def test_elapsed_time_and_age_change_retention_and_query_stays_pure(self):
        event = self.event()
        ledger = self.apply(event)
        before = A.encoded(ledger)
        early = L.observe(ledger, {'clock': 'county-day', 'value': 1}, self.context, self.policy, self.bank)
        later = L.observe(ledger, {'clock': 'county-day', 'value': 61}, self.context, self.policy, self.bank)
        identity = self.item()['conceptRef']['id']
        self.assertGreater(early['concepts'][identity]['retention'], later['concepts'][identity]['retention'])
        self.assertGreater(later['concepts'][identity]['familiarity'] / early['concepts'][identity]['familiarity'],
                           later['concepts'][identity]['retention'] / early['concepts'][identity]['retention'])
        self.assertEqual(A.encoded(ledger), before)
        older = self.person_context('older-person', 1930)
        old_ledger = L.initialize(older, self.policy, self.bank, self.start)
        old_event = self.event(self.response(context=older))
        old_ledger = self.apply(old_event, old_ledger, context=older)
        self.assertLess(self.state(old_ledger)['retention'], self.state(ledger)['retention'])

    def test_interests_affect_learning_and_recorded_decay(self):
        interested = copy.deepcopy(self.policy)
        interested['interests'] = {'kindergarten-arithmetic': 1}
        ledger = L.initialize(self.context, interested, self.bank, self.start)
        event = self.event()
        interested_ledger = self.apply(event, ledger, policy=interested)
        ordinary = self.apply(event)
        self.assertGreater(self.state(interested_ledger)['retention'], self.state(ordinary)['retention'])
        view = L.observe(interested_ledger, {'clock': 'county-day', 'value': 61}, self.context, interested, self.bank)
        ordinary_view = L.observe(ordinary, {'clock': 'county-day', 'value': 61}, self.context, self.policy, self.bank)
        identity = self.item()['conceptRef']['id']
        self.assertGreater(view['concepts'][identity]['retention'], ordinary_view['concepts'][identity]['retention'])

    def test_successful_usage_stabilizes_future_retention_and_bad_usage_refuses(self):
        response = self.response()
        assessed = self.apply(self.event(response))
        practiced = self.apply(self.event(response, kind='practice'))
        self.assertEqual(self.state(practiced)['usageCount'], 1)
        at = {'clock': 'county-day', 'value': 61}
        a = L.observe(assessed, at, self.context, self.policy, self.bank)
        b = L.observe(practiced, at, self.context, self.policy, self.bank)
        identity = self.item()['conceptRef']['id']
        self.assertGreater(b['concepts'][identity]['retention'], a['concepts'][identity]['retention'])
        with self.assertRaisesRegex(ValueError, 'successful independent'):
            self.apply(self.event(self.response(text='0.7'), kind='practice'))

    def test_passive_exposure_requires_real_generated_receipt_and_available_source_unit(self):
        receipt = next(r for r in self.context['person']['receipts'] if r.get('exposedUnitIds'))
        event = L.passive_event('passive-1', self.item()['contentSha256'], receipt['contentSha256'],
                                {'clock': 'county-day', 'value': 1})
        ledger = self.apply(event)
        self.assertGreater(self.state(ledger)['familiarity'], 0)
        self.assertLessEqual(self.state(ledger)['retention'], self.policy['assistedRetentionCap'])
        self.assertEqual(self.state(ledger)['independentSuccesses'], 0)
        body = B.checked(event, 'event'); body['id'] = 'passive-again'
        with self.assertRaisesRegex(ValueError, 'already applied'):
            self.apply(B.seal(body), ledger)
        body['exposureReceiptSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'schooling receipt'):
            self.apply(B.seal(body))
        other = next(i for i in self.items if i['source']['id'] == 'controlled-assessment-b')
        body['itemSha256'] = other['contentSha256']; body['exposureReceiptSha256'] = receipt['contentSha256']
        with self.assertRaisesRegex(ValueError, 'available unit'):
            self.apply(B.seal(body))

    def test_historical_passive_credit_ages_from_schooling_instead_of_becoming_fresh_recall(self):
        old_receipt = next(r for r in self.context['person']['receipts'] if r.get('exposedUnitIds'))
        old_event = L.passive_event('historical-passive', self.item()['contentSha256'],
                                   old_receipt['contentSha256'], {'clock': 'county-day', 'value': 1})
        old = self.apply(old_event)
        recent_context = self.person_context('recent-schooling', 1987)
        recent_receipt = next(r for r in recent_context['person']['receipts'] if r.get('exposedUnitIds'))
        recent_event = L.passive_event('historical-passive', self.item()['contentSha256'],
                                      recent_receipt['contentSha256'], {'clock': 'county-day', 'value': 1})
        recent = L.initialize(recent_context, self.policy, self.bank, self.start)
        recent = self.apply(recent_event, recent, context=recent_context)
        self.assertGreater(self.state(recent)['retention'], self.state(old)['retention'])
        self.assertGreater(self.state(recent)['familiarity'], self.state(old)['familiarity'])
        self.assertEqual(self.state(recent)['independentSuccesses'], 0)
        self.assertEqual(self.state(old)['calibration']['correct'], 0)
        changed = copy.deepcopy(self.context)
        person = B.checked(changed['person'], 'person')
        receipt = B.checked(old_receipt, 'school receipt'); receipt['endYear'] = 1993
        person['receipts'][person['receipts'].index(old_receipt)] = B.seal(receipt)
        changed['person'] = B.seal(person)
        with self.assertRaises(ValueError):
            L.initialize(changed, self.policy, self.bank, self.start)

    def test_undated_history_withholding_cannot_be_bypassed_by_an_attended_receipt(self):
        curriculum = copy.deepcopy(self.context['curriculum']); curriculum['version'] = 'controlled-undated-1'
        unit = curriculum['courses'][0]['units'][0]
        unit['editionYear'], unit['editionEvidence'] = None, None
        plan = copy.deepcopy(self.context['plan']); plan['curriculumRef'] = K.reference(curriculum)
        plan['regions'][0]['cohorts'][0]['curriculumRef'] = K.reference(curriculum)
        backgrounds = B.generate_backgrounds(plan, [curriculum], self.archive)
        profile = self.context['profile']
        person = B.generate_person(profile, backgrounds, plan, [curriculum], self.archive)
        education = B.compile_generated(curriculum, self.archive, plan, backgrounds, profile, person)
        self.assertEqual(education['exposureCandidates'], [])
        self.assertTrue(education['withheldExposures'])
        context = {'archive': self.archive, 'curriculum': curriculum, 'sourceCurricula': [],
                   'plan': plan, 'backgrounds': backgrounds, 'profile': profile, 'person': person, 'education': education}
        bank = self.root / 'undated-history-bank'
        G.build_bank(self.archive, bank, curriculum, self.fixture.split_policy)
        _, items = G.validate_bank(self.archive, bank)
        item = next(i for i in items if i['source']['id'] == 'controlled-assessment-a' and i['exercise']['id'] == 'fraction')
        receipt = next(r for r in person['receipts'] if r.get('exposedUnitIds'))
        event = L.passive_event('withheld-passive', item['contentSha256'], receipt['contentSha256'], self.start)
        ledger = L.initialize(context, self.policy, bank, self.start)
        with self.assertRaisesRegex(ValueError, 'available unit'):
            L.apply_event(ledger, event, context, self.policy, bank)

    def test_cross_learning_uses_exact_link_and_primes_without_target_mastery(self):
        source_event = self.event()
        source = self.apply(source_event)
        event = L.transfer_event('cross-1', source_event['id'], self.item('decimal')['contentSha256'],
                                 {'clock': 'county-day', 'value': 2})
        transferred = self.apply(event, source)
        target = self.state(transferred, 'decimal')
        self.assertGreater(target['priming'], 0)
        self.assertEqual(target['retention'], 0)
        self.assertEqual(target['independentSuccesses'], 0)
        self.assertEqual(transferred['crossLearningLinks'][0]['evidence']['relation'], 'shared-course')
        attempt = self.event(self.response('decimal', '0.4', day=3))
        primed = self.apply(attempt, transferred)
        unprimed = self.apply(attempt, source)
        self.assertGreater(self.state(primed, 'decimal')['retention'], self.state(unprimed, 'decimal')['retention'])
        body = B.checked(event, 'event'); body['id'] = 'cross-again'
        with self.assertRaisesRegex(ValueError, 'already applied'):
            self.apply(B.seal(body), transferred)

    def test_cross_learning_cannot_use_wrong_or_unlinked_source(self):
        wrong_event = self.event(self.response(text='0.7'))
        wrong = self.apply(wrong_event)
        event = L.transfer_event('cross-invalid', wrong_event['id'], self.item('decimal')['contentSha256'],
                                 {'clock': 'county-day', 'value': 2})
        with self.assertRaisesRegex(ValueError, 'successful retrieval'):
            self.apply(event, wrong)
        source_event = self.event()
        source = self.apply(source_event)
        other = next(i for i in self.items if i['source']['id'] == 'controlled-assessment-b')
        event = L.transfer_event('cross-unlinked', source_event['id'], other['contentSha256'],
                                 {'clock': 'county-day', 'value': 2})
        with self.assertRaisesRegex(ValueError, 'curriculum link'):
            self.apply(event, source)

    def test_tutoring_needs_retained_teacher_shared_concept_and_exact_reception(self):
        teacher_context = self.person_context('actual-teacher')
        teacher = L.initialize(teacher_context, self.policy, self.bank, self.start)
        teacher = self.apply(self.event(self.response(context=teacher_context)), teacher, context=teacher_context)
        teacher_sha = teacher['contentSha256']
        teachers = {teacher_sha: {'ledger': teacher, 'context': teacher_context, 'policy': self.policy}}
        response = self.response(mode='tutoring', day=2, assistanceEvidenceRefs=[teacher_sha])
        received = L.reception('received-teaching-1', teacher_sha, L.owner(self.context),
                               self.item()['conceptRef']['id'], 'explicit-received-source-lesson',
                               response['asOfTime'], response['sessionId'])
        response['evidenceRefs'] = [received['contentSha256']]
        event = self.event(response, received=received)
        learned = self.apply(event, teachers=teachers)
        self.assertEqual(self.state(learned)['independentSuccesses'], 0)
        self.assertGreater(self.state(learned)['retention'], 0)
        with self.assertRaises(ValueError):
            self.apply(self.event(response), teachers=teachers)
        with self.assertRaisesRegex(ValueError, 'teacher retained-state'):
            self.apply(event)
        body = B.checked(received, 'reception'); body['recipient'] = L.owner(teacher_context)
        changed = B.checked(event, 'event'); changed['receivedEvidence'] = B.seal(body)
        with self.assertRaisesRegex(ValueError, 'recipient reception'):
            self.apply(B.seal(changed), teachers=teachers)

    def test_teacher_familiarity_without_independent_retention_does_not_teach(self):
        teacher_context = self.person_context('unretained-teacher')
        teacher = L.initialize(teacher_context, self.policy, self.bank, self.start)
        hinted = self.event(self.response(mode='hinted-retrieval', context=teacher_context))
        teacher = self.apply(hinted, teacher, context=teacher_context)
        sha = teacher['contentSha256']
        teachers = {sha: {'ledger': teacher, 'context': teacher_context, 'policy': self.policy}}
        response = self.response(mode='tutoring', day=2, assistanceEvidenceRefs=[sha])
        received = L.reception('received', sha, L.owner(self.context), self.item()['conceptRef']['id'],
                               'received-lesson', response['asOfTime'], response['sessionId'])
        response['evidenceRefs'] = [received['contentSha256']]
        with self.assertRaisesRegex(ValueError, 'does not retain'):
            self.apply(self.event(response, received=received), teachers=teachers)

    def test_received_teaching_cannot_predate_the_teacher_knowledge(self):
        teacher_context = self.person_context('later-teacher')
        teacher = L.initialize(teacher_context, self.policy, self.bank, self.start)
        teacher = self.apply(self.event(self.response(day=2, context=teacher_context)), teacher, context=teacher_context)
        sha = teacher['contentSha256']
        teachers = {sha: {'ledger': teacher, 'context': teacher_context, 'policy': self.policy}}
        response = self.response(mode='tutoring', day=3, assistanceEvidenceRefs=[sha])
        received = L.reception('earlier-reception', sha, L.owner(self.context), self.item()['conceptRef']['id'],
                               'explicit-received-lesson', {'clock': 'county-day', 'value': 1}, response['sessionId'])
        response['evidenceRefs'] = [received['contentSha256']]
        with self.assertRaisesRegex(ValueError, 'observation precedes'):
            self.apply(self.event(response, received=received), teachers=teachers)

    def test_malformed_resealed_events_and_ledgers_fail_closed(self):
        for body in ({'schema': 'speakeasy-person-learning-event/1', 'id': 'malformed'},
                     {'schema': 'speakeasy-person-learning-event/1', 'id': 'malformed',
                      'kind': 'assessment', 'asOfTime': self.start}):
            with self.assertRaises(ValueError):
                self.apply(B.seal(body))
        with self.assertRaises(ValueError):
            L.verify(B.seal({'schema': 'speakeasy-person-educational-memory/1'}),
                     self.context, self.policy, self.bank)
        with self.assertRaises(ValueError):
            self.apply(None)

    def test_time_regression_clock_nan_model_owner_and_policy_order_refuse(self):
        ledger = self.apply(self.event(self.response(day=3)))
        with self.assertRaisesRegex(ValueError, 'chronology'):
            self.apply(self.event(self.response(day=2)), ledger)
        with self.assertRaises(ValueError):
            L.observe(ledger, {'clock': 'county-day', 'value': float('nan')}, self.context, self.policy, self.bank)
        response = self.response(); response['learner']['kind'] = 'model'
        with self.assertRaisesRegex(ValueError, 'person owner'):
            self.apply(self.event(response))
        policy = copy.deepcopy(self.policy); policy['rates']['tutoring'] = 0.5
        with self.assertRaisesRegex(ValueError, 'stronger'):
            L.initialize(self.context, policy, self.bank, self.start)
        with self.assertRaises(ValueError):
            L.observe(ledger, {'clock': 'county-tick', 'value': 60000}, self.context, self.policy, self.bank)

    def test_explicit_tick_policy_has_the_same_learning_and_decay_at_equal_elapsed_days(self):
        daily = self.apply(self.event())
        tick_policy = copy.deepcopy(self.policy); tick_policy['clock'] = 'county-tick'
        tick_start = {'clock': 'county-tick', 'value': 0}
        ticks = L.initialize(self.context, tick_policy, self.bank, tick_start)
        response = self.response(); response['asOfTime'] = {'clock': 'county-tick', 'value': 60000}
        ticks = self.apply(self.event(response), ticks, policy=tick_policy)
        day_view = L.observe(daily, {'clock': 'county-day', 'value': 31}, self.context, self.policy, self.bank)
        tick_view = L.observe(ticks, {'clock': 'county-tick', 'value': 31 * 60000},
                              self.context, tick_policy, self.bank)
        self.assertEqual(day_view['concepts'], tick_view['concepts'])

    def test_bounded_prior_preserves_separate_scores_and_has_no_native_authority(self):
        ledger = self.apply(self.event())
        ledger = self.apply(self.event(self.response('decimal', '0.4', day=2)), ledger)
        prior = L.export_prior(ledger, {'clock': 'county-day', 'value': 3}, self.context,
                               self.policy, self.bank, maximum_concepts=1)
        self.assertEqual(len(prior['concepts']), 1)
        self.assertEqual(prior['omittedConcepts'], 1)
        for key in L.AUTHORITY:
            self.assertFalse(prior[key])
        self.assertIn('familiarity', prior['concepts'][0])
        self.assertIn('calibration', prior['concepts'][0])
        self.assertNotIn('solutionXml', A.encoded(prior).decode())

    def test_source_bank_corruption_refuses_actual_grade_application(self):
        event = self.event()
        private = self.bank / 'assessments.jsonl'
        private.write_bytes(private.read_bytes().replace(b'PRIVATE_SOURCE_SOLUTION', b'INVENTED_SOURCE_SOLUTION'))
        with self.assertRaisesRegex(ValueError, 'source reconstruction'):
            self.apply(event)

    def test_cli_replay_observe_and_export_immutable_outputs(self):
        paths = {}
        for key, value in self.context.items():
            if key == 'archive':
                paths[key] = str(value)
            elif key == 'sourceCurricula':
                paths[key] = []
            else:
                path = self.root / (key + '.json'); path.write_bytes(A.encoded(value)); paths[key] = str(path)
        context_path = self.root / 'context-paths.json'; context_path.write_bytes(A.encoded(paths))
        policy_path = self.root / 'policy.json'; policy_path.write_bytes(A.encoded(self.policy))
        start_path = self.root / 'start.json'; start_path.write_bytes(A.encoded(self.start))
        events_path = self.root / 'events.json'; events_path.write_bytes(A.encoded([self.event()]))
        time_path = self.root / 'time.json'; time_path.write_bytes(A.encoded({'clock': 'county-day', 'value': 2}))
        ledger_path = self.root / 'ledger.json'
        common = ['--context', str(context_path), '--policy', str(policy_path), '--bank', str(self.bank)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(L.main(['replay', *common, '--started-at', str(start_path), '--events', str(events_path),
                                     '--out', str(ledger_path)]), 0)
            for action in ('observe', 'export'):
                self.assertEqual(L.main([action, *common, '--ledger', str(ledger_path), '--as-of', str(time_path),
                                         '--out', str(self.root / (action + '.json'))]), 0)


if __name__ == '__main__':
    unittest.main()
