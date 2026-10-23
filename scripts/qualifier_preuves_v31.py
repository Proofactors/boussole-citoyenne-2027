#!/usr/bin/env python3
"""V31.1 : vérification documentaire des signaux V30, sans conversion en score.

Le programme visite uniquement des pages officielles AN construites à partir des
numéros de scrutin V30. Il ne fait aucune déduction politique et ne modifie jamais
la base publiée. L'absence ou l'échec de téléchargement reste explicitement visible.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.request
import urllib.error
import socket
import ssl
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'data/propositions_v30.json'
OUTPUT = ROOT / 'data/verification_v31.json'
PAGE = ROOT / 'verification.html'
MAX_PAGES = 20
MAX_BYTES = 900_000

class ReadableHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.bits = []
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript','svg','nav','footer'):
            self.depth += 1
        if tag in ('p','h1','h2','h3','li','tr','div') and self.depth == 0:
            self.bits.append(' ')
    def handle_endtag(self, tag):
        if tag in ('script','style','noscript','svg','nav','footer') and self.depth:
            self.depth -= 1
        if tag in ('p','h1','h2','h3','li','tr') and self.depth == 0:
            self.bits.append(' ')
    def handle_data(self, data):
        if self.depth == 0: self.bits.append(data)

def official_url(numero):
    s = str(numero)
    if not re.fullmatch(r'[0-9]{1,6}',s):
        raise ValueError('Numéro de scrutin invalide')
    return f'https://www.assemblee-nationale.fr/dyn/17/scrutins/{s}'

def _official_https(url):
    """Authorize only HTTPS on the Assembly domain, including redirects."""
    try:
        u = urlsplit(url)
        return u.scheme == 'https' and u.hostname in {'www.assemblee-nationale.fr', 'assemblee-nationale.fr'} and not u.username and not u.password and (u.port is None or u.port == 443)
    except ValueError:
        return False

class _OfficialRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _official_https(newurl):
            raise ValueError('redirection_externe_refusee')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def _failure(exc):
    """Produce safe actionable diagnostics, no credentials or entire URLs."""
    if isinstance(exc, urllib.error.HTTPError):
        code = exc.code
        return ('http_temporaire' if code in (429,500,502,503,504) else 'http_refuse',f'HTTP {code}',code in (429,500,502,503,504))
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return ('delai_depasse','Timeout',True)
    if isinstance(exc, ssl.SSLError):
        return ('tls_erreur',type(exc).__name__,False)
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason,(socket.timeout,TimeoutError)):
            return ('delai_depasse','Timeout',True)
        if isinstance(reason,socket.gaierror):
            return ('dns_erreur','DNS',False)
        if isinstance(reason,ssl.SSLError):
            return ('tls_erreur','TLS',False)
        return ('erreur_reseau',type(reason).__name__,True)
    if isinstance(exc, ValueError) and str(exc)=='redirection_externe_refusee':
        return ('redirection_externe_refusee','Redirection hors domaine AN',False)
    return ('erreur_reseau',type(exc).__name__,False)

def download(numero, opener=None, attempts=2, delay=0.3):
    """Read only official Assembly pages, with bounded retries and diagnostics.

    The existing downloaded vote archive remains the source of raw vote records;
    this HTML verification is additional and must never create political codings.
    """
    url=official_url(numero)
    if opener is None:
        opener=urllib.request.build_opener(_OfficialRedirectHandler()).open
    req=urllib.request.Request(url,headers={
        'User-Agent':'BoussoleCitoyenneResearch/1.1 (public parliamentary evidence audit)',
        'Accept':'text/html,application/xhtml+xml;q=0.9',
    })
    attempts=max(1,min(int(attempts),3))
    for attempt in range(1,attempts+1):
        try:
            with opener(req,timeout=12) as res:
                final=res.geturl()
                if not _official_https(final):
                    return {'status':'redirection_externe_refusee','url':url,'text':'','tentatives':attempt}
                kind=res.headers.get('Content-Type','')
                if 'html' not in kind.lower():
                    return {'status':'format_inattendu','url':url,'text':'','detail':kind.split(';')[0][:80],'tentatives':attempt}
                raw=res.read(MAX_BYTES+1)
                if len(raw)>MAX_BYTES:
                    return {'status':'page_trop_volumineuse','url':url,'text':'','tentatives':attempt}
            parser=ReadableHTML(); parser.feed(raw.decode('utf-8','replace'))
            clean=re.sub(r'\s+',' ',''.join(parser.bits)).strip()
            if len(clean)<100:
                return {'status':'texte_insuffisant','url':url,'text':clean,'tentatives':attempt}
            return {'status':'page_officielle_lue','url':url,'text':clean,'tentatives':attempt}
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,OSError,ValueError) as exc:
            status,detail,temporary=_failure(exc)
            if temporary and attempt<attempts:
                if delay>0:time.sleep(delay*attempt)
                continue
            return {'status':status,'url':url,'text':'','detail':detail,'tentatives':attempt}
    raise AssertionError('unreachable')

def compile_registry(source, fetcher=download, limit=MAX_PAGES):
    entries = source.get('propositions',[])
    if not isinstance(entries,list): raise ValueError('Liste des propositions invalide')
    cached={}; results=[]
    for p in entries:
        numero=str(p.get('scrutinNumero',''))
        try: url=official_url(numero)
        except ValueError: continue
        if numero not in cached:
            cached[numero] = fetcher(numero) if len(cached)<limit else {'status':'non_consulte_limite','url':url,'text':''}
        check=cached[numero]
        text=check.get('text','')
        # Checking for the number alone is only a consistency signal, not substantive evidence.
        id_present=bool(re.search(r'\b'+re.escape(numero)+r'\b',text)) if text else False
        results.append({
            'personnaliteId':p.get('personnaliteId'), 'acteurRef':p.get('acteurRef'),
            'questionId':p.get('questionId'), 'question':p.get('question'),
            'scrutinNumero':numero, 'date':p.get('date'), 'voteBrut':p.get('vote'),
            'objetDuScrutin':p.get('objet'), 'typeScrutin':p.get('typeScrutin'),
            'urlOfficielle':url, 'consultation':check['status'],
            'detailTechnique':check.get('detail'), 'tentatives':check.get('tentatives',0),
            'numeroRepereDansPage':id_present,
            'empreinteTexteSha256':hashlib.sha256(text.encode()).hexdigest() if text else None,
            'extraitContextuel':text[:480] if text else None,
            'niveauPreuve':'DOCUMENT NON QUALIFIE - PAS DE POSITION POLITIQUE INFERABLE',
            'codagePropose':None,
            'verificationRequise':['lien entre dispositif exact et affirmation',
                 'identité du votant et date du mandat','sens matériel du vote (amendement/suppression)',
                 'vérification de sources éventuellement contradictoires']
        })
    return {
       'schemaVersion':'31.0', 'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
       'totalSignalements':len(results),
       'scrutinsConsultablesDemandes':sum(v['status']!='non_consulte_limite' for v in cached.values()),
       'pagesLues':sum(v['status']=='page_officielle_lue' for v in cached.values()),
       'causes':{key:sum(v['status']==key for v in cached.values()) for key in sorted({v['status'] for v in cached.values()})},
       'resultats':results,
       'avertissement':'Les données sont documentaires, non des positions. Aucune base politique n’a été modifiée.'
    }

def render(registry):
    e=html.escape
    rows=[]
    for x in registry['resultats']:
        fields=[x.get('personnaliteId'),x.get('questionId'),x.get('date'),x.get('scrutinNumero'),x.get('voteBrut'),x.get('consultation'),x.get('detailTechnique'),x.get('tentatives'),x.get('objetDuScrutin')]
        cells=''.join(f'<td>{e(str(v or "—"))}</td>' for v in fields)
        rows.append('<tr>'+cells+f'<td><a rel="noopener noreferrer" target="_blank" href="{e(x["urlOfficielle"],quote=True)}">Scrutin officiel</a></td></tr>')
    return '''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V31 — Vérification des preuves</title><style>body{font:16px system-ui;background:#f6f8fb;color:#17324b;max-width:1350px;margin:30px auto;padding:0 18px}main{padding:25px;background:white;border-radius:14px}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #dce4e8;text-align:left;vertical-align:top}th{background:#ecf2f7;position:sticky;top:0}a{color:#006778}.warning{padding:16px;background:#fff3d9;border-left:4px solid #b87916}input{padding:10px;max-width:500px;width:95%}</style><main><h1>V31.1 — Vérification et diagnostic réseau</h1><p class="warning"><strong>Aucune position politique n'est calculée ni modifiée.</strong> Le chargement d'une page officielle ne valide pas à lui seul l'interprétation d'un vote. Les extraits ne constituent pas des citations validées.</p><p><strong>'''+str(registry['totalSignalements'])+''' signalements</strong> · '''+str(registry['pagesLues'])+''' pages officielles lues · '''+e(', '.join(f'{k}: {v}' for k,v in registry.get('causes',{}).items()))+''' · '''+e(registry['generatedAt'])+'''</p><label>Filtrer : <input id="search" oninput="filterRows()" placeholder="Personnalité, question, scrutin..."></label><div style="overflow:auto;max-height:75vh"><table><thead><tr><th>Personnalité</th><th>Question</th><th>Date</th><th>Scrutin</th><th>Vote</th><th>Consultation</th><th>Diagnostic</th><th>Tentatives</th><th>Objet</th><th>Source</th></tr></thead><tbody id="rows">'''+''.join(rows)+'''</tbody></table></div><p><a href="propositions.html">← Signaux V30</a></p></main><script>function filterRows(){const q=document.getElementById('search').value.toLowerCase();for(const r of document.querySelectorAll('#rows tr'))r.hidden=!r.textContent.toLowerCase().includes(q)}</script></html>'''

def run():
    src=json.loads(INPUT.read_text(encoding='utf-8'))
    result=compile_registry(src)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    PAGE.write_text(render(result),encoding='utf-8')
    print('V31.1 :',result['totalSignalements'],'signaux,',result['pagesLues'],'pages lues ; aucune position modifiée')
if __name__=='__main__':run()
