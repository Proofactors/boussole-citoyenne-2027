#!/usr/bin/env python3
"""V20 — Collecte prudente de textes complets et registre de passages candidats.
Jamais de modification des positions politiques, ni d'attribution automatique de score.
Utilise seulement la bibliothèque standard Python. Les pages web sont des données non fiables.
"""
import datetime as dt
import html
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sys
import unicodedata
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]
MAX_PAGES = max(0,min(int(os.getenv('BOUSSOLE_MAX_PAGES','12')),40))
MAX_BYTES = 650_000
MAX_TEXT = 24_000
STOP = {'avoir','faire','sont','pour','dans','avec','sans','contre','entre','leur','leurs','cette','ainsi','sera','seront','plus','moins','doit','faut','politique','france','francais','francaise','mettre','place','grand','grande','toute','tous','toutes','comme','selon','apres','avant','cela','question','etat','public','publique','part','afin','encore','plusieurs'}

def read(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(value).casefold()) if not unicodedata.combining(c))

def terms(text):
    return {w for w in re.findall('[a-z]{5,}',normalized(text)) if w not in STOP}

def safe_url(url):
    """Reject local/internal hosts to mitigate SSRF in published queue entries."""
    try:
        p=urlparse(url)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443): return False
        name=p.hostname.lower().rstrip('.')
        if name=='localhost' or name.endswith(('.localhost','.local','.internal','.test')): return False
        try:
            ip=ipaddress.ip_address(name)
            return ip.is_global
        except ValueError: pass
        # Intentionally reject numeric/ambiguous host syntax
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*\.[a-z]{2,}', name): return False
        # DNS safeguard against hostnames resolving to private / metadata networks
        try:
            addresses=socket.getaddrinfo(name,443,type=socket.SOCK_STREAM)
            return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
        except (OSError,ValueError): return False
    except (ValueError,TypeError): return False

class SafeRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not safe_url(newurl): raise ValueError('Redirection non autorisée')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

class TextExtractor(HTMLParser):
    ignored={'script','style','nav','footer','header','form','noscript','svg'}
    def __init__(self):
        super().__init__(convert_charrefs=True); self.block=0; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in self.ignored: self.block+=1
        if tag in ('p','div','article','h1','h2','h3','li','br'): self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in self.ignored and self.block: self.block-=1
        if tag in ('p','article','li'): self.parts.append('\n')
    def handle_data(self,data):
        if not self.block: self.parts.append(data)
    def result(self):
        txt=html.unescape(' '.join(self.parts))
        return re.sub(r'[ \t]+',' ',re.sub(r'\n\s*\n+', '\n',txt)).strip()[:MAX_TEXT]

def fetch(url):
    if not safe_url(url): return None,'Adresse refusée'
    try:
        opener=build_opener(SafeRedirects())
        req=Request(url,headers={'User-Agent':'Boussole2027-veille/1.0 (+public research; no indexing)','Accept':'text/html,application/xhtml+xml'})
        with opener.open(req, timeout=9) as res:
            mime=res.headers.get('Content-Type','').lower()
            if 'text/html' not in mime and 'application/xhtml+xml' not in mime: return None,'Format non HTML'
            raw=res.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES: return None,'Page trop volumineuse'
            charset=res.headers.get_content_charset() or 'utf-8'
        extractor=TextExtractor(); extractor.feed(raw.decode(charset,errors='replace'))
        text=extractor.result()
        return (text,None) if len(text)>100 else (None,'Texte insuffisant')
    except Exception as e:
        return None,'Lecture impossible : '+type(e).__name__

def split_passages(text):
    lines=re.split(r'(?<=[.!?])\s+|\n+',text)
    return [line.strip()[:700] for line in lines if 50<=len(line.strip())<=1200]

def extract_proposals(text,base,limit=12):
    people=list(base['positions'].keys())
    questions=base['affirmations']
    result=[]
    for passage in split_passages(text):
        normal=normalized(passage)
        named=[slug for slug in people if re.search(r'(?<!\w)'+re.escape(normalized(slug.replace('-',' ')))+r'(?!\w)',normal)]
        if not named: continue
        w=terms(passage)
        matches=[]
        for q in questions:
            overlap=sorted(w & terms(str(q.get('text',''))+' '+str(q.get('title',''))))
            if len(overlap)>=2: matches.append((len(overlap),q,overlap))
        matches.sort(key=lambda x:-x[0])
        for count,q,overlap in matches[:3]:
            result.append({'personnalitesMentionnees':named[:4],'questionId':q['id'],'theme':q.get('theme'),
                'passageSource':passage,'motsCommuns':overlap[:8],
                'risques':['Citation ou propos rapporté possibles','Sens, négation et attribution non établis'],
                'valeurProposee':None,'validation':'requise','publicationAutomatique':False,
                'qualification':'passage candidat, pas preuve de position politique'})
            if len(result)>=limit:return result
    return result

def run(root=ROOT, fetcher=fetch):
    base=read(root/'boussole_2027_positions.json',{})
    queue=read(root/'data/queue.json',{})
    if not isinstance(queue,dict) or not isinstance(base.get('positions'),dict) or not isinstance(base.get('affirmations'),list):
        raise ValueError('Base ou file de veille invalide')
    entries=sorted([(k,v) for k,v in queue.items() if isinstance(v,dict)],key=lambda kv: str(kv[1].get('sourcePublishedAt') or ''),reverse=True)
    # Avoid retrying the entire historical queue every run. Selection is bounded.
    old=read(root/'data/registre_preuves_v20.json',{})
    old_entries={x['id']:x for x in old.get('documents',[]) if isinstance(x,dict) and x.get('id')}
    candidates=[(k,v) for k,v in entries if str(v.get('id') or k) not in old_entries][:MAX_PAGES]
    for k,v in candidates:
        identifier=str(v.get('id') or k)
        url=str(v.get('url') or '')
        text,error=fetcher(url)
        mentions=extract_proposals(text,base) if text else []
        old_entries[identifier]={'id':identifier,'titre':v.get('title',''),'url':url,
          'publication':v.get('sourcePublishedAt'),'analyseLe':dt.datetime.now(dt.timezone.utc).isoformat(),
          'lecture':'texte_html' if text else 'indisponible', 'motif':error,
          'nombreCaracteres':len(text) if text else 0,'passages':mentions,
          'modificationPositions':False}
    docs=sorted(old_entries.values(),key=lambda x:x.get('publication') or '',reverse=True)[:1500]
    record={'schemaVersion':1,'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
      'notice':'Détection de passages uniquement. Aucune position attribuée ni publiée automatiquement.',
      'documents':docs,'statistiques':{'documents':len(docs),'textesLus':sum(d['lecture']=='texte_html' for d in docs),
      'passagesCandidats':sum(len(d['passages']) for d in docs),'nouveauxExamines':len(candidates)},
      'publicationAutomatiquePositions':False}
    write(root/'data/registre_preuves_v20.json',record)
    print('V20:',record['statistiques'],'; positions inchangées')
    return record

if __name__=='__main__':run()
