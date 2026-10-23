import importlib.util
import pathlib
import unittest

S=pathlib.Path(__file__).resolve().parents[1]/'scripts/candidatures_auto_v27.py'
spec=importlib.util.spec_from_file_location('candidatures_auto_v27',S)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class TestAuto(unittest.TestCase):
 def test_positive(self):
  self.assertEqual(m.detect('Camille Durand annonce sa candidature à la présidentielle 2027'),'Camille Durand')
 def test_negative(self):
  self.assertIsNone(m.detect('Camille Durand dément sa candidature à la présidentielle 2027'))
  self.assertIsNone(m.detect('Camille Durand pourrait annoncer sa candidature à la présidentielle 2027'))
 def test_two_sources(self):
  q={ 'a':{'title':'Camille Durand annonce sa candidature à la présidentielle 2027','url':'https://journal-a.fr/a'}, 'b':{'title':'Camille Durand confirme sa candidature à la présidentielle 2027','url':'https://journal-b.fr/b'}}
  c,signals=m.discover(q,{});self.assertEqual(len(c),1)
  self.assertEqual(c[0]['id'],'camille-durand')
  c,_=m.discover(q,{'camille-durand':{}});self.assertEqual(c,[])
 def test_same_domain(self):
  q=[{'title':'Camille Durand annonce sa candidature à la présidentielle 2027','url':'https://journal-a.fr/a'},{'title':'Camille Durand confirme sa candidature à la présidentielle 2027','url':'https://journal-a.fr/b'}]
  self.assertFalse(m.discover(q,{})[0])
 def test_no_position(self):
  base={'affirmations':[{'id':'q'}], 'positions':{'ancienne-personne':{'q':{'stance':2}}}}
  updated,new=m.apply(base,[{'id':'camille-durand','nom':'Camille Durand'}]);self.assertEqual(updated['positions']['camille-durand'],{'q':None})
  self.assertEqual(updated['positions']['ancienne-personne']['q']['stance'],2)

if __name__=='__main__':unittest.main()
