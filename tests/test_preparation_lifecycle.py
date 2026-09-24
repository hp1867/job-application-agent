"""Persistence/review tests using synthetic applicant documents and no network."""
import copy,hashlib,unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_hardening as hardening
from backend.app.orchestrator import Orchestrator
from backend.app.services.preparation_lifecycle import invalidate,reconcile,application_job_revision
from backend.app.services.application_service import approve,record_form_review
from backend.app.services.job_service import ingest
from backend.app.agents.application_agent import reserve_submission,confirm_submission
from backend.app.integrations.browser import packet_hash
from backend.app.integrations.browser_queue import BrowserQueue
from backend.app.utils.config import write_json,now
from backend.app.utils.answer_memory import review_hash,revisions

class PreparationLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.fixture=hardening.HardeningTests();self.fixture.setUp()
        self.app=self.fixture.ready();self.db=self.fixture.db;self.root=self.fixture.root
        self.app=record_form_review(self.db,self.app['application_id'],self.fixture.evidence(self.app,answer_memory_hash=review_hash({},self.app['packet']['questions'])))
        self.profile=self.fixture.p;self.job=self.fixture.j;self.aid=self.app['application_id']
        write_json(self.root/'data/candidate_profile.json',self.profile)
        write_json(self.root/'data/job_preferences.json',{'target_roles':['Software Engineering Intern'],'application_threshold':70})
        self.pdf=Path(self.app['packet']['documents']['resume']);self.original=self.pdf.read_bytes()
        self.artifact=self.db.artifact(self.aid,'resume','synthetic-persistence-fixture',{'pdf_path':str(self.pdf),'docx_path':str(self.pdf.with_suffix('.docx')),'test_only':True})
        self.app=self.db.update_application(self.aid,{'resume_version':self.artifact['artifact_id']})
        approve(self.db,self.aid,packet_hash(self.app['packet']))
    def tearDown(self):self.fixture.tearDown()
    def approvals(self):
        with self.db.connect() as c:return c.execute('SELECT COUNT(*) FROM approvals WHERE application_id=?',(self.aid,)).fetchone()[0]
    def test_scope_change_revokes_review_but_preserves_documents(self):
        result=invalidate(self.db,'Synthetic preference change',[self.aid],archive_documents=False)
        app=self.db.application(self.aid)
        self.assertEqual(result['invalidated_applications'],[self.aid]);self.assertEqual(app['status'],'ANALYSED')
        self.assertIsNone(app['packet']);self.assertEqual(self.approvals(),0)
        self.assertEqual(app['resume_version'],self.artifact['artifact_id']);self.assertFalse(self.db.rows('artifacts')[0].get('archived'))
        self.assertEqual(self.pdf.read_bytes(),self.original);self.assertEqual(app['date_found'],self.app['date_found'])
        self.assertEqual(self.db.history(self.aid)[-1]['reason'],'Synthetic preference change')
    def test_content_change_archives_records_without_deleting_files(self):
        invalidate(self.db,'Synthetic content change',[self.aid])
        app=self.db.application(self.aid)
        self.assertIsNone(app['resume_version']);self.assertIsNone(app['validation'])
        self.assertTrue(self.db.rows('artifacts')[0]['archived']);self.assertEqual(self.pdf.read_bytes(),self.original)
    def test_listing_closure_clears_ready_status_without_rewriting_resume(self):
        incoming={**self.job,'listing_state':'CLOSED','is_official':True,'listing_verified_at':now()}
        ingest(self.db,[incoming]);app=self.db.application(self.aid)
        self.assertEqual(app['status'],'ANALYSED');self.assertEqual(self.approvals(),0)
        self.assertEqual(app['resume_version'],self.artifact['artifact_id']);self.assertEqual(self.pdf.read_bytes(),self.original)
    def test_changed_job_content_archives_stale_resume(self):
        incoming={**self.job,'description':'Changed synthetic employer requirements','requirements_reviewed':False,'is_official':True,'listing_verified_at':now()}
        ingest(self.db,[incoming])
        self.assertTrue(self.db.rows('artifacts')[0]['archived']);self.assertIsNone(self.db.application(self.aid)['packet'])
    def test_source_refresh_alone_does_not_invalidate_review(self):
        incoming={**self.job,'listing_verified_at':now(),'is_official':True}
        self.assertEqual(application_job_revision(self.job),application_job_revision(incoming))
        ingest(self.db,[incoming])
        self.assertEqual(self.db.application(self.aid)['status'],'WAITING_FOR_APPROVAL');self.assertEqual(self.approvals(),1)
    def test_reserved_attempt_keeps_exact_packet_and_unique_reservation(self):
        reserve_submission(self.fixture.config,self.profile,self.job,self.app,self.db)
        result=invalidate(self.db,'Synthetic candidate change',[self.aid])
        app=self.db.application(self.aid)
        self.assertEqual(result['receipt_reconciliation_required'],[self.aid]);self.assertEqual(app['packet'],self.app['packet'])
        self.assertEqual(app['status'],'WAITING_FOR_APPROVAL');self.assertEqual(self.approvals(),0)
        self.assertFalse(self.db.rows('artifacts')[0].get('archived'));self.assertIn('receipt',app['next_action'])
        with self.db.connect() as c:self.assertEqual(c.execute('SELECT state FROM submission_attempts').fetchone()[0],'RESERVED')
    def test_invalidation_cancels_claimed_action_as_uncertain(self):
        queue=BrowserQueue(self.root,self.db);run=queue.start(self.aid,'fill')
        queue.enqueue(run,'OBSERVE',{});queue.claim(run)
        invalidate(self.db,'Synthetic form context change',[self.aid],archive_documents=False)
        state=queue.status()
        self.assertEqual(state['runs'][0]['state'],'FAILED');self.assertEqual(state['commands'][0]['state'],'UNCERTAIN')
    def test_orchestrator_never_replaces_an_uncertain_attempt_packet(self):
        reserve_submission(self.fixture.config,self.profile,self.job,self.app,self.db)
        changed={**self.job,'description':'A new synthetic role description','is_official':True,'listing_verified_at':now()}
        write_json(self.root/'data/inbox/jobs/changed.json',[changed])
        with patch('backend.app.orchestrator.tailor',side_effect=AssertionError('An attempted packet must not be regenerated')):
            result=Orchestrator(self.root).run(False,True)
        app=self.db.application(self.aid)
        self.assertEqual(app['packet'],self.app['packet']);self.assertEqual(self.pdf.read_bytes(),self.original)
        self.assertEqual(result['applications_prepared'],0);self.assertFalse(result['errors'])
    def test_direct_profile_edit_is_reconciled_on_next_run(self):
        changed=copy.deepcopy(self.profile);changed['full_name']='Another Synthetic Candidate'
        write_json(self.root/'data/candidate_profile.json',changed)
        Orchestrator(self.root).run(False,False)
        app=self.db.application(self.aid)
        self.assertNotIn(app['status'],{'READY_TO_APPLY','WAITING_FOR_APPROVAL'})
        self.assertIsNone(app['packet']);self.assertEqual(self.approvals(),0);self.assertTrue(self.db.rows('artifacts')[0]['archived'])
    def test_direct_document_edit_is_reconciled_on_next_run(self):
        self.pdf.write_bytes(b'Corrupted synthetic test document')
        Orchestrator(self.root).run(False,False)
        self.assertIsNone(self.db.application(self.aid)['packet']);self.assertEqual(self.approvals(),0)
        self.assertTrue(self.db.rows('artifacts')[0]['archived'])
    def test_expired_eligibility_does_not_stay_ready(self):
        self.db.save_job({**self.job,'closing_at':'2000-01-01'})
        Orchestrator(self.root).run(False,False)
        self.assertEqual(self.db.application(self.aid)['status'],'ANALYSED');self.assertEqual(self.approvals(),0)
        self.assertEqual(self.pdf.read_bytes(),self.original)
    def test_direct_answer_edit_invalidates_the_review_on_next_run(self):
        questions=[{'question':'Preferred name','answer':'Old alias','verified':True,'requires_manual_confirmation':False}]
        write_json(self.root/'data/application_answers.json',questions)
        self.app=record_form_review(self.db,self.aid,self.fixture.evidence(self.app,questions=questions,answer_memory_hash=review_hash(revisions(questions),questions)))
        approve(self.db,self.aid,packet_hash(self.app['packet']))
        write_json(self.root/'data/application_answers.json',[{**questions[0],'answer':'New alias'}])
        Orchestrator(self.root).run(False,False)
        self.assertIsNone(self.db.application(self.aid)['packet']);self.assertEqual(self.approvals(),0)
        self.assertFalse(self.db.rows('artifacts')[0].get('archived'))
    def test_increased_threshold_removes_ready_state(self):
        write_json(self.root/'data/job_preferences.json',{'target_roles':['Software Engineering Intern'],'application_threshold':100})
        Orchestrator(self.root).run(False,False)
        self.assertEqual(self.db.application(self.aid)['status'],'ANALYSED');self.assertEqual(self.approvals(),0)
    def test_submitted_history_is_not_rewritten(self):
        reserve_submission(self.fixture.config,self.profile,self.job,self.app,self.db)
        confirm_submission(self.db,self.aid,{'confirmation_text':'Synthetic receipt only','confirmation_url':'https://example.test/receipt'})
        before=self.db.application(self.aid);history=self.db.history(self.aid)
        invalidate(self.db,'Synthetic later preference change')
        self.assertEqual(self.db.application(self.aid),before);self.assertEqual(self.db.history(self.aid),history)

if __name__=='__main__':unittest.main()
