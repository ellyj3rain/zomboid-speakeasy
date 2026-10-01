"""Actual archive producers and defect controls for source-derived assessment."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import decision_authoring as A
import education_assessment as G
import education_corpus as C
import education_curriculum as K


MODULE = '''<document xmlns="http://cnx.rice.edu/cnxml" xmlns:m="http://www.w3.org/1998/Math/MathML" id="module-one">
<title>Controlled sourced arithmetic</title><content><section id="arithmetic"><title>Exact quantities</title>
<para id="instruction">Give one numeric answer to each arithmetic question.</para>
<exercise id="fraction"><problem id="fraction-problem"><para>What is one divided by two?</para></problem>
<solution id="fraction-solution"><title>Solution</title><para><m:math><m:mfrac><m:mn>1</m:mn><m:mn>2</m:mn></m:mfrac></m:math></para></solution></exercise>
<exercise id="decimal"><problem id="decimal-problem"><para>What is two divided by five?</para></problem>
<solution id="decimal-solution"><para>0.4</para></solution></exercise>
<exercise id="units"><problem id="units-problem"><para>What length is two metres?</para></problem>
<solution id="units-solution"><para><m:math><m:mrow><m:mn>2</m:mn><m:mspace/><m:mtext>m</m:mtext></m:mrow></m:math></para></solution></exercise>
<exercise id="choice"><problem id="choice-problem"><para>Which option does the source select?</para>
<list list-type="enumerated" number-style="lower-alpha"><item>First option</item><item>Second option</item></list></problem>
<solution id="choice-solution"><para>B</para></solution></exercise>
<exercise id="choice-explanation"><problem id="choice-explanation-problem"><para>Select one option.</para>
<list list-type="enumerated" number-style="upper-alpha"><item>One option</item><item>Another option</item></list></problem>
<solution id="choice-explanation-solution"><para>The correct answer is (a). The source explains its choice.</para></solution></exercise>
<exercise id="missing"><problem id="missing-problem"><para>What is the missing answer?</para></problem></exercise>
<exercise id="multipart"><problem id="multipart-problem"><para>Find ⓐ one value and ⓑ another value.</para></problem>
<solution id="multipart-solution"><list list-type="labeled-item"><item>ⓐ 1</item><item>ⓑ 2</item></list></solution></exercise>
<exercise id="prose"><problem id="prose-problem"><para>Explain the reasoning.</para></problem>
<solution id="prose-solution"><para>PRIVATE_SOURCE_SOLUTION. A reasoned explanation has several parts.</para></solution></exercise>
<exercise id="algebra"><problem id="algebra-problem"><para>Solve the equation.</para></problem>
<solution id="algebra-solution"><para><m:math><m:mrow><m:mi>x</m:mi><m:mo>=</m:mo><m:mn>2</m:mn></m:mrow></m:math></para></solution></exercise>
<exercise><problem id="unidentified-problem"><para>Count objects.</para></problem>
<solution id="unidentified-solution"><para>3</para></solution></exercise>
</section></content></document>'''.encode()


COLLECTION = b'''<collection xmlns="http://cnx.rice.edu/collxml" xmlns:md="http://cnx.rice.edu/mdml">
<metadata><md:title>Controlled source fixture</md:title>
<md:license url="http://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0 International</md:license></metadata>
<content><module document="module-one"/></content></collection>'''


class EducationAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.archive, self.bank = self.root / 'archive', self.root / 'bank'
        self.catalogue = {'schema': 'speakeasy-education-source-catalogue/1',
                          'standing': 'candidate-sources', 'sources': [
            {'id': 'controlled-assessment-' + name, 'provider': 'openstax-github',
             'repository': 'openstax/controlled-' + name, 'revision': name * 40,
             'stages': ['primary'], 'subjects': ['mathematics']} for name in ('a', 'b')]}
        files = {'LICENSE': b'Attribution 4.0 International\nControlled source license.',
                 'modules/module-one/index.cnxml': MODULE,
                 'collections/controlled.collection.xml': COLLECTION}
        self.files = files
        trees = {}
        for source in self.catalogue['sources']:
            entries = [{'path': path, 'type': 'blob', 'size': len(data),
                        'sha': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()}
                       for path, data in files.items()]
            trees[source['revision']] = A.encoded({'sha': source['revision'], 'truncated': False, 'tree': entries})
        def fetch(url):
            if '/git/trees/' in url:
                return trees[url.split('/git/trees/')[1].split('?')[0]], url
            path = url.split('/' + url.split('/')[5] + '/', 1)[1]
            return files[path], url
        with patch.object(C, 'fetch', side_effect=fetch):
            self.assertTrue(C.acquire(self.catalogue, self.archive))
        self.split_policy = {'schema': 'speakeasy-educational-source-splits/1',
                             'owner': 'caller:controlled-source-partition',
                             'assignments': {'controlled-assessment-a': 'test', 'controlled-assessment-b': 'test'}}
        self.manifest = G.build_bank(self.archive, self.bank, split_policy=self.split_policy)
        self.rows = [A.loads(line) for line in (self.bank / 'assessments.jsonl').read_text(encoding='utf-8').splitlines()]

    def tearDown(self):
        self.tmp.cleanup()

    def item(self, identity):
        return next(v for v in self.rows if v['source']['id'] == 'controlled-assessment-a'
                    and v['exercise']['id'] == identity)

    def response(self, identity='fraction', text='0.5', **changes):
        value = {'schema': 'speakeasy-educational-assessment-response/1',
                 'itemSha256': self.item(identity)['contentSha256'],
                 'learner': {'kind': 'person', 'id': 'learner-one', 'version': 'person-snapshot-one'},
                 'sessionId': 'recorded-assessment-session', 'asOfTime': {'clock': 'county-tick', 'value': 9000},
                 'learningMode': 'independent-retrieval', 'assistanceEvidenceRefs': [],
                 'evidenceRefs': ['actual-recorded-response'], 'response': text}
        value.update(changes)
        return value

    def graded(self, identity='fraction', text='0.5', **changes):
        return G.grade(self.archive, self.bank, self.response(identity, text, **changes))

    def test_actual_producer_preserves_source_bound_bank(self):
        manifest, rows = G.validate_bank(self.archive, self.bank)
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(len(rows), 20)
        self.assertEqual(manifest['counts']['eligible'], 10)
        self.assertEqual(manifest['counts']['missingAnswer'], 2)
        row = self.item('fraction')
        self.assertEqual(row['exercise']['problemIds'], ['fraction-problem'])
        self.assertEqual(row['exercise']['solutionIds'], ['fraction-solution'])
        self.assertIn('mfrac', row['solutionXml'][0])
        self.assertEqual(row['gradingTarget']['value'], {'numerator': 1, 'denominator': 2})
        self.assertEqual(row['source']['version'], 'a' * 40)
        self.assertEqual(row['conceptRef']['source'], row['source'])
        self.assertEqual(row['conceptRef']['exerciseId'], 'fraction')
        self.assertFalse(manifest['personalRetentionAuthority'])

    def test_correct_fraction_and_equivalent_decimal(self):
        for text in ('1/2', '0.5', '5e-1'):
            receipt = self.graded(text=text)
            self.assertEqual((receipt['status'], receipt['earnedPoints'], receipt['maxPoints']), ('correct', 1, 1))
            self.assertTrue(receipt['independentRetrievalEvidence'])
            self.assertEqual(receipt['asOfTime'], {'clock': 'county-tick', 'value': 9000})
            self.assertFalse(receipt['nativeSkillAuthority'])
            self.assertFalse(receipt['independentMasteryAuthority'])

    def test_wrong_numeric_response_is_scored_incorrect(self):
        receipt = self.graded(text='1/3')
        self.assertEqual((receipt['status'], receipt['earnedPoints'], receipt['confidence']), ('incorrect', 0, 1))

    def test_mixed_numbers_and_adjacent_math_terms_cannot_invent_scalar_targets(self):
        import xml.etree.ElementTree as ET
        problem = ET.fromstring('<problem xmlns="http://cnx.rice.edu/cnxml" id="p"><para>Give the value.</para></problem>')
        for body in ('<m:mn>1</m:mn><m:mfrac><m:mn>3</m:mn><m:mn>4</m:mn></m:mfrac>',
                     '<m:mn>1</m:mn><m:mn>2</m:mn>'):
            solution = ET.fromstring('<solution xmlns="http://cnx.rice.edu/cnxml" '
                                     'xmlns:m="http://www.w3.org/1998/Math/MathML" id="s">'
                                     '<para><m:math><m:mrow>' + body + '</m:mrow></m:math></para></solution>')
            target, reason = G.target([problem], [solution])
            self.assertIsNone(target)
            self.assertEqual(reason, 'source-answer-not-automatically-gradable')
        self.assertEqual(G.quantity('-(1/2)')['value'], {'numerator': -1, 'denominator': 2})

    def test_mathematical_choice_option_text_does_not_flatten_away_exponents(self):
        import xml.etree.ElementTree as ET
        problem = ET.fromstring('<problem xmlns="http://cnx.rice.edu/cnxml" '
            'xmlns:m="http://www.w3.org/1998/Math/MathML" id="p"><para>Select one.</para>'
            '<list list-type="enumerated" number-style="lower-alpha">'
            '<item><m:math><m:msup><m:mn>10</m:mn><m:mn>2</m:mn></m:msup></m:math></item>'
            '<item>Another option</item></list></problem>')
        options = G.choice_options(problem)
        self.assertIsNone(options[0]['text'])
        self.assertIn('msup', options[0]['xml'])

    def test_unknown_freeform_is_not_invented_incorrectness(self):
        receipt = self.graded(text='I think the answer is half.')
        self.assertEqual(receipt['status'], 'unrecognized-response')
        self.assertIsNone(receipt['earnedPoints'])
        self.assertEqual(receipt['maxPoints'], 1)
        self.assertEqual(receipt['confidence'], 0)
        self.assertFalse(receipt['independentRetrievalEvidence'])

    def test_units_convert_with_explicit_versioned_policy(self):
        self.assertEqual(self.graded('units', '200 cm')['status'], 'correct')
        self.assertEqual(self.graded('units', '2 kg')['status'], 'incorrect')
        self.assertEqual(self.graded('units', '2')['status'], 'incorrect')
        self.assertEqual(self.graded('units', '2 cubits')['status'], 'unrecognized-response')
        self.assertEqual(G.quantity('2 m/s^2')['dimension'], 'acceleration')

    def test_numeric_tolerance_has_explicit_caller_owner(self):
        policy = {'schema': 'speakeasy-educational-grading-policy/1', 'owner': 'caller:recorded-rounding-rule',
                  'absoluteTolerance': '0.01', 'relativeTolerance': '0', 'unitPolicy': 'explicit-exact-unit-table/1'}
        self.assertEqual(self.graded('decimal', '0.399')['status'], 'incorrect')
        receipt = self.graded('decimal', '0.399', gradingPolicy=policy)
        self.assertEqual(receipt['status'], 'correct')
        self.assertEqual(receipt['gradingPolicy'], policy)
        policy['owner'] = 'source-guessed-rounding'
        with self.assertRaisesRegex(ValueError, 'explicit caller owner'):
            self.graded('decimal', '0.399', gradingPolicy=policy)

    def test_multiple_choice_uses_source_key_or_exact_option(self):
        for text in ('B', '(b)', 'Second option'):
            self.assertEqual(self.graded('choice', text)['status'], 'correct')
        self.assertEqual(self.graded('choice', 'A')['status'], 'incorrect')
        self.assertEqual(self.graded('choice', 'I prefer B')['status'], 'unrecognized-response')
        self.assertEqual(self.graded('choice-explanation', 'A')['status'], 'correct')

    def test_missing_answer_and_multipart_remain_coverage_gaps(self):
        for identity, reason in [('missing', 'missing-source-answer'), ('multipart', 'multipart-answer-ambiguous'),
                                 ('prose', 'source-answer-not-automatically-gradable'),
                                 ('algebra', 'source-answer-not-automatically-gradable')]:
            item = self.item(identity)
            self.assertIsNone(item['gradingTarget'])
            self.assertEqual(item['eligibility'], reason)
            receipt = self.graded(identity, '1')
            self.assertEqual(receipt['status'], 'ungradable-target')
            self.assertIsNone(receipt['earnedPoints'])
            self.assertEqual(receipt['maxPoints'], 0)

    def test_source_without_original_exercise_id_is_ungradable(self):
        row = next(v for v in self.rows if v['exercise']['id'] is None)
        self.assertEqual(row['eligibility'], 'missing-source-element-identity')

    def test_learner_inputs_preserve_problem_and_context_without_answers(self):
        public = (self.bank / 'learner-items.jsonl').read_text(encoding='utf-8')
        self.assertNotIn('PRIVATE_SOURCE_SOLUTION', public)
        self.assertNotIn('solutionXml', public)
        self.assertNotIn('gradingTarget', public)
        self.assertNotIn('correctKey', public)
        self.assertNotIn('fraction-solution', public)
        item = G.learner_input(self.item('fraction'))
        self.assertIn('Give one numeric answer', str(item['input']['contextXml']))
        self.assertIn('What is one divided by two?', str(item['input']['problemXml']))

    def test_rehashed_target_tamper_fails_against_actual_source(self):
        rows = copy.deepcopy(self.rows)
        row = rows[0]
        self.assertEqual(row['gradingTarget']['kind'], 'numeric')
        row['gradingTarget']['value'] = {'numerator': 7, 'denominator': 1}
        row['gradingTarget']['baseValue'] = {'numerator': 7, 'denominator': 1}
        row.pop('contentSha256')
        rows[0] = A.seal(row)
        private = G.serialized(rows)
        (self.bank / 'assessments.jsonl').write_bytes(private)
        manifest = copy.deepcopy(self.manifest)
        manifest['assessmentsSha256'] = C.sha(private)
        manifest.pop('contentSha256')
        C.write_json(self.bank / 'manifest.json', A.seal(manifest))
        with self.assertRaisesRegex(ValueError, 'differs from source reconstruction'):
            G.grade(self.archive, self.bank, self.response())

    def test_source_corruption_fails_before_grade(self):
        path = self.archive / 'controlled-assessment-a/source/modules/module-one/index.cnxml'
        path.write_bytes(path.read_bytes() + b'CORRUPTED_SOURCE')
        with self.assertRaisesRegex(ValueError, 'protected educational source changed'):
            self.graded()

    def test_rehashed_public_solution_leak_fails_source_reconstruction(self):
        data = (self.bank / 'learner-items.jsonl').read_bytes() + b'PRIVATE_SOURCE_SOLUTION'
        (self.bank / 'learner-items.jsonl').write_bytes(data)
        manifest = copy.deepcopy(self.manifest)
        manifest['learnerItemsSha256'] = C.sha(data)
        manifest.pop('contentSha256')
        C.write_json(self.bank / 'manifest.json', A.seal(manifest))
        with self.assertRaisesRegex(ValueError, 'metadata differs from source reconstruction'):
            G.validate_bank(self.archive, self.bank)

    def test_hints_tutoring_passive_and_cross_learning_cannot_claim_independent_mastery(self):
        for mode in ('hinted-retrieval', 'tutoring', 'passive-learning', 'cross-learning'):
            refs = [] if mode == 'passive-learning' else ['actual-person-tutoring-communication-receipt']
            receipt = self.graded(learningMode=mode, assistanceEvidenceRefs=refs)
            self.assertEqual(receipt['status'], 'correct')
            self.assertFalse(receipt['independentRetrievalEvidence'])
            self.assertFalse(receipt['independentMasteryAuthority'])
        with self.assertRaisesRegex(ValueError, 'cannot claim independent retrieval'):
            self.graded(assistanceEvidenceRefs=['a-hint-was-given'])
        with self.assertRaisesRegex(ValueError, 'assistance evidence'):
            self.graded(learningMode='tutoring')

    def test_family_splits_exclude_whole_book_answers_from_evaluation_training(self):
        families = self.manifest['sourceFamilyComponents']['sourceFamilies']
        self.assertEqual(len(families), 1)
        self.assertEqual(families[0]['sourceIds'], ['controlled-assessment-a', 'controlled-assessment-b'])
        self.assertEqual({r['familyId'] for r in self.rows}, {families[0]['id']})
        proof = G.validate_training_isolation(self.manifest, [], archive=self.archive, bank=self.bank)
        self.assertEqual(proof['evaluationSourceIds'], ['controlled-assessment-a', 'controlled-assessment-b'])
        self.assertEqual(proof, G.validate_training_isolation(self.manifest, [], archive=self.archive, bank=self.bank))
        with self.assertRaisesRegex(ValueError, 'solutions leaked'):
            G.validate_training_isolation(self.manifest, ['controlled-assessment-b'], archive=self.archive, bank=self.bank)
        bad = copy.deepcopy(self.split_policy)
        bad['assignments'].pop('controlled-assessment-a')
        with self.assertRaisesRegex(ValueError, 'every whole source'):
            G.build_bank(self.archive, self.root / 'incomplete-splits', split_policy=bad)

    def test_identical_source_module_cannot_be_relabelled_into_different_partitions(self):
        bad = copy.deepcopy(self.split_policy)
        bad['assignments']['controlled-assessment-b'] = 'train'
        with self.assertRaisesRegex(ValueError, 'related source component crosses partitions'):
            G.build_bank(self.archive, self.root / 'leaking-splits', split_policy=bad)
        self.assertFalse((self.root / 'leaking-splits').exists())
        _, rows = G.derive(self.archive)
        self.assertEqual(len({row['split'] for row in rows}), 1)

    def test_foundation_source_family_request_is_bound_and_cannot_split_shared_modules(self):
        family = self.manifest['sourceFamilyComponents']['sourceFamilies'][0]
        request = {'schema': 'speakeasy-educational-source-splits', 'schemaVersion': 1,
                   'sourceFamilies': [family], 'splits': {'train': [], 'validation': [], 'test': [family['id']]}}
        bank = self.root / 'foundation-bank'
        manifest = G.build_bank(self.archive, bank, split_policy=request)
        proof = G.validate_training_isolation(manifest, request, archive=self.archive, bank=bank)
        self.assertEqual(proof['trainingInventoryKind'], 'foundation-source-family-request')
        self.assertEqual(proof['trainingInventorySha256'], A.digest(request))
        bad = copy.deepcopy(request)
        bad['sourceFamilies'] = [{'id': 'independent-a', 'sourceIds': ['controlled-assessment-a']},
                                 {'id': 'independent-b', 'sourceIds': ['controlled-assessment-b']}]
        bad['splits'] = {'train': ['independent-b'], 'validation': [], 'test': ['independent-a']}
        with self.assertRaisesRegex(ValueError, 'related source component crosses caller source families'):
            G.validate_training_isolation(manifest, bad, archive=self.archive, bank=bank)

    def acquire_related(self, destination, modules, same_repository=False):
        catalogue = copy.deepcopy(self.catalogue)
        if same_repository:
            for source in catalogue['sources']:
                source['repository'] = 'openstax/same-book'
        responses = {}
        for source in catalogue['sources']:
            files = {'LICENSE': self.files['LICENSE'], 'modules/module-one/index.cnxml': modules[source['id']],
                     'collections/controlled.collection.xml': COLLECTION}
            tree = {'sha': source['revision'], 'truncated': False, 'tree': [
                {'path': path, 'type': 'blob', 'size': len(data),
                 'sha': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()}
                for path, data in files.items()]}
            responses[f"https://api.github.com/repos/{source['repository']}/git/trees/{source['revision']}?recursive=1"] = A.encoded(tree)
            for path, data in files.items():
                responses[f"https://raw.githubusercontent.com/{source['repository']}/{source['revision']}/{path}"] = data
        with patch.object(C, 'fetch', side_effect=lambda url: (responses[url], url)):
            self.assertTrue(C.acquire(catalogue, destination))
        return C.verified_sources(destination)

    def test_different_revisions_of_one_publisher_book_cannot_cross_partitions(self):
        modules = {}
        for i, identity in enumerate(('controlled-assessment-a', 'controlled-assessment-b')):
            modules[identity] = (f'<document xmlns="http://cnx.rice.edu/cnxml"><content><exercise id="e-{i}">'
                f'<problem id="p-{i}"><para>What is the controlled value {i}?</para></problem>'
                f'<solution id="s-{i}"><para>{i}</para></solution></exercise></content></document>').encode()
        archive = self.root / 'same-book-revisions'
        sources = self.acquire_related(archive, modules, same_repository=True)
        graph = G.source_components(sources, archive)
        self.assertEqual(len(graph['sourceFamilies']), 1)
        self.assertEqual({edge['kind'] for edge in graph['sharedEvidence']}, {'publisher-book-lineage'})
        bad = copy.deepcopy(self.split_policy)
        bad['assignments']['controlled-assessment-b'] = 'train'
        with self.assertRaisesRegex(ValueError, 'related source component crosses partitions'):
            G.build_bank(archive, self.root / 'same-book-leak', split_policy=bad)

    def test_shared_problem_solution_pair_joins_otherwise_different_module_bytes(self):
        archive = self.root / 'related-module-archive'
        altered = MODULE.replace(b'<content>', b'<content><para id="different-content">A different module introduction.</para>')
        self.assertNotEqual(C.sha(MODULE), C.sha(altered))
        sources = self.acquire_related(archive, {'controlled-assessment-a': MODULE, 'controlled-assessment-b': altered})
        graph = G.source_components(sources, archive)
        self.assertEqual(len(graph['sourceFamilies']), 1)
        self.assertIn('source-exercise-problem-solution', {edge['kind'] for edge in graph['sharedEvidence']})
        bank = self.root / 'related-module-bank'
        manifest = G.build_bank(archive, bank, split_policy=self.split_policy)
        with self.assertRaisesRegex(ValueError, 'related source component'):
            G.validate_training_isolation(manifest, ['controlled-assessment-b'], archive=archive, bank=bank)

    def test_renamed_source_ids_do_not_hide_identical_question_answer_pairs(self):
        root = ET.fromstring(MODULE)
        for element in root.iter():
            if 'id' in element.attrib:
                element.set('id', 'renamed-' + element.get('id'))
        altered = ET.tostring(root, encoding='utf-8')
        self.assertNotEqual(C.sha(MODULE), C.sha(altered))
        archive = self.root / 'renamed-module-archive'
        sources = self.acquire_related(archive, {'controlled-assessment-a': MODULE,
                                                'controlled-assessment-b': altered})
        graph = G.source_components(sources, archive)
        self.assertEqual(len(graph['sourceFamilies']), 1)
        self.assertIn('source-exercise-problem-solution',
                      {edge['kind'] for edge in graph['sharedEvidence']})
        bad = copy.deepcopy(self.split_policy)
        bad['assignments']['controlled-assessment-b'] = 'train'
        with self.assertRaisesRegex(ValueError, 'related source component crosses partitions'):
            G.build_bank(archive, self.root / 'renamed-copy-leak', split_policy=bad)
        bank = self.root / 'renamed-module-bank'
        manifest = G.build_bank(archive, bank, split_policy=self.split_policy)
        rows = [A.loads(line) for line in (bank / 'assessments.jsonl').read_text(encoding='utf-8').splitlines()]
        renamed = next(row for row in rows if row['source']['id'] == 'controlled-assessment-b'
                       and row['exercise']['id'] == 'renamed-fraction')
        self.assertEqual(renamed['exercise']['problemIds'], ['renamed-fraction-problem'])
        self.assertIn('id="renamed-fraction-problem"', renamed['learnerInput']['problemXml'][0])
        with self.assertRaisesRegex(ValueError, 'related source component'):
            G.validate_training_isolation(manifest, ['controlled-assessment-b'], archive=archive, bank=bank)

    def test_isolation_proof_reconstructs_components_after_rehashed_manifest_tamper(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['splitPolicy']['assignments']['controlled-assessment-b'] = 'train'
        manifest.pop('contentSha256')
        manifest = A.seal(manifest)
        with self.assertRaisesRegex(ValueError, 'isolation bank differs from actual source reconstruction'):
            G.validate_training_isolation(manifest, ['controlled-assessment-b'], archive=self.archive, bank=self.bank)

    def curriculum(self):
        source = C.verified_sources(self.archive)[0]
        entry, text, coverage = next(C.texts(source, self.archive))
        def unit(identity, start, end):
            return {'id': identity, 'title': 'Exact source selector', 'sourceId': source['id'],
                    'sourceVersion': source['sourceVersion'], 'editionYear': None, 'editionEvidence': None,
                    'temporalStanding': 'source-period-review-required',
                    'selector': {'sourcePath': entry['path'], 'sourceSha256': entry['sha256'],
                                 'extractionSha256': C.sha(text.encode()), 'startCharacter': start,
                                 'endCharacter': end, 'excerptSha256': C.sha(text[start:end].encode()),
                                 'format': coverage['format']},
                    'activities': [{'kind': 'exercise', 'literalEvidence': 'What is one divided by two?'}]}
        start = text.index('What is one divided by two?')
        units = [unit('whole-module-unit', 0, len(text)), unit('problem-fragment-unit', start, start + 27)]
        courses = [{'id': level + '-mathematics', 'level': level, 'subject': 'mathematics',
                    'title': 'Source mathematics', 'requirement': 'core', 'prerequisites': [],
                    'optionalUnitIds': [], 'units': units if i == 0 else [],
                    'coverageNeeds': [] if i == 0 else ['Source units unavailable']}
                   for i, level in enumerate(K.LEVELS)]
        return {'schema': 'speakeasy-educational-curriculum/1', 'id': 'controlled-assessment-curriculum',
                'version': '1', 'standing': 'candidate-curriculum', 'title': 'Controlled source curriculum',
                'levels': K.LEVELS, 'courses': courses, 'specializations': [],
                'regionalPolicy': {'sharedCore': 'required-course-and-unit-identities',
                                   'optionalUnitNumerator': 1, 'optionalUnitDenominator': 5,
                                   'owner': 'explicit-region-cohort-institution-history',
                                   'migration': 'preserve-source-education-history'}, 'knownCoverageGaps': []}

    def test_course_units_require_exact_exercise_coverage_by_verified_selectors(self):
        curriculum = self.curriculum()
        bank = self.root / 'curriculum-bank'
        G.build_bank(self.archive, bank, curriculum, self.split_policy)
        _, rows = G.validate_bank(self.archive, bank, curriculum)
        item = next(v for v in rows if v['source']['id'] == 'controlled-assessment-a' and v['exercise']['id'] == 'fraction')
        self.assertEqual([v['unitId'] for v in item['courseUnits']], ['whole-module-unit'])
        self.assertEqual(item['courseUnits'][0]['curriculumRef'], K.reference(curriculum))

    def test_receipts_are_exact_replay_and_time_domain_bound(self):
        response = self.response()
        first = G.grade(self.archive, self.bank, response)
        self.assertEqual(first, G.grade(self.archive, self.bank, response))
        later = G.grade(self.archive, self.bank, {**response, 'asOfTime': {'clock': 'county-tick', 'value': 18000}})
        self.assertNotEqual(first['contentSha256'], later['contentSha256'])
        self.assertEqual(first['conceptRef'], later['conceptRef'])
        with self.assertRaisesRegex(ValueError, 'UTC offset'):
            self.graded(asOfTime={'clock': 'utc', 'value': '2026-09-30T00:00:00'})
        with self.assertRaisesRegex(ValueError, 'recorded evidence'):
            self.graded(evidenceRefs=[])

    def test_unknown_assessment_or_changed_source_version_refuses(self):
        with self.assertRaisesRegex(ValueError, 'unknown item'):
            G.grade(self.archive, self.bank, {**self.response(), 'itemSha256': '0' * 64})
        record = A.read(self.archive / 'acquisition.json')
        record['sources'][0]['sourceVersion'] = 'f' * 40
        C.write_json(self.archive / 'acquisition.json', record)
        with self.assertRaisesRegex(ValueError, 'source metadata differs'):
            self.graded()

    def test_existing_bank_and_receipts_remain_immutable(self):
        before = (self.bank / 'manifest.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'preserve prior version'):
            G.build_bank(self.archive, self.bank)
        self.assertEqual((self.bank / 'manifest.json').read_bytes(), before)
        responses = self.root / 'responses.jsonl'
        responses.write_bytes(G.serialized([self.response()]))
        out = self.root / 'receipts.jsonl'
        args = ['grade', '--archive', str(self.archive), '--bank', str(self.bank),
                '--responses', str(responses), '--out', str(out)]
        self.assertEqual(G.main(args), 0)
        recorded = out.read_bytes()
        self.assertEqual(A.loads(recorded.decode())['earnedPoints'], 1)
        self.assertEqual(G.main(args), 2)
        self.assertEqual(out.read_bytes(), recorded)


if __name__ == '__main__':
    unittest.main()
