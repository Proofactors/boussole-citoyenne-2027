#!/usr/bin/env python3
"""V29: bilan de couverture AN, sans inférence ni modification des positions."""
import datetime as dt
import html
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def summarize(base, matches, votes):
    by_id = {p['id']: p for p in matches['personnalites']}
    rows = []
    for slug, pos in base['positions'].items():
        p = by_id.get(slug, {})
        count = sum(isinstance(v, dict) and type(v.get('stance')) is int for v in pos.values())
        rows.append({'personnalite': slug, 'id_an': p.get('acteurRef'), 'identification': p.get('statut', 'non_identifie'), 'votes': len(p.get('scrutins', [])), 'positions': count})
    return {'date': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'scrutinsEchantillon': len(votes['scrutins']), 'scrutinsArchive': votes.get('totalParsed'), 'personnalites': len(rows), 'votesIndividuels': sum(p['votes'] for p in rows), 'identifiantsUniques': sum(p['identification'] == 'identifiant_unique' for p in rows), 'lignes': rows, 'avertissement': 'Un vote individuel ne prouve pas une opinion générale. Aucune position politique n’est créée ou modifiée.'}

def render(d):
    lines = ''.join('<tr><td>' + html.escape(r['personnalite']) + '</td><td>' + html.escape(r['identification']) + '</td><td>' + html.escape(r['id_an'] or '—') + '</td><td>' + str(r['votes']) + '</td><td>' + str(r['positions']) + '</td></tr>' for r in d['lignes'])
    return ('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Couverture des preuves — V29</title>'
            '<style>body{max-width:1050px;margin:2em auto;padding:1em;font:16px/1.5 system-ui;color:#183048}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #dce3e9;padding:.65em;text-align:left}input{padding:.7em;max-width:400px;width:90%}.info{background:#eaf2f7;padding:1em;border-radius:12px}</style>'
            '<h1>Suivi documentaire — V29</h1><p class="info">' + html.escape(d['avertissement']) + '</p><p>'
            + str(d['scrutinsEchantillon']) + ' scrutins indexés dans l’échantillon · ' + str(d['scrutinsArchive']) + ' dans l’archive officielle · ' + str(d['identifiantsUniques']) + ' identifiants uniques · ' + str(d['votesIndividuels']) + ' votes associés aux personnalités suivies.</p>'
            '<label>Filtrer : <input id="q" oninput="for(let x of document.querySelectorAll(\'tbody tr\'))x.hidden=!x.textContent.toLowerCase().includes(this.value.toLowerCase())"></label>'
            '<table><thead><tr><th>Personnalité</th><th>Correspondance AN</th><th>ID officiel</th><th>Votes individuels</th><th>Positions déjà codées</th></tr></thead><tbody>' + lines + '</tbody></table><p>Un zéro peut signifier : aucun mandat durant la période, absence au scrutin, ou aucune correspondance.</p></html>')

def run():
    base = json.loads((ROOT / 'boussole_2027_positions.json').read_text(encoding='utf-8'))
    matches = json.loads((ROOT / 'data/rapprochement_votes_v25.json').read_text(encoding='utf-8'))
    votes = json.loads((ROOT / 'data/votes_an_v24.json').read_text(encoding='utf-8'))
    out = summarize(base, matches, votes)
    (ROOT / 'data/couverture_v29.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'couverture.html').write_text(render(out), encoding='utf-8')
    print('V29:', out['scrutinsEchantillon'], 'scrutins;', out['votesIndividuels'], 'votes associés')

if __name__ == '__main__':
    run()
