"""Real compiler/grader reconstruction with explicit controlled people and migrations."""
import copy
import json
import unittest
import decision_authoring as A
import education_backgrounds as B
import education_learning as L
import education_runtime_registry as R
import test_education_learning as F


class EducationRuntimeRegistryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=F.EducationLearningTests('test_actual_grader_receipt_changes_person_memory_and_is_attributable')
        self.fixture.setUp()
        self.plan=copy.deepcopy(self.fixture.base['plan'])
        outside=copy.deepcopy(self.plan['regions'][0]); outside['id']='outside-birth-region'
        outside['cohorts'][0]['id']='outside-source-cohort'; outside['cohorts'][0]['institutions'][0]['id']='outside-source-school'
        self.plan['regions'].append(outside)
        self.world=self.plan['worldOwner']
        self.definition=A.encoded({'schema':'controlled-world-definition/1','worldOwner':self.world})
        curriculum=self.fixture.base['curriculum']
        backgrounds=B.generate_backgrounds(self.plan,[curriculum],self.fixture.archive)
        self.entries=[]
        for identity,outside_person in [('learner-one',False),('outsider-person',True)]:
            profile=copy.deepcopy(self.fixture.context['profile']); profile['id']=identity
            if outside_person:
                profile['birthRegionId']='outside-birth-region'
                profile['migrations']=[{'year':1980,'fromRegionId':'outside-birth-region','toRegionId':'kentucky'}]
            context={**self.fixture.base,'plan':self.plan,'backgrounds':backgrounds,'profile':profile}
            context['person']=B.generate_person(profile,backgrounds,self.plan,[curriculum],self.fixture.archive)
            context['education']=B.compile_generated(curriculum,self.fixture.archive,self.plan,backgrounds,profile,context['person'])
            policy=copy.deepcopy(self.fixture.policy); policy['ticksPerDay']=R.TICKS_PER_DAY
            ledger=L.initialize(context,policy,self.fixture.bank,self.fixture.start)
            response=self.fixture.response(context=context)
            event=L.assessment_event('controlled-registry-response-'+identity,response,self.fixture.archive,self.fixture.bank)
            ledger=L.apply_event(ledger,event,context,policy,self.fixture.bank)
            self.entries.append({'context':context,'ledger':ledger,'policy':policy,'bank':self.fixture.bank,
                'asOfTime':{'clock':'county-day','value':3},'teachers':None,'maximumConcepts':128})
        self.registry=R.build_registry(self.definition,self.world,self.entries)

    def tearDown(self): self.fixture.tearDown()

    def test_source_reconstructed_two_people_and_outsider_profile_are_exact(self):
        self.assertEqual(self.registry,R.verify_registry(self.registry,self.definition,self.world,self.entries))
        self.assertEqual(len(self.registry['rows']),2)
        outsider=next(row for row in self.registry['rows'] if row['personId']=='outsider-person')
        self.assertEqual(outsider['sourceProfile']['birthRegionId'],'outside-birth-region')
        self.assertEqual(outsider['sourceProfile']['currentRegionId'],'kentucky')
        self.assertEqual(outsider['sourceProfile']['migrations'],self.entries[1]['context']['profile']['migrations'])
        self.assertEqual(outsider['sourceProfileSha256'],A.digest(outsider['sourceProfile']))
        self.assertEqual(outsider['rawPriorSha256'],A.digest(outsider['prior']))
        for flag in L.AUTHORITY: self.assertFalse(self.registry[flag])

    def test_definition_identity_matches_existing_sao_canonical_body(self):
        changed=R.build_registry(self.definition+b'\n',self.world,self.entries)
        self.assertEqual(changed,self.registry)
        body=json.loads(self.definition)
        pretty=json.dumps(body,ensure_ascii=False,indent=2).encode('utf-8')+b'\n'
        self.assertEqual(self.registry,R.build_registry(pretty,self.world,self.entries))
        body['label']='Montréal 漢 🙂'
        unicode_raw=json.dumps(body,ensure_ascii=False,indent=2).encode('utf-8')+b'\n'
        escaped_raw=json.dumps(body,ensure_ascii=True,sort_keys=True).encode('utf-8')
        self.assertEqual(R.definition_bytes(unicode_raw,self.world),R.definition_bytes(escaped_raw,self.world))
        expected=json.dumps(body,ensure_ascii=True,sort_keys=True,separators=(',', ':'),allow_nan=False).encode('utf-8')
        self.assertEqual(R.definition_bytes(unicode_raw,self.world),R.hashlib.sha256(expected).hexdigest())
        body['changedValue']=True
        with self.assertRaisesRegex(ValueError,'source reconstruction'):
            R.verify_registry(self.registry,A.encoded(body),self.world,self.entries)

    def test_world_owner_mismatch_refuses_source_relabel(self):
        changed=copy.deepcopy(self.world); changed['seed']='other-seed'
        with self.assertRaisesRegex(ValueError,'source owner|different world'):
            R.build_registry(self.definition,changed,self.entries)

    def test_duplicate_person_and_unbounded_rows_refuse(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            R.build_registry(self.definition,self.world,[self.entries[0],self.entries[0]])
        with self.assertRaisesRegex(ValueError,'bounded'):
            R.build_registry(self.definition,self.world,[self.entries[0]]*129)

    def test_resealed_prior_or_birth_profile_drift_fails_reconstruction(self):
        for field in ('prior','sourceProfile'):
            body=B.checked(self.registry,'registry'); row=B.checked(body['rows'][0],'row')
            if field=='prior':
                prior=B.checked(row['prior'],'prior'); prior['concepts'][0]['retention']=1
                row['prior']=B.seal(prior); row['rawPriorSha256']=A.digest(row['prior'])
            else:
                row['sourceProfile']['birthYear']+=1; row['sourceProfileSha256']=A.digest(row['sourceProfile'])
            body['rows'][0]=B.seal(row)
            with self.assertRaisesRegex(ValueError,'source reconstruction'):
                R.verify_registry(B.seal(body),self.definition,self.world,self.entries)

    def test_ledger_and_context_tampering_refuse_before_registry_output(self):
        entries=copy.deepcopy(self.entries)
        entries[0]['context']['profile']['birthYear']+=1
        with self.assertRaises(ValueError): R.build_registry(self.definition,self.world,entries)
        entries=copy.deepcopy(self.entries); body=B.checked(entries[0]['ledger'],'ledger')
        next(iter(body['concepts'].values()))['retention']=1; entries[0]['ledger']=B.seal(body)
        with self.assertRaisesRegex(ValueError,'source/event reconstruction'):
            R.build_registry(self.definition,self.world,entries)

    def test_native_clock_and_invalid_json_definition_refuse(self):
        entries=copy.deepcopy(self.entries); entries[0]['policy']['ticksPerDay']=60000
        # County-day policy change changes the binding even where elapsed values are identical.
        with self.assertRaises(ValueError): R.build_registry(self.definition,self.world,entries)
        with self.assertRaises(ValueError): R.build_registry(b'{"x":1,"x":2}',self.world,self.entries)

    def test_order_is_stable_and_returned_views_are_detached(self):
        self.assertEqual(self.registry,R.build_registry(self.definition,self.world,list(reversed(self.entries))))
        copied=R.verify_registry(self.registry,self.definition,self.world,self.entries)
        copied['rows'][0]['sourceProfile']['birthYear']=1900
        self.assertNotEqual(copied,self.registry)


if __name__=='__main__': unittest.main()
