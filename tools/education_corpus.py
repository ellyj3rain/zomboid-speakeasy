#!/usr/bin/env python3
"""Acquire immutable educational texts and prepare exact source-bound review data."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET
import zipfile

import decision_authoring as A
import cross_module_rows as J
import training_evidence as E

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / 'corpus/education/catalogue.json'
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024
EXTRACTION_VERSION = 3
STAGES = {'kindergarten','primary','middle-school','secondary','college'}
SUBJECTS = {'literacy','mathematics','physics','biology','chemistry','geography',
            'history','civics','social-science','economics','health','arts','practical-skills',
            'languages','literature'}

def source_id(value):
    A.require(isinstance(value,str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',value),
              'educational source id must be a safe directory component')
    return value

def html_from_zip(data):
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        entries=[v for v in package.infolist() if v.filename.lower().endswith(('.html','.htm'))]
        A.require(len(entries)==1 and entries[0].file_size<=MAX_SOURCE_BYTES,
                  'ambiguous or oversized publisher HTML book')
        return package.read(entries[0])

def sha(data):
    return hashlib.sha256(data).hexdigest()

def fetch(url):
    request = urllib.request.Request(url,headers={'User-Agent':'Speakeasy-Education-Source-Archive/1'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request,timeout=30) as response:
                data=response.read(MAX_DOWNLOAD_BYTES+1)
                A.require(len(data)<=MAX_DOWNLOAD_BYTES,'source download exceeds bound')
                return data,response.geturl()
        except urllib.error.HTTPError as error:
            if error.code==403 and url.startswith('https://api.github.com/') and shutil.which('gh'):
                # The authenticated publisher transport uses the existing local
                # GitHub session. Credentials never enter archive or tool output.
                result=subprocess.run(['gh','api',url],capture_output=True,timeout=60)
                A.require(result.returncode==0,'authenticated publisher request failed')
                A.require(len(result.stdout)<=MAX_DOWNLOAD_BYTES,'source download exceeds bound')
                return result.stdout,url
            if error.code not in (429,500,502,503,504) or attempt==2: raise
        except (TimeoutError,urllib.error.URLError):
            if attempt==2: raise

def write_json(path,value):
    path.write_bytes(A.encoded(value)+b'\n')

def local_path(root,name):
    path=(root/name).resolve()
    A.require(path.is_relative_to(root.resolve()),'source path escapes archive')
    return path

def validate_catalogue(value):
    A.require(value.get('schema')=='speakeasy-education-source-catalogue/1','unsupported educational catalogue')
    A.require(value.get('standing')=='candidate-sources','catalogue cannot approve source admission')
    sources=value.get('sources')
    A.require(isinstance(sources,list) and sources,'empty educational catalogue')
    ids=set()
    for source in sources:
        source_id(source.get('id'))
        A.require(source['id'] not in ids,'duplicate educational source');ids.add(source['id'])
        A.require(isinstance(source.get('stages'),list) and source['stages']
                  and set(source['stages'])<=STAGES,'unsupported educational stages')
        A.require(isinstance(source.get('subjects'),list) and source['subjects']
                  and set(source['subjects'])<=SUBJECTS,'unsupported educational subjects')
        if source.get('provider')=='gutenberg':
            A.require(type(source.get('bookId')) is int and source['bookId']>0,'invalid Gutenberg id')
            A.require(source.get('format','text') in {'text','html-archive'},'unsupported Gutenberg format')
        else:
            A.require(source.get('provider')=='openstax-github'
                      and re.fullmatch(r'openstax/[a-z0-9-]+',source.get('repository',''))
                      and re.fullmatch('[0-9a-f]{40}',source.get('revision','')),
                      'unsupported publisher or unpinned source revision')
    return sources

def publisher_rights(source,archive,files=None):
    """Reconstruct the existing CC BY edition grant from every archived member.

    A module can inherit its containing collection's grant, never the generic
    repository LICENSE alone. The full bundle must pass; no text is dropped.
    Returned membership evidence is derived from bytes, not index assertions.
    """
    files=source['files'] if files is None else files
    license_paths=[v['path'] for v in files if Path(v['path']).name.lower()
                   in {'license','license.txt','license.md'}]
    A.require(license_paths,'publisher license absent')
    for path in license_paths:
        terms=local_path(archive,path).read_text(encoding='utf-8')
        A.require(terms.splitlines() and terms.splitlines()[0].strip()=='Attribution 4.0 International',
                  'publisher license is not the expected CC BY 4.0')
    cn='{http://cnx.rice.edu/cnxml}';col='{http://cnx.rice.edu/collxml}'
    md='{http://cnx.rice.edu/mdml}'
    def grant(root,namespace,path,required):
        metadata=root.findall(namespace+'metadata')
        A.require(len(metadata)<=1,'ambiguous publisher metadata: '+path)
        declarations=metadata[0].findall('.//'+md+'license') if metadata else []
        # Other namespaces/locations cannot silently override a scoped grant.
        all_declarations=[v for v in root.iter() if v.tag.rsplit('}',1)[-1]=='license']
        A.require(all_declarations==declarations,'unsupported publisher rights declaration: '+path)
        A.require(declarations or not required,'publisher collection license absent: '+path)
        urls=[];texts=[]
        for declaration in declarations:
            url=declaration.get('url','');parts=urlsplit(url)
            A.require(parts.scheme in {'http','https'} and parts.netloc=='creativecommons.org'
                      and parts.path.rstrip('/')=='/licenses/by/4.0' and not parts.query and not parts.fragment,
                      'publisher member license is not the expected CC BY 4.0: '+path)
            text=''.join(declaration.itertext())
            # Strip only the actual supported name separators. Unknown letters,
            # symbols and clauses must survive whole-name comparison.
            label=re.sub(r'[ \t\r\n.\-]','',text.casefold())
            # Some actual publisher collections declare only the formal URI.
            # Preserve that empty display text; every present name must agree.
            A.require(not text.strip() or label in {
                'creativecommonsattributionlicense','creativecommonsattributionlicense40',
                'creativecommonsattribution40international','ccby40'},
                'publisher license declaration text is incompatible or ambiguous: '+path)
            urls.append(url)
            texts.append(text)
        return urls,texts
    modules={};collections=[]
    prefix=source['id']+'/source/modules/'
    for entry in files:
        path=entry['path']
        if not path.endswith('.cnxml'):continue
        A.require(path.startswith(prefix) and path.endswith('/index.cnxml'),
                  'unsupported publisher module membership: '+path)
        identity=path[len(prefix):-len('/index.cnxml')]
        A.require(re.fullmatch(r'[A-Za-z0-9_-]+',identity) and identity not in modules,
                  'ambiguous publisher module membership: '+path)
        root=ET.fromstring(local_path(archive,path).read_bytes())
        A.require(root.tag==cn+'document','unsupported publisher module: '+path)
        content_ids=root.findall(cn+'metadata/'+md+'content-id')
        A.require(len(content_ids)<=1 and (not content_ids or content_ids[0].text==identity),
                  'publisher module identity differs: '+path)
        urls,texts=grant(root,cn,path,False)
        modules[identity]={'path':path,'sha256':entry['sha256'],
                           'declaredLicenseUrls':urls,'declaredLicenseTexts':texts,'collectionPaths':[]}
    A.require(modules,'publisher has no educational modules')
    for entry in files:
        path=entry['path']
        if not path.endswith('.collection.xml'):continue
        root=ET.fromstring(local_path(archive,path).read_bytes())
        A.require(root.tag==col+'collection','unsupported publisher collection: '+path)
        urls,texts=grant(root,col,path,True)
        contents=root.findall(col+'content')
        A.require(len(contents)==1,'publisher collection membership absent or ambiguous: '+path)
        member_nodes=list(contents[0].iter(col+'module'))
        A.require([v for v in root.iter() if v.tag.rsplit('}',1)[-1]=='module']==member_nodes,
                  'unsupported publisher collection membership: '+path)
        members=[v.get('document') for v in member_nodes]
        A.require(members,'publisher collection membership absent: '+path)
        for identity in members:
            A.require(identity in modules,'publisher collection member missing: '+path)
            if path not in modules[identity]['collectionPaths']:
                modules[identity]['collectionPaths'].append(path)
        collections.append({'path':path,'sha256':entry['sha256'],
                            'declaredLicenseUrls':urls,'declaredLicenseTexts':texts,'moduleIds':members})
    A.require(collections,'publisher collection membership absent')
    for module in modules.values():
        A.require(module['collectionPaths'],'orphan publisher module rights: '+module['path'])
    return {'license':{'id':'CC-BY-4.0','evidencePaths':license_paths,
                      'attributionRequired':True,'publisher':source['repository']},
            'collections':collections,'modules':modules}

def acquire_one(source,root):
    directory=local_path(root,source_id(source['id']));directory.mkdir()
    files=[]
    def preserve(name,data,url):
        path=local_path(directory,name);path.parent.mkdir(parents=True,exist_ok=True)
        A.require(not path.exists(),'source bytes already exist')
        path.write_bytes(data)
        files.append({'path':str(path.relative_to(root)).replace('\\','/'),
                      'sha256':sha(data),'bytes':len(data),'url':url})
    result=dict(source)
    if source['provider']=='gutenberg':
        book=source['bookId']
        url=f'https://www.gutenberg.org/ebooks/{book}'
        metadata,resolved=fetch(url);preserve('publisher.html',metadata,resolved)
        page=metadata.decode('utf-8')
        A.require('Public domain in the USA' in page,'publisher does not establish US public-domain standing')
        formats=re.findall(r'href="([^"]+)"\s+type="([^"]+)"',page)
        choices=[(path,mime) for path,mime in formats if mime=='application/zip'] if source.get('format')=='html-archive' else [
            (path,mime) for path,mime in formats if mime.startswith('text/plain')]
        if not choices and source.get('format')!='html-archive':
            choices=[(path,mime) for path,mime in formats if mime=='application/prs.tex']
        A.require(choices,'publisher offers no supported educational text or TeX source')
        resource,mime=choices[0]
        source_url=urljoin(url,resource)
        A.require(source_url.startswith('https://www.gutenberg.org/'),'publisher source leaves approved host')
        text,resolved=fetch(source_url)
        if mime=='application/zip':
            preserve('publisher.zip',text,resolved)
            text=html_from_zip(text)
        decoded=text.decode('utf-8-sig')
        if mime.startswith('text/plain'):
            A.require(re.search(r'\*\*\* START OF (?:THE|THIS) PROJECT GUTENBERG',decoded,re.I),
                      'download is not an actual Gutenberg source text')
        elif mime=='application/prs.tex':
            A.require('Project Gutenberg' in decoded and '\\begin{document}' in decoded,
                      'download is not an actual published TeX textbook')
        else:
            A.require('PROJECT GUTENBERG' in decoded.upper(),'download is not a Gutenberg HTML book')
        preserve('source.tex' if mime=='application/prs.tex' else 'source.html' if mime=='application/zip'
                 else 'source.txt',text,resolved)
        result['license']={'id':'public-domain-US','evidencePath':files[0]['path'],
                           'termsIncludedInSource':True,'jurisdiction':'United States'}
        title=re.search(r'<title>(.*?)</title>',page,re.S)
        result['title']=re.sub(r'\s+',' ',title[1]).strip() if title else source['id']
        result['sourceVersion']=sha(text)
    else:
        repo,revision=source['repository'],source['revision']
        tree,url=fetch(f'https://api.github.com/repos/{repo}/git/trees/{revision}?recursive=1')
        preserve('publisher-tree.json',tree,url)
        records=json.loads(tree)
        A.require(records.get('truncated') is False,'publisher tree is incomplete')
        A.require(records.get('sha')==revision,'publisher tree does not match pinned revision')
        entries=[v for v in records['tree'] if v.get('type')=='blob'
                 and (v['path'].endswith('.cnxml') or v['path'].endswith('.collection.xml')
                      or Path(v['path']).name.lower() in {'license','license.txt','license.md','metadata.json'})]
        A.require(entries and any(v['path'].endswith('.cnxml') for v in entries),'publisher has no educational modules')
        A.require(sum(v.get('size',0) for v in entries)<=MAX_SOURCE_BYTES,'educational source exceeds bound')
        def download(entry):
            data,url=fetch(f'https://raw.githubusercontent.com/{repo}/{revision}/{entry["path"]}')
            A.require(len(data)==entry['size'],'publisher source byte size differs')
            actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            A.require(actual==entry['sha'],'publisher Git blob identity differs')
            return entry,data,url
        with ThreadPoolExecutor(max_workers=4) as pool:
            for entry,data,url in pool.map(download,entries):
                preserve('source/'+entry['path'],data,url)
        result['license']=publisher_rights(source,root,files)['license']
        result['title']=repo.split('/')[1]
        result['sourceVersion']=revision
    result['files']=files
    result['standing']='unreviewed-educational-source'
    result['personalAcquisition']='not-established'
    result['consentResolution']='unreviewed'
    result['textBytes']=sum(v['bytes'] for v in files if v['path'].endswith(('.txt','.tex','.cnxml','/source.html')))
    write_json(directory/'source.json',result)
    return result

def acquire(catalogue,output,only=None,reuse=None):
    J.protected_artifacts()
    output=output.resolve()
    sources=validate_catalogue(catalogue)
    if only:
        A.require(set(only)<=set(v['id'] for v in sources),'unknown selected source')
        sources=[v for v in sources if v['id'] in only]
    A.require(not output.exists(),'educational archive already exists; preserve prior version')
    output.mkdir(parents=True)
    write_json(output/'catalogue.json',catalogue)
    prior={v['id']:v for v in verified_sources(reuse)} if reuse else {}
    completed,failed=[],[]
    for source in sources:
        try:
            retained=prior.get(source['id'])
            if retained and all(retained.get(key)==value for key,value in source.items()):
                directory=local_path(output,source_id(source['id']));directory.mkdir()
                for entry in retained['files']:
                    target=local_path(output,entry['path']);target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(local_path(reuse,entry['path']).read_bytes())
                record=retained;write_json(directory/'source.json',record)
            else:
                record=acquire_one(source,output)
            completed.append(record)
            print(f"ACQUIRED {source['id']}: {record['textBytes']} source bytes",flush=True)
        except (OSError,UnicodeError,ValueError,ET.ParseError) as error:
            failed.append({'id':source['id'],'reason':str(error)})
            print(f"UNAVAILABLE {source['id']}: {error}",flush=True)
        write_json(output/'acquisition.json',{'schema':'speakeasy-educational-acquisition/1',
            'acquiredAtUtc':datetime.now(timezone.utc).isoformat(),'catalogueSha256':A.digest(catalogue),
            'sources':completed,'failures':failed,'trainingRows':0,'datasetAdmission':'unreviewed'})
    A.require(completed,'no actual educational content acquired')
    return not failed

def verified_sources(archive,*,allow_legacy=False):
    archive=archive.resolve()
    record=A.read(archive/'acquisition.json')
    A.require(record.get('schema')=='speakeasy-educational-acquisition/1','unsupported source archive')
    A.require(record.get('datasetAdmission')=='unreviewed' and record.get('trainingRows')==0,
              'acquisition cannot supply training approval')
    sources=record.get('sources');A.require(isinstance(sources,list) and sources,'empty source archive')
    ids=set()
    catalogue_path=archive/'catalogue.json'
    A.require(catalogue_path.is_file() or allow_legacy,
              'archive catalogue snapshot missing; legacy label binding unavailable')
    catalogue=None
    if catalogue_path.exists():
        catalogue=A.read(catalogue_path)
        A.require(A.digest(catalogue)==record['catalogueSha256'],'archive catalogue identity differs')
        catalogue={s['id']:s for s in validate_catalogue(catalogue)}
    for source in sources:
        identity=source_id(source.get('id'))
        A.require(identity not in ids,'duplicate archive source');ids.add(identity)
        A.require(A.read(local_path(archive,identity+'/source.json'))==source,
                  'archive source metadata differs from preserved source manifest')
        validate_catalogue({'schema':'speakeasy-education-source-catalogue/1',
                            'standing':'candidate-sources','sources':[source]})
        if catalogue is not None:
            A.require(identity in catalogue and all(source.get(k)==v for k,v in catalogue[identity].items()),
                      'source metadata differs from archived catalogue')
        A.require(source.get('standing')=='unreviewed-educational-source','source standing differs')
        A.require(source.get('personalAcquisition')=='not-established'
                  and source.get('consentResolution')=='unreviewed','source acquisition standing differs')
        files=source.get('files')
        A.require(isinstance(files,list) and files,'empty source file inventory')
        paths=set()
        for entry in source['files']:
            A.require(isinstance(entry.get('path'),str) and entry['path'].startswith(identity+'/')
                      and entry['path'] not in paths,'source file inventory differs');paths.add(entry['path'])
            data=local_path(archive,entry['path']).read_bytes()
            A.require(sha(data)==entry['sha256'] and len(data)==entry['bytes'],'protected educational source changed')
        if source['provider']=='gutenberg':
            evidence=identity+'/publisher.html'
            A.require(evidence in paths,'publisher rights evidence absent')
            page=local_path(archive,evidence).read_text(encoding='utf-8')
            A.require('Public domain in the USA' in page,'publisher public-domain evidence differs')
            bodies=[entry for entry in files if entry['path'] in (identity+'/source.txt',identity+'/source.tex',identity+'/source.html')]
            A.require(len(bodies)==1,'Gutenberg source body inventory differs')
            if source.get('format')=='html-archive':
                zip_path=identity+'/publisher.zip'
                A.require(zip_path in paths and bodies[0]['path']==identity+'/source.html',
                          'publisher HTML archive inventory differs')
                A.require(html_from_zip(local_path(archive,zip_path).read_bytes())==
                          local_path(archive,bodies[0]['path']).read_bytes(),
                          'derived HTML differs from preserved publisher archive')
            else:
                A.require(bodies[0]['path']!=identity+'/source.html','source HTML format differs')
            A.require(source['sourceVersion']==bodies[0]['sha256'],'Gutenberg source version differs')
            expected={'id':'public-domain-US','jurisdiction':'United States',
                      'evidencePath':evidence,'termsIncludedInSource':True}
            A.require(source['license']==expected,'Gutenberg license metadata differs')
            publisher=next(entry for entry in files if entry['path']==evidence)
            A.require(publisher['url'].rstrip('/')==f"https://www.gutenberg.org/ebooks/{source['bookId']}",
                      'Gutenberg publisher identity differs')
        else:
            tree_path=identity+'/publisher-tree.json'
            A.require(tree_path in paths,'publisher tree absent')
            tree=A.read(local_path(archive,tree_path))
            A.require(tree.get('truncated') is False and tree.get('sha')==source['revision']
                      and source['sourceVersion']==source['revision'],'publisher version identity differs')
            entries=[v for v in tree['tree'] if v.get('type')=='blob'
                     and (v['path'].endswith('.cnxml') or v['path'].endswith('.collection.xml')
                          or Path(v['path']).name.lower() in {'license','license.txt','license.md','metadata.json'})]
            expected_paths={identity+'/source/'+v['path'] for v in entries}|{tree_path}
            A.require(paths==expected_paths,'publisher text inventory differs')
            for entry in entries:
                data=local_path(archive,identity+'/source/'+entry['path']).read_bytes()
                digest=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
                A.require(len(data)==entry['size'] and digest==entry['sha'],'publisher Git source identity differs')
            A.require(source['license']==publisher_rights(source,archive)['license'],
                      'publisher license metadata differs')
    return sources

class BookHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style'}:self.skip+=1
        elif not self.skip:
            if tag in {'p','div','br','h1','h2','h3','li','tr'}:self.parts.append('\n')
            if tag=='img':self.parts.append('[Figure: '+dict(attrs).get('alt','unavailable')+']')
    def handle_endtag(self,tag):
        if tag in {'script','style'}:self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)

def texts(source,archive):
    for entry in source['files']:
        path=local_path(archive,entry['path'])
        if path.suffix=='.txt' and path.name=='source.txt':
            text=path.read_text(encoding='utf-8-sig')
            start=re.search(r'\*\*\* START OF (?:THE|THIS) PROJECT GUTENBERG.*?\*\*\*',text,re.I)
            end=re.search(r'\*\*\* END OF (?:THE|THIS) PROJECT GUTENBERG',text,re.I)
            A.require(start and end and start.end()<end.start(),'missing source text boundaries')
            yield entry,text[start.end():end.start()].strip(),{'format':'plain-text','figures':'not-in-text-format'}
        elif path.suffix=='.cnxml':
            root=ET.fromstring(path.read_bytes())
            content=root.find('{http://cnx.rice.edu/cnxml}content')
            A.require(content is not None,'educational module content missing')
            # Serialized markup retains mathematics, exercise/solution structure,
            # attribution and figure references; unseen images stay unavailable.
            text=ET.tostring(content,encoding='unicode')
            yield entry,text,{'format':'cnxml','figures':'references-preserved-images-not-acquired'}
        elif path.suffix=='.tex' and path.name=='source.tex':
            text=path.read_text(encoding='utf-8-sig')
            start=text.find(r'\begin{document}');end=text.find(r'\end{document}',start)
            A.require(start>=0 and end>start,'missing TeX document boundaries')
            # Preserve the full raw export separately. Training candidates use
            # the book body, excluding preamble, license and appended SyncTeX.
            yield entry,text[start+len(r'\begin{document}'):end].strip(),{
                'format':'tex-source','figures':'references-preserved-images-not-acquired'}
        elif path.suffix=='.html' and path.name=='source.html':
            text=path.read_text(encoding='utf-8-sig')
            start=re.search(r'\*\*\* START OF (?:THE|THIS) PROJECT GUTENBERG.*?\*\*\*',text,re.I|re.S)
            end=re.search(r'\*\*\* END OF (?:THE|THIS) PROJECT GUTENBERG',text,re.I)
            A.require(start and end and start.end()<end.start(),'missing HTML book boundaries')
            parser=BookHTML();parser.feed(text[start.end():end.start()])
            yield entry,''.join(parser.parts).strip(),{'format':'html-text-with-figure-references',
                'figures':'publisher-archive-preserved-not-projected'}

def candidate_rows(sources,archive,chunk_chars):
    rows=[]
    for source in sources:
        for entry,text,coverage in texts(source,archive):
            for start in range(0,len(text),chunk_chars):
                excerpt=text[start:start+chunk_chars]
                if not excerpt.strip(): continue
                row={'schema':'speakeasy-educational-text/1','sourceId':source['id'],
                     'sourceVersion':source['sourceVersion'],'sourcePath':entry['path'],
                     'sourceSha256':entry['sha256'],'extractionSha256':sha(text.encode()),
                     'startCharacter':start,'endCharacter':start+len(excerpt),
                     'text':excerpt,'stages':source['stages'],'subjects':source['subjects'],
                     'license':source['license'],'coverage':coverage,
                     'objective':'shared-base-next-token','standing':'unreviewed',
                     'currentWorldAuthority':False,'personalAcquisitionAuthority':False}
                row['contentSha256']=A.digest(row);rows.append(row)
    A.require(rows,'no educational text extracted')
    return rows

def review_proposal(sources,archive,data,rows,chunk_chars):
    proposal={'schema':'speakeasy-educational-source-review/1',
              'extractionVersion':EXTRACTION_VERSION,'chunkCharacters':chunk_chars,
              'sourceArchiveSha256':sha((archive/'acquisition.json').read_bytes()),
              'candidateTextsSha256':sha(data),'candidateTexts':len(rows),
              'actualTextCharacters':sum(len(v['text']) for v in rows),
              'sources':[{'id':s['id'],'title':s['title'],'version':s['sourceVersion'],
                          'license':s['license'],'stages':s['stages'],'subjects':s['subjects']} for s in sources],
              'task':'shared-cognitive-base','scope':'source-content-and-training-admission',
              'reviewRequirements':['source-quality','source-license','author-consent-resolution',
                                    'dated-factual-content','historical-bias','missing-figures'],
              'personKnowledge':'Requires separate person-owned acquisition and retention evidence',
              'policyAuthority':False,'datasetAdmission':'unreviewed','trainingRows':0}
    proposal['contentSha256']=A.digest(proposal)
    return proposal

def prepare(archive,output,chunk_chars=4096):
    J.protected_artifacts()
    archive,output=archive.resolve(),output.resolve()
    A.require(type(chunk_chars) is int and 256<=chunk_chars<=16384,'invalid source chunk bound')
    sources=verified_sources(archive)
    A.require(not output.exists(),'educational preparation already exists')
    rows=candidate_rows(sources,archive,chunk_chars)
    data=b''.join(A.encoded(v)+b'\n' for v in rows)
    proposal=review_proposal(sources,archive,data,rows,chunk_chars)
    output.mkdir(parents=True)
    (output/'candidate-texts.jsonl').write_bytes(data)
    write_json(output/'review-proposal.json',proposal)
    print(f"PREPARED {len(sources)} educational sources, {len(rows)} candidate chunks, "
          f"{proposal['actualTextCharacters']} source characters; zero admitted training rows")
    return proposal

def validated_preparation(archive,prepared):
    archive,prepared=archive.resolve(),prepared.resolve()
    J.protected_artifacts();sources=verified_sources(archive)
    proposal=A.read(prepared/'review-proposal.json')
    body=dict(proposal);declared=body.pop('contentSha256',None)
    A.require(declared==A.digest(body),'review proposal hash differs')
    A.require(proposal['sourceArchiveSha256']==sha((archive/'acquisition.json').read_bytes()),'review archive differs')
    data=(prepared/'candidate-texts.jsonl').read_bytes()
    A.require(sha(data)==proposal['candidateTextsSha256'],'reviewed educational text differs')
    chunk_chars=proposal.get('chunkCharacters')
    A.require(proposal.get('extractionVersion')==EXTRACTION_VERSION and type(chunk_chars) is int
              and 256<=chunk_chars<=16384,'unsupported reviewed extraction')
    rows=candidate_rows(sources,archive,chunk_chars)
    expected_data=b''.join(A.encoded(v)+b'\n' for v in rows)
    A.require(data==expected_data,'reviewed rows do not derive from preserved educational sources')
    A.require(proposal==review_proposal(sources,archive,expected_data,rows,chunk_chars),
              'educational review metadata differs from reconstructed source evidence')
    return proposal,data

def admission_manifest(proposal,data,approval_hash):
    return {'schema':'speakeasy-educational-training-dataset/1','task':'shared-cognitive-base',
            'objective':'shared-base-next-token','sourceReviewSha256':proposal['contentSha256'],
            'approvalReceiptSha256':approval_hash,'textsSha256':sha(data),
            'trainingRows':proposal['candidateTexts'],'policyAuthority':False,
            'currentWorldAuthority':False,'personalAcquisitionAuthority':False}

def automatic_evaluation(proposal,data):
    """Record source/data checks; learning grades belong to learner assessments."""
    value={'schema':'speakeasy-educational-source-evaluation/1',
           'sourceReviewSha256':proposal['contentSha256'],
           'sourceArchiveSha256':proposal['sourceArchiveSha256'],
           'textsSha256':sha(data),'sources':len(proposal['sources']),
           'passages':proposal['candidateTexts'],'textCharacters':proposal['actualTextCharacters'],
           'checks':{'publisherProvenance':'passed','editionAndRightsBinding':'passed',
                     'sourceByteIntegrity':'passed','extractionReconstruction':'passed',
                     'passageAndMetadataReconstruction':'passed','protectedSources':'passed'},
           'status':'eligible-prerequisite-pretraining-material',
           'evaluationKind':'source-data-integrity','learnerGrade':None,
           'personalRetentionAuthority':False,'currentWorldAuthority':False,
           'limits':['source-checks-do-not-measure-learning',
                     'historical-person-exposure-remains-dated',
                     'unprojected-figures-and-unanswered-exercises-remain-coverage-limits']}
    value['contentSha256']=A.digest(value)
    return value

def automatic_manifest(proposal,data,evaluation):
    value=admission_manifest(proposal,data,None)
    value.update(schema='speakeasy-educational-training-dataset/2',
                 sourceAdmissionKind='automated-prerequisite-material',
                 evaluationReceiptSha256=evaluation['contentSha256'])
    return value

def validate_admitted(archive,prepared,dataset,store=None):
    """Revalidate source derivation and the saved admission receipt before training use."""
    proposal,data=validated_preparation(archive,prepared)
    manifest=A.read(dataset.resolve()/'manifest.json')
    if manifest.get('sourceAdmissionKind')=='automated-prerequisite-material':
        evaluation=automatic_evaluation(proposal,data)
        A.require(A.read(dataset.resolve()/'evaluation.json')==evaluation,'automated source evaluation differs')
        expected=automatic_manifest(proposal,data,evaluation)
    else:
        approval=manifest.get('approvalReceiptSha256')
        (store or E.Store()).decision(approval,proposal['contentSha256'],status='approved')
        expected=admission_manifest(proposal,data,approval)
    A.require(manifest==expected,'educational admission manifest differs')
    A.require((dataset.resolve()/'texts.jsonl').read_bytes()==data,'admitted educational texts differ')
    return manifest

def admit(archive,prepared,output,approval_hash=None,store=None):
    output=output.resolve()
    proposal,data=validated_preparation(archive,prepared)
    evaluation=None
    if approval_hash is not None:
        (store or E.Store()).decision(approval_hash,proposal['contentSha256'],status='approved')
        manifest=admission_manifest(proposal,data,approval_hash)
    else:
        evaluation=automatic_evaluation(proposal,data)
        manifest=automatic_manifest(proposal,data,evaluation)
    A.require(not output.exists(),'admitted educational dataset already exists')
    output.mkdir(parents=True)
    (output/'texts.jsonl').write_bytes(data)
    if evaluation is not None: write_json(output/'evaluation.json',evaluation)
    write_json(output/'manifest.json',manifest)
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['acquire','prepare','admit','verify'])
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--catalogue',type=Path,default=CATALOGUE)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--prepared',type=Path)
    parser.add_argument('--approval-sha256')
    parser.add_argument('--source',action='append')
    parser.add_argument('--reuse',type=Path)
    args=parser.parse_args()
    try:
        if args.action=='acquire': return 0 if acquire(A.read(args.catalogue),args.archive,args.source,args.reuse) else 1
        if args.action=='verify':
            print(f'VERIFIED {len(verified_sources(args.archive))} immutable educational sources');return 0
        A.require(args.output is not None,'output directory required')
        if args.action=='prepare': prepare(args.archive,args.output)
        else:
            A.require(args.prepared is not None,'exact prepared text required')
            admit(args.archive,args.prepared,args.output,args.approval_sha256)
        return 0
    except (OSError,ValueError,ET.ParseError) as error:
        print('FAULT: '+str(error));return 1

if __name__=='__main__':
    raise SystemExit(main())
