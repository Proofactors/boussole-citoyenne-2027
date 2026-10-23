#!/usr/bin/env python3
"""V30 – rapprochement EXPLORATOIRE de scrutins avec des questions.
Aucun score, aucune nouvelle position politique n'est produit. Le titre du
scrutin seul est insuffisant pour qualifier le sens substantiel d'un amendement.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'boussole_2027_positions.json'
JOINED = ROOT / 'data/rapprochement_votes_v25.json'
OUT = ROOT / 'data/propositions_v30.json'
PAGE = ROOT / 'propositions.html'

# Déclencheurs stricts et ciblés. Un terme générique (ex. sécurité sociale)
# n'est volontairement PAS une preuve de pertinence pour une question.
RULES = {
 'retraite-62': [(r'age legal', r'62 ans'), (r'depart a la retraite', r'62 ans')],
 'abroger-2023': [(r'abrogation', r'reforme des retraites'), (r'abroger', r'reforme des retraites')],
 'capitalisation': [(r'retraite', r'capitalisation')],
 'smic': [(r'\bsmic\b', r'augment|revaloris|hausse')],
 'isf': [(r'impot sur la fortune',), (r'\bisf\b',)],
 'droit-du-sol': [(r'droit du sol',)],
 'peines-planchers': [(r'peines? planchers?',)],
 'nucleaire': [(r'reacteurs? nucleaires?',)],
 'thermique-2035': [(r'voitures? thermiques?', r'2035')],
 'proportionnelle': [(r'scrutin proportionnel',), (r'proportionnelle', r'legislativ')],
 'ric': [(r'referendum d initiative citoyenne',)],
 'fin-de-vie': [(r'aide a mourir',), (r'fin de vie', r'aide')],
 'cannabis': [(r'cannabis', r'legalis')],
 'tva-energie': [(r'\btva\b', r'energie|electricite|gaz|carburant')],
 'otan': [(r'otan', r'commandement integre')],
 'ukraine': [(r'ukraine', r'aide militaire|livraison d armes')],
 'zan': [(r'zero artificialisation nette',), (r'\bzan\b', r'artificialis')],
}

def normalized(s):
    s = unicodedata.normalize('NFKD', str(s).casefold())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', s)).strip()

def candidate_question_ids(title, valid_ids):
    t=normalized(title)
    return [qid for qid,pairs in RULES.items() if qid in valid_ids and any(all(re.search(p,t) for p in pair) for pair in pairs)]

def scrutiny_type(title):
    t=normalized(title)
    if 'suppression' in t or 'supprimer' in t: return 'amendement_de_suppression'
    if 'amendement' in t: return 'amendement'
    if 'article' in t: return 'article'
    return 'indetermine'

def build(base,joined):
    questions={q['id']:q for q in base['affirmations']}
    # Proposer une ligne pour chaque couple scrutin/personnalité/question.
    proposals=[]; seen=set(); total_votes=0; distinct_scrutins=set()
    for p in joined['personnalites']:
        if p.get('statut')!='identifiant_unique' or not p.get('acteurRef'): continue
        for vote in p.get('scrutins',[]):
            total_votes+=1
            vid=str(vote.get('numero',''))
            title=str(vote.get('titre',''))
            date=str(vote.get('date',''))
            if not vid or not title:continue
            distinct_scrutins.add((date,vid))
            for qid in candidate_question_ids(title,questions):
                key=(p['id'],date,vid,qid)
                if key in seen: continue
                seen.add(key)
                status='à_documenter'
                proposals.append({
                    'personnaliteId':p['id'],'acteurRef':p['acteurRef'],
                    'questionId':qid,'question':questions[qid]['text'],
                    'scrutinNumero':vid,'date':date,'objet':title,
                    'vote':vote.get('vote','inconnu'),
                    'typeScrutin':scrutiny_type(title),
                    'sourceScrutin':f'https://www.assemblee-nationale.fr/dyn/17/scrutins/{vid}',
                    'statut':status,
                    'niveauPreuve':'signalement_par_intitule_uniquement',
                    'justification':'Correspondance lexicale avec l’intitulé du scrutin ; contenu exact non vérifié.',
                    'positionProposee':None,
                    'verificationRequise':['texte intégral et dispositif du scrutin ou amendement',
                      'sens exact de la mesure', 'mandat et attribution du vote',
                      'concordance avec la formulation de la question',
                      'éventuelles sources contradictoires']
                })
    proposals.sort(key=lambda x:(x['date'],int(x['scrutinNumero']) if x['scrutinNumero'].isdigit() else 0),reverse=True)
    return {'schemaVersion':'30.0', 'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
      'sources':{'votes':joined.get('votesSource'),'acteurs':joined.get('actorsSource')},
      'baseSha256':hashlib.sha256(json.dumps(base,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
      'totalVotesLies':total_votes,'scrutinsDistincts':len(distinct_scrutins),
      'questionsAvecRegles':len(set(RULES).intersection(questions)),
      'propositions':proposals,'nombrePropositions':len(proposals),
      'important':'AUCUNE position n’est créée ni modifiée. Les signalements lexicaux ne constituent pas des preuves politiques.'}

def render(out):
    e=html.escape
    rows=[]
    for x in out['propositions'][:1000]:
        e=html.escape
        rows.append('<tr><td>'+e(x['personnaliteId'])+'</td><td>'+e(x['date'])+'</td><td><a href="'+e(x['sourceScrutin'],quote=True)+'" rel="noopener noreferrer" target="_blank">'+e(x['scrutinNumero'])+'</a></td><td>'+e(x['questionId'])+'</td><td>'+e(x['vote'])+'</td><td>'+e(x['typeScrutin'])+'</td><td>'+e(x['objet'])+'</td></tr>')
    return '''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Propositions documentaires V30</title><style>body{font:16px system-ui;max-width:1300px;margin:auto;padding:24px;color:#1d3345;background:#f8fafc}main{background:white;border:1px solid #dce3ea;border-radius:14px;padding:24px}table{border-collapse:collapse;width:100%}td,th{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #ddd}th{position:sticky;top:0;background:#edf1f6}input{padding:10px;max-width:500px;width:95%}.note{background:#fff6e3;padding:16px;border-left:4px solid #c58e38}a{color:#14568a}small{color:#536779}</style><main><h1>Signaux documentaires – V30</h1><p class="note"><strong>Attention :</strong> correspondances exploratoires par mots-clés dans les intitulés des scrutins. Aucun vote n'est converti en opinion. Aucune position de la Boussole n'est modifiée. Une vérification du texte intégral est indispensable.</p><p><strong>'''+str(out['nombrePropositions'])+''' signalements</strong> · '''+str(out['totalVotesLies'])+''' votes liés examinés · '''+str(out['questionsAvecRegles'])+''' questions dotées d'une règle lexicale · '''+e(out['generatedAt'])+'''</p><label>Rechercher : <input id="q" oninput="filterRows()" placeholder="Personnalité, question, numéro…"></label><div style="overflow:auto;max-height:75vh"><table><thead><tr><th>Personnalité</th><th>Date</th><th>Scrutin</th><th>Question</th><th>Vote brut</th><th>Type</th><th>Objet</th></tr></thead><tbody id="rows">'''+''.join(rows)+'''</tbody></table></div><p><small>Le scrutin renvoie à la 17e législature. Les données brutes restent disponibles dans le dépôt. Le résultat zéro est valide : aucun intitulé suffisamment précis dans l'échantillon.</small></p></main><script>function filterRows(){let q=document.getElementById('q').value.toLowerCase();for(let row of document.getElementById('rows').rows)row.hidden=!row.textContent.toLowerCase().includes(q)}</script></html>'''

def run():
    base=json.loads(BASE.read_text(encoding='utf8'))
    joined=json.loads(JOINED.read_text(encoding='utf8'))
    out=build(base,joined)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
    PAGE.write_text(render(out),encoding='utf8')
    print(f"V30 : {out['totalVotesLies']} votes liés, {out['nombrePropositions']} signalements non validés. Aucune position modifiée.")

if __name__=='__main__':run()
