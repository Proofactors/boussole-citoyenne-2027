import sys,unittest,json, pathlib
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import integrer_programmes_v35 as m
class V35(unittest.TestCase):
 def setUp(self):
  self.questions=json.loads((ROOT/'config/questions_v35.json').read_text())
  self.src={'personnalite_id':'exemple','personnalite':'Exemple','url':'https://exemple.fr/programme','nature':'programme_2027_publie','domaines_autorises':['exemple.fr']}
 def test_150_questions(self):self.assertEqual(len(self.questions),150)
 def test_extraction_et_neutralite(self):
  with patch.object(m,'public_url',return_value=True):
   report,state=m.gather({'sources':[self.src]},self.questions,fetch=lambda u:(b'<html><body><p>Nous souhaitons augmenter le SMIC de 200 euros.</p><p>La protection des arbres est importante.</p></body></html>','text/html'))
  matches=[r for r in report['rapprochements'] if r['question_id']=='smic']
  self.assertTrue(matches)
  self.assertTrue(all(r['position_suggeree'] is None for r in report['rapprochements']))
  self.assertEqual(report['nombre_questions'],150)
 def test_version_sans_changement(self):
  b=b'<p>Le salaire minimum devrait augmenter.</p>'
  prev={'sources':{'exemple':{'sha256':m.hashlib.sha256(b).hexdigest(),'date_changement':'2026-01-01'}}}
  with patch.object(m,'public_url',return_value=True):
   report,state=m.gather({'sources':[self.src]},self.questions,fetch=lambda u:(b,'text/html'),prior=prev)
  self.assertFalse(report['sources'][0]['changement_detecte'])
  self.assertEqual(state['sources']['exemple']['date_changement'],'2026-01-01')
 def test_dont_extrapolate(self):
  self.assertFalse(m.eligible(next(q for q in self.questions if q['id']=='nucleaire'),'La France a besoin de plus de moyens.'))
 def test_html_escapes(self):
  report={'rapprochements':[]}
  output=m.render(report,self.questions)
  self.assertIn('150 questions',output)
if __name__=='__main__':unittest.main()
