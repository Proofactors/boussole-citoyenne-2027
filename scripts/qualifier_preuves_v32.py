#!/usr/bin/env python3
"""V32: documenter le degré de vérification des signaux V31, sans coder d'opinion.

Une page officielle lisible ou un mot-clé commun ne démontre PAS une position.
La page de scrutin peut aussi présenter un simple résumé plutôt qu'un texte législatif.
"""
from __future__ import annotations
import datetime as dt
import html
import json
from pathlib import Path
import re
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/verification_v31.json'
BASE=ROOT/'boussole_2027_positions.json'
OUT=ROOT/'data/qualification_v32.json'
PAGE=ROOT/'qualification.html'

def normaliser(text):
    s=unicodedata.normalize('NFKD',str(text or '').casefold())
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9]+',' ',s)).strip()

def qualifier(source,base):
    questions={q['id']:q['text'] for q in base.get('affirmations',[])}
    results=[]
    for p in source.get('resultats',[]):
        question=questions.get(p.get('questionId'))
        if not question: continue
        checked=p.get('consultation')=='page_officielle_lue'
        number_found=p.get('numeroRepereDansPage') is True
        title=p.get('objetDuScrutin') or ''
        kind=p.get('typeScrutin') or 'indetermine'
        sensitive=('suppression' in normaliser(title) or kind in ('amendement','amendement_de_suppression'))
        # Strict documentary stages: deliberately do not infer vote direction or legislation meaning.
        level='page_inaccessible'
        if checked: level='page_consultee_numero_confirme' if number_found else 'page_consultee_numero_non_confirme'
        reasons=['Le libellé du scrutin et le texte intégral de la mesure doivent être comparés à la question.',
                 'Vérifier le contexte, les votes individuels, l’identité et les éventuelles contradictions.']
        if sensitive: reasons.append('Amendement ou suppression : le sens matériel du vote ne peut pas être inversé automatiquement.')
        if not checked: reasons.append('Page officielle indisponible : une preuve complémentaire est nécessaire.')
        if checked and not number_found: reasons.append('Numéro de scrutin non retrouvé dans l’extrait téléchargé.')
        results.append({'personnaliteId':p.get('personnaliteId'), 'questionId':p.get('questionId'),
                        'question':question,'scrutinNumero':p.get('scrutinNumero'), 'date':p.get('date'),
                        'voteBrut':p.get('voteBrut'),'typeScrutin':kind,'objet':title,
                        'source':p.get('urlOfficielle'),'empreinteTexteSha256':p.get('empreinteTexteSha256'),
                        'niveauDocumentaire':level,'pointsAVerifier':reasons,
                        'positionSuggeree':None, 'publicationAutomatiqueAutorisee':False})
    return {'schemaVersion':'32.0','generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
            'total':len(results),'pagesConsultees':sum(x['niveauDocumentaire'].startswith('page_consultee') for x in results),
            'positionsSuggerees':0,'important':'Registre de qualification préalable. Aucune position -2/+2 n’est inférée ou publiée.',
            'resultats':results}

def rendre(reg):
    e=html.escape
    lines=[]
    for p in reg['resultats']:
        link=p.get('source','')
        if not (isinstance(link,str) and re.fullmatch(r'https://www\.assemblee-nationale\.fr/dyn/17/scrutins/[0-9]{1,6}',link)): link=''
        anchor=f'<a href="{e(link,quote=True)}" target="_blank" rel="noopener noreferrer">Scrutin officiel</a>' if link else '—'
        lines.append('<article class="entry"><div class="fields"><div><strong>'+e(str(p['personnaliteId']))+'</strong><br><small>'+e(str(p['date']))+'</small></div><div>Question : <strong>'+e(str(p['questionId']))+'</strong><br>'+e(str(p['question']))+'</div><div>Vote brut : <strong>'+e(str(p['voteBrut']))+'</strong><br>Scrutin : '+e(str(p['scrutinNumero']))+'</div></div><p><b>Objet :</b> '+e(str(p['objet']))+'</p><p><b>Contrôle :</b> '+e(p['niveauDocumentaire'])+' · <b>Aucune position proposée</b></p><details><summary>Points à vérifier</summary><ul>'+''.join('<li>'+e(x)+'</li>' for x in p['pointsAVerifier'])+'</ul></details><p>'+anchor+'</p></article>')
    css="""<style>*{box-sizing:border-box}body{margin:0;background:#f4f7fa;color:#193249;font:16px/1.55 system-ui,sans-serif}main{max-width:1050px;margin:auto;padding:20px 14px 60px}h1{font-size:clamp(24px,4vw,34px)}.entry{background:#fff;border:1px solid #dce5ed;border-radius:14px;padding:18px;margin:12px 0;overflow-wrap:anywhere}.fields{display:grid;grid-template-columns:minmax(130px,1fr) minmax(0,2fr) minmax(110px,1fr);gap:12px}.warn{background:#fff5dd;border-left:4px solid #bc8b36;padding:14px}a{color:#11686b}summary{cursor:pointer;font-weight:600}input{width:100%;max-width:450px;padding:11px;border:1px solid #a9bac6;border-radius:8px;font:inherit}small{color:#526578}@media(max-width:690px){.fields{grid-template-columns:1fr}.entry{padding:14px}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}</style>"""
    return '<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Qualification V32 — Boussole citoyenne</title>'+css+'</head><body><main><h1>Qualification documentaire — V32</h1><p class="warn">Ce tableau rassemble des contrôles préalables. <strong>Aucune position politique nouvelle n’a été calculée ou publiée.</strong> Une page de scrutin consultée ne suffit pas à établir le sens matériel d’une mesure.</p><p>'+str(reg['total'])+' signalements · '+str(reg['pagesConsultees'])+' lignes avec page consultée · 0 positions suggérées</p><label for="filter">Filtrer les signalements</label><p><input id="filter" placeholder="Personnalité, question, scrutin..."></p><div id="entries">'+''.join(lines)+'</div><p><a href="verification.html">← Vérification V31.1</a></p></main><script>document.getElementById("filter").addEventListener("input",e=>{const q=e.target.value.toLowerCase();for(const a of document.querySelectorAll(".entry"))a.hidden=!a.textContent.toLowerCase().includes(q)})</script></body></html>'

def run():
    base=json.loads(BASE.read_text(encoding='utf8'))
    source=json.loads(SOURCE.read_text(encoding='utf8'))
    result=qualifier(source,base)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    PAGE.write_text(rendre(result),encoding='utf8')
    print(f"V32 : {result['total']} signalements, {result['positionsSuggerees']} positions proposées")
if __name__=='__main__':run()
