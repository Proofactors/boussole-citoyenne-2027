import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

MOD=Path(__file__).resolve().parents[1]/'scripts/rapprocher_votes_v25.py'
spec=importlib.util.spec_from_file_location('v25',MOD)
v25=importlib.util.module_from_spec(spec);spec.loader.exec_module(v25)

class TestsV25(unittest.TestCase):
    def test_name_accents(self):
        self.assertEqual(v25.norm('Jean-Luc Mélenchon'),v25.norm('jean-luc-melenchon'.replace('-',' ')))
    def test_parse_actor(self):
        obj={'acteur':{'uid':'PA123','etatCivil':{'ident':{'prenom':'Jean-Luc','nom':'Mélenchon'}}}}
        self.assertEqual(v25.parse_actor(obj)['uid'],'PA123')
    def test_unique_ambiguous_and_unmatched(self):
        people=[{'uid':'PA1','nomComplet':'Marine Le Pen'}, {'uid':'PA2','nomComplet':'Marine Le Pen'}, {'uid':'PA3','nomComplet':'Jean-Luc Mélenchon'}]
        result=v25.match_personalities(['marine-le-pen','jean-luc-melenchon','nathalie-arthaud'],people)
        self.assertEqual(result['marine-le-pen']['statut'],'ambigu')
        self.assertEqual(result['jean-luc-melenchon']['acteurRef'],'PA3')
        self.assertEqual(result['nathalie-arthaud']['statut'],'non_trouve')
    def test_join_and_no_stance(self):
        b={'positions':{'jean-luc-melenchon':{},'marine-le-pen':{}}}
        a=[{'uid':'PA3','nomComplet':'Jean-Luc Mélenchon'}]
        v={'source':'test','scrutins':[{'numero':'1','date':'2026-10-23','titre':'Un vote','votes':[{'acteurRef':'PA3','vote':'pour'}]}]}
        r=v25.join_votes(b,v,a)
        self.assertEqual(r['personnalites'][0]['decompte']['pour'],1)
        self.assertNotIn('stance',r['personnalites'][0])
    def test_extract_zip(self):
        data={'acteur':{'uid':'PA3','etatCivil':{'ident':{'prenom':'Jean-Luc','nom':'Mélenchon'}}}}
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:z.writestr('json/acteur/PA3.json',json.dumps(data))
        self.assertEqual(len(v25.parse_archive(out.getvalue())),1)

if __name__=='__main__':unittest.main()
