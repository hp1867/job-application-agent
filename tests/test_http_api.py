import json,tempfile,threading,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from backend.app.main import create_server
from backend.app.agents.duplicate_checker import merge
from backend.app.agents.email_monitor import match_application
from tests.test_pipeline import job
from backend.app.integrations.database import Database
from backend.app.integrations.browser import packet_hash
from backend.app.services.application_service import approve

class HttpApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='job-agent-api-test-')
        self.server=create_server(Path(self.tmp.name),0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_address[1])
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3);self.tmp.cleanup()
    def call(self,path,data=None,headers=None):
        req=Request(self.url+path,None if data is None else json.dumps(data).encode(),headers or {})
        with urlopen(req,timeout=5) as r:return json.load(r)
    def test_health_is_dry_run(self):self.assertTrue(self.call('/api/health')['dry_run'])
    def test_fresh_workspace_has_editable_defaults(self):
        state=self.call('/api/state')
        self.assertEqual(state['preferences']['target_roles'],[])
        self.assertEqual(state['answers'],[])
        self.assertFalse(state['profile']['identity_confirmed'])
    def test_bad_host_rejected(self):
        with self.assertRaises(HTTPError) as exc:self.call('/api/health',headers={'Host':'attacker.test'})
        self.assertEqual(exc.exception.code,403)
    def test_mutation_without_csrf_rejected(self):
        with self.assertRaises(HTTPError) as exc:self.call('/api/preferences',{'application_threshold':72})
        self.assertEqual(exc.exception.code,403)
    def test_wrong_origin_rejected_even_with_token(self):
        token=self.call('/api/state')['csrf']
        with self.assertRaises(HTTPError) as exc:self.call('/api/preferences',{'application_threshold':72},{'X-Job-Agent-CSRF':token,'Origin':'https://attacker.test'})
        self.assertEqual(exc.exception.code,403)
    def test_preference_edit_persists_locally(self):
        token=self.call('/api/state')['csrf']
        self.assertTrue(self.call('/api/preferences',{'application_threshold':72},{'X-Job-Agent-CSRF':token})['saved'])
        self.assertEqual(self.call('/api/state')['preferences']['application_threshold'],72)
    def seed_review_only_fixture(self):
        # Deliberately incomplete synthetic packet for API invalidation testing;
        # it could not pass real document/eligibility/submission gates.
        db=Database(Path(self.tmp.name)/'data/job_agent.sqlite3');item=job();db.save_job(item);app=db.ensure_application(item)
        for status in ('ANALYSED','SHORTLISTED','RESUME_READY','READY_TO_APPLY','WAITING_FOR_APPROVAL'):
            app=db.update_application(app['application_id'],{},status,'Synthetic API lifecycle test only')
        app=db.update_application(app['application_id'],{'validation':{'result':'PASS','synthetic_test_stub':True},'packet':{'test_only':True,'questions':[{'question':'Preferred name','answer':'Test','verified':True,'requires_manual_confirmation':False}]}})
        approve(db,app['application_id'],packet_hash(app['packet']))
        return db,app['application_id']
    def test_changed_preference_revokes_old_application_review(self):
        db,aid=self.seed_review_only_fixture();token=self.call('/api/state')['csrf']
        self.call('/api/preferences',{'application_threshold':72},{'X-Job-Agent-CSRF':token})
        self.assertEqual(db.application(aid)['status'],'ANALYSED');self.assertIsNone(db.application(aid)['packet'])
        with db.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM approvals').fetchone()[0],0)
    def test_unchanged_preference_does_not_revoke_review(self):
        db,aid=self.seed_review_only_fixture();token=self.call('/api/state')['csrf']
        self.call('/api/preferences',{'application_threshold':70},{'X-Job-Agent-CSRF':token})
        self.assertEqual(db.application(aid)['status'],'WAITING_FOR_APPROVAL')
    def test_changed_answer_revokes_only_affected_review(self):
        token=self.call('/api/state')['csrf'];headers={'X-Job-Agent-CSRF':token}
        self.call('/api/answer',{'question':'Preferred name','answer':'Test','verified':True,'requires_manual_confirmation':False},headers)
        db,aid=self.seed_review_only_fixture()
        self.call('/api/answer',{'question':'Preferred name','answer':'New test alias','verified':True,'requires_manual_confirmation':False},headers)
        self.assertEqual(db.application(aid)['status'],'ANALYSED');self.assertIsNone(db.application(aid)['packet'])
    def test_new_unrelated_answer_does_not_erase_preparation(self):
        token=self.call('/api/state')['csrf'];db,aid=self.seed_review_only_fixture()
        self.call('/api/answer',{'question':'Preferred team','answer':'Synthetic testing','verified':True,'requires_manual_confirmation':False},{'X-Job-Agent-CSRF':token})
        self.assertEqual(db.application(aid)['status'],'WAITING_FOR_APPROVAL')
    def test_empty_profile_cannot_confirm_identity(self):
        token=self.call('/api/state')['csrf']
        with self.assertRaises(HTTPError) as exc:self.call('/api/profile',{'identity_confirmed':True},{'X-Job-Agent-CSRF':token})
        self.assertEqual(exc.exception.code,400)
    def test_no_submit_endpoint(self):
        token=self.call('/api/state')['csrf']
        with self.assertRaises(HTTPError) as exc:self.call('/api/submit',{}, {'X-Job-Agent-CSRF':token})
        self.assertEqual(exc.exception.code,404)
    def test_path_traversal_rejected(self):
        with self.assertRaises(HTTPError) as exc:self.call('/%2e%2e/%2e%2e/.env')
        self.assertEqual(exc.exception.code,403)

class FreshnessTests(unittest.TestCase):
    def test_other_candidates_does_not_mean_rejection(self):
        from backend.app.agents.email_classifier import classify
        result=classify({'subject':'Your application update','body':'We are still reviewing your application alongside other candidates. The recruitment process is ongoing.'})
        self.assertEqual(result['classification'],'GENERAL_UPDATE')
    def test_not_an_offer_requires_review(self):
        from backend.app.agents.email_classifier import classify
        result=classify({'subject':'Next steps','body':'This is not an offer of employment. We would be pleased to discuss a formal job offer for this role after final approval.'})
        self.assertEqual(result['classification'],'UNKNOWN')
    def test_company_legal_suffix_does_not_duplicate_role(self):
        from backend.app.agents.duplicate_checker import same_job
        self.assertTrue(same_job(job(company='Example Employer Pty Ltd'),job(company='Example Employer',source_url='https://another.test/advert/42')))
    def test_older_capture_cannot_reopen_closed_job(self):
        a=job(is_official=True,listing_state='CLOSED',listing_verified_at='2026-09-07T05:00:00+00:00')
        b=job(is_official=True,listing_state='OPEN',listing_verified_at='2026-09-06T05:00:00+00:00')
        self.assertEqual(merge(a,b)['listing_state'],'CLOSED')
    def test_same_content_retains_reviewed_requirements(self):
        a=job(is_official=True,listing_verified_at='2026-09-06T05:00:00+00:00')
        b=job(is_official=True,listing_verified_at='2026-09-07T05:00:00+00:00',requirements_reviewed=False,required_skills=[],requirements=[])
        self.assertTrue(merge(a,b)['requirements_reviewed']);self.assertEqual(merge(a,b)['required_skills'],['Python'])
    def test_changed_description_invalidates_review(self):
        a=job(is_official=True,listing_verified_at='2026-09-06T05:00:00+00:00')
        b=job(is_official=True,listing_verified_at='2026-09-07T05:00:00+00:00',description='New mandatory requirements',requirements_reviewed=False)
        self.assertFalse(merge(a,b)['requirements_reviewed'])
    def test_email_dates_compare_instants_not_strings(self):
        j=job();a={'application_id':'fixture','job_id':j['job_id'],'company':'Example Employer','role':'Software Engineering Intern','date_applied':'2026-09-07T05:00:00+00:00'}
        m={'subject':'Example Employer Software Engineering Intern','body':'Application received','received_at':'2026-09-07T10:00:00+10:00'}
        self.assertIsNone(match_application(m,[a],[j])[0])

if __name__=='__main__':unittest.main()
