import json, pathlib, re, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class IntegrationV34(unittest.TestCase):
 def test_catalogue_10(self):
  sources=json.loads((ROOT/'config/programmes_officiels.json').read_text())['sources']
  self.assertEqual(len(sources),10)
  self.assertEqual(len({s['personnalite_id'] for s in sources}),10)
 def test_offline_catalogue_matches(self):
  src=(ROOT/'index.html').read_text()
  match=re.search(r'const OFFLINE_PROGRAMS = (\[.*?\]);',src)
  self.assertIsNotNone(match)
  embedded=json.loads(match.group(1))
  configured=json.loads((ROOT/'config/programmes_officiels.json').read_text())['sources']
  self.assertEqual({x['url'] for x in embedded},{x['url'] for x in configured})
 def test_workflow_programmes(self):
  text=(ROOT/'.github/workflows/veille.yml').read_text()
  self.assertIn('scripts/surveiller_programmes_v33.py',text)
  self.assertIn('programmes.html',text)
