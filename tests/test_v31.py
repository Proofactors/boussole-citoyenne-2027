import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v31',ROOT/'scripts/qualifier_preuves_v31.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
BASE={'propositions':[{'personnaliteId':'exemple','acteurRef':'PA123','questionId':'fin-de-vie','question':'Fin de vie','scrutinNumero':'8280','date':'2026-07-15','vote':'pour','objet':'Texte législatif','typeScrutin':'indetermine'}]}
class V31Tests(unittest.TestCase):
 def test_origin_officielle(self):
  self.assertEqual(m.official_url('8280'),'https://www.assemblee-nationale.fr/dyn/17/scrutins/8280')
 def test_numero_invalide(self):
  for value in ['https://evil.example','../../private','12?x=1']:
   with self.assertRaises(ValueError):m.official_url(value)
 def test_aucun_codage(self):
  original=repr(BASE)
  r=m.compile_registry(BASE,lambda n:{'status':'page_officielle_lue','text':'scrutin 8280 '+('texte ' * 60)},limit=2)
  self.assertEqual(repr(BASE),original)
  self.assertIsNone(r['resultats'][0]['codagePropose'])
  self.assertEqual(r['pagesLues'],1)
 def test_limite_des_requetes(self):
  s={'propositions':[dict(BASE['propositions'][0],scrutinNumero=str(i)) for i in range(100,104)]}
  calls=[]
  def fake(n):calls.append(n);return {'status':'page_officielle_lue','text':'texte '*40}
  r=m.compile_registry(s,fake,limit=2)
  self.assertEqual(len(calls),2)
  self.assertEqual(r['totalSignalements'],4)
 def test_cache_scrutin(self):
  s={'propositions':BASE['propositions']*2}
  calls=[]
  def fake(n):calls.append(n);return {'status':'texte_insuffisant','text':''}
  m.compile_registry(s,fake)
  self.assertEqual(len(calls),1)
 def test_html_escaped(self):
  r=m.compile_registry(BASE,lambda n:{'status':'texte_insuffisant','text':''})
  r['resultats'][0]['objetDuScrutin']='<script>alert(1)</script>'
  self.assertIn('&lt;script&gt;',m.render(r))
 def test_zero_result(self):
  r=m.compile_registry({'propositions':[]})
  self.assertIn('0 signalements',m.render(r))
if __name__=='__main__':unittest.main()

class V311Diagnostics(unittest.TestCase):
 def test_domain_security(self):
  self.assertTrue(m._official_https('https://www.assemblee-nationale.fr/dyn/17/scrutins/8280'))
  for u in ['http://www.assemblee-nationale.fr/x','https://assemblee-nationale.fr.evil.org/x','https://127.0.0.1/x','https://user@www.assemblee-nationale.fr/x']:
   self.assertFalse(m._official_https(u))
 def test_http_404_diagnostic(self):
  import urllib.error
  def error(req,timeout):raise urllib.error.HTTPError(req.full_url,404,'Not Found',{},None)
  x=m.download('8280',opener=error,delay=0)
  self.assertEqual(x['status'],'http_refuse')
  self.assertEqual(x['detail'],'HTTP 404')
  self.assertEqual(x['tentatives'],1)
 def test_http_503_retry(self):
  import urllib.error
  calls=[]
  def error(req,timeout):
   calls.append(1)
   raise urllib.error.HTTPError(req.full_url,503,'Unavailable',{},None)
  x=m.download('8280',opener=error,delay=0)
  self.assertEqual(x['status'],'http_temporaire')
  self.assertEqual(len(calls),2)
 def test_dns_error(self):
  import urllib.error,socket
  def error(req,timeout):raise urllib.error.URLError(socket.gaierror(8,'DNS error'))
  x=m.download('8280',opener=error,delay=0)
  self.assertEqual(x['status'],'dns_erreur')
  self.assertEqual(x['tentatives'],1)
 def test_report_diagnostics(self):
  source={'propositions':[dict(BASE['propositions'][0],scrutinNumero='8280')]}
  x=m.compile_registry(source,lambda n:{'status':'http_refuse','text':'','detail':'HTTP 403','tentatives':2})
  self.assertEqual(x['causes']['http_refuse'],1)
  self.assertIn('HTTP 403',m.render(x))
  self.assertIsNone(x['resultats'][0]['codagePropose'])
