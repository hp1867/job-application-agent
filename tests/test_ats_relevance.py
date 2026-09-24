import unittest
from backend.app.agents.ats_relevance import report

class ATSRelevanceTests(unittest.TestCase):
    def setUp(self):
        self.manifest={'blocks':[{'field':'education','text':'Bachelor of Software Engineering'},
            {'field':'projects','text':'Built Python software with automated tests.'}]}
        self.text='Bachelor of Software Engineering Built Python software with automated tests.'
        self.job={'required_skills':['Python'],'preferred_skills':['Rust'],
            'requirements':[{'field':'education','op':'contains','value':'Software Engineering','label':'Relevant degree'}]}
    def evaluate(self):return report(self.manifest,self.job,self.text,facts_pass=True)
    def test_invalid_facts_have_no_relevance_score(self):
        result=report(self.manifest,self.job,self.text)
        self.assertEqual(result['status'],'UNAVAILABLE');self.assertIsNone(result['overall_score'])
    def test_required_and_optional_coverage_are_separate(self):
        result=self.evaluate()
        self.assertEqual(result['required_skills']['percent'],100)
        self.assertEqual(result['preferred_skills']['percent'],0)
        self.assertEqual(result['overall_score'],100)
        self.assertEqual(result['status'],'PARTIAL')
    def test_missing_requirements_are_unscored_not_passes(self):
        self.job={};result=self.evaluate()
        self.assertIsNone(result['overall_score']);self.assertEqual(result['scored_components'],[])
    def test_deduplicates_skill_terms_case_insensitively(self):
        self.job['required_skills']=['Python','python',' Rust ','']
        self.assertEqual(self.evaluate()['required_skills']['percent'],50)
    def test_degree_keyword_in_project_does_not_match_education(self):
        self.manifest['blocks'][0]['text']='Bachelor of Arts'
        self.assertEqual(self.evaluate()['education']['percent'],0)
    def test_years_of_experience_requires_review(self):
        self.job['requirements']=[{'field':'employment_experience','op':'gte','value':2,'label':'Two years employment'}]
        result=self.evaluate()['experience']
        self.assertEqual(result['review_count'],1);self.assertIsNone(result['percent'])
    def test_project_requirement_coverage_is_section_specific(self):
        self.job['requirements']=[{'field':'projects','op':'contains','value':'automated tests','label':'Testing project'}]
        self.assertEqual(self.evaluate()['experience']['percent'],100)
    def test_does_not_mutate_resume_or_job(self):
        import copy
        before=copy.deepcopy((self.manifest,self.job))
        self.evaluate();self.assertEqual((self.manifest,self.job),before)
