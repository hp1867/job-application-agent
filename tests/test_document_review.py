import hashlib,tempfile,unittest
from pathlib import Path
from tests.test_pipeline import profile,job
from backend.app.agents.cover_letter_generator import generate,compose
from backend.app.agents.cover_letter_validator import validate_cover
from backend.app.agents.resume_tailor import tailor
from backend.app.integrations.database import Database
from backend.app.services.artifact_review import record_review
from backend.app.utils.config import write_json,now
from backend.app.orchestrator import Orchestrator

class DocumentReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='job-agent-document-test-');self.root=Path(self.temp.name)
        self.p=profile();self.j=job(cover_letter_required=True)
    def tearDown(self):self.temp.cleanup()
    def test_cover_letter_exact_content_validation(self):
        manifest=generate(self.p,self.j,self.root)
        result=validate_cover(manifest,self.p,self.j)
        self.assertTrue(result['facts_pass']);self.assertEqual(result['result'],'FAIL')
        self.assertIn('Visual layout review pending for DOCX and PDF',result['errors'])
    def test_cover_letter_unmanifested_claim_rejected(self):
        from docx import Document
        manifest=generate(self.p,self.j,self.root)
        doc=Document(manifest['docx_path']);doc.add_paragraph('I hold an invented PhD.');doc.save(manifest['docx_path'])
        self.assertFalse(validate_cover(manifest,self.p,self.j)['facts_pass'])
    def test_cover_letter_wrong_company_rejected(self):
        manifest=generate(self.p,self.j,self.root)
        self.assertFalse(validate_cover(manifest,self.p,job(company='Different Employer'))['facts_pass'])
    def test_project_without_bullets_does_not_break_generation(self):
        self.p['projects']=[{'name':'Synthetic incomplete project','bullets':[]}]
        self.assertTrue(compose(self.p,self.j));self.assertTrue(validate_cover(generate(self.p,self.j,self.root),self.p,self.j)['facts_pass'])
    def test_cover_letter_changes_version_with_verified_profile(self):
        before=generate(self.p,self.j,self.root);self.p['full_name']='Another Synthetic Candidate'
        after=generate(self.p,self.j,self.root)
        self.assertNotEqual(before['fingerprint'],after['fingerprint'])
    def test_bare_visual_pass_is_not_accepted_by_review_service(self):
        db=Database(self.root/'data/job_agent.sqlite3');db.save_job(self.j);app=db.ensure_application(self.j)
        manifest=tailor(self.p,self.j,self.root);art=db.artifact(app['application_id'],'resume',manifest['fingerprint'],manifest)
        write_json(self.root/'data/candidate_profile.json',self.p)
        evidence={'result':'PASS','reviewed_by':'Synthetic test','review_notes':'No actual rendering','reviewed_at':now(),
                  'pdf_sha256':hashlib.sha256(Path(manifest['pdf_path']).read_bytes()).hexdigest(),'docx_sha256':hashlib.sha256(Path(manifest['docx_path']).read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError,'Every rendered page'):record_review(self.root,db,art['artifact_id'],evidence)
    def test_repeated_pipeline_does_not_rewrite_cover_letter(self):
        write_json(self.root/'data/candidate_profile.json',self.p);write_json(self.root/'data/inbox/jobs/test.json',[self.j])
        write_json(self.root/'data/job_preferences.json',{'target_roles':['Software Engineering Intern'],'preferred_locations':['Melbourne'],'application_threshold':70})
        engine=Orchestrator(self.root);a=engine.run(False,True)
        self.assertFalse(a['errors'],a['errors'])
        before=next(x for x in engine.db.rows('artifacts') if x['kind']=='cover_letter')
        sha=hashlib.sha256(Path(before['pdf_path']).read_bytes()).hexdigest()
        b=engine.run(False,True);after=next(x for x in engine.db.rows('artifacts') if x['kind']=='cover_letter')
        self.assertFalse(b['errors'],b['errors']);self.assertEqual(b['applications_prepared'],0)
        self.assertEqual(sha,hashlib.sha256(Path(after['pdf_path']).read_bytes()).hexdigest());self.assertEqual(before['created_at'],after['created_at'])

if __name__=='__main__':unittest.main()
