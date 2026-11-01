#!/usr/bin/env python3
"""Contrôles de cohérence non intrusifs de Ma Boussole V36.
N'écrit aucun fichier, ne modifie aucune position et n'effectue aucun accès réseau.
"""
import json
import re
import sys
from pathlib import Path


def auditer(root: Path) -> list[str]:
    erreurs = []
    fichiers = ['index.html', 'candidatures.html', 'programmes.html',
                'programmes-analyse.html', 'config/candidatures_v36.json',
                'config/questions_v35.json', 'boussole_2027_positions.json',
                'manifest.json']
    for nom in fichiers:
        if not (root / nom).is_file():
            erreurs.append(f'Fichier absent : {nom}')
    if erreurs:
        return erreurs
    index = (root/'index.html').read_text(encoding='utf-8')
    cand = (root/'candidatures.html').read_text(encoding='utf-8')
    if not re.search(r'version\s*36', index, re.I):
        erreurs.append('index.html : bandeau V36 non trouvé')
    if not re.search(r'<meta\s+name=["\']viewport["\']', index, re.I):
        erreurs.append('index.html : meta viewport absente')
    if '@media' not in index:
        erreurs.append('index.html : aucune règle CSS responsive détectée')
    if 'candidatures.html' not in index:
        erreurs.append('index.html : lien candidatures absent')
    if 'suivi V36' not in cand:
        erreurs.append('candidatures.html : référence V36 absente')
    for label in ('Raphaël Glucksmann','Olivier Faure','Ségolène Royal','Emmanuel Maurel','Jérôme Guedj'):
        if label not in cand:
            erreurs.append(f'candidatures.html : entrée absente : {label}')
    try:
        infos = json.loads((root/'config/candidatures_v36.json').read_text(encoding='utf-8'))
        if infos.get('version') != 'V36':
            erreurs.append('config/candidatures_v36.json : mauvaise version')
    except (ValueError, OSError) as exc:
        erreurs.append(f'config/candidatures_v36.json : JSON invalide : {exc}')
    try:
        questions = json.loads((root/'config/questions_v35.json').read_text(encoding='utf-8'))
        if not isinstance(questions, list) or len(questions) != 150:
            erreurs.append('config/questions_v35.json : référentiel différent de 150 questions')
        elif len({q.get('id') for q in questions}) != 150:
            erreurs.append('config/questions_v35.json : identifiants non uniques')
    except (ValueError, OSError) as exc:
        erreurs.append(f'config/questions_v35.json : JSON invalide : {exc}')
    return erreurs


if __name__ == '__main__':
    dossier = Path(__file__).resolve().parents[1]
    resultats = auditer(dossier)
    if resultats:
        for erreur in resultats:
            print('ÉCHEC :', erreur)
        sys.exit(1)
    print('OK : V36, pages liées, JSON, 150 questions et présence des règles responsive.')
    print('Note : ce contrôle statique ne remplace pas les essais visuels ni les tests des calculs.')
