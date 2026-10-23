#!/usr/bin/env python3
"""Page publique V23 de diagnostic, échappement des données non fiables."""
import html,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
r=json.loads((R/'data/registre_preuves_v20.json').read_text(encoding='utf-8'))
e=lambda s: html.escape(str(s if s is not None else ''),quote=True)
rows=[]
for d in r.get('documents',[]):
    rows.append('<tr><td>'+e(d.get('titre'))+'</td><td>'+e(d.get('lecture'))+'</td><td>'+e(d.get('motif') or '—')+'</td><td>'+e(d.get('urlEffective') or '—')+'</td></tr>')
s=r['statistiques']
content='''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Diagnostic V23 — Boussole citoyenne</title><style>body{font:16px system-ui;background:#f3f7fa;color:#142d40;margin:0}header{background:#173e57;color:white;padding:24px}main{max-width:1100px;margin:24px auto;padding:0 18px}section{background:white;border-radius:10px;padding:20px;overflow:auto;margin:16px 0}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;text-align:left;padding:10px}th{background:#edf3f7}input{padding:10px;max-width:90%;width:400px}a{color:#087088}</style><header><h1>Diagnostic documentaire — V23</h1><p>Causes précises d'échec, conversion HTTPS contrôlée et reprise des documents antérieurs.</p></header><main>'''
content+=f'<section><strong>{s["documents"]}</strong> documents · <strong>{s["textesLus"]}</strong> textes lus · <strong>{s["pdfLus"]}</strong> PDF lus · <strong>{s["passagesCandidats"]}</strong> passages candidats · <strong>{s["nouveauxExamines"]}</strong> examinés pendant ce passage</section>'
content+='<section><h2>Causes de non-lecture</h2><ul>'+''.join(f'<li>{e(k)} : {e(v)}</li>' for k,v in sorted(s.get('echecsParCause',{}).items(),key=lambda x:-x[1]))+'</ul></section>'
content+='<section><label for="q">Rechercher : </label><input id="q" type="search" placeholder="Titre ou cause" oninput="document.querySelectorAll(\'tbody tr\').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(this.value.toLowerCase()))"><table><thead><tr><th>Document</th><th>Lecture</th><th>Diagnostic</th><th>Adresse normalisée</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></section><p><a href="diagnostic.html">← Diagnostic V22</a></p></main></html>'
(R/'diagnostic-v23.html').write_text(content,encoding='utf-8')
print('V23 diagnostic-v23.html créé :',len(rows),'documents')
