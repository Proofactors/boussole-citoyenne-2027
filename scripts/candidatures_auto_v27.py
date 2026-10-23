#!/usr/bin/env python3
"""Détection conservatrice de candidatures annoncées dans au moins deux médias distincts.
N'infère jamais de positions politiques. Statut publié: signalement concordant, non officiel.
"""
import datetime as dt
import hashlib
import html
import json
import pathlib
import re
import unicodedata
from collections import defaultdict
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
DECLARATION = [
    re.compile(r"(?P<nom>[A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ][\wÀ-ÿ'-]+(?:\s+(?:de|du|d'|le|la|[A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ][\wÀ-ÿ'-]+)){1,3})\s+(?:annonce|confirme|officialise|déclare|dévoile)\s+(?:sa\s+)?candidature\s+(?:à|pour)\s+(?:l[’']élection\s+)?(?:la\s+)?présidentielle(?:\s+de)?\s+2027",re.I),
    re.compile(r"(?P<nom>[A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ][\wÀ-ÿ'-]+(?:\s+(?:de|du|d'|le|la|[A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ][\wÀ-ÿ'-]+)){1,3})\s+(?:se\s+déclare|s[’']est\s+déclaré(?:e)?)\s+candidat(?:e)?\s+(?:à|pour)\s+(?:l[’']élection\s+)?(?:la\s+)?présidentielle(?:\s+de)?\s+2027",re.I),
]
DENIAL = re.compile(r"\b(?:ne\s+(?:sera|serai|suis|se\s+présentera)\s+pas|renonce|dément|dement|n[’']est\s+pas\s+candidat|n[’']a\s+pas\s+annoncé|conditionnel|hypothèse|hypothese|pourrait|envisagerait|rumeur)\b",re.I)
COMMON = {'La République','Le Monde','Le Parisien','L Assemblée','Assemblée Nationale','France Info','Jean Luc'}

def slug(s):
    s=''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+','-',s).strip('-')

def domain(url):
    p=urlparse(url)
    if p.scheme not in ('http','https') or not p.hostname or '.' not in p.hostname or p.username or p.password: return None
    host=p.hostname.lower().removeprefix('www.')
    if host.endswith(('.local','.internal','.test')): return None
    return host

def detect(title):
    title=re.sub(r'\s+',' ',title).strip()
    if DENIAL.search(title): return None
    for pattern in DECLARATION:
        m=pattern.search(title)
        if not m:continue
        name=m.group('nom').strip(' -–—:,.')
        words=name.split()
        if len(words)<2 or len(words)>4 or len(name)>90 or name in COMMON:continue
        if any(w.lower() in {'présidentielle','candidature','pour','annonce','confirme','officiellement'} for w in words):continue
        return name
    return None

def discover(queue,positions,previous=None,min_domains=2):
    previous=previous or {}
    found=defaultdict(list)
    for rec in (queue.values() if isinstance(queue,dict) else queue):
        if not isinstance(rec,dict):continue
        title=str(rec.get('title') or '').strip()
        name=detect(title)
        url=str(rec.get('url') or '')
        host=domain(url)
        if not name or not host:continue
        key=slug(name)
        # Ignorer les noms déjà présents, sans transformer une mention en nouvelle personne.
        if key in positions:continue
        found[key].append({'nom':name,'titre':title,'url':url,'domaine':host,'date_source':rec.get('sourcePublishedAt','')})
    candidates=[]
    for key,items in sorted(found.items()):
        distinct={x['domaine'] for x in items}
        # Une source syndiquée peut être dupliquée : seuls les domaines différents comptent.
        if len(distinct)<min_domains:continue
        candidates.append({'id':key,'nom':items[0]['nom'],'statut':'candidature_signalee_par_sources_concordantes_non_verifiee','preuves':items[:10], 'domaines_distincts':len(distinct),'positions_documentees':0})
    return candidates,found

def apply(base,candidates):
    updated=json.loads(json.dumps(base))
    if len(updated['positions'])+len(candidates)>250:raise ValueError('Limite de 250 profils atteinte')
    added=[]
    for row in candidates:
        if row['id'] in updated['positions']:continue
        updated['positions'][row['id']]={q['id']:None for q in updated['affirmations']}
        added.append(row)
    return updated,added

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    base_path=ROOT/'boussole_2027_positions.json'
    base=json.loads(base_path.read_text(encoding='utf-8'))
    queue_path=ROOT/'data/queue.json'
    queue=json.loads(queue_path.read_text(encoding='utf-8')) if queue_path.exists() else {}
    candidates,signals=discover(queue,base['positions'])
    nextbase,added=apply(base,candidates)
    registry=ROOT/'data/candidatures_automatiques.json'
    old=json.loads(registry.read_text(encoding='utf-8')) if registry.exists() else {'ajouts':[]}
    if added:
        write_json(base_path,nextbase)
        manifest_path=ROOT/'manifest.json'
        man=json.loads(manifest_path.read_text(encoding='utf-8'))
        raw=base_path.read_bytes()
        sha=hashlib.sha256(raw).hexdigest()
        man.update({'schemaVersion':1,'sha256':sha,'datasetVersion':'auto-profils-'+sha[:20],
                    'publishedAt':dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'questions':len(nextbase['affirmations']),'personalities':len(nextbase['positions']),
                    'positions':sum(1 for ps in nextbase['positions'].values() for p in ps.values() if isinstance(p,dict) and isinstance(p.get('stance'),int) and not isinstance(p.get('stance'),bool)),
                    'editorialStatus':'Nouveaux profils signalés automatiquement par au moins deux sources ; candidatures NON vérifiées ; positions non attribuées.'})
        write_json(manifest_path,man)
    old['ajouts'].extend([{**x,'ajoute_le':dt.datetime.now(dt.timezone.utc).isoformat()} for x in added])
    old['derniere_execution']=dt.datetime.now(dt.timezone.utc).isoformat()
    old['signalements_a_source_unique']=[{'id':k,'nom':v[0]['nom'],'sources':len({x['domaine'] for x in v})} for k,v in signals.items() if len({x['domaine'] for x in v})<2]
    write_json(registry,old)
    rows=''.join('<tr><td>'+html.escape(x['nom'])+'</td><td>'+html.escape(x['statut'].replace('_',' '))+'</td><td>'+str(x['domaines_distincts'])+'</td><td>'+''.join('<p><a rel="noopener noreferrer" href="'+html.escape(e['url'],quote=True)+'">'+html.escape(e['titre'])+'</a></p>' for e in x['preuves'])+'</td></tr>' for x in old['ajouts'])
    (ROOT/'candidatures.html').write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Candidatures — Boussole V27</title><style>body{font:16px system-ui;max-width:1100px;margin:2em auto;padding:0 1em}table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #ddd;padding:1em;vertical-align:top;text-align:left}a{overflow-wrap:anywhere}</style><h1>Suivi automatique des candidatures</h1><p><strong>Attention :</strong> les profils sont ajoutés après au moins deux titres de sources distinctes comportant une annonce explicite. Cela ne constitue ni une candidature officiellement validée ni une certification journalistique. Aucune opinion ne leur est attribuée.</p><p>Profils ajoutés automatiquement : '+str(len(old['ajouts']))+'. Candidatures signalées par une seule source : '+str(len(old['signalements_a_source_unique']))+'.</p><table><tr><th>Personnalité</th><th>Statut</th><th>Sources distinctes</th><th>Références</th></tr>'+rows+'</table></html>',encoding='utf-8')
    print('Ajouts automatiques :',len(added),' ; signalements à source unique :',len(old['signalements_a_source_unique']))

if __name__=='__main__':main()
