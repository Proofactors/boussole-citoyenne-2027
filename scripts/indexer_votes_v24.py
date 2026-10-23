#!/usr/bin/env python3
"""V24: indexe les votes nominatifs AN officiels; aucune attribution d'opinion politique.
Source : https://data.assemblee-nationale.fr/travaux-parlementaires/votes
Fichier officiel JSON ZIP 17e legislature. Exécutable par GitHub Actions Python stdlib.
"""
import datetime as dt
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'votes_an_v24.json'
PAGE=ROOT/'votes.html'
SOURCE='https://data.assemblee-nationale.fr/static/openData/repository/17/loi/scrutins/Scrutins.json.zip'
MAX_ZIP=45*1024*1024
MAX_MEMBER=2*1024*1024
MAX_MEMBERS=18000
MAX_RECENT=1200


def textval(v):
    if isinstance(v,(str,int,float)):return str(v)
    if isinstance(v,dict):return str(v.get('#text',v.get('value','')))
    return ''

def aslist(obj):
    if obj is None:return []
    return obj if isinstance(obj,list) else [obj]

def parse_vote(data):
    """Retourne un scrutin avec votants par acteurRef, sans déduire le sens d'une politique."""
    s=data.get('scrutin',data)
    if not isinstance(s,dict):return None
    number=textval(s.get('numero',''))
    date=textval(s.get('dateScrutin',''))[:10]
    title=textval(s.get('titre',''))
    uid=textval(s.get('uid',''))
    # L'open data AN répartit les groupes et les votes en decompteNominatif.
    votes=[]
    aliases={'pours':'pour','contres':'contre','abstentions':'abstention',
             'nonVotants':'non-votant','nonvotants':'non-votant'}
    def visit(n,category=None):
        if isinstance(n,list):
            for v in n:visit(v,category)
        elif isinstance(n,dict):
            if category and 'acteurRef' in n:
                ref=textval(n.get('acteurRef'))
                if re.fullmatch(r'PA\d+',ref):votes.append({'acteurRef':ref,'vote':category})
            for k,v in n.items():
                nextcat=aliases.get(k,category)
                visit(v,nextcat)
    visit(s.get('ventilationVotes',{}))
    # Une même référence ne doit pas recevoir deux interprétations contradictoires.
    groups={}
    for v in votes:
        aid=v['acteurRef'];val=v['vote']
        if aid in groups and groups[aid]!=val:groups[aid]='conflit'
        else:groups[aid]=val
    if not number and not uid:return None
    return {'uid':uid,'numero':number,'date':date,'titre':title,
            'votes':[{'acteurRef':aid,'vote':val} for aid,val in sorted(groups.items())]}


def download_zip(url=SOURCE,opener=urllib.request.urlopen):
    if url!=SOURCE:raise ValueError('Source non autorisée')
    req=urllib.request.Request(url,headers={'User-Agent':'Boussole-citoyenne-2027/24 (donnees publiques)'})
    with opener(req,timeout=35) as res:
        raw=res.read(MAX_ZIP+1)
    if len(raw)>MAX_ZIP:raise ValueError('Archive trop volumineuse')
    if not zipfile.is_zipfile(io.BytesIO(raw)):raise ValueError('Le contenu recu nest pas un ZIP')
    return raw


def index_zip(raw,limit=MAX_RECENT):
    parsed=[]; count=0;bad=0
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=[x for x in z.infolist() if x.filename.lower().endswith('.json') and not x.is_dir()]
        if len(names)>MAX_MEMBERS:raise ValueError('Trop de fichiers dans archive')
        for info in names:
            if info.file_size>MAX_MEMBER:bad+=1;continue
            try:
                d=json.loads(z.read(info).decode('utf-8-sig'))
                item=parse_vote(d)
                if item:parsed.append(item);count+=1
            except (ValueError,UnicodeError,RuntimeError,zipfile.BadZipFile):bad+=1
    parsed.sort(key=lambda s:(s['date'],int(s['numero']) if s['numero'].isdigit() else 0),reverse=True)
    return parsed[:limit],count,bad


def public_html(dataset):
    lines=[]
    for item in dataset['scrutins']:
        labels={'pour':0,'contre':0,'abstention':0,'non-votant':0,'conflit':0}
        for vote in item['votes']:labels[vote['vote']]=labels.get(vote['vote'],0)+1
        title=html.escape(item['titre'])
        lines.append(f'<tr><td>{html.escape(item["date"])}</td><td>{html.escape(item["numero"])}</td><td>{title}</td><td>{len(item["votes"])}</td><td>{labels["pour"]}/{labels["contre"]}/{labels["abstention"]}</td></tr>')
    body='\n'.join(lines)
    return f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Scrutins AN — Boussole V24</title><style>body{{font-family:system-ui;max-width:1150px;margin:auto;padding:24px;color:#203347}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:10px;text-align:left}}tr:hover{{background:#f6f8fa}}.notice{{background:#edf4fa;padding:14px;border-radius:9px}}input{{padding:10px;width:min(95%,440px)}}</style><h1>Scrutins publics — Assemblée nationale</h1><p class="notice">Inventaire documentaire V24. Ce tableau ne mesure <strong>aucune proximité politique</strong> et ne modifie pas la base de la Boussole. Source : <a href="https://data.assemblee-nationale.fr/travaux-parlementaires/votes">Assemblée nationale — données ouvertes</a>. Actualisé : {html.escape(dataset['generatedAt'])}.</p><p>{len(dataset['scrutins'])} scrutins récents affichés, {dataset['totalParsed']} scrutins reconnus dans l'archive, {dataset['invalid']} entrées ignorées.</p><label>Rechercher un scrutin : <input id="q" oninput="filter()"></label><table><thead><tr><th>Date</th><th>N°</th><th>Objet</th><th>Votes reconnus</th><th>Pour/contre/abst.</th></tr></thead><tbody id="rows">{body}</tbody></table><script>function filter(){{let q=document.getElementById('q').value.toLowerCase();for(let r of document.getElementById('rows').rows)r.hidden=!r.textContent.toLowerCase().includes(q)}}</script></html>'''


def run():
    raw=download_zip()
    items,total,bad=index_zip(raw)
    d={'schemaVersion':'24.0','source':SOURCE,'archiveSha256':hashlib.sha256(raw).hexdigest(),
       'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
       'totalParsed':total,'invalid':bad,'scrutins':items,
       'editorialStatus':'scrutins officiels indexés, aucune position politique inférée'}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    PAGE.write_text(public_html(d),encoding='utf-8')
    print('AN V24: ',total,'scrutins; affiches',len(items),'erreurs',bad)

if __name__=='__main__':run()
