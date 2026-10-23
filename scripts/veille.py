#!/usr/bin/env python3
"""Boussole V11: collect RSS/Atom into a review queue, without automatically assigning stances."""
import argparse, datetime as dt, hashlib, html, json, pathlib, re, urllib.parse, urllib.request, uuid, xml.etree.ElementTree as ET
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent
UTC = dt.timezone.utc

def readj(path, default):
    p=pathlib.Path(path)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default

def writej(path, data):
    p=pathlib.Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def clean(s):
    return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]*>',' ',s or ''))).strip()

def get(node, names):
    for n in names:
        e=node.find(n)
        if e is not None and e.text: return clean(e.text)
    return ''

def parse_feed(raw):
    root=ET.fromstring(raw)
    items=[]
    if root.tag.endswith('rss') or root.find('channel') is not None:
        for item in root.findall('.//channel/item'):
            items.append({'title':get(item,['title']), 'url':get(item,['link']), 'date':get(item,['pubDate']), 'excerpt':get(item,['description'])})
    elif root.tag.endswith('feed'):
        ns='{http://www.w3.org/2005/Atom}'
        for item in root.findall(ns+'entry'):
            link=next((e.get('href','') for e in item.findall(ns+'link') if e.get('rel','alternate')=='alternate'), '')
            link=link or next((e.get('href','') for e in item.findall(ns+'link')), '')
            items.append({'title':get(item,[ns+'title']), 'url':link, 'date':get(item,[ns+'published',ns+'updated']), 'excerpt':get(item,[ns+'summary',ns+'content'])})
    else: raise ValueError('Format RSS/Atom non reconnu')
    return items

def keywords(value):
    return {t for t in re.findall(r'[a-zàâäçéèêëîïôöùûüÿœæ-]{5,}',value.lower()) if t not in {'doit','faut','pour','dans','avec','cette','leurs','entre','plusieurs','politique','être','mettre','faire','contre','avoir'}}

def scan(base, queue, feeds, offline=False):
    persons=base['positions']; questions=base['affirmations']; new=[]; faults=[]
    for source in feeds:
        url=source.get('url',''); fid=source.get('id','inconnu')
        try:
            if not offline and urllib.parse.urlsplit(url).scheme != 'https':
                raise ValueError('HTTPS obligatoire pour la collecte réseau')
            if offline:
                filepath=ROOT/source['fixture']; raw=filepath.read_bytes()
            else:
                req=urllib.request.Request(url,headers={'User-Agent':'BoussoleCitoyenne2027/11 (veille documentaire)'})
                with urllib.request.urlopen(req,timeout=15) as r:
                    if int(r.headers.get('Content-Length','0'))>2_000_000: raise ValueError('Flux trop volumineux')
                    raw=r.read(2_000_001)
                    if len(raw)>2_000_000: raise ValueError('Flux trop volumineux')
            for item in parse_feed(raw):
                target=item['url']; parsed=urllib.parse.urlsplit(target)
                if parsed.scheme not in ('https','http') or not parsed.netloc: continue
                uid=hashlib.sha256((fid+'|'+target.split('#')[0]).encode()).hexdigest()[:24]
                if uid in queue: continue
                content=' '.join([item['title'],item['excerpt']]).lower()
                possible=[]
                for slug in persons:
                    name=slug.replace('-',' ')
                    if name in content: possible.append(slug)
                ranked=sorted(((len(keywords(q['text']+' '+q.get('title','')) & keywords(content)),q['id']) for q in questions),reverse=True)
                candidates=[qid for score,qid in ranked if score>=2][:5]
                record={'id':uid,'status':'a_examiner','feed':fid,'title':item['title'],'url':target,'sourcePublishedAt':item['date'],
                   'excerpt':item['excerpt'][:1000],'personalitiesSuggested':possible,'questionsSuggested':candidates,
                   'candidateStance':None,'review':None,'detectedAt':dt.datetime.now(UTC).isoformat(),
                   'warning':'Correspondances indicatives; titre et résumé RSS ne constituent pas une preuve suffisante.'}
                queue[uid]=record; new.append(record)
        except (OSError,ValueError,ET.ParseError,KeyError) as e: faults.append({'feed':fid,'error':str(e)})
    return new,faults

def export_review(queue,path):
    import csv
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        fields=['id','status','feed','title','url','sourcePublishedAt','personalitiesSuggested','questionsSuggested','excerpt']
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',delimiter=';');w.writeheader()
        for r in queue.values():
            r=dict(r);r['personalitiesSuggested']=', '.join(r['personalitiesSuggested']);r['questionsSuggested']=', '.join(r['questionsSuggested']);w.writerow(r)

def main():
    p=argparse.ArgumentParser(description=__doc__); s=p.add_subparsers(dest='cmd',required=True)
    q=s.add_parser('scan');q.add_argument('--fixture',action='store_true',help='Utiliser les flux locaux fictifs (aucun accès réseau)');q.add_argument('--feeds',default='config/feeds.json')
    r=s.add_parser('review');r.add_argument('id');r.add_argument('--status',choices=['valide','rejete','a_completer'],required=True);r.add_argument('--personality');r.add_argument('--question');r.add_argument('--stance',type=int);r.add_argument('--evidence');r.add_argument('--date');r.add_argument('--reviewer',required=True)
    s.add_parser('publish');s.add_parser('status')
    a=p.parse_args(); base=readj(ROOT/'data/boussole_2027_positions.json',{}); queue_path=ROOT/'output/queue.json'; queue=readj(queue_path,{})
    if a.cmd=='scan':
        feeds=readj(ROOT/a.feeds,[]); new, faults=scan(base,queue,feeds,a.fixture);writej(queue_path,queue)
        export_review(queue,ROOT/'output/revue.csv')
        print(json.dumps({'new':len(new),'total':len(queue),'errors':faults},ensure_ascii=False))
    elif a.cmd=='status':
        print(json.dumps({'total':len(queue),'statuses':{s:sum(x['status']==s for x in queue.values()) for s in sorted({x['status'] for x in queue.values()})}},ensure_ascii=False))
    elif a.cmd=='review':
        if a.id not in queue: p.error('ID inconnu'); item=queue[a.id]
        item=queue[a.id]
        if a.status=='valide':
            if not all([a.personality,a.question,a.evidence,a.date]) or a.stance is None: p.error('Validation : personnalité, question, stance, citation et date obligatoires')
            if a.personality not in base['positions']: p.error('Personnalité inconnue')
            if a.question not in {x['id'] for x in base['affirmations']}: p.error('Question inconnue')
            if a.stance not in {-2,-1,0,1,2}: p.error('Stance hors intervalle -2..2')
            try: dt.date.fromisoformat(a.date)
            except ValueError: p.error('Date attendue au format YYYY-MM-DD')
            if len(a.evidence.strip())<20: p.error('Citation/preuve trop courte')
        item['status']=a.status; item['review']={'reviewer':a.reviewer,'reviewedAt':dt.datetime.now(UTC).isoformat(),'personality':a.personality,'question':a.question,'stance':a.stance,'evidence':a.evidence,'date':a.date}
        writej(queue_path,queue);export_review(queue,ROOT/'output/revue.csv');print('Revue enregistrée :',a.id,a.status)
    elif a.cmd=='publish':
        # Publications only from explicit reviewed records. Never automatically infer a political stance.
        from copy import deepcopy
        updated=deepcopy(base); changes=[]
        for rec in queue.values():
            if rec['status']!='valide' or not rec.get('review'):continue
            rev=rec['review'];person=rev['personality']; qid=rev['question'];old=updated['positions'][person].get(qid)
            new={'stance':rev['stance'],'summary':'Citation validée : '+rev['evidence'], 'source':rec['url'], 'sourceTitle':rec['title'],'date':rev['date'],'year2022':rev['date'].startswith('2022')}
            if old!=new:
                updated['positions'][person][qid]=new
                changes.append({'item':rec['id'],'personality':person,'question':qid,'previous':old,'new':new,'reviewer':rev['reviewer']})
        if not changes:
            print('Aucune position validée à publier; base inchangée.');return
        import copy
        out=ROOT/'output/published';out.mkdir(parents=True,exist_ok=True)
        datafile='boussole_2027_positions_v13.json'; b=(json.dumps(updated,ensure_ascii=False,indent=2)+'\n').encode('utf-8'); (out/datafile).write_bytes(b)
        latest=dt.datetime.now(UTC).isoformat(); manifest={'schemaVersion':1,'datasetVersion':dt.datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')+'-v13','publishedAt':latest,'dataFile':datafile,'sha256':hashlib.sha256(b).hexdigest(),'questions':len(updated['affirmations']),'personalities':len(updated['positions']),'positions':sum(1 for v in updated['positions'].values() for record in v.values() if record is not None),'editorialStatus':'validation_partielle','description':'Seules les modifications listées au journal ont été validées; le reste de la base historique demeure non audité.'}
        writej(out/'boussole_2027_manifest_v13.json',manifest);writej(out/'journal_changements.json',changes)
        print('Publication:',len(changes),'changement(s); SHA-256',manifest['sha256'])

if __name__=='__main__':main()
