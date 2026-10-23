import importlib.util
import pathlib
import unittest
P = pathlib.Path(__file__).resolve().parents[1] / 'scripts/suivi_couverture_v29.py'
spec = importlib.util.spec_from_file_location('v29', P)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class Tests(unittest.TestCase):
    def test_unknown(self):
        base = {'positions': {'x': {'q': None}}}
        matches = {'personnalites': [{'id': 'x', 'statut': 'non_trouve', 'scrutins': []}]}
        result = mod.summarize(base, matches, {'scrutins': [], 'totalParsed': 5})
        self.assertEqual(result['lignes'][0]['positions'], 0)
        self.assertEqual(result['votesIndividuels'], 0)
    def test_known(self):
        base = {'positions': {'x': {'q': {'stance': -1}}}}
        matches = {'personnalites': [{'id': 'x', 'statut': 'identifiant_unique', 'acteurRef': 'PA123', 'scrutins': [{'vote': 'pour'}]}]}
        result = mod.summarize(base, matches, {'scrutins': [{}], 'totalParsed': 9})
        self.assertEqual(result['lignes'][0]['positions'], 1)
        self.assertEqual(result['votesIndividuels'], 1)
if __name__ == '__main__': unittest.main()
