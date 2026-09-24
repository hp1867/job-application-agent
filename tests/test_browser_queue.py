"""Synthetic queue safety tests. No browser, employer or mail network is contacted."""
import copy,json,sqlite3,tempfile,threading,time,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
from tests.test_pipeline import profile,job
from backend.app.orchestrator import Orchestrator
from backend.app.agents.job_analyser import analyse
from backend.app.integrations.browser import prepare_packet
from backend.app.integrations.browser_queue import BrowserQueue,BrowserBridgeError,QueuedBrowserDriver
from backend.app.services.browser_service import run_browser
from backend.app.utils.config import ROOT,write_json

class BrowserQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='job-browser-unit-')
        self.root=Path(self.temp.name);self.engine=Orchestrator(self.root);self.db=self.engine.db
        write_json(self.root/'data/job_preferences.json',{'target_roles':['Software Engineering Intern'],'application_threshold':70})
        self.profile=profile();write_json(self.root/'data/candidate_profile.json',self.profile)
        write_json(self.root/'data/browser_fixture.json',{'synthetic_test_only':True,'browser_url':'http://127.0.0.1:8767/'})
        self.job=job(source_url='https://example.test/jobs/browser-fixture');self.job['analysis']=analyse(self.job,self.profile,{})
        self.db.save_job(self.job);app=self.db.ensure_application(self.job);self.aid=app['application_id']
        for status in ('ANALYSED','SHORTLISTED','RESUME_READY','READY_TO_APPLY'):
            self.db.update_application(self.aid,{},status,'Synthetic transport test only')
        self.document=self.root/'generated/resumes/synthetic-test.txt'
        self.document.write_text('SYNTHETIC_TEST_CANDIDATE\nTest Candidate',encoding='utf-8')
        packet=prepare_packet(self.profile,self.job,{'pdf_path':str(self.document)})
        self.db.update_application(self.aid,{'packet':packet,'score':95,'validation':{'result':'PASS','synthetic_test_stub':True}})
        self.queue=BrowserQueue(self.root,self.db)
    def tearDown(self):self.temp.cleanup()
    def enqueue(self,action='OBSERVE'):
        run=self.queue.start(self.aid,'fill');command=self.queue.enqueue(run,action,{})
        return run,command
    def test_only_one_active_workflow_per_application(self):
        self.queue.start(self.aid,'fill')
        with self.assertRaises(sqlite3.IntegrityError):self.queue.start(self.aid,'fill')
    def test_cli_acknowledges_dash_prefixed_claim_token(self):
        import io
        from contextlib import redirect_stdout
        from backend.app.cli import main
        run,command=self.enqueue()
        with patch('backend.app.integrations.browser_queue.secrets.token_urlsafe',return_value='-synthetic-claim-token'):
            claim=self.queue.claim(run)['command']
        args=['job-agent','--root',str(self.root),'browser-reply',command,'--token='+claim['claim_token'],
              '--result-json',json.dumps({'observation_source':'Synthetic CLI regression'})]
        output=io.StringIO()
        with patch('sys.argv',args),redirect_stdout(output):main()
        self.assertTrue(json.loads(output.getvalue())['recorded'])
        self.assertEqual(self.queue.status()['commands'][0]['state'],'ACKNOWLEDGED')
    def test_claim_is_once_and_tokens_are_hashed(self):
        run,command=self.enqueue();claim=self.queue.claim(run)['command']
        self.assertIsNone(self.queue.claim(run)['command'])
        with self.db.connect() as c:row=dict(c.execute('SELECT * FROM browser_commands WHERE command_id=?',(command,)).fetchone())
        self.assertNotEqual(row['claim_hash'],claim['claim_token']);self.assertNotIn(claim['claim_token'],json.dumps(self.queue.status()))
    def test_wrong_token_missing_evidence_and_duplicate_reply_refused(self):
        run,command=self.enqueue();claim=self.queue.claim(run)['command']
        with self.assertRaises(BrowserBridgeError):self.queue.reply(command,'incorrect',{'observation_source':'synthetic unit test'})
        with self.assertRaises(ValueError):self.queue.reply(command,claim['claim_token'],{})
        self.queue.reply(command,claim['claim_token'],{'observation_source':'synthetic unit test'})
        with self.assertRaises(BrowserBridgeError):self.queue.reply(command,claim['claim_token'],{'observation_source':'synthetic unit test'})
    def test_action_executor_claim_is_bound_to_exact_payload(self):
        run,command=self.enqueue();claim=self.queue.claim(run)['command']
        self.assertEqual(self.queue.validate_claim(claim)['application_id'],self.aid)
        altered=copy.deepcopy(claim);altered['payload']={'value':'untrusted'}
        with self.assertRaises(BrowserBridgeError):self.queue.validate_claim(altered)
    def test_acknowledged_action_cannot_execute_again(self):
        run,command=self.enqueue();claim=self.queue.claim(run)['command']
        self.queue.reply(command,claim['claim_token'],{'observation_source':'Synthetic acknowledged action'})
        with self.assertRaises(BrowserBridgeError):self.queue.validate_claim(claim)
    def test_failed_start_is_not_left_active(self):
        self.profile['intake_deferred']=True;write_json(self.root/'data/candidate_profile.json',self.profile)
        with self.assertRaises(BrowserBridgeError):self.queue.start(self.aid,'fill')
        self.assertEqual(self.queue.status()['runs'][0]['state'],'FAILED')
    def test_profile_change_prevents_claim(self):
        run,command=self.enqueue();self.profile['phone']='+61 400 111 111';write_json(self.root/'data/candidate_profile.json',self.profile)
        with self.assertRaises(BrowserBridgeError):self.queue.claim(run)
    def test_document_change_prevents_claim(self):
        run,command=self.enqueue();self.document.write_text('changed fixture',encoding='utf-8')
        with self.assertRaises(BrowserBridgeError):self.queue.claim(run)
    def test_answer_memory_change_prevents_claim(self):
        run,command=self.enqueue()
        write_json(self.root/'data/application_answers.json',[{'question':'Preferred name','answer':'New synthetic answer','verified':True}])
        with self.assertRaises(BrowserBridgeError):self.queue.claim(run)
    def test_revoked_validation_prevents_claim(self):
        run,command=self.enqueue();self.db.update_application(self.aid,{'validation':{'result':'FAIL'}})
        with self.assertRaises(BrowserBridgeError):self.queue.claim(run)
    def test_claimed_timeout_is_uncertain_not_requeued(self):
        run,command=self.enqueue();self.queue.claim(run)
        with self.db.connect() as c:c.execute('UPDATE browser_commands SET expires_at=? WHERE command_id=?',('2000-01-01T00:00:00+00:00',command))
        self.queue.expire();status=self.queue.status()
        self.assertEqual(status['commands'][0]['state'],'UNCERTAIN');self.assertEqual(status['runs'][0]['state'],'FAILED')
        self.assertIsNone(self.queue.claim(run)['command'])
    def test_missing_worker_heartbeat_expires_run(self):
        run,command=self.enqueue()
        with self.db.connect() as c:c.execute('UPDATE browser_runs SET updated_at=? WHERE run_id=?',('2000-01-01T00:00:00+00:00',run))
        self.queue.expire();self.assertEqual(self.queue.run(run)['state'],'FAILED')
    def test_suspended_worker_cannot_revive_an_expired_lease(self):
        run,command=self.enqueue()
        with self.db.connect() as c:c.execute('UPDATE browser_runs SET updated_at=? WHERE run_id=?',('2000-01-01T00:00:00+00:00',run))
        with self.assertRaises(BrowserBridgeError):self.queue.wait_result(command)
        self.assertEqual(self.queue.run(run)['state'],'FAILED')
    def test_fixture_never_enables_submit_or_real_employer_navigation(self):
        with self.assertRaises(BrowserBridgeError):self.queue.start(self.aid,'submit')
        run=self.queue.start(self.aid,'fill');driver=QueuedBrowserDriver(self.queue,run)
        with self.assertRaises(BrowserBridgeError):driver.navigate('https://employer.test/apply')
        with self.assertRaises(BrowserBridgeError):self.queue.enqueue(run,'SUBMIT_AND_OBSERVE_CONFIRMATION',{})
        with self.db.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM submission_attempts').fetchone()[0],0)
    def test_synthetic_validation_cannot_escape_fixture(self):
        write_json(self.root/'data/browser_fixture.json',{})
        with self.assertRaises(BrowserBridgeError):self.queue.start(self.aid,'fill')
    def test_driver_requires_observed_action_success(self):
        run=self.queue.start(self.aid,'fill');driver=QueuedBrowserDriver(self.queue,run)
        with patch.object(self.queue,'wait_result',return_value={'observation_source':'test only'}):
            with self.assertRaises(BrowserBridgeError):driver.fill({'label':'Full name'},'Test Candidate')
    def test_full_workflow_queue_reaches_approval_without_submission(self):
        results={};errors=[]
        def worker():
            try:results.update(run_browser(self.root,self.db,self.aid,timeout=30))
            except Exception as exc:errors.append(exc)
        thread=threading.Thread(target=worker);thread.start();actions=[];observations=0
        try:
            deadline=time.monotonic()+15
            while thread.is_alive() and time.monotonic()<deadline:
                item=self.queue.claim()['command']
                if item is None:time.sleep(.02);continue
                actions.append(item['action'])
                result={'ok':True,'observation_source':'synthetic unit-test driver, not a real browser'}
                if item['action']=='OBSERVE':
                    observations+=1
                    result.update({'fields':[{'question':'Full name','candidate_field':'full_name','locator':{'label':'Full name'}},{'question':'Email','candidate_field':'email','locator':{'label':'Email'}}],
                        'upload_controls':{'resume':{'label':'Test resume'}},'website_permits_automation':True,'website_policy_evidence':'Synthetic local test only',
                        'captcha':False,'mfa':False,'login_required':False,'form_reviewed':True,'legal_review_complete':True,'fields_filled':observations==2,'uploads_confirmed':observations==2})
                elif item['action']=='NAVIGATE':self.assertEqual(item['payload']['url'],'http://127.0.0.1:8767/')
                self.queue.reply(item['command_id'],item['claim_token'],result)
            thread.join(2)
        finally:
            if thread.is_alive():
                for run in self.queue.status()['runs']:self.queue.finish(run['run_id'],'Test cleanup')
                thread.join(2)
        self.assertFalse(errors,errors);self.assertFalse(thread.is_alive())
        self.assertEqual(actions,['NAVIGATE','OBSERVE','FILL','FILL','UPLOAD','OBSERVE'])
        self.assertEqual(results['status'],'WAITING_FOR_APPROVAL');self.assertFalse(results['submitted'])
        self.assertEqual(self.queue.status()['runs'][0]['state'],'DONE')
        self.assertTrue(all(c['state']=='ACKNOWLEDGED' for c in self.queue.status()['commands']))
        with self.db.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM submission_attempts').fetchone()[0],0)

if __name__=='__main__':unittest.main()
