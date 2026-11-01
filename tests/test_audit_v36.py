import importlib.util
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/auditer_v36.py'
spec = importlib.util.spec_from_file_location('auditer_v36', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TestAuditV36(unittest.TestCase):
    def test_dossier_incomplet_echoue(self):
        with tempfile.TemporaryDirectory() as tmp:
            erreurs = module.auditer(Path(tmp))
            self.assertTrue(any('index.html' in x for x in erreurs))

    def test_version_et_questions_verifiees(self):
        racine = Path(__file__).resolve().parents[1]
        if (racine / 'index.html').is_file() and (racine / 'manifest.json').is_file() and (racine / 'boussole_2027_positions.json').is_file():
            self.assertEqual(module.auditer(racine), [])


if __name__ == '__main__':
    unittest.main()
