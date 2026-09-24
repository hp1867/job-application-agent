import unittest
from backend.app.utils.answer_memory import revisions,review_hash
from backend.app.agents.application_agent import answer_question

class AnswerMemoryTests(unittest.TestCase):
    def test_unrelated_answer_does_not_change_form_revision(self):
        current=[{'question':'Preferred name','answer':'Test','verified':True,'requires_manual_confirmation':False}]
        revised=current+[{'question':'Preferred team','answer':'Testing','verified':True}]
        self.assertEqual(review_hash(revisions(current),current),review_hash(revisions(revised),current))
    def test_revoked_verification_changes_form_revision(self):
        current=[{'question':'Preferred name','answer':'Test','verified':True,'requires_manual_confirmation':False}]
        revised=[{**current[0],'verified':False}]
        self.assertNotEqual(review_hash(revisions(current),current),review_hash(revisions(revised),current))
    def test_conflicting_answers_are_not_autofilled(self):
        current=[{'question':'Preferred name','answer':'First','verified':True,'requires_manual_confirmation':False},
                 {'question':'Preferred name','answer':'Second','verified':True,'requires_manual_confirmation':False}]
        self.assertEqual(answer_question('Preferred name',current)['action'],'ASK')
    def test_duplicate_identical_answers_do_not_change_revision(self):
        current=[{'question':'Preferred name','answer':'Test','verified':True,'requires_manual_confirmation':False}]
        self.assertEqual(revisions(current),revisions(current*2))

if __name__=='__main__':unittest.main()
