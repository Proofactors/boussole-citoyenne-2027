#!/usr/bin/env python3
"""Boussole V27.1 : candidatures signalées par 2 domaines d'édition indépendants.
L'absence de signalement ne signifie pas absence de candidature. Aucune position n'est inférée.
"""
import datetime as dt
import hashlib
import html
import json
import pathlib
import re
import unicodedata
from collections import defaultdict
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
NAME = r"[A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ][a-zàâäéèêëîïôöùûüçÿœæA-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ'’\-]+(?:\s+(?:(?:de|du|des|d'|le|la|van)\s+)?[A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ][a-zàâäéèêëîïôöùûüçÿœæA-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ'’\-]+){1,3}"
ELECTION = r"(?:l[’']élection\s+)?(?:la\s+)?présidentielle(?:\s+(?:de|en))?\s*2027|(?:l[’']?)?Élysée\s+(?:en\s+)?2027"
PATTERNS = [
    re.compile(rf"(?P<nom>{NAME})\s+(?:annonce|confirme|officialise|déclare|dévoile|lance)\s+(?:officiellement\s+)?sa\s+candidature\s+(?:à|pour)\s+(?:{ELECTION})",re.I),
    re.compile(rf"(?P<nom>{NAME})\s+(?:se\s+déclare|s[’']est\s+déclaré(?:e)?|se\s+présente|sera)\s+candidat(?:e)?\s+(?:à|pour)\s+(?:{ELECTION})",re.I),
    re.compile(rf"(?P<nom>{NAME})\s+se\s+présente\s+(?:à|pour)\s+(?:{ELECTION})",re.I),
    re.compile(rf"(?P<nom>{NAME})\s+(?:entre|se\s+lance)\s+dans\s+la\s+course\s+(?:à|pour)\s+(?:{ELECTION})",re.I),
    re.compile(rf"(?P<nom>{NAME})\s+(?:est\s+)?candidat(?:e)?\s+(?:déclaré(?:e)?\s+)?(?:à|pour)\s+(?:{ELECTION})",re.I),
    re.compile(rf"(?:{ELECTION})\s*[:–—-]\s*(?P<nom>{NAME})\s+(?:annonce|officialise|confirme)\s+sa\s+candidature",re.I),
]
NEGATIVE = re.compile(r"\b(?:renonce|retire\s+sa\s+candidature|dément|n[’']est\s+pas\s+candidat|ne\s+(?:se\s+présentera|sera)\s+pas|n[’']a\s+pas\s+annoncé|pourrait|envisage|envisagerait|hypothèse|rumeur|supposée|possible\s+candidature|pas\s+encore\s+candidat|conditionnel|interrogé|pressenti|pressentie)\b", re.I)
BAD_NAMES = {'la france','le monde','le parisien','le sénat','le senat','la république','le président','la présidente','le gouvernement','le candidat','la candidate','france info','france inter','france télévision','france télévisions','france 24','elysee 2027'}


def slug(value):
    norm=''.join(c for c in unicodedata.normalize('NFKD',value.lower()) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+','-',norm).strip('-')


def domain(url):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password: return None
    host=p.hostname.lower().removeprefix('www.')
    if '.' not in host or host.endswith(('.local','.internal','.test')): return None
    return host


def detect(text):
    text=html.unescape(re.sub(r'<[^>]*>', ' ', str(text)))
    text=re.sub(r'\s+', ' ',text).strip()
    if NEGATIVE.search(text): return None
    for pattern in PATTERNS:
        match=pattern.search(text)
        if not match: continue
        name=match.group('nom').strip(' .:;,–—-')
        if not (2 <= len(name.split()) <= 4) or len(name)>85 or name.lower() in BAD_NAMES: continue
        if any(w.lower() in {'présidentielle','candidature','annonce','confirme','officiellement','le','la'} for w in name.split()): continue
        return name
    return None


def signals_from_queue(queue,existing):
    found=defaultdict(list)
    records=queue.values() if isinstance(queue,dict) else queue
    for rec in records:
        if not isinstance(rec,dict): continue
        title=str(rec.get('title') or '')
        excerpt=str(rec.get('excerpt') or '')[:1500]
        # Le titre seul prime ; le résumé est une possibilité additionnelle.
        name=detect(title) or detect(excerpt)
        host=domain(str(rec.get('url') or ''))
        if not name or not host: continue
        key=slug(name)
        if key in existing: continue
        found[key].append({'nom':name,'titre':title,'extrait':excerpt[:350], 'url':rec['url'], 'domaine':host, 'date_source':rec.get('sourcePublishedAt','')})
    # Supprimer les doublons d'articles par URL et distinguer les éditeurs.
    for key,items in list(found.items()):
        seen=set()
        found[key]=[item for item in items if not (item['url'] in seen or seen.add(item['url']))]
    return found


def discover(queue,existing,min_domains=2):
    found=signals_from_queue(queue,existing)
    candidates=[]
    for key,items in sorted(found.items()):
        domains={i['domaine'] for i in items}
        if len(domains) < min_domains: continue
        candidates.append({'id':key,'nom':items[0]['nom'],'statut':'candidature_signalee_non_verifiee','preuves':items[:12],'domaines_distincts':len(domains),'positions_documentees':0})
    return candidates,found


def apply(base,candidates):
    updated=json.loads(json.dumps(base))
    if len(updated['positions'])+len(candidates)>250: raise ValueError('Limite de 250 profils atteinte')
    added=[]
    for row in candidates:
        if row['id'] in updated['positions']: continue
        updated['positions'][row['id']]={q['id']:None for q in updated['affirmations']}
        added.append(row)
    return updated,added


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def page(data,found,base,added):
    rows=[]
    for row in data['ajouts']:
        links=''.join('<p><a target="_blank" rel="noopener noreferrer" href="'+html.escape(e['url'],quote=True)+'">'+html.escape(e['titre'] or e['url'])+'</a></p>' for e in row.get('preuves',[]))
        rows.append('<tr><td>'+html.escape(row['nom'])+'</td><td>Signalée, non vérifiée officiellement</td><td>'+str(row.get('domaines_distincts',0))+'</td><td>'+links+'</td></tr>')
    signals=''.join('<tr><td>'+html.escape(r['nom'])+'</td><td>'+str(r['sources'])+'</td><td>'+html.escape(r.get('exemple',''))+'</td></tr>' for r in data['signalements_a_source_unique'])
    errors_note='Les articles sont repérés par des expressions explicites dans leur titre ou résumé RSS. Plusieurs domaines ne garantissent pas des sources journalistiques indépendantes. Une absence de résultat ne prouve pas une absence de candidature.'
    return ('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Candidatures — Boussole V27.1</title><style>body{font:16px/1.5 system-ui;max-width:1100px;margin:2em auto;padding:0 1em;color:#183047}h1{color:#113b55}table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #ddd;padding:.7em;text-align:left;vertical-align:top}a{overflow-wrap:anywhere}.stats{display:flex;gap:1rem;flex-wrap:wrap}.stat{border:1px solid #ddd;border-radius:10px;padding:1em;flex:1;min-width:140px}.muted{color:#526477}</style><h1>Suivi des candidatures — V27.1</h1><p class="muted">'+html.escape(errors_note)+'</p><div class="stats"><div class="stat"><b>'+str(data['documents_analysees'])+'</b><div>Publications analysées</div></div><div class="stat"><b>'+str(data['annonces_distinctes'])+'</b><div>Personnes détectées hors base</div></div><div class="stat"><b>'+str(len(data['ajouts']))+'</b><div>Profils ajoutés au total</div></div><div class="stat"><b>'+str(len(data['signalements_a_source_unique']))+'</b><div>Signalements à source unique</div></div></div><h2>Profils ajoutés</h2><table><tr><th>Nom</th><th>Statut</th><th>Domaines</th><th>Preuves</th></tr>'+''.join(rows)+'</table><h2>Signalements à compléter</h2><table><tr><th>Nom</th><th>Domaines</th><th>Exemple</th></tr>'+signals+'</table><p class="muted">Les nouveaux profils n’ont aucune position attribuée. Aucun calcul politique ne dépend de simples annonces de candidature.</p></html>')


def main():
    base_path=ROOT/'boussole_2027_positions.json'
    base=json.loads(base_path.read_text(encoding='utf-8'))
    queue_path=ROOT/'data/queue.json'
    queue=json.loads(queue_path.read_text(encoding='utf-8')) if queue_path.exists() else {}
    candidates,signals=discover(queue,base['positions'])
    updated,added=apply(base,candidates)
    registry=ROOT/'data/candidatures_automatiques.json'
    old=json.loads(registry.read_text(encoding='utf-8')) if registry.exists() else {'ajouts':[]}
    if added:
        write_json(base_path,updated)
        man_path=ROOT/'manifest.json'
        man=json.loads(man_path.read_text(encoding='utf-8'))
        sha=hashlib.sha256(base_path.read_bytes()).hexdigest()
        man.update({'schemaVersion':1,'sha256':sha,'datasetVersion':'auto-profils-'+sha[:20], 'publishedAt':dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'questions':len(updated['affirmations']),'personalities':len(updated['positions']), 'positions':sum(1 for ps in updated['positions'].values() for p in ps.values() if isinstance(p,dict) and type(p.get('stance')) is int), 'editorialStatus':'Nouveaux profils ajoutés à partir de deux domaines distincts ; candidatures non vérifiées officiellement ; aucune opinion créée.'})
        write_json(man_path,man)
    known={x.get('id') for x in old.get('ajouts',[])}
    old.setdefault('ajouts',[]).extend([{**x,'ajoute_le':dt.datetime.now(dt.timezone.utc).isoformat()} for x in added if x['id'] not in known])
    old['derniere_execution']=dt.datetime.now(dt.timezone.utc).isoformat()
    old['documents_analysees']=len(queue)
    old['annonces_distinctes']=len(signals)
    old['signalements_a_source_unique']=[{'id':k,'nom':v[0]['nom'],'sources':len({x['domaine'] for x in v}),'exemple':v[0]['titre']} for k,v in signals.items() if len({x['domaine'] for x in v})<2]
    write_json(registry,old)
    (ROOT/'candidatures.html').write_text(page(old,signals,base,added),encoding='utf-8')
    print('V27.1 :',len(queue),'documents ;',len(signals),'personnes détectées ;',len(added),'nouveaux profils')

if __name__=='__main__': main()
