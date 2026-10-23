import importlib.util,io,json,zipfile,unittest
from pathlib import Path
path=Path(__file__).resolve().parents[1]/'scripts'/'indexer_votes_v24.py'
spec=importlib.util.spec_from_file_location('votesv24',path); v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
class TestV24(unittest.TestCase):
 def data(self):
  nominatif = {
   'pours': {'votant': [{'acteurRef':'PA123'}]},
   'contres': {'votant': [{'acteurRef':'PA456'}]},
   'abstentions': {'votant': [{'acteurRef':'PA789'}]}
  }
  return {'scrutin': {'uid':'VTANR5L17V42','numero':'42',
    'dateScrutin':'2026-10-22','titre':'Vote fictif',
    'ventilationVotes': {'organe': {'groupes': {
       'groupe':[{'vote': {'decompteNominatif':nominatif}}]
    }}}}}
 def test_individual_votes(self):
  r=v.parse_vote(self.data());self.assertEqual([x['vote'] for x in r['votes']],['pour','contre','abstention'])
 def test_no_political_score(self):
  r=v.parse_vote(self.data());self.assertTrue(all('stance' not in x for x in r['votes']))
 def test_zip(self):
  z=io.BytesIO()
  with zipfile.ZipFile(z,'w') as a:a.writestr('vote.json',json.dumps(self.data()))
  records,count,bad=v.index_zip(z.getvalue());self.assertEqual((count,bad),(1,0));self.assertEqual(len(records),1)
 def test_untrusted_url(self):
  with self.assertRaises(ValueError):v.download_zip('http://localhost/private')
 def test_html_escapes_title(self):
  d={'scrutins':[dict(v.parse_vote(self.data()),titre='<script>')],'generatedAt':'now','totalParsed':1,'invalid':0}
  self.assertIn('&lt;script&gt;',v.public_html(d))
if __name__=='__main__':unittest.main()
