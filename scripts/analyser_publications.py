#!/usr/bin/env python3
"""Triage automatisé des publications collectées. Ne publie aucune position politique.
Aucun appel à une IA externe ni utilisation de secret. Les citations sont tirées de
l'extrait RSS, non présumées provenir d'une déclaration de la personnalité.
"""
import csv
import datetime as dt
import html
import json
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[1]
STOP = {'avoir','faire','sont','pour','dans','avec','sans','contre','entre','leur','leurs','cette','ainsi','sera','seront','plus','moins','doit','faut','politique','france','francais','francaise','mettre','place','grand','grande','toute','tous','toutes','comme','selon','apres','avant','cette','cela','question','etat','public','publique','part','afin'}

def load(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(s).casefold()) if not unicodedata.combining(c))

def words(s):
    return {w for w in re.findall(r'[a-z]{5,}',norm(s)) if w not in STOP}

def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', str(text)) if len(s.strip())>20]

def analyse(item,base):
    title=str(item.get('title') or '')
    excerpt=str(item.get('excerpt') or '')[:2500]
    full=(title+' '+excerpt).strip()
    nf=norm(full)
    people=[]
    for slug in base['positions']:
        name=norm(slug.replace('-',' '))
        if re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',nf):
            people.append(slug)
    # Les rapprochements thématiques ne constituent PAS une preuve de prise de position.
    qhits=[]
    fw=words(full)
    for q in base['affirmations']:
        qwords=words(q.get('text','')+' '+q.get('title',''))
        matches=sorted(fw & qwords)
        if len(matches)>=2:
            qhits.append({'questionId':q['id'],'theme':q.get('theme',''), 'keywords':matches[:8], 'keywordCount':len(matches)})
    qhits.sort(key=lambda q:(-q['keywordCount'],q['questionId']))
    # La présence d'un nom ET de termes en rapport avec une question ne suffit jamais.
    if people and qhits: rank='a_examiner_en_priorite'
    elif people or qhits: rank='a_qualifier'
    else: rank='signal_non_qualifie'
    quotes=sentences(excerpt)[:3]
    if not quotes and excerpt.strip(): quotes=[excerpt.strip()[:500]]
    return {
        'id':item.get('id'), 'title':title, 'url':item.get('url'), 'sourcePublishedAt':item.get('sourcePublishedAt'),
        'priorite':rank, 'personnalitesMentionnees':people[:12], 'questionsPotentielles':qhits[:8],
        'extraitsRSS':quotes, 'positionProposee':None,
        'statutPreuve':'non_verifiee', 'eligiblePublicationAutomatique':False,
        'avertissement':'Correspondances automatiques sur titre/résumé RSS; aucune citation attribuée à une personnalité et aucun positionnement déduit.'
    }

def run(root=ROOT):
    base=load(root/'boussole_2027_positions.json',{})
    queue=load(root/'data/queue.json',{})
    if not isinstance(queue,dict) or not isinstance(base.get('affirmations'),list) or not isinstance(base.get('positions'),dict):
        raise ValueError('Fichiers base ou file de veille invalides')
    analysis=[analyse(item,base) for item in queue.values() if isinstance(item,dict)]
    analysis.sort(key=lambda a:(a.get('sourcePublishedAt') or '',a.get('id') or ''),reverse=True)
    summary={k:sum(a['priorite']==k for a in analysis) for k in ('a_examiner_en_priorite','a_qualifier','signal_non_qualifie')}
    path=root/'data/propositions_analyse.json'
    dump(path,{'schemaVersion':1,'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'total':len(analysis), 'statistiques':summary,'publicationAutomatiquePositions':False,'propositions':analysis})
    csvfile=root/'data/propositions_analyse.csv'
    with csvfile.open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.writer(file,delimiter=';')
        writer.writerow(['Priorité','Publication','Personnalités mentionnées','Questions potentielles','URL','Date','Extrait RSS','Statut'])
        for a in analysis:
            writer.writerow([a['priorite'],a['title'],', '.join(a['personnalitesMentionnees']), ', '.join(q['questionId'] for q in a['questionsPotentielles']),a['url'],a['sourcePublishedAt'],' | '.join(a['extraitsRSS']),a['statutPreuve']])
    print(f"Analyse: {len(analysis)} publications; {summary}; aucune modification des positions")
    return analysis

if __name__=='__main__':run()
