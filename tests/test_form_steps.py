"""Synthetic multi-page regression tests. No browser or employer requests."""
import copy,tempfile,unittest
from pathlib import Path
from tests.test_pipeline import profile,job
from backend.app.integrations.database import Database
from backend.app.integrations.browser import prepare_packet
from backend.app.integrations.application_workflow import ApplicationWorkflow
from backend.app.integrations.form_steps import resolve_control,validate_advance
from backend.app.utils.config import now


def page(identity='contact',final=False,**changes):
    return {'step_id':identity,'is_final_step':final,'observation_source':'Synthetic step fixture',
        'website_permits_automation':True,'website_policy_evidence':'Owned synthetic fixture only',
        'application_identity_verified':True,'application_identity_evidence':'Exact synthetic role',
        'fields':[],'upload_controls':{},'confirmed_uploads':[],
        'fields_filled':True,'form_reviewed':True,'legal_review_complete':True,'uploads_confirmed':True,
        'next_control':None if final else {'kind':'CONTINUE','submits_application':False,'label':'Next',
            'locator':'next','evidence':'Synthetic non-submitting button','next_step_id':'review'},**changes}


class StepsDriver:
    def __init__(self,pages):self.pages=pages;self.index=0;self.actions=[];self.uncertain=False
    def navigate(self,url):self.actions.append(('navigate',));self.index=0
    def observe(self):return copy.deepcopy(self.pages[self.index])
    def fill(self,locator,value):self.actions.append(('fill',locator,value))
    def upload(self,locator,path):self.actions.append(('upload',locator))
    def advance(self,control,step_id):
        self.actions.append(('advance',step_id))
        if self.uncertain:raise RuntimeError('Synthetic uncertain click outcome')
        self.index+=1
    def submit_and_observe_confirmation(self):raise AssertionError('Never submit in a filling test')


class FormStepsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='job-multistep-');self.root=Path(self.temp.name)
        self.db=Database(self.root/'data/job_agent.sqlite3');self.p=profile();self.j=job()
        self.j['analysis']={'eligibility':{'status':'ELIGIBLE'}};self.db.save_job(self.j)
        app=self.db.ensure_application(self.j);self.aid=app['application_id']
        for status in ('ANALYSED','SHORTLISTED','RESUME_READY','READY_TO_APPLY'):
            self.db.update_application(self.aid,{},status,'Synthetic multipage setup')
        document=self.root/'generated/resume.txt';document.parent.mkdir();document.write_text('SYNTHETIC_TEST_CANDIDATE')
        packet=prepare_packet(self.p,self.j,{'pdf_path':str(document)})
        self.db.update_application(self.aid,{'packet':packet,'validation':{'result':'PASS','synthetic_test_stub':True}})
        self.first=page(fields=[{'question':'Full name','candidate_field':'full_name','locator':'name'}],
            upload_controls={'resume':'file'},confirmed_uploads=['resume'])
        self.last=page('review',True)
        self.driver=StepsDriver([self.first,self.last])
    def tearDown(self):self.temp.cleanup()
    def run_fill(self,answers=None):
        return ApplicationWorkflow(self.db,self.driver).fill(self.p,self.j,self.db.application(self.aid),answers or [])
    def test_two_pages_reach_review_without_submission(self):
        result=self.run_fill()
        self.assertEqual(result['status'],'WAITING_FOR_APPROVAL');self.assertFalse(result['submitted'])
        self.assertEqual(result['completed_steps'],['contact'])
        self.assertEqual(sum(x[0]=='advance' for x in self.driver.actions),1)
        self.assertEqual(self.db.application(self.aid)['form_progress']['uploaded_kinds'],['resume'])
    def test_unknown_question_pauses_then_resumes_same_page(self):
        self.last['fields']=[{'question':'Preferred name','locator':'preferred'}]
        self.assertEqual(self.run_fill()['unresolved_questions'],['Preferred name'])
        actions=len(self.driver.actions)
        answers=[{'question':'Preferred name','answer':'Test','verified':True,'requires_manual_confirmation':False,'last_verified':now()}]
        self.assertEqual(self.run_fill(answers)['status'],'WAITING_FOR_APPROVAL')
        self.assertEqual(self.driver.actions[actions:],[('fill','preferred','Test')])
    def test_unknown_first_page_does_not_advance(self):
        self.first['fields'].append({'question':'Exact GPA','locator':'gpa'})
        self.assertEqual(self.run_fill()['unresolved_questions'],['Exact GPA'])
        self.assertFalse(any(x[0]=='advance' for x in self.driver.actions))
    def test_legal_declaration_is_not_autofilled(self):
        self.first['fields']=[{'question':'I certify this information is true','candidate_field':'full_name','locator':'legal'}]
        self.run_fill();self.assertFalse(any(x[0] in ('fill','advance') for x in self.driver.actions))
    def test_protections_stop_before_filling(self):
        for flag,reason in [('captcha','CAPTCHA'),('mfa','MFA'),('login_required','LOGIN_REQUIRED')]:
            with self.subTest(flag=flag):
                self.first[flag]=True;self.driver.actions=[]
                self.assertEqual(self.run_fill()['reason'],reason)
                self.assertFalse(any(x[0]=='fill' for x in self.driver.actions));del self.first[flag]
    def test_second_page_permission_is_rechecked(self):
        self.last['website_permits_automation']=False
        self.assertEqual(self.run_fill()['reason'],'AUTOMATION_PROHIBITED')
    def test_identity_evidence_required(self):
        self.first['application_identity_verified']=False
        self.assertEqual(self.run_fill()['reason'],'FORM_STATE_CHANGED')
        self.assertEqual(self.driver.actions,[('navigate',)])
    def test_missing_upload_receipt_stops_next(self):
        self.first['confirmed_uploads']=[]
        self.assertEqual(self.run_fill()['reason'],'RESUME_UPLOAD_FAILURE')
        self.assertFalse(any(x[0]=='advance' for x in self.driver.actions))
    def test_uncertain_next_is_never_replayed_on_old_page(self):
        self.driver.uncertain=True
        with self.assertRaises(RuntimeError):self.run_fill()
        saved=self.db.application(self.aid)['form_progress']
        self.assertTrue(saved['awaiting_transition']);self.assertEqual(saved['current_step_id'],'review')
        before=list(self.driver.actions)
        self.assertEqual(self.run_fill()['reason'],'FORM_STATE_CHANGED')
        self.assertEqual(self.driver.actions,before)
    def test_uncertain_next_can_resume_at_expected_observed_destination(self):
        self.driver.uncertain=True
        with self.assertRaises(RuntimeError):self.run_fill()
        self.driver.index=1;self.driver.uncertain=False
        self.assertEqual(self.run_fill()['status'],'WAITING_FOR_APPROVAL')
        self.assertEqual(sum(x[0]=='advance' for x in self.driver.actions),1)
    def test_expired_progress_stops(self):
        self.last['fields']=[{'question':'Unknown question','locator':'unknown'}];self.run_fill()
        saved=self.db.application(self.aid)['form_progress'];saved['observed_at']='2000-01-01T00:00:00+00:00'
        self.db.update_application(self.aid,{'form_progress':saved})
        self.assertEqual(self.run_fill()['reason'],'FORM_STATE_CHANGED')
    def test_completed_answer_change_stops(self):
        self.first['fields']=[{'question':'Preferred name','locator':'preferred'}]
        self.last['fields']=[{'question':'Unknown question','locator':'unknown'}]
        answers=[{'question':'Preferred name','answer':'Test','verified':True,'requires_manual_confirmation':False}]
        self.run_fill(answers);answers[0]['answer']='Different'
        self.assertEqual(self.run_fill(answers)['reason'],'FORM_STATE_CHANGED')
    def test_loop_is_blocked(self):
        self.last.update(is_final_step=False,next_control={**self.first['next_control'],'next_step_id':'contact'})
        self.assertEqual(self.run_fill()['reason'],'FORM_STEP_LIMIT')
    def test_submit_disguised_as_continue_is_refused(self):
        for label in ('Submit','Apply now','Accept and continue','Finish','Send application','I agree'):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):validate_advance({**self.first['next_control'],'label':label},'contact')
    def test_nested_verified_education_and_invalid_paths(self):
        packet=self.db.application(self.aid)['packet']
        control={'question':'University','candidate_path':['education',0,'institution']}
        self.assertEqual(resolve_control(control,self.p,packet,[])['answer'],'Example University')
        for path in (['education',-1,'institution'],['education',True,'institution'],['education',99],['education']):
            with self.subTest(path=path):
                self.assertEqual(resolve_control({**control,'candidate_path':path},self.p,packet,[])['action'],'ASK')

