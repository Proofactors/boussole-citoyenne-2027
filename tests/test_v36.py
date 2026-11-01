import json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class CandidateTests(unittest.TestCase):
 def test_unambiguous_status(self):
  data=json.loads((ROOT/'config/candidatures_v36.json').read_text()); entries={x['id']:x for x in data['entries']}
  self.assertEqual(entries['raphael-glucksmann']['status'],'designe_primaire')
  for pid in ('olivier-faure','segolene-royal','emmanuel-maurel','jerome-guedj'):
   self.assertEqual(entries[pid]['status'],'non_retenu_primaire')
 def test_sources_and_uniqueness(self):
  data=json.loads((ROOT/'config/candidatures_v36.json').read_text());ids=[x['id'] for x in data['entries']]
  self.assertEqual(len(ids),len(set(ids)))
  self.assertTrue(all(x['evidence'] and all(u.startswith('https://') for u in x['evidence']) for x in data['entries']))
 def test_no_scoring_changes(self):
  self.assertIn("const RELEASE='V36'",(ROOT/'index.html').read_text())
  self.assertTrue((ROOT/'candidatures.html').exists())
if __name__=='__main__':unittest.main()
