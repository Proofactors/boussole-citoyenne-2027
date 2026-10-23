#!/usr/bin/env python3
"""Page de preuves potentielles; échappement systématique du contenu non fiable."""
from pathlib import Path
import html,json
ROOT=Path(__file__).resolve().parents[1]
doc=json.loads((ROOT/'data/registre_preuves_v20.json').read_text(encoding='utf-8'))
E=lambda x: html.escape(str(x if x is not None else ''),quote=True)
rows=[]
for item in doc['documents']:
    url=str(item.get('url') or '')
    link=E(url) if url.startswith('https://') else '#'
    ps=item.get('passages',[])
    passages=''.join('<details><summary>'+E(', '.join(p['personnalitesMentionnees']))+' · '+E(p['questionId'])+'</summary><blockquote>'+E(p['passageSource'])+'</blockquote><p>Passage à vérifier : aucune valeur politique attribuée.</p></details>' for p in ps)
    rows.append('<tr><td>'+E(item.get('titre'))+'</td><td>'+E(item.get('lecture'))+'</td><td>'+str(len(ps))+'</td><td>'+passages+'</td><td><a target="_blank" rel="noopener noreferrer" href="'+link+'">Source ↗</a></td></tr>')
html_doc="""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Registre de preuves — Boussole 2027</title><style>body{font:15px system-ui,sans-serif;margin:0;background:#f4f7fa;color:#18374a}header{background:#183f56;color:white;padding:25px max(18px,calc((100vw - 1160px)/2))}main{max-width:1160px;margin:24px auto;padding:0 18px}.card{background:white;padding:20px;border-radius:12px;border:1px solid #dce5eb;overflow:auto}table{border-collapse:collapse;width:100%}th,td{text-align:left;border-bottom:1px solid #dbe4eb;padding:12px;vertical-align:top}th{background:#eef3f7}blockquote{border-left:3px solid #90a6b6;padding-left:14px;max-width:650px}details{margin:8px 0}input{padding:10px;border:1px solid #cdd8e0;border-radius:7px;width:min(95%,350px)}a{color:#08758d}</style></head><body><header><h1>Registre documentaire — V20</h1><p>Passages candidats extraits de pages publiques. Aucun codage politique validé automatiquement.</p></header><main><div class="card"><p><strong>__NUM__ documents suivis · __TXT__ textes lus · __PASS__ passages candidats</strong></p><p>Un passage contenant un nom et des termes proches d’une question n’est pas une preuve de soutien ou d’opposition. Attribution, contexte et négation exigent une vérification éditoriale.</p><label>Recherche : <input id="filtre" type="search" oninput="filterRows()" placeholder="Personnalité, question, article"></label></div><div class="card"><table><thead><tr><th>Publication</th><th>Accès</th><th>Passages</th><th>Extraits à vérifier</th><th>Lien</th></tr></thead><tbody>__ROWS__</tbody></table></div><p><a href="analyse.html">← Analyse V19</a></p></main><script>function filterRows(){let q=document.getElementById('filtre').value.toLocaleLowerCase('fr');document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLocaleLowerCase('fr').includes(q));}</script></body></html>"""
for a,b in {'__NUM__':doc['statistiques']['documents'],'__TXT__':doc['statistiques']['textesLus'],'__PASS__':doc['statistiques']['passagesCandidats'],'__ROWS__':'\n'.join(rows) or '<tr><td colspan="5">Aucune publication disponible.</td></tr>'}.items(): html_doc=html_doc.replace(a,str(b))
(ROOT/'preuves.html').write_text(html_doc,encoding='utf-8')
print('preuves.html généré')
