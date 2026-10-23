#!/usr/bin/env python3
"""V21: HTML/PDF extraction with bounded retries and source-level diagnostics.
No political scores are automatically inferred or changed.
"""
import datetime as dt
from io import BytesIO
import os
import re
from pathlib import Path
import sys
from urllib.request import Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extraire_declarations as v20

ROOT = Path(__file__).resolve().parents[1]
MAX_DOCS = max(0, min(int(os.getenv('BOUSSOLE_MAX_DOCS','18')), 40))
MAX_BYTES = 5_000_000
PDF_PAGES = 12
RETRY_AFTER_HOURS = 24
MAX_ATTEMPTS = 3

def extract_pdf(raw):
    try:
        from pypdf import PdfReader
    except ImportError:
        return None, 'Dépendance pypdf absente (voir workflow V21)'
    try:
        reader = PdfReader(BytesIO(raw), strict=False)
        if reader.is_encrypted: return None, 'PDF protégé'
        pages = []
        for page in reader.pages[:PDF_PAGES]:
            pages.append(page.extract_text(extraction_mode='plain') or '')
        text = re.sub(r'\s+', ' ', '\n'.join(pages)).strip()[:v20.MAX_TEXT]
        if len(text) < 100:
            return None, 'PDF sans texte exploitable (numérisation ou contenu trop court)'
        return text, None
    except Exception as e:
        return None, 'Lecture PDF impossible : '+type(e).__name__

def retrieve(url):
    if not v20.safe_url(url): return None, 'Adresse refusée', 'refuse'
    try:
        req = Request(url, headers={'User-Agent':'Boussole2027-veille/1.1 (analyse documentaire publique)', 'Accept':'text/html,application/xhtml+xml,application/pdf'})
        with build_opener(v20.SafeRedirects()).open(req, timeout=15) as res:
            content_type = res.headers.get('Content-Type','').lower()
            raw = res.read(MAX_BYTES+1)
            if len(raw) > MAX_BYTES: return None, 'Document trop volumineux (> 5 Mo)', 'limite'
            is_pdf = ('application/pdf' in content_type or raw[:5] == b'%PDF-')
            if is_pdf:
                text, error = extract_pdf(raw)
                return text, error, 'pdf' if text else 'indisponible'
            if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
                return None, 'Format non géré : '+content_type[:80], 'non_gere'
            charset = res.headers.get_content_charset() or 'utf-8'
            parser = v20.TextExtractor()
            parser.feed(raw.decode(charset, errors='replace'))
            text = parser.result()
            return (text, None, 'html') if len(text)>100 else (None,'Texte HTML insuffisant','indisponible')
    except Exception as e:
        return None, 'Accès impossible : '+type(e).__name__, 'indisponible'

def timestamp(value):
    try:
        return dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except (ValueError,TypeError):
        return None

def due(previous, now):
    if not previous: return True
    if previous.get('lecture') in ('html','pdf','texte_html'): return False
    # Legacy V20 failures have no attempt counter: retry them during migration.
    if 'tentatives' not in previous: return True
    attempts = int(previous.get('tentatives',1))
    if attempts >= MAX_ATTEMPTS: return False
    last = timestamp(previous.get('analyseLe'))
    return not last or (now-last).total_seconds() >= RETRY_AFTER_HOURS*3600

def run(root=ROOT, retriever=retrieve, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    base=v20.read(root/'boussole_2027_positions.json', {})
    queue=v20.read(root/'data/queue.json', {})
    old=v20.read(root/'data/registre_preuves_v20.json', {})
    if not isinstance(queue,dict) or not isinstance(base.get('positions'),dict) or not isinstance(base.get('affirmations'),list):
        raise ValueError('Base ou file documentaire invalide')
    history={str(x['id']):x for x in old.get('documents',[]) if isinstance(x,dict) and x.get('id')}
    sorted_items = sorted(((str(v.get('id') or k),v) for k,v in queue.items() if isinstance(v,dict)),key=lambda pair:str(pair[1].get('sourcePublishedAt') or ''),reverse=True)
    selection = [(k,v) for k,v in sorted_items if due(history.get(k), now)][:MAX_DOCS]
    for identifier,item in selection:
        prior=history.get(identifier,{})
        url=str(item.get('url') or '')
        text,error,kind=retriever(url)
        proposals=v20.extract_proposals(text,base) if text else []
        history[identifier]={
          'id':identifier,'titre':item.get('title',''),'url':url,
          'publication':item.get('sourcePublishedAt'),'analyseLe':now.isoformat(),
          'lecture':kind if text else 'indisponible', 'formatDetecte':kind,
          'motif':error,'nombreCaracteres':len(text) if text else 0,
          'tentatives':int(prior.get('tentatives',0))+1,
          'passages':proposals,'modificationPositions':False
        }
    documents=sorted(history.values(),key=lambda d:str(d.get('publication') or ''),reverse=True)[:1500]
    formats={k:sum(d.get('lecture')==k for d in documents) for k in ('html','pdf','texte_html','indisponible')}
    failed_reasons={}
    for doc in documents:
        if doc.get('lecture')=='indisponible':
            reason=doc.get('motif') or 'Inconnu'
            failed_reasons[reason]=failed_reasons.get(reason,0)+1
    stats={'documents':len(documents),'textesLus':len(documents)-formats['indisponible'],
           'pdfLus':formats['pdf'],'htmlLus':formats['html']+formats['texte_html'],
           'passagesCandidats':sum(len(d.get('passages',[])) for d in documents),
           'nouveauxExamines':len(selection),'echecsParCause':failed_reasons}
    record={'schemaVersion':2,'generatedAt':now.isoformat(),
        'notice':'Extraction documentaire et passage candidat uniquement. Aucune note politique créée automatiquement.',
        'documents':documents,'statistiques':stats,'publicationAutomatiquePositions':False}
    v20.write(root/'data/registre_preuves_v20.json',record)
    print('V21:',stats, '; positions inchangées')
    return record

if __name__ == '__main__': run()
