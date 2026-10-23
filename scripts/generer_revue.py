#!/usr/bin/env python3
"""Generate a read-only, browser-accessible review dashboard from RSS queue.
This script never changes political stances or the published dataset.
"""
import collections, datetime as dt, html, json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def read(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
queue=read(ROOT/'data/queue.json',{})
status=read(ROOT/'data/status.json',{})
items=list(queue.values())
items.sort(key=lambda x:(x.get('sourcePublishedAt',''),x.get('detectedAt','')),reverse=True)
H=lambda value:html.escape(str(value or ''),quote=True)
def badge(n):return str(n) if n else '—'
rows=[]
for item in items:
    candidates=item.get('personalitiesSuggested') or []
    questions=item.get('questionsSuggested') or []
    score=2*bool(candidates)+bool(questions)
    priority='À examiner en priorité' if score==3 else ('À qualifier' if score else 'Signal non qualifié')
    url=str(item.get('url') or '')
    href=H(url) if url.startswith('https://') else '#'
    title=H(item.get('title') or '(Sans titre)')
    rows.append(f'<tr><td><span class="tag">{H(priority)}</span></td><td>{title}<div class="muted">{H(item.get("feed"))} · {H(item.get("sourcePublishedAt"))}</div></td><td>{H(", ".join(candidates)) or "—"}</td><td>{H(", ".join(questions)) or "—"}</td><td><a href="{href}" target="_blank" rel="noopener noreferrer">Source ↗</a></td></tr>')
errors=status.get('errors') or []
errors_html=''.join(f'<li><strong>{H(e.get("feed"))}</strong> : {H(e.get("error"))}</li>' for e in errors)
page='''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Veille documentaire — Boussole 2027</title>
<style>body{margin:0;background:#f4f7fa;color:#132c41;font:16px system-ui,sans-serif}header{background:#183e56;color:white;padding:30px max(16px,calc((100vw - 1180px)/2))}main{max-width:1180px;margin:auto;padding:24px 16px}h1{margin:0 0 8px}h2{margin-top:36px}p{line-height:1.5}.box{background:white;border-radius:12px;padding:20px;margin:16px 0;border:1px solid #dae2ea}.metrics{display:flex;gap:16px;flex-wrap:wrap}.metric{flex:1;min-width:160px}.metric strong{font-size:28px;display:block}table{width:100%;border-collapse:collapse;background:white;font-size:14px}th,td{text-align:left;padding:12px;border-bottom:1px solid #dce6eb;vertical-align:top}th{background:#e6edf3}a{color:#0b6282}.muted{color:#5c7183;font-size:12px;margin-top:6px}.tag{background:#e6edf5;padding:4px 7px;border-radius:7px;white-space:nowrap}.scroll{overflow-x:auto}footer{margin-top:30px;color:#556d80}</style>
<header><h1>Veille documentaire · Boussole 2027</h1><p>Publications détectées automatiquement, sans attribution de positions politiques.</p></header><main>
<div class="metrics"><div class="box metric"><strong>__TOTAL__</strong>Publications suivies</div><div class="box metric"><strong>__PENDING__</strong>À examiner</div><div class="box metric"><strong>__ERRORS__</strong>Sources en erreur</div></div>
<div class="box"><strong>Dernière recherche :</strong> __DATE__<p>Les noms et questions ci-dessous sont des rapprochements lexicaux indicatifs. Ils ne prouvent ni l'identité de l'auteur d'une prise de position, ni son accord avec une mesure. Aucune position de la Boussole n'est modifiée par ce tableau.</p></div>
<h2>Publications recueillies</h2><div class="scroll"><table><thead><tr><th>Signalement</th><th>Publication</th><th>Personnalités possibles</th><th>Questions possibles</th><th>Document</th></tr></thead><tbody>__ROWS__</tbody></table></div>
<h2>Erreurs des sources</h2><div class="box">__FAULTS__</div><footer>Base documentaire expérimentale. Références à contrôler avant toute utilisation comme preuve.</footer></main></html>'''
repl={'__TOTAL__':str(len(items)),'__PENDING__':str(sum(x.get('status')=='a_examiner' for x in items)),'__ERRORS__':str(len(errors)),'__DATE__':H(status.get('lastScan','Non renseignée')),'__ROWS__':'\n'.join(rows) or '<tr><td colspan="5">Aucune publication collectée.</td></tr>','__FAULTS__':('<ul>'+errors_html+'</ul>') if errors else 'Aucune erreur signalée lors de la dernière collecte.'}
for key,value in repl.items():page=page.replace(key,value)
out=ROOT/'revue.html';out.write_text(page,encoding='utf8')
print('Tableau de veille généré:',len(items),'publications -> revue.html')
