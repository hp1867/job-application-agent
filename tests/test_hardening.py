import copy,json,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
from tests.test_pipeline import profile,job
from backend.app.orchestrator import Orchestrator
from backend.app.integrations.database import Database
from backend.app.integrations.browser import prepare_packet,packet_hash
from backend.app.integrations.application_workflow import ApplicationWorkflow
from backend.app.integrations.public_ats import read_board,search_scope
from backend.app.services.candidate_intake import defer_candidate
from backend.app.services.application_service import approve,record_form_review
from backend.app.services.report_service import daily_report,local_day
from backend.app.agents.application_agent import gates,reserve_submission
from backend.app.agents.resume_tailor import tailor
from backend.app.agents.resume_validator import validate
from backend.app.agents.job_analyser import analyse
from backend.app.models.contracts import export_schemas
from backend.app.models.candidate import FIELDS
from backend.app.models.job import normalise
from backend.app.utils.config import write_json,read_json,now

class FakeBrowser:
    """No network, no real employer. Records only synthetic actions."""
    def __init__(self,overrides=None):
        self.actions=[];self.overrides=overrides or {}
    def navigate(self,url):
        assert url.startswith('https://example.test/');self.actions.append(('navigate',url))
    def fill(self,locator,value):self.actions.append(('fill',locator,value))
    def upload(self,locator,path):self.actions.append(('upload',locator,path))
    def observe(self):
        return {'fields':[{'question':'Full name','candidate_field':'full_name','locator':'fake-name'},{'question':'Email','candidate_field':'email','locator':'fake-email'}],
            'upload_controls':{'resume':'fake-upload'},'observation_source':'Synthetic browser fixture',
            'website_permits_automation':True,'website_policy_evidence':'Synthetic fixture permission only',
            'form_reviewed':True,'fields_filled':True,'uploads_confirmed':True,'legal_review_complete':True,**self.overrides}
    def submit_and_observe_confirmation(self):
        self.actions.append(('submit',));return {'confirmation_text':'Synthetic local receipt','confirmation_url':'https://example.test/receipt'}

class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='job-agent-isolated-');self.root=Path(self.temp.name)
        self.p=profile();self.j=job(listing_verified_at=now());self.db=Database(self.root/'data/job_agent.sqlite3')
        self.config={'dry_run':False,'production_approved':True,'automation_level':2,'application_threshold':70,'auto_submit_threshold':80}
    def tearDown(self):self.temp.cleanup()
    def ready(self,reviewed=True):
        self.j['analysis']=analyse(self.j,self.p,{});self.j['analysis']['scoring']['overall_score']=95
        self.db.save_job(self.j);a=self.db.ensure_application(self.j)
        for status in ('ANALYSED','SHORTLISTED','RESUME_READY','READY_TO_APPLY'):a=self.db.update_application(a['application_id'],{},status,'Synthetic fixture setup')
        manifest=tailor(self.p,self.j,self.root);manifest['visual_review']='PASS' # Synthetic test, not a real document QA attestation.
        validation=validate(manifest,self.p,self.j);self.assertEqual(validation['result'],'PASS')
        a=self.db.update_application(a['application_id'],{'packet':prepare_packet(self.p,self.j,manifest),'validation':validation,'score':95})
        if reviewed:a=record_form_review(self.db,a['application_id'],self.evidence(a))
        return a
    def evidence(self,a,**changes):
        return {'expected_packet_hash':packet_hash(a['packet']),'observation_source':'Synthetic isolated fixture',
                'observed_at':now(),'form_reviewed':True,'fields_filled':True,'uploads_confirmed':True,'legal_review_complete':True,
                'website_permits_automation':True,'website_policy_evidence':'Synthetic fixture only','questions':[],**changes}
    def test_exact_level_two_approval_then_fake_receipt(self):
        a=self.ready();self.assertIn('EXACT_APPLICATION_APPROVAL_REQUIRED',gates(self.config,self.p,self.j,a,self.db)['blockers'])
        approve(self.db,a['application_id'],packet_hash(a['packet']))
        self.assertTrue(gates(self.config,self.p,self.j,a,self.db)['allowed'])
        fake=FakeBrowser();done=ApplicationWorkflow(self.db,fake).submit(self.config,self.p,self.j,a)
        self.assertEqual(done['status'],'APPLIED');self.assertTrue(done['date_applied'])
        with self.assertRaises(ValueError):ApplicationWorkflow(self.db,fake).submit(self.config,self.p,self.j,a)
        self.assertEqual(fake.actions.count(('submit',)),1)
    def test_dry_run_never_calls_driver_submit(self):
        a=self.ready();approve(self.db,a['application_id'],packet_hash(a['packet']));fake=FakeBrowser()
        with self.assertRaises(ValueError):ApplicationWorkflow(self.db,fake).submit({**self.config,'dry_run':True},self.p,self.j,a)
        self.assertEqual(fake.actions,[])
    def test_same_employer_destination_cannot_submit_under_second_record(self):
        first=self.ready();approve(self.db,first['application_id'],packet_hash(first['packet']))
        reserve_submission(self.config,self.p,self.j,first,self.db)
        self.j=job(company='Another observed employer label',listing_verified_at=now())
        second=self.ready();approve(self.db,second['application_id'],packet_hash(second['packet']))
        self.assertIn('SUBMISSION_TARGET_ALREADY_ATTEMPTED',gates(self.config,self.p,self.j,second,self.db)['blockers'])
    def test_level_one_never_calls_driver_submit(self):
        a=self.ready();fake=FakeBrowser()
        with self.assertRaises(ValueError):ApplicationWorkflow(self.db,fake).submit({**self.config,'automation_level':1},self.p,self.j,a)
        self.assertEqual(fake.actions,[])
    def test_level_three_strict_separate_threshold(self):
        a=self.ready();config={**self.config,'automation_level':3}
        self.j['analysis']['scoring']['overall_score']=80
        self.db.save_job(self.j)
        self.assertIn('SCORE_BELOW_THRESHOLD',gates(config,self.p,self.j,a,self.db)['blockers'])
        self.j['analysis']['scoring']['overall_score']=81
        self.db.save_job(self.j)
        self.assertTrue(gates(config,self.p,self.j,a,self.db)['allowed'])
    def test_changed_form_requires_new_approval(self):
        a=self.ready();approve(self.db,a['application_id'],packet_hash(a['packet']))
        a=record_form_review(self.db,a['application_id'],self.evidence(a,questions=[{'question':'Notice period','answer':None,'verified':False,'requires_manual_confirmation':True}]))
        self.assertIn('UNRESOLVED_QUESTIONS',gates(self.config,self.p,self.j,a,self.db)['blockers'])
        self.assertIn('EXACT_APPLICATION_APPROVAL_REQUIRED',gates(self.config,self.p,self.j,a,self.db)['blockers'])
    def test_changed_document_invalidates_packet(self):
        a=self.ready();Path(a['packet']['documents']['resume']).write_bytes(b'Synthetic changed document')
        self.assertIn('APPLICATION_DOCUMENT_CHANGED',gates(self.config,self.p,self.j,a,self.db)['blockers'])
    def test_stale_and_future_form_reviews_block(self):
        a=self.ready()
        for hours in (-3,3):
            a=record_form_review(self.db,a['application_id'],self.evidence(a,observed_at=(datetime.now(timezone.utc)+timedelta(hours=hours)).isoformat()))
            self.assertIn('FORM_REVIEW_EXPIRED',gates(self.config,self.p,self.j,a,self.db)['blockers'])
    def test_stale_listing_needs_recheck(self):
        a=self.ready();self.j['listing_verified_at']='2020-01-01T00:00:00+00:00'
        self.assertIn('LISTING_RECHECK_REQUIRED',gates(self.config,self.p,self.j,a,self.db)['blockers'])
    def test_unverified_packet_value_blocks(self):
        a=self.ready();a['packet']['verified_fields']['technical_skills']=['Invented claim']
        self.assertIn('UNVERIFIED_FORM_FIELD',gates(self.config,self.p,self.j,a,self.db)['blockers'])
    def test_fake_browser_fill_and_upload_no_submission(self):
        a=self.ready(False);fake=FakeBrowser();result=ApplicationWorkflow(self.db,fake).fill(self.p,self.j,a,[])
        self.assertEqual(result['status'],'WAITING_FOR_APPROVAL');self.assertFalse(result['submitted'])
        self.assertEqual([x[0] for x in fake.actions],['navigate','fill','fill','upload'])
    def test_captcha_stops_before_filling(self):
        a=self.ready(False);fake=FakeBrowser({'captcha':True})
        self.assertEqual(ApplicationWorkflow(self.db,fake).fill(self.p,self.j,a,[])['reason'],'CAPTCHA')
        self.assertEqual(len(fake.actions),1)
    def test_unknown_question_blocks_readiness(self):
        a=self.ready(False);fake=FakeBrowser({'fields':[{'question':'Exact GPA?','locator':'fake-gpa'}]})
        result=ApplicationWorkflow(self.db,fake).fill(self.p,self.j,a,[])
        self.assertEqual(result['status'],'READY_TO_APPLY');self.assertEqual(result['unresolved_questions'],['Exact GPA?'])
    def test_changed_website_permission_blocks_final_readiness(self):
        a=self.ready(False);fake=FakeBrowser();initial=fake.observe()
        with patch.object(fake,'observe',side_effect=[initial,{**initial,'website_permits_automation':False,'website_policy_evidence':None}]):
            result=ApplicationWorkflow(self.db,fake).fill(self.p,self.j,a,[])
        self.assertEqual(result['status'],'READY_TO_APPLY')
        self.assertFalse(self.db.application(a['application_id'])['packet']['website_permits_automation'])
    def test_new_final_page_question_requires_another_review(self):
        a=self.ready(False);fake=FakeBrowser();initial=fake.observe()
        final={**initial,'fields':initial['fields']+[{'question':'Do you certify this declaration?','locator':'fake-declaration'}]}
        with patch.object(fake,'observe',side_effect=[initial,final]):result=ApplicationWorkflow(self.db,fake).fill(self.p,self.j,a,[])
        self.assertEqual(result['status'],'READY_TO_APPLY');self.assertEqual(result['unresolved_questions'],['Do you certify this declaration?'])
    def test_unknown_question_can_resume_after_a_verified_answer(self):
        from backend.app.utils.answer_memory import revisions,review_hash
        a=self.ready(False);fake=FakeBrowser();fields=fake.observe()['fields']+[{'question':'Preferred name','locator':'fake-preferred-name'}]
        fake.overrides={'fields':fields}
        first=ApplicationWorkflow(self.db,fake).fill(self.p,self.j,a,[])
        self.assertEqual(first['status'],'READY_TO_APPLY');self.assertEqual(first['unresolved_questions'],['Preferred name'])
        self.assertEqual(self.db.application(a['application_id'])['browser_blocker'],'UNKNOWN_QUESTION')
        self.assertFalse(any(action[0]=='fill' and action[1]=='fake-preferred-name' for action in fake.actions))
        answers=[{'question':'Preferred name','answer':'Synthetic alias','verified':True,'requires_manual_confirmation':False}]
        current=self.db.application(a['application_id'])
        second=ApplicationWorkflow(self.db,fake).fill(self.p,self.j,current,answers)
        self.assertEqual(second['status'],'WAITING_FOR_APPROVAL');self.assertFalse(second['submitted'])
        current=self.db.application(a['application_id'])
        self.assertIsNone(current['browser_blocker']);self.assertEqual(current['packet']['answer_memory_hash'],review_hash(revisions(answers),current['packet']['questions']))
    def test_changed_answer_memory_invalidates_submission_review(self):
        from backend.app.utils.answer_memory import revisions,review_hash
        questions=[{'question':'Preferred name','answer':'Original','verified':True,'requires_manual_confirmation':False}]
        memory=revisions(questions)
        a=self.ready();a=record_form_review(self.db,a['application_id'],self.evidence(a,questions=questions,answer_memory_hash=review_hash(memory,questions)))
        approve(self.db,a['application_id'],packet_hash(a['packet']))
        self.assertTrue(gates({**self.config,'answer_memory_revisions':memory},self.p,self.j,a,self.db)['allowed'])
        result=gates({**self.config,'answer_memory_revisions':revisions([{**questions[0],'answer':'Changed'}])},self.p,self.j,a,self.db)
        self.assertIn('ANSWER_MEMORY_CHANGED_REVIEW_REQUIRED',result['blockers'])
    def test_uncertain_submission_preserves_unique_reservation(self):
        a=self.ready();approve(self.db,a['application_id'],packet_hash(a['packet']));fake=FakeBrowser()
        with patch.object(fake,'submit_and_observe_confirmation',side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):ApplicationWorkflow(self.db,fake).submit(self.config,self.p,self.j,a)
        with self.db.connect() as c:self.assertEqual(c.execute('SELECT state FROM submission_attempts').fetchone()[0],'RESERVED')
        current=self.db.application(a['application_id'])
        self.assertIn('SUBMISSION_ALREADY_ATTEMPTED',gates(self.config,self.p,self.j,current,self.db)['blockers'])
    def test_deferred_candidate_preserves_archive_and_skips_personal_work(self):
        a=self.ready();write_json(self.root/'data/candidate_profile.json',self.p)
        result=defer_candidate(self.root,self.db);self.assertTrue(result['original_files_preserved'])
        self.assertEqual(len(list((self.root/'data/private_archive').glob('*.json'))),1)
        clean=read_json(self.root/'data/candidate_profile.json');self.assertIsNone(clean['full_name']);self.assertTrue(clean['intake_deferred'])
        with patch('backend.app.orchestrator.tailor',side_effect=AssertionError('Must not tailor')),patch('backend.app.orchestrator.monitor',side_effect=AssertionError('Must not read mail')):
            report=Orchestrator(self.root).run(False,True)
        self.assertIsNone(report['top_jobs'][0]['score']);self.assertEqual(report['applications_prepared'],0)
        self.assertIsNone(self.db.application(a['application_id'])['packet'])
    def test_mail_only_skips_when_no_submissions(self):
        # Dormant legacy capability: explicitly opt in only in this isolated test.
        write_json(self.root/'data/workflow_scope.json',{'post_submission_enabled':True})
        write_json(self.root/'data/candidate_profile.json',self.p)
        with patch('backend.app.orchestrator.monitor',side_effect=AssertionError('No mail reads')):
            self.assertEqual(Orchestrator(self.root).mail_only()['email']['state'],'NO_SUBMITTED_APPLICATIONS')
    def test_public_greenhouse_read_adapter(self):
        board={'provider':'greenhouse','board':'example','company':'Example Employer','evidence_url':'https://example.test/careers'}
        response={'jobs':[{'id':42,'title':'Graduate Software Engineer','location':{'name':'Melbourne, Australia'},'content':'&lt;p&gt;Learn Python.&lt;/p&gt;','absolute_url':'https://example.test/jobs/42'}]}
        with patch('backend.app.integrations.public_ats.fetch_json',return_value=response):records=read_board(board)
        self.assertTrue(search_scope(records[0]));self.assertFalse(records[0]['requirements_reviewed']);self.assertEqual(records[0]['description'],'Learn Python.')
        with self.assertRaises(ValueError):read_board({**board,'board':'../../private'})
    def test_public_lever_read_adapter(self):
        board={'provider':'lever','board':'example','company':'Example Employer','evidence_url':'https://example.test/careers'}
        with patch('backend.app.integrations.public_ats.fetch_json',return_value=[{'id':'42','text':'Junior Developer','categories':{'location':'Melbourne'},'descriptionPlain':'Python','hostedUrl':'https://example.test/jobs/42'}]):
            self.assertEqual(read_board(board)[0]['external_id'],'42')
    def test_job_schema_rejects_invalid_arrays_and_salary(self):
        for changes in ({'required_skills':'Python'},{'salary_min':float('nan')},{'source_url':'file:///secret'}):
            with self.assertRaises(ValueError):job(**changes)
    def test_exported_candidate_contract_has_all_fields(self):
        result=export_schemas(self.root);schema=read_json(self.root/'schemas/candidate_profile.schema.json')
        self.assertEqual(len(result['schemas_exported']),6);self.assertTrue(set(FIELDS)<=set(schema['required']))
    def test_daily_report_uses_local_calendar_date(self):
        self.assertEqual(local_day('2026-09-07T15:00:00+00:00'),'2026-09-08')
        report=daily_report(self.root,self.db,'2026-09-07');self.assertEqual(report['applications_submitted'],0)

if __name__=='__main__':unittest.main()
