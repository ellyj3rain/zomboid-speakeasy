"""Educational acquisition and training admission refuse missing source authority."""
import json
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

if __name__=='__main__':
    unittest.main()
