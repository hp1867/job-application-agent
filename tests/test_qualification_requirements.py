import unittest
from tests.test_pipeline import profile,job
from backend.app.agents.eligibility_checker import evaluate

class QualificationRequirementTests(unittest.TestCase):
    def test_raw_qualification_change_invalidates_preparation_revision(self):
        from backend.app.integrations.browser import job_revision
        original=job(experience_required='One year')
        self.assertNotEqual(job_revision(original),job_revision({**original,'experience_required':'Five years'}))
    def test_work_arrangement_change_invalidates_preparation_revision(self):
        from backend.app.integrations.browser import job_revision
        original=job()
        self.assertNotEqual(job_revision(original),job_revision({**original,'location':'Sydney'}))
    def test_raw_experience_is_not_silently_eligible(self):
        result=evaluate(job(experience_required='Two years commercial development'),profile(),{})
        self.assertIn('experience_required',result['unknowns'])
    def test_raw_education_is_not_silently_eligible(self):
        result=evaluate(job(requirements=[],education_required='Masters degree'),profile(),{})
        self.assertIn('education_required',result['unknowns'])
    def test_unrelated_project_check_does_not_cover_employment(self):
        j=job(experience_required='Two years paid employment',requirements=[{'field':'projects','op':'exists','label':'Project'}])
        self.assertIn('experience_required',evaluate(j,profile(),{})['unknowns'])
    def test_unsupported_experience_operator_remains_reviewable(self):
        j=job(experience_required='Two years',requirements=[{'field':'employment_experience','op':'years_at_least','value':2,'label':'Two years'}])
        self.assertIn('Two years',evaluate(j,profile(),{})['unknowns'])
