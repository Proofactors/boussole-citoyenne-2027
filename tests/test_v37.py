import json, unittest, pathlib, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parent.parent
class TestV37(unittest.TestCase):
 def test_questions_inchangees(self):
  q=json.loads((ROOT/'config/questions_v35.json').read_text()); a=json.loads((ROOT/'data/audit_questions_v37.json').read_text()); self.assertEqual(len(q),150); self.assertEqual(len(a['questions']),150); self.assertEqual({x['id'] for x in q},{x['id'] for x in a['questions']}); self.assertEqual(a['questions_modifiees_automatiquement'],0)
 def test_candidatures(self):
  d=json.loads((ROOT/'config/candidatures_v36.json').read_text()); ids={x['id'] for x in d['entries']}; self.assertIn('teddy-riner',ids); self.assertIn('raphael-glucksmann',ids); self.assertEqual(len(ids),len(d['entries']))
 def test_programme_primary(self):
  x=json.loads((ROOT/'config/programmes_officiels.json').read_text())['sources']; m=next(s for s in x if s['personnalite_id']=='jean-luc-melenchon'); self.assertEqual(m['url'],'https://melenchon2027.fr/programme/livre')
 def test_pages(self):
  subprocess.run([sys.executable,str(ROOT/'scripts/generer_suivi_v37.py')],check=True,capture_output=True)
  self.assertIn('Teddy Riner',(ROOT/'candidatures.html').read_text()); self.assertIn('Audit éditorial',(ROOT/'audit-questions.html').read_text())
if __name__=='__main__':unittest.main()
