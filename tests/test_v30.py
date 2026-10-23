import copy
import importlib.util
import unittest
from pathlib import Path

MODULE=Path(__file__).resolve().parents[1]/'scripts'/'qualifier_preuves_v30.py'
spec=importlib.util.spec_from_file_location('qualifier_v30',MODULE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
BASE={'affirmations':[{'id':'retraite-62','text':'Retraite à 62 ans','theme':'retraites'}, {'id':'smic','text':'Augmenter le SMIC','theme':'travail'}], 'positions':{'exemple':{'retraite-62':None}}}
JOIN={'personnalites':[{'id':'exemple','statut':'identifiant_unique','acteurRef':'PA123','scrutins':[{'numero':'100','date':'2026-10-20','titre':"l'amendement de suppression de l'âge légal de départ à la retraite à 62 ans",'vote':'pour','acteurRef':'PA123'}, {'numero':'101','date':'2026-10-21','titre':'article du projet de financement de la sécurité sociale','vote':'contre','acteurRef':'PA123'}]}]}

class V30(unittest.TestCase):
 def test_correspondance_specifique(self):
  self.assertEqual(m.candidate_question_ids("L'âge légal de départ à la retraite fixé à 62 ans",{'retraite-62','smic'}),['retraite-62'])
 def test_termes_generiques_exclus(self):
  self.assertEqual(m.candidate_question_ids('Article 9 du financement de la sécurité sociale',{'retraite-62','smic'}),[])
 def test_suppression_identifiee(self):
  self.assertEqual(m.scrutiny_type('Amendement de suppression de l’article 10'),'amendement_de_suppression')
 def test_aucune_position_modifiee(self):
  before=copy.deepcopy(BASE)
  out=m.build(BASE,JOIN)
  self.assertEqual(BASE,before)
  self.assertEqual(out['nombrePropositions'],1)
  self.assertIsNone(out['propositions'][0]['positionProposee'])
  self.assertEqual(out['propositions'][0]['vote'],'pour')
 def test_identifiant_ambigu_non_attribue(self):
  j=copy.deepcopy(JOIN);j['personnalites'][0]['statut']='ambigu'
  self.assertEqual(m.build(BASE,j)['nombrePropositions'],0)
 def test_zero_resultat_rendu(self):
  j=copy.deepcopy(JOIN);j['personnalites'][0]['scrutins']=[]
  self.assertIn('0 signalements',m.render(m.build(BASE,j)))
 def test_html_echappement(self):
  out=m.build(BASE,JOIN);out['propositions'][0]['objet']='<script>alert(1)</script>'
  page=m.render(out)
  self.assertIn('&lt;script&gt;',page)

if __name__=='__main__':unittest.main()
