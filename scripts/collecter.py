#!/usr/bin/env python3
"""Veille automatique RSS : ne déduit ni ne publie de positions non validées."""
import datetime as dt, hashlib, json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import veille

def read(p,default):
    return json.loads(p.read_text(encoding='utf8')) if p.exists() else default

def put(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

base=read(ROOT/'boussole_2027_positions.json',{})
queue_file=ROOT/'data/queue.json'
queue=read(queue_file,{})
feeds=read(ROOT/'config/feeds.json',[])
items,errors=veille.scan(base,queue,feeds,offline=False)
put(queue_file,queue)
put(ROOT/'data/status.json',{'lastScan':dt.datetime.now(dt.timezone.utc).isoformat(),'newArticles':len(items),'pendingReview':sum(1 for x in queue.values() if x.get('status')=='a_examiner'),'errors':errors,'warning':'La collecte ne modifie pas les positions politiques.'})
print('Nouvelles publications:',len(items),'Erreurs:',len(errors))
