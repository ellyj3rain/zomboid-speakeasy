"""Educational acquisition and training admission refuse missing source authority."""
import json
import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import decision_authoring as A
import education_corpus as C
import training_evidence as E

CATALOGUE={'schema':'speakeasy-education-source-catalogue/1','standing':'candidate-sources',
 'sources':[{'id':'controlled-arithmetic','provider':'gutenberg','bookId':1,
             'stages':['primary'],'subjects':['mathematics']}]}
PAGE=b'<title>Controlled historical arithmetic</title>Public domain in the USA <a href="/files/1/1.txt" type="text/plain">Text</a>'
TEXT=b'*** START OF THE PROJECT GUTENBERG EBOOK CONTROL ***\nControlled arithmetic example. Exercise: one plus one.\n*** END OF THE PROJECT GUTENBERG EBOOK CONTROL ***'

class EducationCorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.archive=self.root/'archive';self.prepared=self.root/'prepared'
        def fetch(url): return (PAGE if '/ebooks/' in url else TEXT),url
        self.fetch=patch.object(C,'fetch',side_effect=fetch);self.fetch.start()
        C.acquire(CATALOGUE,self.archive)
    def tearDown(self):
        self.fetch.stop();self.tmp.cleanup()
    def prepare(self,path=None):
        return C.prepare(self.archive,path or self.prepared,256)
    def approval(self,subject,**changes):
        lineage={'evidenceRef':'speakeasy:content-sha256:'+subject}
        value={'schema':'mousecat.skill-invocation/2','action':'await','skillRef':'crucible',
               'status':'answered','interactionId':'controlled-review',
               'items':[{'id':'controlled-item','shape':'decision','lineage':lineage}],
               'responses':[{'itemId':'controlled-item','shape':'decision','status':'answered',
                             'value':'approved','selectedOption':'approved',
                             'selectedOptions':['approved'],'lineage':lineage,'notes':None}]}
        value.update(changes)
        store=self.root/'evidence';store.mkdir(exist_ok=True)
        digest=A.digest(value);C.write_json(store/(digest+'.json'),value)
        return E.Store(store),digest
    def test_exact_source_body_is_preserved(self):
        source=C.verified_sources(self.archive)[0]
        self.assertEqual((self.archive/'controlled-arithmetic/source.txt').read_bytes(),TEXT)
        self.assertEqual(source['sourceVersion'],C.sha(TEXT))

    def test_automatic_prerequisite_admission_needs_no_operator_ruling(self):
        self.prepare()
        dataset=self.root/'automatic-dataset'
        with patch.object(E.Store,'decision',side_effect=AssertionError('unwanted manual gate')):
            manifest=C.admit(self.archive,self.prepared,dataset)
            self.assertEqual(C.validate_admitted(self.archive,self.prepared,dataset),manifest)
        self.assertEqual(manifest['sourceAdmissionKind'],'automated-prerequisite-material')
        self.assertIsNone(manifest['approvalReceiptSha256'])
        evaluation=A.read(dataset/'evaluation.json')
        self.assertEqual(evaluation['status'],'eligible-prerequisite-pretraining-material')
        self.assertIsNone(evaluation['learnerGrade'])
        evaluation['learnerGrade']=1
        C.write_json(dataset/'evaluation.json',evaluation)
        with self.assertRaisesRegex(ValueError,'automated source evaluation differs'):
            C.validate_admitted(self.archive,self.prepared,dataset)

    def test_automatic_admission_cannot_accept_rehashed_invented_rows(self):
        proposal=self.prepare()
        rows=[json.loads(line) for line in (self.prepared/'candidate-texts.jsonl').read_text().splitlines()]
        rows[0]['text']='Invented unseen objects.'
        rows[0].pop('contentSha256');rows[0]['contentSha256']=A.digest(rows[0])
        data=b''.join(A.encoded(row)+b'\n' for row in rows)
        (self.prepared/'candidate-texts.jsonl').write_bytes(data)
        proposal['candidateTextsSha256']=C.sha(data)
        proposal.pop('contentSha256');proposal['contentSha256']=A.digest(proposal)
        C.write_json(self.prepared/'review-proposal.json',proposal)
        with self.assertRaisesRegex(ValueError,'do not derive'):
            C.admit(self.archive,self.prepared,self.root/'automatic-dataset')
    def test_relative_acquisition_path_resolves(self):
        prior=Path.cwd()
        try:
            os.chdir(self.root)
            C.acquire(CATALOGUE,Path('relative-archive'))
            self.assertEqual(len(C.verified_sources(Path('relative-archive'))),1)
        finally: os.chdir(prior)
    def test_source_corruption_refuses_preparation(self):
        (self.archive/'controlled-arithmetic/source.txt').write_bytes(TEXT+b'changed')
        with self.assertRaisesRegex(ValueError,'protected educational source changed'):
            self.prepare()
        self.assertFalse(self.prepared.exists())
    def test_duplicate_catalogue_refuses(self):
        value=dict(CATALOGUE);value['sources']=CATALOGUE['sources']*2
        with self.assertRaisesRegex(ValueError,'duplicate'):
            C.validate_catalogue(value)
    def test_unpinned_publisher_refuses(self):
        value=dict(CATALOGUE);value['sources']=[{'id':'unversioned','provider':'openstax-github',
             'repository':'openstax/osbooks-physics','revision':'main',
             'stages':['secondary'],'subjects':['physics']}]
        with self.assertRaisesRegex(ValueError,'unpinned'):
            C.validate_catalogue(value)
    def test_preparation_is_deterministic_and_unreviewed(self):
        first=self.prepare();second=self.prepare(self.root/'second')
        self.assertEqual(first,second)
        self.assertEqual((self.prepared/'candidate-texts.jsonl').read_bytes(),
                         (self.root/'second/candidate-texts.jsonl').read_bytes())
        self.assertEqual(first['trainingRows'],0)
        row=json.loads((self.prepared/'candidate-texts.jsonl').read_text().splitlines()[0])
        self.assertIn('Controlled arithmetic example',row['text'])
        self.assertFalse(row['currentWorldAuthority']);self.assertFalse(row['personalAcquisitionAuthority'])
        self.assertEqual(row['objective'],'shared-base-next-token')
    def test_foreign_approval_refuses_training(self):
        self.prepare();store,digest=self.approval('0'*64)
        with self.assertRaisesRegex(ValueError,'exact subject'):
            C.admit(self.archive,self.prepared,self.root/'dataset',digest,store)
        self.assertFalse((self.root/'dataset').exists())
    def test_missing_approval_refuses_training(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError,'missing evidence'):
            C.admit(self.archive,self.prepared,self.root/'dataset','0'*64,E.Store(self.root/'missing'))
    def test_reviewed_exact_fixture_can_admit(self):
        proposal=self.prepare();store,digest=self.approval(proposal['contentSha256'])
        result=C.admit(self.archive,self.prepared,self.root/'dataset',digest,store)
        self.assertEqual(result['trainingRows'],proposal['candidateTexts'])
        self.assertFalse(result['policyAuthority']);self.assertFalse(result['currentWorldAuthority'])
        self.assertEqual((self.root/'dataset/texts.jsonl').read_bytes(),
                         (self.prepared/'candidate-texts.jsonl').read_bytes())
    def test_reviewed_text_mutation_refuses(self):
        proposal=self.prepare();store,digest=self.approval(proposal['contentSha256'])
        with (self.prepared/'candidate-texts.jsonl').open('ab') as handle: handle.write(b'changed')
        with self.assertRaisesRegex(ValueError,'reviewed educational text differs'):
            C.admit(self.archive,self.prepared,self.root/'dataset',digest,store)
    def test_archive_reuse_preserves_prior_bytes(self):
        before=(self.archive/'acquisition.json').read_bytes()
        self.fetch.stop()
        try:
            with patch.object(C,'fetch',side_effect=AssertionError('unexpected download')):
                C.acquire(CATALOGUE,self.root/'derived',reuse=self.archive)
            self.assertEqual((self.archive/'acquisition.json').read_bytes(),before)
            self.assertEqual((self.root/'derived/controlled-arithmetic/source.txt').read_bytes(),TEXT)
        finally: self.fetch.start()
    def test_archive_path_escape_refuses(self):
        value=A.read(self.archive/'acquisition.json')
        value['sources'][0]['files'][0]['path']='../foreign'
        C.write_json(self.archive/'acquisition.json',value)
        with self.assertRaisesRegex(ValueError,'source metadata differs|escapes archive'):
            C.verified_sources(self.archive)

    def test_source_id_escape_refuses_before_writing(self):
        value=dict(CATALOGUE);value['sources']=[dict(CATALOGUE['sources'][0],id='../escaped')]
        target=self.root/'unsafe'
        with self.assertRaisesRegex(ValueError,'safe directory component'):
            C.acquire(value,target)
        self.assertFalse(target.exists());self.assertFalse((self.root/'escaped').exists())

    def rewrite_source(self,**changes):
        record=A.read(self.archive/'acquisition.json')
        record['sources'][0].update(changes)
        C.write_json(self.archive/'controlled-arithmetic/source.json',record['sources'][0])
        C.write_json(self.archive/'acquisition.json',record)

    def test_metadata_only_version_mutation_refuses_all_consumers(self):
        self.rewrite_source(sourceVersion='0'*64)
        for operation in (lambda:C.verified_sources(self.archive),self.prepare,
                          lambda:C.acquire(CATALOGUE,self.root/'reuse',reuse=self.archive)):
            with self.assertRaisesRegex(ValueError,'source version differs'):
                operation()
        self.assertFalse(self.prepared.exists())

    def test_metadata_only_license_mutation_refuses(self):
        self.rewrite_source(license={'id':'invented-license'})
        with self.assertRaisesRegex(ValueError,'license metadata differs'):
            self.prepare()

    def test_archived_catalogue_prevents_stage_relabel(self):
        self.rewrite_source(stages=['college'])
        with self.assertRaisesRegex(ValueError,'archived catalogue'):
            C.verified_sources(self.archive)

    def test_missing_catalogue_refuses_current_pipeline(self):
        (self.archive/'catalogue.json').unlink()
        self.rewrite_source(stages=['college'])
        with self.assertRaisesRegex(ValueError,'legacy label binding unavailable'):
            self.prepare()
        self.assertFalse(self.prepared.exists())

    def test_exact_approval_cannot_admit_invented_or_authoritative_rows(self):
        proposal=self.prepare()
        rows=[json.loads(line) for line in (self.prepared/'candidate-texts.jsonl').read_text().splitlines()]
        rows[0]['text']='Invented unseen county supplies.'
        rows[0]['currentWorldAuthority']=True
        rows[0].pop('contentSha256');rows[0]['contentSha256']=A.digest(rows[0])
        data=b''.join(A.encoded(row)+b'\n' for row in rows)
        (self.prepared/'candidate-texts.jsonl').write_bytes(data)
        proposal['candidateTextsSha256']=C.sha(data)
        proposal.pop('contentSha256');proposal['contentSha256']=A.digest(proposal)
        C.write_json(self.prepared/'review-proposal.json',proposal)
        store,digest=self.approval(proposal['contentSha256'])
        with self.assertRaisesRegex(ValueError,'do not derive'):
            C.admit(self.archive,self.prepared,self.root/'dataset',digest,store)
        self.assertFalse((self.root/'dataset').exists())

    def test_exact_approval_cannot_change_counts_or_model_authority(self):
        proposal=self.prepare()
        proposal.update(candidateTexts=99,policyAuthority=True)
        proposal.pop('contentSha256');proposal['contentSha256']=A.digest(proposal)
        C.write_json(self.prepared/'review-proposal.json',proposal)
        store,digest=self.approval(proposal['contentSha256'])
        with self.assertRaisesRegex(ValueError,'review metadata differs'):
            C.admit(self.archive,self.prepared,self.root/'dataset',digest,store)
        self.assertFalse((self.root/'dataset').exists())

    def test_tex_extraction_excludes_license_preamble_and_appended_build_metadata(self):
        path=self.root/'source.tex'
        path.write_text('license and preamble\\begin{document}Actual math $a+b$. '
                        'Exercise.\\end{document}SYNC METADATA')
        source={'files':[{'path':'source.tex'}]}
        extracted=list(C.texts(source,self.root))
        self.assertEqual(extracted[0][1],'Actual math $a+b$. Exercise.')

    def test_actual_html_archive_retains_book_and_excludes_page_license(self):
        html=b'<html>Publisher preamble *** START OF THE PROJECT GUTENBERG EBOOK CONTROL ***<h1>Geometry</h1><p>Draw a line.</p><img alt="Triangle" src="images/a.png">*** END OF THE PROJECT GUTENBERG EBOOK CONTROL *** License</html>'
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as package:
            package.writestr('book/book.html',html);package.writestr('book/images/a.png',b'figure')
        page=b'<title>Actual geometry</title>Public domain in the USA <a href="/book.zip" type="application/zip">Book</a>'
        value=dict(CATALOGUE);value['sources']=[dict(CATALOGUE['sources'][0],format='html-archive')]
        with patch.object(C,'fetch',side_effect=lambda url:(page if '/ebooks/' in url else stream.getvalue(),url)):
            C.acquire(value,self.root/'html')
        source=C.verified_sources(self.root/'html')[0]
        self.assertEqual((self.root/'html/controlled-arithmetic/publisher.zip').read_bytes(),stream.getvalue())
        self.assertEqual((self.root/'html/controlled-arithmetic/source.html').read_bytes(),html)
        _,text,coverage=list(C.texts(source,self.root/'html'))[0]
        self.assertEqual(coverage['figures'],'publisher-archive-preserved-not-projected')
        self.assertIn('Draw a line.',text);self.assertIn('[Figure: Triangle]',text)
        self.assertNotIn('Publisher preamble',text);self.assertNotIn('License',text)
        changed=html.replace(b'Draw a line.',b'Invented world facts.')
        (self.root/'html/controlled-arithmetic/source.html').write_bytes(changed)
        record=A.read(self.root/'html/acquisition.json');record['sources'][0]['sourceVersion']=C.sha(changed)
        entry=next(f for f in record['sources'][0]['files'] if f['path'].endswith('/source.html'))
        entry.update(sha256=C.sha(changed),bytes=len(changed))
        C.write_json(self.root/'html/acquisition.json',record)
        C.write_json(self.root/'html/controlled-arithmetic/source.json',record['sources'][0])
        with self.assertRaisesRegex(ValueError,'derived HTML differs'):
            C.verified_sources(self.root/'html')

class PublisherRightsTests(unittest.TestCase):
    """Publisher-shaped controls run the real acquisition and archive owners."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.archive=self.root/'archive'
        self.source={'id':'controlled-publisher','provider':'openstax-github',
                     'repository':'openstax/controlled-publisher','revision':'a'*40,
                     'stages':['college'],'subjects':['economics']}
        self.catalogue={'schema':'speakeasy-education-source-catalogue/1',
                        'standing':'candidate-sources','sources':[self.source]}
        self.files={'LICENSE':b'Attribution 4.0 International\nControlled publisher terms.',
                    'modules/m1/index.cnxml':self.module(),
                    'collections/book.collection.xml':self.collection()}
    def tearDown(self):self.tmp.cleanup()
    @staticmethod
    def module(identity='m1',declaration=''):
        return ('<document xmlns="http://cnx.rice.edu/cnxml" xmlns:md="http://cnx.rice.edu/mdml">'
                '<metadata><md:content-id>'+identity+'</md:content-id>'+declaration+'</metadata>'
                '<content><para>Controlled publisher instruction.</para></content></document>').encode()
    @staticmethod
    def collection(members=('m1',),url='http://creativecommons.org/licenses/by/4.0/',declaration=None):
        # The NC-SA URL and wording reproduce the original Introduction to
        # Business 2e collection's declaration, independently of generic LICENSE.
        declaration=('<md:license url="'+url+'">Creative Commons '+
                     ('Attribution-NonCommercial-ShareAlike' if 'by-nc-sa' in url else 'Attribution')+
                     ' 4.0 International</md:license>') if declaration is None else declaration
        return ('<collection xmlns="http://cnx.rice.edu/collxml" xmlns:md="http://cnx.rice.edu/mdml">'
                '<metadata><md:title>Controlled source</md:title>'+declaration+'</metadata>'
                '<content>'+''.join('<module document="'+v+'"/>' for v in members)+
                '</content></collection>').encode()
    @staticmethod
    def blob(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    def acquire(self):
        tree=A.encoded({'sha':self.source['revision'],'truncated':False,'tree':[
            {'path':p,'type':'blob','size':len(raw),'sha':self.blob(raw)} for p,raw in self.files.items()]})
        def fetch(url):
            if '/git/trees/' in url:return tree,url
            return self.files[url.split('/'+self.source['revision']+'/',1)[1]],url
        with patch.object(C,'fetch',side_effect=fetch):return C.acquire(self.catalogue,self.archive)
    def refused(self,reason):
        with self.assertRaisesRegex(ValueError,'no actual educational content acquired'):self.acquire()
        record=A.read(self.archive/'acquisition.json')
        self.assertEqual(record['sources'],[]);self.assertEqual(record['trainingRows'],0)
        self.assertRegex(record['failures'][0]['reason'],reason)
        self.assertFalse((self.archive/'controlled-publisher/source.json').exists())
        # Preserve the entire failed bundle as evidence; never drop offending members.
        for p,raw in self.files.items():
            self.assertEqual((self.archive/'controlled-publisher/source'/p).read_bytes(),raw)
    def reseal_raw(self,path,raw):
        record=A.read(self.archive/'acquisition.json');source=record['sources'][0]
        full='controlled-publisher/source/'+path
        (self.archive/full).write_bytes(raw)
        entry=next(v for v in source['files'] if v['path']==full)
        entry.update(sha256=C.sha(raw),bytes=len(raw))
        treepath='controlled-publisher/publisher-tree.json';tree=A.read(self.archive/treepath)
        member=next(v for v in tree['tree'] if v['path']==path)
        member.update(sha=self.blob(raw),size=len(raw))
        C.write_json(self.archive/treepath,tree);data=(self.archive/treepath).read_bytes()
        next(v for v in source['files'] if v['path']==treepath).update(sha256=C.sha(data),bytes=len(data))
        C.write_json(self.archive/'controlled-publisher/source.json',source)
        C.write_json(self.archive/'acquisition.json',record)
    def test_matching_collection_inheritance_and_module_override(self):
        self.files['modules/m2/index.cnxml']=self.module('m2',
            '<md:license url="https://creativecommons.org/licenses/by/4.0">CC BY 4.0</md:license>')
        self.files['collections/book.collection.xml']=self.collection(('m1','m2'))
        self.files['collections/second.collection.xml']=self.collection(('m1',))
        self.assertTrue(self.acquire());source=C.verified_sources(self.archive)[0]
        rights=C.publisher_rights(source,self.archive)
        self.assertEqual(len(rights['collections']),2);self.assertEqual(len(rights['modules']),2)
        self.assertEqual(rights['modules']['m1']['declaredLicenseUrls'],[])
        self.assertEqual(len(rights['modules']['m1']['collectionPaths']),2)
        self.assertEqual(rights['modules']['m2']['declaredLicenseUrls'],
                         ['https://creativecommons.org/licenses/by/4.0'])
        prepared=self.root/'prepared';dataset=self.root/'dataset'
        C.prepare(self.archive,prepared,256);C.admit(self.archive,prepared,dataset)
        C.validate_admitted(self.archive,prepared,dataset)
        self.assertEqual(len(list(C.texts(source,self.archive))),2)
    def test_generic_by4_cannot_override_actual_nc_collection_declaration(self):
        self.files['collections/book.collection.xml']=self.collection(url='http://creativecommons.org/licenses/by-nc-sa/4.0/')
        self.refused('member license is not the expected CC BY 4.0')
    def test_mixed_bundle_refuses_whole_source(self):
        self.files['collections/second.collection.xml']=self.collection(url='https://creativecommons.org/licenses/by-nc-sa/4.0/')
        self.refused('member license is not the expected CC BY 4.0')
    def test_explicit_incompatible_module_override_refuses(self):
        self.files['modules/m1/index.cnxml']=self.module(declaration=
            '<md:license url="http://creativecommons.org/licenses/by-nc-sa/4.0/">NC-SA</md:license>')
        self.refused('member license is not the expected CC BY 4.0')
    def test_unknown_module_rights_refuse(self):
        self.files['modules/m1/index.cnxml']=self.module(declaration='<md:license>Unknown terms</md:license>')
        self.refused('member license is not the expected CC BY 4.0')
    def test_missing_collection_declaration_refuses(self):
        self.files['collections/book.collection.xml']=self.collection(declaration='')
        self.refused('collection license absent')
    def test_absent_collection_membership_refuses(self):
        del self.files['collections/book.collection.xml']
        self.refused('collection membership absent')
    def test_orphan_module_cannot_inherit_generic_license(self):
        self.files['modules/m2/index.cnxml']=self.module('m2')
        self.refused('orphan publisher module rights')
    def test_missing_collection_member_refuses(self):
        self.files['collections/book.collection.xml']=self.collection(('m1','missing'))
        self.refused('collection member missing')
    def test_module_identity_mismatch_refuses(self):
        self.files['modules/m1/index.cnxml']=self.module('other')
        self.refused('module identity differs')
    def test_collection_members_outside_content_are_not_silently_ignored(self):
        self.files['collections/book.collection.xml']=self.collection().replace(
            b'</collection>',b'<module document="unknown"/></collection>')
        self.refused('unsupported publisher collection membership')
    def test_supported_license_url_spellings(self):
        for i,url in enumerate(['http://creativecommons.org/licenses/by/4.0/',
                                'https://creativecommons.org/licenses/by/4.0/',
                                'http://creativecommons.org/licenses/by/4.0',
                                'https://creativecommons.org/licenses/by/4.0']):
            with self.subTest(url=url):
                self.archive=self.root/str(i)
                self.files['collections/book.collection.xml']=self.collection(url=url)
                self.assertTrue(self.acquire());C.verified_sources(self.archive)
    def test_unknown_or_lookalike_license_urls_refuse(self):
        for i,url in enumerate(['https://creativecommons.org/licenses/by/3.0/',
                                'https://creativecommons.org.evil/licenses/by/4.0/',
                                'https://creativecommons.org/licenses/by/4.0/?new=terms']):
            with self.subTest(url=url):
                self.archive=self.root/str(i)
                self.files['collections/book.collection.xml']=self.collection(url=url)
                self.refused('member license is not the expected CC BY 4.0')
    def test_license_outside_metadata_cannot_supply_or_override_rights(self):
        self.files['modules/m1/index.cnxml']=self.module().replace(b'<para>',
            b'<license url="http://creativecommons.org/licenses/by-nc-sa/4.0/"/><para>')
        self.refused('unsupported publisher rights declaration')
    def test_resealed_indexes_cannot_authorize_raw_nc_collection_at_any_consumer(self):
        self.acquire();prepared=self.root/'prepared';dataset=self.root/'dataset'
        C.prepare(self.archive,prepared,256);C.admit(self.archive,prepared,dataset)
        self.reseal_raw('collections/book.collection.xml',
                        self.collection(url='http://creativecommons.org/licenses/by-nc-sa/4.0/'))
        target=self.root/'new-prepared';new_dataset=self.root/'new-dataset'
        operations=[lambda:C.verified_sources(self.archive),lambda:C.prepare(self.archive,target,256),
                    lambda:C.admit(self.archive,prepared,new_dataset),
                    lambda:C.validate_admitted(self.archive,prepared,dataset),
                    lambda:C.acquire(self.catalogue,self.root/'reused',reuse=self.archive)]
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError,'member license is not the expected CC BY 4.0'):operation()
        self.assertFalse(target.exists());self.assertFalse(new_dataset.exists())
    def test_metadata_only_license_reseal_cannot_replace_raw_grant(self):
        self.acquire();record=A.read(self.archive/'acquisition.json');source=record['sources'][0]
        source['license']['evidencePaths']=['controlled-publisher/source/collections/book.collection.xml']
        C.write_json(self.archive/'controlled-publisher/source.json',source)
        C.write_json(self.archive/'acquisition.json',record)
        with self.assertRaisesRegex(ValueError,'publisher license metadata differs'):C.verified_sources(self.archive)

    def test_by_uri_cannot_override_restrictive_collection_text(self):
        declaration='<md:license url="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International</md:license>'
        self.files['collections/book.collection.xml']=self.collection(declaration=declaration)
        self.refused('declaration text is incompatible or ambiguous')

    def test_by_uri_cannot_override_restrictive_module_text(self):
        declaration='<md:license url="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International</md:license>'
        self.files['modules/m1/index.cnxml']=self.module(declaration=declaration)
        self.refused('declaration text is incompatible or ambiguous')

    def test_restrictive_unknown_and_conflicting_version_text_variants_refuse(self):
        variants=['CC BY-NC 4.0','CC BY-SA 4.0','CC BY-ND 4.0','Noncommercial use only',
                  'All rights reserved','Creative Commons Attribution License 3.0',
                  'Unknown licensing terms','CC BY 4.0 except commercial use',
                  'Creative Commons Attribution <md:em>NonCommercial</md:em> License']
        for i,text in enumerate(variants):
            for kind in ['collection','module']:
                with self.subTest(text=text,kind=kind):
                    self.archive=self.root/(str(i)+'-'+kind)
                    declaration='<md:license url="http://creativecommons.org/licenses/by/4.0/">'+text+'</md:license>'
                    self.files['collections/book.collection.xml']=self.collection()
                    self.files['modules/m1/index.cnxml']=self.module()
                    if kind=='collection':self.files['collections/book.collection.xml']=self.collection(declaration=declaration)
                    else:self.files['modules/m1/index.cnxml']=self.module(declaration=declaration)
                    self.refused('declaration text is incompatible or ambiguous')

    def test_actual_publisher_by_name_aliases_and_uri_only_declarations_are_preserved(self):
        aliases=['Creative Commons Attribution License','Creative Commons Attribution License 4.0',
                 'Creative Commons Attribution 4.0 International','CC BY 4.0','CC-BY-4.0','']
        for i,text in enumerate(aliases):
            with self.subTest(text=text):
                self.archive=self.root/str(i)
                declaration='<md:license url="http://creativecommons.org/licenses/by/4.0/">'+text+'</md:license>'
                self.files['collections/book.collection.xml']=self.collection(declaration=declaration)
                self.files['modules/m1/index.cnxml']=self.module(declaration=declaration)
                self.assertTrue(self.acquire());source=C.verified_sources(self.archive)[0]
                rights=C.publisher_rights(source,self.archive)
                self.assertEqual(rights['collections'][0]['declaredLicenseTexts'],[text])
                self.assertEqual(rights['modules']['m1']['declaredLicenseTexts'],[text])

    def resealed_text_refuses_all_consumers(self,kind,text='Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International'):
        self.acquire();prepared=self.root/'prepared';dataset=self.root/'dataset'
        C.prepare(self.archive,prepared,256);C.admit(self.archive,prepared,dataset)
        declaration='<md:license url="https://creativecommons.org/licenses/by/4.0/">'+text+'</md:license>'
        path='collections/book.collection.xml' if kind=='collection' else 'modules/m1/index.cnxml'
        raw=self.collection(declaration=declaration) if kind=='collection' else self.module(declaration=declaration)
        self.reseal_raw(path,raw)
        target=self.root/'new-prepared';new_dataset=self.root/'new-dataset'
        for operation in [lambda:C.verified_sources(self.archive),lambda:C.prepare(self.archive,target,256),
                          lambda:C.admit(self.archive,prepared,new_dataset),
                          lambda:C.validate_admitted(self.archive,prepared,dataset),
                          lambda:C.acquire(self.catalogue,self.root/'reused',reuse=self.archive)]:
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError,'declaration text is incompatible or ambiguous'):operation()
        self.assertFalse(target.exists());self.assertFalse(new_dataset.exists())

    def test_resealed_contradictory_collection_text_refuses_all_consumers(self):
        self.resealed_text_refuses_all_consumers('collection')

    def test_resealed_contradictory_module_text_refuses_all_consumers(self):
        self.resealed_text_refuses_all_consumers('module')

    def test_unknown_unicode_clauses_symbols_and_invisible_text_are_not_discarded(self):
        variants=['Creative Commons Attribution License 非商業利用のみ',
                  'Creative Commons Attribution License केवल गैर-वाणिज्यिक',
                  'Creative Commons Attribution License 🚫',
                  'Creative Commons Attribution License\u200b',
                  'Creative Commons Attribution License / restricted',
                  'Creative Commons Attribution License ©']
        for i,text in enumerate(variants):
            for kind in ['collection','module']:
                with self.subTest(text=text,kind=kind):
                    self.archive=self.root/(str(i)+'-'+kind)
                    declaration='<md:license url="http://creativecommons.org/licenses/by/4.0/">'+text+'</md:license>'
                    self.files['collections/book.collection.xml']=self.collection()
                    self.files['modules/m1/index.cnxml']=self.module()
                    if kind=='collection':self.files['collections/book.collection.xml']=self.collection(declaration=declaration)
                    else:self.files['modules/m1/index.cnxml']=self.module(declaration=declaration)
                    self.refused('declaration text is incompatible or ambiguous')

    def test_resealed_unicode_collection_clause_refuses_all_consumers(self):
        self.resealed_text_refuses_all_consumers('collection','Creative Commons Attribution License 非商業利用のみ')

    def test_resealed_unicode_module_clause_refuses_all_consumers(self):
        self.resealed_text_refuses_all_consumers('module','Creative Commons Attribution License 非商業利用のみ')


if __name__=='__main__':
    unittest.main()
