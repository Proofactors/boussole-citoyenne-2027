#!/usr/bin/env python3
# V35: ingest official-source snapshots, extract tentative issue evidence; NEVER assign scores.
# Network access restricted to allowlisted hosts
from __future__ import annotations
import json, re, html, pathlib, hashlib, datetime as dt, unicodedata
from collections import defaultdict
from html.parser import HTMLParser
from urllib.parse import urlparse
try:
    from surveiller_programmes_v33 import ROOT, CFG, public_url, GuardedRedirect, MAX_BYTES
except ImportError:
    from scripts.surveiller_programmes_v33 import ROOT, CFG, public_url, GuardedRedirect, MAX_BYTES
import urllib.request

QUESTIONS=ROOT/'config/questions_v35.json'
OUT=ROOT/'data/programmes_preuves_v35.json'
HTML=ROOT/'programmes-analyse.html'
STATE=ROOT/'data/programmes_versions_v35.json'
MAX_SNIPPETS_PER_SOURCE=35
MAX_CANDIDATES_PER_QUESTION=8

# Exact policy terms, deliberately not inferred from candidate's entire platform.
# Match alone never denotes approval/disapproval, endorsement or stance.
TERM_ALIASES={
 'retraite-62':['retraite a 62 ans','depart a 62 ans'],
 'abroger-2023':['reforme des retraites','abrogation de la reforme'],
 'smic':['smic','salaire minimum'],
 'isf':['impot sur la fortune','isf'],
 'taxe-zucman':['taxe zucman'],
 'nucleaire':['reacteurs nucleaires','centrales nucleaires','energie nucleaire'],
 'ric':['referendum d initiative citoyenne','ric'],
 'vie-republique':['sixieme republique','6e republique','vie republique'],
 'fin-de-vie':['aide a mourir','fin de vie','euthanasie'],
 'immigration':['immigration legale','immigration'],
 'proportionnelle':['scrutin proportionnel','representation proportionnelle'],
 'ukraine':['aide a l ukraine','soutien a l ukraine'],
 'pesticides':['glyphosate','pesticides'],
 'eolien':['eoliennes','eolien'],
 'deserts-medicaux':['deserts medicaux'],
 'droit-du-sol':['droit du sol'],
 'uniforme':['uniforme scolaire','uniforme a l ecole'],
 'cannabis':['legalisation du cannabis','cannabis'],
 'encadrement-loyers':['encadrement des loyers','gel des loyers'],
 'tva-energie':['tva sur l energie','tva sur les produits'],
 'ame':['aide medicale d etat'],
 'zan':['zero artificialisation nette'],
 'palestine':['palestine'],
 'otan':['otan'],
 'parcoursup':['parcoursup'],
}
STOP={'pour','contre','avec','dans','plus','moins','doit','etre','faut','une','des','les','aux','sur','pas','tout','tous','leur','sans','qui','que','est','par','lui','elle','france','francais','francaise','politique','publique','public','national','nationale','deux','doivent','faire','maintenir','reduire','renforcer','interdire','creer','augmenter','autoriser'}
def norm(s):
    s=unicodedata.normalize('NFKD',s.lower())
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+',' ',s).strip()
class Paragraphs(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.current=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript','nav','footer','header'):self.skip+=1
        if not self.skip and tag in ('p','li','h1','h2','h3','h4','article','section','br'):self.flush()
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript','nav','footer','header') and self.skip:self.skip-=1
        elif not self.skip and tag in ('p','li','h1','h2','h3','h4','article','section'):self.flush()
    def handle_data(self,s):
        if not self.skip:self.current.append(s)
    def flush(self):
        s=re.sub(r'\s+',' ',' '.join(self.current)).strip();self.current=[]
        if 28<=len(s)<=1100:self.parts.append(s)
    def finish(self):self.flush();return list(dict.fromkeys(self.parts))
def eligible(q,p):
    t=norm(p);qid=q['id']; aliases=[norm(x) for x in TERM_ALIASES.get(qid,[])]
    # No single common token keyword matches (e.g. "france", "national").
    explicit=any(re.search(r'(?<!\w)'+re.escape(k)+r'(?!\w)',t) for k in aliases if len(k)>3)
    title_tokens=[w for w in norm(q['title']).split() if len(w)>=5 and w not in STOP]
    if not explicit and len(title_tokens)>=2:
        explicit=sum(bool(re.search(r'(?<!\w)'+re.escape(w)+r'(?!\w)',t)) for w in title_tokens)>=2
    return explicit

def gather(config,questions,fetch=None,prior=None,now=None):
    now=now or dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    prior=prior or {}; versions=dict(prior.get('sources',{})); evidence=[]; diagnostics=[]
    ids={q['id'] for q in questions};assert len(ids)==150
    for src in config['sources']:
        sid=src['personnalite_id']; uri=src['url']; host=urlparse(uri).hostname or ''
        allowed={h.lower().removeprefix('www.') for h in src['domaines_autorises']}
        if not public_url(uri,allowed):
            diagnostics.append({'id':sid,'statut':'adresse_non_validee','url':uri});continue
        try:
            if fetch: raw,ctype=fetch(uri)
            else:
                opener=urllib.request.build_opener(GuardedRedirect(allowed))
                with opener.open(urllib.request.Request(uri,headers={'User-Agent':'BoussoleCitoyenne/35 (veille documentaire)','Accept':'text/html,application/pdf'}),timeout=15) as response:
                    raw=response.read(MAX_BYTES+1);ctype=response.headers.get('Content-Type','')
            if len(raw)>MAX_BYTES:raise ValueError('taille_excessive')
            digest=hashlib.sha256(raw).hexdigest()
            old=versions.get(sid,{})
            changed=bool(old.get('sha256') and old['sha256']!=digest)
            versions[sid]={'sha256':digest,'date_derniere_verification':now,'date_changement':now if changed or not old else old.get('date_changement',now),'url':uri,'nature':src['nature']}
            if raw.startswith(b'%PDF') or 'pdf' in ctype.lower():
                # Binary PDFs are recorded as watched but NOT called extracted; pypdf optional in CI.
                try:
                    from pypdf import PdfReader
                    import io
                    reader=PdfReader(io.BytesIO(raw));pieces=[(pg.extract_text() or '') for pg in list(reader.pages)[:30]]
                    paragraphs=[x.strip() for page in pieces for x in re.split(r'(?<=[.!?])\s+|\n{2,}',page) if 28<=len(x.strip())<=1100]
                    extraction='pdf_texte_partiel_30_pages'
                except Exception:paragraphs=[];extraction='pdf_non_extrait'
            elif 'html' in ctype.lower() or raw[:30].lower().find(b'<html')>=0 or raw[:30].lower().find(b'<!doctype')>=0:
                parser=Paragraphs();parser.feed(raw.decode('utf-8','replace'));paragraphs=parser.finish();extraction='html'
            else:paragraphs=[];extraction='format_non_pris_en_charge'
            count=0
            for q in questions:
                if count>=MAX_SNIPPETS_PER_SOURCE:break
                matched=[p for p in paragraphs if eligible(q,p)]
                if matched:
                    for p in matched[:2]:
                        evidence.append({'personnalite_id':sid,'personnalite':src['personnalite'],'question_id':q['id'],'question':q['text'],'theme':q['theme'],'extrait_a_verifier':p[:650],'source_url':uri,'source_sha256':digest,'date_collecte':now,'nature_source':src['nature'],'qualification':'correspondance_lexicale_non_interpretee','position_suggeree':None,'statut':'a_verifier'})
                        count+=1
            diagnostics.append({'id':sid,'statut':'consulte','changement_detecte':changed,'extraction':extraction,'passages':len(paragraphs),'indices':count,'url':uri})
        except Exception as exc:diagnostics.append({'id':sid,'statut':'echec_consultation','diagnostic':type(exc).__name__+': '+str(exc)[:110],'url':uri})
    evidence.sort(key=lambda x:(x['question_id'],x['personnalite_id']))
    return {'schemaVersion':35,'date_generation':now,'nombre_questions':len(questions),'avertissement':'Rapprochements lexicaux non vérifiés. Aucune approbation, opposition, position ou score politique déduit. Une page source ne remplace pas un programme complet.','sources':diagnostics,'rapprochements':evidence}, {'schemaVersion':35,'sources':versions}

def render(data,questions):
    esc=lambda x:html.escape(str(x),quote=True)
    grouped=defaultdict(list)
    for r in data['rapprochements']:grouped[r['question_id']].append(r)
    cards=[]
    for q in questions:
        group=grouped.get(q['id'],[])
        snippets=''.join('<article class="proof"><strong>'+esc(r['personnalite'])+'</strong> · <small>'+esc(r['nature_source'].replace('_',' '))+'</small><blockquote>'+esc(r['extrait_a_verifier'])+'</blockquote><a target="_blank" rel="noopener noreferrer" href="'+esc(r['source_url'])+'">Page source ↗</a><p class="muted">Correspondance lexicale non validée · Position non attribuée</p></article>' for r in group[:MAX_CANDIDATES_PER_QUESTION])
        if not snippets:snippets='<p class="muted">Aucune correspondance dans les documents récupérés.</p>'
        cards.append('<details class="question" data-search="'+esc(norm(q['title']+' '+q['text']+' '+' '.join(r['personnalite'] for r in group)))+'"><summary><b>'+esc(q['title'])+'</b> <span>'+esc(q['theme'])+' · '+str(len(group))+' extrait(s)</span></summary><p>'+esc(q['text'])+'</p>'+snippets+'</details>')
    return '''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Programmes et 150 questions — V35</title><style>*{box-sizing:border-box}body{margin:0;background:#f4f7fb;color:#172438;font:16px/1.55 system-ui,-apple-system,sans-serif}main{max-width:1020px;margin:auto;padding:clamp(12px,3vw,35px)}h1{font-size:clamp(1.35rem,4vw,2rem)}.intro,.question{background:white;border:1px solid #d8e1ef;border-radius:12px;padding:clamp(12px,2vw,22px);margin:12px 0;overflow-wrap:anywhere}.question summary{cursor:pointer;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.question summary span,.muted,small{color:#526276}.proof{border-top:1px solid #d8e1ef;padding:12px 0}.proof blockquote{margin:9px 0;padding:9px 12px;border-left:3px solid #2866a0;background:#f5f8fe}a{color:#13578c}input{width:100%;max-width:620px;padding:13px;border:1px solid #9baabe;border-radius:8px;font:inherit}@media(max-width:480px){body{font-size:15px}.question summary{display:block}.question summary span{display:block}}</style></head><body><main><h1>Programmes officiels × 150 questions</h1><section class="intro"><p>Registre automatique d'indices textuels, pas un registre de positions politiques. Un rapprochement de mots ne prouve ni approbation ni opposition. Les documents HTML ou PDF accessibles sont analysés dans des limites de taille. Les autres questions restent visibles.</p><p><b>'''+str(len(questions))+''' questions</b> · <b>'''+str(len(data['rapprochements']))+''' extraits indicatifs</b> · <b>0 position attribuée automatiquement</b>.</p><label for="search">Filtrer par question, thème ou personnalité</label><p><input id="search" type="search" placeholder="Ex. retraites, santé, écologie…"></p><p><a href="programmes.html">Catalogue des programmes</a> · <a href="./">Retour à la Boussole</a></p></section>'''+''.join(cards)+'''</main><script>document.getElementById('search').addEventListener('input',e=>{const v=e.target.value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');for(const card of document.querySelectorAll('.question'))card.hidden=!card.dataset.search.includes(v)});</script></body></html>'''
def main():
    config=json.loads(CFG.read_text('utf8'));questions=json.loads(QUESTIONS.read_text('utf8'))
    previous=json.loads(STATE.read_text('utf8')) if STATE.exists() else None
    report,version=gather(config,questions,prior=previous)
    OUT.parent.mkdir(exist_ok=True,parents=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    STATE.write_text(json.dumps(version,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    HTML.write_text(render(report,questions),encoding='utf8')
    print('V35 :',len(questions),'questions ;',len(report['rapprochements']),'indices ; 0 score changé')
if __name__=='__main__':main()
