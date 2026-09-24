import tempfile,unittest
from pathlib import Path
from tests.test_pipeline import profile,job
from backend.app.utils.role_scope import assess
from backend.app.agents.eligibility_checker import evaluate
from backend.app.orchestrator import Orchestrator
from backend.app.utils.config import write_json

class RoleScopeTests(unittest.TestCase):
    def test_unrelated_search_result_is_not_a_technology_role(self):
        item=job(title='Voice Talent - Australian English (female) - Remote',description='Use AI software and technology to record voice samples.')
        self.assertEqual(assess(item,{})['status'],'OUT_OF_SCOPE')
        self.assertEqual(evaluate(item,profile(),{})['status'],'NOT_ELIGIBLE')
    def test_supported_role_variants(self):
        for title in ('Associate Software Engineer','Cyber Security Intern','Junior Backend Engineer','Graduate Full-stack Developer','Information Technology Intern','SOC Analyst Intern','IT Service Desk Intern'):
            self.assertEqual(assess(job(title=title),{})['status'],'IN_SCOPE',title)
    def test_ambiguous_graduate_program_is_review_not_rejection(self):
        item=job(title='2027 Graduate Program')
        self.assertEqual(assess(item,{})['status'],'NEEDS_REVIEW')
        self.assertEqual(evaluate(item,profile(),{})['status'],'NEEDS_REVIEW')
    def test_explicit_preferences_are_editable(self):
        prefs={'target_roles':['Accounting Graduate']}
        self.assertEqual(assess(job(title='Graduate Accounting Program'),prefs)['status'],'IN_SCOPE')
        self.assertEqual(assess(job(),prefs)['status'],'OUT_OF_SCOPE')
    def test_empty_targets_require_configuration(self):
        self.assertEqual(assess(job(),{'target_roles':[]})['status'],'NEEDS_REVIEW')
    def test_unrelated_role_is_retained_but_never_shortlisted_or_reported_as_top(self):
        with tempfile.TemporaryDirectory(prefix='job-role-scope-') as folder:
            root=Path(folder);engine=Orchestrator(root)
            write_json(root/'data/candidate_profile.json',profile())
            write_json(root/'data/job_preferences.json',{'target_roles':['Software Engineering Intern'],'application_threshold':70})
            write_json(root/'data/inbox/jobs/fixture.json',[job(title='Voice Talent',description='Technology company using Python and React')])
            report=engine.run(False,False)
            self.assertEqual(len(engine.db.rows('jobs')),1)
            self.assertEqual(report['top_jobs'],[]);self.assertEqual(report['excluded_jobs'],1)
            self.assertEqual(engine.db.rows('applications')[0]['status'],'ANALYSED')
            self.assertEqual(engine.db.rows('jobs')[0]['analysis']['scoring']['components']['career_relevance'],0)

if __name__=='__main__':unittest.main()
