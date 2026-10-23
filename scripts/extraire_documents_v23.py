#!/usr/bin/env python3
"""V23: récupérateur prudent : diagnostics explicites, HTTPS parlementaire, reprises ciblées.
Ne modifie jamais les positions politiques. Compatible avec la file et le registre V21/V22.
"""
from __future__ import annotations
import datetime as dt
import ipaddress
import os
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import extraire_documents_v21 as previous
import extraire_declarations as v20

ROOT=Path(__file__).resolve().parents[1]
# HTTP -> HTTPS upgrade ONLY for verified official hostnames, never for arbitrary sources.
OFFICIAL_HOSTS={'www.senat.fr','senat.fr','www.assemblee-nationale.fr',
 'assemblee-nationale.fr','data.assemblee-nationale.fr'}
MAX_DOCS=max(0,min(int(os.getenv('BOUSSOLE_MAX_DOCS','18')),40))
MAX_BYTES=previous.MAX_BYTES
MAX_ATTEMPTS=3
RETRY_AFTER_HOURS=24

def normalize_url(value):
    """Return canonical URL or explicit refusal; no implicit external fetch."""
    try:
        p=urlsplit(str(value or '').strip())
        host=(p.hostname or '').lower().rstrip('.')
        if not host or p.username or p.password or p.port not in (None,80,443):
            return None,'url_invalide'
        if p.scheme not in ('http','https'):
            return None,'protocole_non_autorise'
        if p.scheme=='http' and host not in OFFICIAL_HOSTS:
            return None,'http_non_autorise'
        if p.scheme=='http' and p.port not in (None,80):
            return None,'port_non_autorise'
        if p.scheme=='https' and p.port not in (None,443):
            return None,'port_non_autorise'
        result=urlunsplit(('https',host,p.path or '/',p.query,''))
        return result, ('http_officiel_converti_https' if p.scheme=='http' else None)
    except (ValueError,TypeError):
        return None,'url_invalide'

def validate_destination(url,resolver=None):
    """Only publicly routable IPv4/IPv6 destinations; DNS checks before every redirect."""
    normalized,reason=normalize_url(url)
    if not normalized: return False,reason
    host=urlsplit(normalized).hostname
    if host=='localhost' or host.endswith(('.localhost','.local','.internal','.test')):
        return False,'hote_local_interdit'
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*\.[a-z]{2,}',host):
        return False,'nom_hote_invalide'
    try:
        lookup=resolver or socket.getaddrinfo
        addresses=lookup(host,443,type=socket.SOCK_STREAM)
        if not addresses:return False,'dns_sans_adresse'
        if not all(ipaddress.ip_address(rec[4][0]).is_global for rec in addresses):
            return False,'dns_adresse_non_publique'
    except (OSError,ValueError,IndexError,KeyError):
        return False,'dns_echec'
    return True,reason

class CheckedRedirects(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        canonical,_=normalize_url(newurl)
        allowed,why=validate_destination(canonical) if canonical else (False,'redirection_'+_)
        if not allowed:raise ValueError('redirection_'+str(why))
        return super().redirect_request(req,fp,code,msg,headers,canonical)

def retrieve(url):
    canonical,conversion=normalize_url(url)
    if not canonical:return None,conversion,'refuse',None
    allowed,reason=validate_destination(canonical)
    if not allowed:return None,reason,'refuse',canonical
    try:
        req=Request(canonical,headers={'User-Agent':'Boussole2027/23 (veille parlementaire publique)',
                 'Accept':'text/html,application/xhtml+xml,application/pdf'})
        with build_opener(CheckedRedirects()).open(req,timeout=15) as response:
            mime=response.headers.get('Content-Type','').lower()
            raw=response.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES:return None,'document_trop_volumineux','limite',canonical
            is_pdf=('application/pdf' in mime or raw.startswith(b'%PDF-'))
            if is_pdf:
                text,error=previous.extract_pdf(raw)
                return text,(error or conversion),'pdf' if text else 'indisponible',canonical
            if 'text/html' not in mime and 'application/xhtml+xml' not in mime:
                return None,'mime_non_pris_en_charge:'+mime[:64],'non_gere',canonical
            charset=response.headers.get_content_charset() or 'utf-8'
            parser=v20.TextExtractor()
            parser.feed(raw.decode(charset,errors='replace'))
            content=parser.result()
            if len(content)<100:return None,'texte_html_insuffisant','indisponible',canonical
            return content,conversion,'html',canonical
    except HTTPError as error:
        return None,'http_'+str(error.code),'indisponible',canonical
    except URLError as error:
        return None,'reseau_'+type(error.reason).__name__,'indisponible',canonical
    except ValueError as error:
        return None,str(error)[:100],'refuse',canonical
    except (TimeoutError,OSError) as error:
        return None,'reseau_'+type(error).__name__,'indisponible',canonical
    except Exception as error:
        return None,'lecture_'+type(error).__name__,'indisponible',canonical

def due(previous,now):
    if not previous:return True
    if previous.get('lecture') in ('html','pdf','texte_html'):return False
    prior_reason=str(previous.get('motif') or '')
    # One migration retry for older generic refusals; don't infinitely retry.
    if prior_reason=='Adresse refusée' and previous.get('versionDiagnostic')!=23:return True
    if 'tentatives' not in previous:return True
    if int(previous.get('tentatives',0))>=MAX_ATTEMPTS:return False
    stamp=__import__("extraire_documents_v21").timestamp(previous.get('analyseLe'))
    return stamp is None or (now-stamp).total_seconds()>=RETRY_AFTER_HOURS*3600

def run(root=ROOT,retriever=retrieve,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    base=v20.read(root/'boussole_2027_positions.json',{})
    queue=v20.read(root/'data/queue.json',{})
    old=v20.read(root/'data/registre_preuves_v20.json',{})
    if not isinstance(queue,dict) or not isinstance(base.get('positions'),dict) or not isinstance(base.get('affirmations'),list):
        raise ValueError('Base ou file de veille invalide')
    history={str(d['id']):d for d in old.get('documents',[]) if isinstance(d,dict) and d.get('id')}
    entries=sorted(((str(v.get('id') or k),v) for k,v in queue.items() if isinstance(v,dict)),
                   key=lambda row:str(row[1].get('sourcePublishedAt') or ''),reverse=True)
    selected=[(uid,item) for uid,item in entries if due(history.get(uid),now)][:MAX_DOCS]
    for uid,item in selected:
        prior=history.get(uid,{})
        text,error,kind,canonical=retriever(str(item.get('url') or ''))
        passages=v20.extract_proposals(text,base) if text else []
        history[uid]={'id':uid,'titre':item.get('title',''),'url':item.get('url',''),
          'urlEffective':canonical,'publication':item.get('sourcePublishedAt'),
          'analyseLe':now.isoformat(),'lecture':kind if text else 'indisponible',
          'formatDetecte':kind,'motif':error,'versionDiagnostic':23,
          'nombreCaracteres':len(text) if text else 0,
          'tentatives':int(prior.get('tentatives',0))+1,'passages':passages,
          'modificationPositions':False}
    docs=sorted(history.values(),key=lambda d:str(d.get('publication') or ''),reverse=True)[:1500]
    reasons={}
    for d in docs:
        if d.get('lecture')=='indisponible':
            code=d.get('motif') or 'inconnu'
            reasons[code]=reasons.get(code,0)+1
    stats={'documents':len(docs),'textesLus':sum(d.get('lecture') in ('html','pdf','texte_html') for d in docs),
        'pdfLus':sum(d.get('lecture')=='pdf' for d in docs),
        'passagesCandidats':sum(len(d.get('passages') or []) for d in docs),
        'nouveauxExamines':len(selected),'echecsParCause':reasons}
    result={'schemaVersion':23,'generatedAt':now.isoformat(),
        'notice':'Diagnostic et extraction uniquement. Aucun codage politique automatique.',
        'documents':docs,'statistiques':stats,'publicationAutomatiquePositions':False}
    v20.write(root/'data/registre_preuves_v20.json',result)
    print('V23 extraction :',stats,'positions inchangées')
    return result

if __name__=='__main__':run()
