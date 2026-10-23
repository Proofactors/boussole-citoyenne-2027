import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from qualifier_preuves_v32 import qualifier, rendre
class V32Tests(unittest.TestCase):
 def setUp(self):
  self.base={'affirmations':[{'id':'fin-de-vie','text':'Autoriser une aide à mourir'}]}
  self.data={'resultats':[{'personnaliteId':'test','questionId':'fin-de-vie','scrutinNumero':'8280','date':'2026-07-15','voteBrut':'pour','objetDuScrutin':'vote sur l’ensemble du texte','typeScrutin':'indetermine','consultation':'page_officielle_lue','numeroRepereDansPage':True,'urlOfficielle':'https://www.assemblee-nationale.fr/dyn/17/scrutins/8280'}]}
 def test_no_coding(self):
  r=qualifier(self.data,self.base)
  self.assertEqual(r['positionsSuggerees'],0)
  self.assertIsNone(r['resultats'][0]['positionSuggeree'])
  self.assertFalse(r['resultats'][0]['publicationAutomatiqueAutorisee'])
 def test_official_page_not_proof(self):
  r=qualifier(self.data,self.base)
  self.assertEqual(r['resultats'][0]['niveauDocumentaire'],'page_consultee_numero_confirme')
 def test_unavailable_page(self):
  self.data['resultats'][0]['consultation']='http_refuse'
  self.assertEqual(qualifier(self.data,self.base)['resultats'][0]['niveauDocumentaire'],'page_inaccessible')
 def test_amendment_warning(self):
  self.data['resultats'][0]['typeScrutin']='amendement_de_suppression'
  a=qualifier(self.data,self.base)['resultats'][0]
  self.assertTrue(any('suppression' in x.lower() for x in a['pointsAVerifier']))
 def test_html_escape(self):
  self.data['resultats'][0]['objetDuScrutin']='<script>alert(1)</script>'
  h=rendre(qualifier(self.data,self.base))
  self.assertIn('&lt;script&gt;',h)
  self.assertNotIn('<script>alert(1)</script>',h)
if __name__=='__main__':unittest.main()
