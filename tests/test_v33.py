import json, pathlib, sys, unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from surveiller_programmes_v33 import generate, render_page
class ProgrammesTest(unittest.TestCase):
 def setUp(self):self.c={'sources':[{'personnalite_id':'test-personne','personnalite':'Test Personne','editeur':'Site fictif','url':'https://example.com/programme','domaines_autorises':['example.com'],'nature':'programme_de_campagne'}]}
 def test_catalogue_without_sources(self):self.assertEqual(generate({'sources':[]})['sources'],[])
 def test_reject_duplicate_candidate(self):
  c={'sources':self.c['sources']*2}
  with self.assertRaises(ValueError):generate(c)
 def test_reject_bad_id(self):
  self.c['sources'][0]['personnalite_id']='../../bad'
  with self.assertRaises(ValueError):generate(self.c)
 def test_report_escaped(self):
  d={'sources':[{'personnalite':'<script>alert(1)</script>','statut':'test','editeur':'x','url':'https://example.com','date_verification':'now','empreinte_sha256':None}]}
  self.assertNotIn('<script>',render_page(d))
if __name__=='__main__': unittest.main()
