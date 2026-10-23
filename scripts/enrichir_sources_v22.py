#!/usr/bin/env python3
"""V22: enrichit le registre documentaire avec résumés RSS et diagnostics.
Un résumé RSS ou un index de scrutin N'EST PAS une preuve de position personnelle.
Aucune modification de boussole_2027_positions.json ni de manifest.json.
"""
from __future__ import annotations
import collections
import datetime as dt
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
import zipfile
from io import BytesIO
from urllib.parse import urlparse
import sys

ROOT=Path(__file__).resolve().parents[1]
AN_VOTES_URL='https://data.assemblee-nationale.fr/static/openData/repository/17/loi/scrutins/Scrutins.json.zip'
MAX_ZIP_BYTES=32_000_000
MAX_ZIP_ITEMS=25000
MAX_UNCOMPRESSED_ITEM=1_200_000


def read(path,default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def norm_text(value):
    return re.sub(r'\s+',' ',re.sub(r'<[^>]{0,300}>',' ',str(value or ''))).strip()

def index_zip(raw):
    """Inventory only. Votes are not mapped to questionnaire questions or political scores."""
    results=[]
    with zipfile.ZipFile(BytesIO(raw)) as z:
        allfiles=[x for x in z.infolist() if not x.is_dir() and x.filename.lower().endswith('.json')]
        if len(allfiles)>MAX_ZIP_ITEMS: raise ValueError('Archive avec trop de fichiers')
        for info in allfiles:
            if info.file_size>MAX_UNCOMPRESSED_ITEM: continue
            # Do not extract archive contents to the filesystem (ZIP-slip resistant).
            try:
                item=json.loads(z.read(info))
            except (ValueError,UnicodeDecodeError,RuntimeError,KeyError):
                continue
            obj=item.get('scrutin',item) if isinstance(item,dict) else {}
            if not isinstance(obj,dict): continue
            uid=str(obj.get('uid') or info.filename.rsplit('/',1)[-1].replace('.json',''))
            title=norm_text(obj.get('titre') or obj.get('libelle') or '')[:400]
            date=str(obj.get('dateScrutin') or '')[:30]
            results.append({'id':uid,'date':date,'intitule':title,'referenceArchive':AN_VOTES_URL,
                            'qualification':'Scrutin officiel non relié à une position de la Boussole'})
    return results

def fetch_archive(url=AN_VOTES_URL):
    if urlparse(url).scheme!='https' or urlparse(url).hostname!='data.assemblee-nationale.fr':
        raise ValueError('Domaine source non autorisé')
    req=urllib.request.Request(url,headers={'User-Agent':'Boussole2027/22 (inventaire de données ouvertes)'})
    with urllib.request.urlopen(req,timeout=35) as response:
        body=response.read(MAX_ZIP_BYTES+1)
    if len(body)>MAX_ZIP_BYTES: raise ValueError('Archive trop volumineuse; collecte refusée')
    return index_zip(body)

def run(root=ROOT, now=None, archive_reader=fetch_archive):
    now=now or dt.datetime.now(dt.timezone.utc)
    queue=read(root/'data/queue.json',{})
    register=read(root/'data/registre_preuves_v20.json',{})
    if not isinstance(queue,dict) or not isinstance(register.get('documents',[]),list):
        raise ValueError('Registre ou file documentaire invalide')
    docs=[]; diagnostics=collections.Counter(); from_rss=0
    for obj in register.get('documents',[]):
        if not isinstance(obj,dict): continue
        doc=dict(obj)
        entry=queue.get(str(doc.get('id')), {})
        excerpt=norm_text(entry.get('excerpt',''))[:1500] if isinstance(entry,dict) else ''
        doc['resumeRss']=excerpt
        doc['resumeRssDisponible']=bool(excerpt)
        doc['provenanceResume']='flux RSS non vérifié sur le document original' if excerpt else None
        doc['utilisableCommePreuvePolitique']=False
        # Avoid presenting a 404/403 as a valid text read.
        status=str(doc.get('motif') or 'non précisé')
        if doc.get('lecture') in ('html','pdf','texte_html'):
            diagnostics['Texte intégral lu']+=1
        else:
            diagnostics[status]+=1
            if excerpt: from_rss+=1
        docs.append(doc)
    total=len(docs)
    stats={'documentsSuivis':total,
           'documentsLus':sum(d.get('lecture') in ('html','pdf','texte_html') for d in docs),
           'documentsSansTexteAvecResumeRss':from_rss,
           'documentsSansTexteNiResume':sum(d.get('lecture') not in ('html','pdf','texte_html') and not d.get('resumeRssDisponible') for d in docs),
           'passagesCandidats':sum(len(d.get('passages') or []) for d in docs),
           'erreursParCause':dict(diagnostics)}
    inventory={'statut':'non demandé','scrutins':[],'erreur':None}
    if os.environ.get('BOUSSOLE_AN_VOTES','0')=='1':
        try:
            items=archive_reader()
            inventory={'statut':'archive lue','scrutins':items[-250:],'nombreScrutinsDansArchive':len(items),
                       'erreur':None,'source':AN_VOTES_URL}
        except Exception as ex:
            inventory={'statut':'échec sans modification de la base','scrutins':[],
                       'erreur':type(ex).__name__+': '+str(ex)[:150],'source':AN_VOTES_URL}
    result={'schemaVersion':22,'genereLe':now.isoformat(),
            'avertissement':'Résumé RSS et scrutin sont des signaux documentaires, pas des preuves suffisantes pour attribuer un soutien ou une opposition.',
            'documents':docs,'statistiques':stats,'inventaireAN':inventory,'modificationPositions':False}
    write(root/'data/diagnostic_v22.json',result)
    print('V22 diagnostic:',json.dumps(stats,ensure_ascii=False),'scrutins:',inventory['statut'])
    return result

if __name__=='__main__':run()
