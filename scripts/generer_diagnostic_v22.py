#!/usr/bin/env python3
"""Tableau HTML de suivi V22 sans scripts externes; contenu échappé."""
import html
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
doc=json.loads((ROOT/'data/diagnostic_v22.json').read_text(encoding='utf-8'))
e=lambda v:html.escape(str(v if v is not None else ''),quote=True)
rows=[]
for d in doc['documents']:
    link=d.get('url','')
    safe=link if link.startswith(('https://www.senat.fr/','https://www.assemblee-nationale.fr/','https://data.assemblee-nationale.fr/')) else ''
    name=e(d.get('titre',''))
    summary=e(d.get('resumeRss') or 'Aucun résumé RSS')
    why=e(d.get('motif') or 'Aucune erreur indiquée')
    rows.append(f'<tr><td>{name}</td><td>{e(d.get("lecture"))}</td><td>{why}</td><td><details><summary>Voir le résumé RSS</summary>{summary}<p><small>Résumé non vérifié sur le texte intégral : aucune attribution politique.</small></p></details></td><td>'+ (f'<a href="{e(safe)}" rel="noopener noreferrer" target="_blank">Source ↗</a>' if safe else 'Lien non autorisé') + '</td></tr>')
s=doc['statistiques']; index=doc['inventaireAN']
head=f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Diagnostic documentaire V22</title><style>body{{font:15px system-ui;background:#f5f7fa;color:#17364d;margin:0}}header{{background:#173e57;color:white;padding:24px max(20px,calc((100vw - 1100px)/2))}}main{{max-width:1100px;margin:24px auto;padding:0 16px}}section{{background:white;border:1px solid #d9e2ea;border-radius:12px;padding:18px;margin:14px 0;overflow:auto}}table{{border-collapse:collapse;width:100%}}td,th{{padding:12px;border-bottom:1px solid #dee7ec;text-align:left;vertical-align:top}}th{{background:#edf3f7}}summary{{cursor:pointer}}input{{padding:10px;width:min(92%,360px)}}a{{color:#06758a}}.counts{{display:flex;gap:12px;flex-wrap:wrap}}.counts span{{background:#edf3f7;padding:14px;border-radius:8px}}</style></head><body><header><h1>Diagnostic documentaire — V22</h1><p>Accès aux textes, résumés RSS et index des scrutins officiels. Aucune position politique n'est modifiée.</p></header><main><section class="counts"><span><strong>{s['documentsSuivis']}</strong> documents</span><span><strong>{s['documentsLus']}</strong> textes complets</span><span><strong>{s['documentsSansTexteAvecResumeRss']}</strong> replis RSS</span><span><strong>{s['documentsSansTexteNiResume']}</strong> sans texte ni résumé</span><span><strong>{s['passagesCandidats']}</strong> passages candidats</span></section><section><p><strong>Scrutins AN :</strong> {e(index.get('statut'))} — {e(index.get('nombreScrutinsDansArchive','—'))} recensés.</p><p>{e(index.get('erreur') or '')}</p><p><small>La présence d'un scrutin ne signifie pas que le vote porte directement sur une affirmation, ni qu'il établit une position individuelle.</small></p></section><section><label for="filtre">Filtrer les documents : </label><input id="filtre" placeholder="Mot du titre, motif, résumé" oninput="document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLocaleLowerCase('fr').includes(this.value.toLocaleLowerCase('fr')))" type="search"><table><thead><tr><th>Publication</th><th>Lecture</th><th>Diagnostic</th><th>Résumé RSS</th><th>Source</th></tr></thead><tbody>'''
foot='''</tbody></table></section><p><a href="preuves.html">← Registre V21</a></p></main></body></html>'''
(ROOT/'diagnostic.html').write_text(head+'\n'.join(rows)+foot,encoding='utf-8')
print('V22 diagnostic.html créé :',len(rows),'documents')
