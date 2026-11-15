#!/usr/bin/env python3
"""Generate purely descriptive V37 pages. No opinion data is modified."""
import html, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
ESC=lambda s: html.escape(str(s),quote=True)
CSS="""*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#19304a;font:16px/1.55 system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:clamp(12px,4vw,32px)}a{color:#07548e;overflow-wrap:anywhere}.card{background:white;border:1px solid #d8e0e8;border-radius:12px;padding:clamp(12px,3vw,22px);margin:12px 0}h1{font-size:clamp(1.45rem,4vw,2rem)}h2{font-size:1.15rem}p{overflow-wrap:anywhere}.muted{color:#516477}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,290px),1fr));gap:12px}.tag{display:inline-block;background:#e9eff7;padding:3px 8px;border-radius:5px;font-size:.85em}select,input{max-width:100%;font:inherit;padding:10px}details{margin:8px 0}summary{cursor:pointer}footer{padding:20px 0}@media(max-width:480px){.card{padding:14px}main{padding:12px}}"""
def shell(title,inner):
 return '<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+ESC(title)+'</title><style>'+CSS+'</style></head><body><main>'+inner+'<footer><a href="index.html">← Boussole</a> · <a href="programmes.html">Programmes</a> · <a href="audit-questions.html">Audit des questions</a></footer></main></body></html>'
def candidatures():
 d=json.loads((ROOT/'config/candidatures_v36.json').read_text())
 labels={'designe_primaire':'Désigné à une primaire','non_retenu_primaire':'Non retenu à une primaire','declare':'Candidature déclarée','declare_sous_condition':'Candidature conditionnelle','intention_non_formalisee':'Intention à confirmer','potentiel':'Candidature envisagée'}
 cards=[]
 for e in d['entries']:
  links=' '.join('<a href="'+ESC(u)+'" target="_blank" rel="noopener noreferrer">Source</a>' for u in e.get('evidence',[]) if u.startswith('https://'))
  cards.append('<article class="card" data-status="'+ESC(e['status'])+'"><h2>'+ESC(e['name'])+'</h2><p class="muted">'+ESC(e.get('party',''))+'</p><p><span class="tag">'+ESC(labels.get(e['status'],e['status']))+'</span></p><p>'+ESC(e.get('note',''))+'</p><p class="muted">Date indiquée : '+ESC(e.get('status_since','non précisée'))+'</p><p>'+links+'</p></article>')
 inner='<h1>Suivi des candidatures — V37</h1><p class="card">Répertoire documentaire au '+ESC(d['as_of'])+'. Aucune candidature n’est encore certifiée par ce registre comme validée par le Conseil constitutionnel. Les personnes non retenues dans une primaire conservent leur historique de positions. La date indiquée peut être celle du recensement.</p><label for="filtre">Afficher : </label><select id="filtre"><option value="">Tous les statuts</option>'+''.join('<option value="'+ESC(k)+'">'+ESC(v)+'</option>' for k,v in labels.items())+'</select><div class="grid" id="cartes">'+''.join(cards)+'</div><script>document.getElementById("filtre").addEventListener("change",function(){document.querySelectorAll("[data-status]").forEach(function(el){el.hidden=!!this.value&&el.dataset.status!==this.value},this)});</script>'
 (ROOT/'candidatures.html').write_text(shell('Candidatures 2027 — V37',inner))
def audit():
 d=json.loads((ROOT/'data/audit_questions_v37.json').read_text())
 priorities=[x for x in d['questions'] if x.get('statut')!='conserver']
 cards=[]
 for e in priorities:
  cards.append('<article class="card"><h2>'+ESC(e['titre'])+'</h2><p><span class="tag">'+ESC(e['theme'])+'</span> <span class="tag">'+ESC(e['statut'])+'</span></p><p><strong>Formulation actuelle :</strong> '+ESC(e['formulation_actuelle'])+'</p><p><strong>Proposition non activée :</strong> '+ESC(e.get('formulation_proposee_non_active','—'))+'</p><p class="muted">'+ESC(e.get('justification',''))+'</p><p class="muted">ID stable : '+ESC(e['id'])+'</p></article>')
 inner='<h1>Audit éditorial des 150 questions — V37</h1><p class="card">'+str(d['total_questions'])+' questions conservées, sans modification automatique. '+str(len(priorities))+' sujets signalés pour examen éditorial. Toute modification substantielle exige une réévaluation des anciennes positions et une gestion de version.</p><div class="grid">'+''.join(cards)+'</div>'
 (ROOT/'audit-questions.html').write_text(shell('Audit des questions V37',inner))
if __name__=='__main__': candidatures(); audit(); print('V37: pages candidatures et audit générées; aucune position modifiée')
