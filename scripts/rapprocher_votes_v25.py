#!/usr/bin/env python3
"""V25: liaison prudente des identifiants officiels AN avec les personnalités Boussole.
Ne modifie JAMAIS boussole_2027_positions.json / manifest.json.
"""
import datetime as dt
import hashlib
import html
import io
import json
from pathlib import Path
import re
import unicodedata
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'boussole_2027_positions.json'
VOTES = ROOT / 'data/votes_an_v24.json'
OUTPUT = ROOT / 'data/rapprochement_votes_v25.json'
HTML = ROOT / 'votes-personnalites.html'
OFFICIAL = ('https://data.assemblee-nationale.fr/static/openData/repository/17/amo/'
            'deputes_senateurs_ministres_legislature/'
            'AMO20_dep_sen_min_tous_mandats_et_organes.json.zip')
MAX_DOWNLOAD = 45 * 1024 * 1024
MAX_MEMBER = 2 * 1024 * 1024
MAX_ACTORS = 6000


def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).casefold()
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def textval(obj):
    if isinstance(obj, str): return obj
    if isinstance(obj, dict): return textval(obj.get('#text', obj.get('value','')))
    return ''


def parse_actor(data):
    a = data.get('acteur', data)
    if not isinstance(a, dict): return None
    uid = textval(a.get('uid', ''))
    ident = (a.get('etatCivil') or {}).get('ident') or {}
    first = textval(ident.get('prenom',''))
    last = textval(ident.get('nom',''))
    if not re.fullmatch(r'PA\d+', uid) or not first or not last: return None
    return {'uid':uid, 'prenom':first, 'nom':last, 'nomComplet':f'{first} {last}'}


def parse_archive(raw):
    actors=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members=[i for i in z.infolist() if i.filename.endswith('.json') and not i.is_dir() and ('acteur' in i.filename.lower() or '/acteurs/' in i.filename.lower())]
        if len(members)>MAX_ACTORS: raise ValueError('Trop de fichiers acteurs')
        for item in members:
            if item.file_size>MAX_MEMBER: continue
            try:
                d=json.loads(z.read(item).decode('utf-8-sig'))
                parsed=parse_actor(d)
                if parsed: actors.append(parsed)
            except (UnicodeError, ValueError, zipfile.BadZipFile):
                continue
    return actors


def download_actors(url=OFFICIAL,opener=urllib.request.urlopen):
    if url != OFFICIAL: raise ValueError('Source inconnue')
    req=urllib.request.Request(url,headers={'User-Agent':'BoussoleCitoyenne/25 (recherche publique)'})
    with opener(req,timeout=60) as response: raw=response.read(MAX_DOWNLOAD+1)
    if len(raw)>MAX_DOWNLOAD or not zipfile.is_zipfile(io.BytesIO(raw)):
        raise ValueError('Archive AN invalide ou trop volumineuse')
    return raw


def match_personalities(slugs, actors):
    # Une seule occurrence pour un nom strictement égal. Aucun rapprochement approximatif.
    by_name={}
    for a in actors: by_name.setdefault(norm(a['nomComplet']),set()).add(a['uid'])
    used={}; matches={}
    for slug in slugs:
        candidates=sorted(by_name.get(norm(slug.replace('-', ' ')),set()))
        state='identifiant_unique' if len(candidates)==1 else ('ambigu' if candidates else 'non_trouve')
        matches[slug]={'statut':state,'acteurRef':candidates[0] if len(candidates)==1 else None,'candidats':candidates}
        if len(candidates)==1: used.setdefault(candidates[0],[]).append(slug)
    # Interdire qu'un même identifiant soit attribué à plusieurs personnalités
    for slugs_list in used.values():
        if len(slugs_list)>1:
            for slug in slugs_list:matches[slug].update(statut='ambigu',acteurRef=None)
    return matches


def join_votes(base,votes,actors):
    candidates=match_personalities(base['positions'].keys(),actors)
    index={m['acteurRef']: slug for slug,m in candidates.items() if m['acteurRef']}
    examples={slug:[] for slug in candidates}; count={slug:{'pour':0,'contre':0,'abstention':0,'non-votant':0,'conflit':0} for slug in candidates}
    for item in votes['scrutins']:
        for v in item.get('votes',[]):
            slug=index.get(v.get('acteurRef'))
            if not slug:continue
            stance=v.get('vote','')
            if stance not in count[slug]:stance='conflit'
            count[slug][stance]+=1
            examples[slug].append({'date':item.get('date',''),'numero':item.get('numero',''),
                'titre':item.get('titre',''),'vote':stance,'acteurRef':v['acteurRef']})
    return {'version':'25.0', 'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'actorsSource':OFFICIAL,'votesSource':votes.get('source',''),'votesArchiveSha256':votes.get('archiveSha256',''),
        'coverageNote':'Scrutins récents seulement (au plus 1 200). Absence dans le tableau ≠ absence de vote.',
        'editorialStatus':'Preuves de votes bruts; aucune inférence de position et aucune modification de la Boussole.',
        'personnalites':[{ 'id':slug,**m,'decompte':count[slug],'scrutins':examples[slug]}
                       for slug,m in candidates.items()]}


def render(result):
    rows=[]
    for p in result['personnalites']:
        tr=[]
        for v in p['scrutins'][:30]:
            tr.append('<li><b>'+html.escape(v['date'])+'</b> · scrutin '+html.escape(str(v['numero']))+
                      ' · '+html.escape(v['vote'])+' — '+html.escape(v['titre'])+'</li>')
        details='<details><summary>Voir '+str(len(p['scrutins']))+' vote(s) retrouvé(s)</summary><ul>'+''.join(tr)+'</ul></details>' if tr else '—'
        rows.append('<tr><td>'+html.escape(p['id'])+'</td><td>'+html.escape(p['statut'])+'</td><td>'+html.escape(p['acteurRef'] or '—')+'</td><td>'+str(len(p['scrutins']))+'</td><td>'+details+'</td></tr>')
    return '''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Votes par personnalité — V25</title>
<style>body{max-width:1150px;margin:2rem auto;padding:1rem;font:16px system-ui;color:#203347}table{border-collapse:collapse;width:100%}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #dce3e9;padding:.7rem}td:nth-child(5){max-width:520px}li{margin:.5rem 0}input{padding:10px;max-width:420px;width:90%}summary{cursor:pointer}.note{padding:1rem;background:#edf4fa;border-radius:10px}</style>
<h1>Votes nominatifs : correspondances avec la Boussole — V25</h1><p class="note">Correspondances par noms complets strictement égaux dans les données officielles. Les votes ne sont pas des opinions générales. Aucune position -2 à +2 n'est calculée. Échantillon : les 1 200 derniers scrutins indexés, non l'ensemble de la carrière.</p>
<p>Mis à jour : '''+html.escape(result['generatedAt'])+'''</p><label>Filtrer : <input id="q" oninput="filterRows()"></label><table><thead><tr><th>Personnalité</th><th>Correspondance</th><th>Identifiant AN</th><th>Votes retrouvés</th><th>Scrutins et objets</th></tr></thead><tbody id="rows">'''+''.join(rows)+'''</tbody></table><script>function filterRows(){let q=document.getElementById('q').value.toLowerCase();for(let r of document.getElementById('rows').rows)r.hidden=!r.textContent.toLowerCase().includes(q)}</script></html>'''


def run():
    base=json.loads(BASE.read_text(encoding='utf-8'))
    votes=json.loads(VOTES.read_text(encoding='utf-8'))
    raw=download_actors()
    actors=parse_archive(raw)
    if len(actors)<50: raise RuntimeError(f'Archive officielle non reconnue : {len(actors)} acteurs')
    result=join_votes(base,votes,actors)
    result['actorsArchiveSha256']=hashlib.sha256(raw).hexdigest()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    HTML.write_text(render(result),encoding='utf-8')
    print('V25:',len(actors),'acteurs;',sum(p['statut']=='identifiant_unique' for p in result['personnalites']),'correspondances uniques;',sum(len(p['scrutins']) for p in result['personnalites']),'votes liés')

if __name__=='__main__':run()
