#!/usr/bin/env python3
"""V33 - veille des pages officielles des programmes, sans extraction de positions.
Aucune conclusion d'opinion n'est inférée automatiquement ; seuls des liens et métadonnées
sont publiés. Pas de suivi de sources externes non autorisées ; taille et délai bornés.
"""
from __future__ import annotations
import datetime as dt
import hashlib, html, json, os, pathlib, re, socket, ssl, ipaddress, urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = ROOT / 'config/programmes_officiels.json'
OUT = ROOT / 'programmes.json'
PAGE = ROOT / 'programmes.html'
MAX_BYTES = 1_200_000

class Stripper(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript'): self.skip+=1
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript') and self.skip: self.skip-=1
    def handle_data(self,data):
        if not self.skip: self.parts.append(data)

def public_url(url, domains):
    u=urlparse(url)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443): return False
    host=u.hostname.lower().rstrip('.')
    if host not in domains and host.removeprefix("www.") not in domains and ("www." + host) not in domains: return False
    # Resolve all A/AAAA addresses and reject any non-global destination (SSRF guard).
    try:
        results=socket.getaddrinfo(host,443,proto=socket.IPPROTO_TCP)
        ips={entry[4][0] for entry in results}
        return bool(ips) and all(ipaddress.ip_address(ip).is_global for ip in ips)
    except (OSError,ValueError): return False

class GuardedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed): self.allowed=allowed
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not public_url(newurl,self.allowed): raise ValueError('Redirection non autorisée')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def inspect_source(source, fetcher=None):
    allowed={d.lower().removeprefix('www.') for d in source['domaines_autorises']}
    url=source['url']
    result={k:source[k] for k in ('personnalite_id','personnalite','editeur','url','nature')}
    result.update(statut_editorial=source.get('statut_editorial','a_documenter'), note_editoriale=source.get('note_editoriale',''))
    result.update(statut='indisponible',date_verification=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),empreinte_sha256=None)
    if not public_url(url,allowed):
        result['diagnostic']='Adresse hors domaine autorisé ou DNS non public';return result
    try:
        if fetcher:
            raw,content_type=fetcher(url)
        else:
            opener=urllib.request.build_opener(GuardedRedirect(allowed))
            with opener.open(urllib.request.Request(url,headers={'User-Agent':'BoussoleCitoyenne/33 (+veille documentaire)','Accept':'text/html,application/pdf'}),timeout=12) as response:
                content_type=response.headers.get('Content-Type','').lower()
                raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES: raise ValueError('Document trop volumineux')
        if 'html' in content_type:
            parser=Stripper();parser.feed(raw.decode('utf-8','replace'))
            content=re.sub(r'\s+',' ',' '.join(parser.parts)).strip()
            low=content.lower()
            # This is an information *availability* label, not a verification of program completeness.
            result['statut']='programme_officiel_reference' if ('programme' in low or 'avenir en commun' in low) else 'page_officielle_a_examiner'
            result['aperçu']=content[:180]
        elif 'pdf' in content_type or raw[:4]==b'%PDF':
            result['statut']='document_pdf_officiel_reference'
            result['aperçu']='Fichier PDF officiel référencé, contenu non interprété.'
        else:
            result['statut']='format_non_pris_en_charge'
        result['empreinte_sha256']=hashlib.sha256(raw).hexdigest()
    except Exception as e:
        result['diagnostic']=type(e).__name__+': '+str(e)[:150]
    return result

def generate(cfg, fetcher=None):
    sources=cfg.get('sources',[])
    if not isinstance(sources,list) or len(sources)>150:raise ValueError('Configuration invalide')
    seen=set(); entries=[]
    for s in sources:
        ident=s.get('personnalite_id','')
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,90}',ident):raise ValueError('Identifiant invalide')
        if ident in seen:raise ValueError('Doublon de candidat')
        seen.add(ident)
        if not s.get('domaines_autorises') or not isinstance(s['domaines_autorises'],list):raise ValueError('Domaines officiels requis')
        entries.append(inspect_source(s,fetcher))
    return {'schemaVersion':1,'date_generation':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
            'avertissement':'Référencement des programmes officiels, non validation de toutes leurs mesures. Aucune position politique n’est inférée.',
            'sources':entries}

def render_page(data):
    esc=lambda x:html.escape(str(x),quote=True)
    rows=''.join(f'<article><h2>{esc(s["personnalite"])}</h2><p><strong>{esc(s.get("statut_editorial","non_classe").replace("_"," "))}</strong> · {esc(s["editeur"])}</p><p>{esc(s.get("note_editoriale",""))}</p><p>État de la consultation automatique : {esc(s["statut"].replace("_"," "))}</p><p><a target="_blank" rel="noopener noreferrer" href="{esc(s["url"])}">Consulter la source officielle ↗</a></p><small>Consulté : {esc(s["date_verification"])} · Empreinte : {esc(s.get("empreinte_sha256") or "non disponible")}</small></article>' for s in data['sources'])
    if not rows:rows='<p>Aucun programme officiel référencé pour le moment.</p>'
    return '<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Programmes officiels — Boussole</title><style>body{font:16px system-ui;max-width:850px;margin:auto;padding:clamp(14px,4vw,35px);background:#f5f7fb;color:#172438}article{background:white;padding:18px;margin:13px 0;border:1px solid #d7dfed;border-radius:12px;overflow-wrap:anywhere}a{color:#145b9c}small{color:#556778}</style><h1>Programmes officiels suivis</h1><p>Les liens sont automatiquement vérifiés dans les domaines officiels autorisés. Un programme référencé n’a pas été analysé ni validé proposition par proposition. Aucun score n’est modifié.</p>'+rows+'<p><a href="./">Retour à la Boussole</a></p></html>'

def main():
    cfg=json.loads(CFG.read_text('utf-8'))
    data=generate(cfg)
    # Respect existing catalog if a temporary network error occurs: keep last verified entry.
    if OUT.exists():
        try:
            old={p['personnalite_id']:p for p in json.loads(OUT.read_text('utf-8')).get('sources',[])}
            for p in data['sources']:
                if p['statut']=='indisponible' and p['personnalite_id'] in old and old[p['personnalite_id']].get('empreinte_sha256'):
                    p['dernier_document_valide']=old[p['personnalite_id']]['empreinte_sha256']
        except (ValueError,KeyError,TypeError):pass
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    PAGE.write_text(render_page(data),encoding='utf-8')
    print('Programmes surveillés:',len(data['sources']),'accessibles:',sum(p['statut']!='indisponible' for p in data['sources']))

if __name__=='__main__': main()
