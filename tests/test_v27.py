import importlib.util, pathlib, unittest
P=pathlib.Path(__file__).resolve().parents[1]/'scripts/candidatures_auto_v27.py'
spec=importlib.util.spec_from_file_location('v271',P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_annonce(self):
  self.assertEqual(m.detect('Camille Durand annonce sa candidature à la présidentielle 2027'),'Camille Durand')
  self.assertEqual(m.detect('Camille Durand se présente à la présidentielle 2027'),'Camille Durand')
  self.assertEqual(m.detect('Présidentielle 2027 : Camille Durand confirme sa candidature'),'Camille Durand')
 def test_refus_incertitude(self):
  self.assertIsNone(m.detect('Camille Durand pourrait annoncer sa candidature à la présidentielle 2027'))
  self.assertIsNone(m.detect('Camille Durand renonce à sa candidature à la présidentielle 2027'))
  self.assertIsNone(m.detect('Camille Durand envisagerait de se présenter à la présidentielle 2027'))
 def test_resume_et_sources(self):
  q={'a':{'title':'Actualité politique','excerpt':'Camille Durand annonce sa candidature à la présidentielle 2027','url':'https://www.franceinfo.fr/a'}, 'b':{'title':'Camille Durand se présente à la présidentielle 2027','url':'https://www.france24.com/b'}}
  proposed,found=m.discover(q,{})
  self.assertEqual(len(proposed),1)
  self.assertEqual(proposed[0]['id'],'camille-durand')
  self.assertEqual(len(found['camille-durand']),2)
 def test_domaine_identique_et_doublons(self):
  q=[{'title':'Camille Durand annonce sa candidature à la présidentielle 2027','url':'https://franceinfo.fr/a'}, {'title':'Camille Durand confirme sa candidature à la présidentielle 2027','url':'https://www.franceinfo.fr/b'}]
  self.assertFalse(m.discover(q,{})[0])
 def test_existants(self):
  q=[{'title':'Camille Durand annonce sa candidature à la présidentielle 2027','url':'https://franceinfo.fr/a'},{'title':'Camille Durand confirme sa candidature à la présidentielle 2027','url':'https://france24.com/b'}]
  self.assertFalse(m.discover(q,{'camille-durand':{}})[0])
 def test_aucune_opinion(self):
  base={'affirmations':[{'id':'q'}],'positions':{'ancien':{'q':{'stance':1}}}}
  updated,added=m.apply(base,[{'id':'camille-durand','nom':'Camille Durand'}])
  self.assertIsNone(updated['positions']['camille-durand']['q'])
  self.assertEqual(updated['positions']['ancien']['q']['stance'],1)
if __name__=='__main__':unittest.main()
