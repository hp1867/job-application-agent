import unittest
import json,types
from pathlib import Path
from unittest.mock import AsyncMock,Mock,patch
from backend.app.integrations.aihawk_executor import observed_control
from backend.app.integrations.aihawk_executor import AIHawkExecutor
from backend.app.integrations.browser import prepare_packet
from tests.test_pipeline import profile,job

class AIHawkControlTests(unittest.TestCase):
    def setUp(self):self.snapshot={'interactive_elements':[{'id':'name','selector':'#name','tag':'input','type':'text'}]}
    def test_exact_observed_id(self):self.assertEqual(observed_control(self.snapshot,{'id':'name'})['selector'],'#name')
    def test_exact_observed_selector(self):self.assertEqual(observed_control(self.snapshot,{'selector':'#name'})['id'],'name')
    def test_missing_control_refused(self):
        with self.assertRaises(ValueError):observed_control(self.snapshot,{'id':'other'})
    def test_ambiguous_control_refused(self):
        self.snapshot['interactive_elements']*=2
        with self.assertRaises(ValueError):observed_control(self.snapshot,{'id':'name'})
    def test_disabled_control_refused(self):
        self.snapshot['interactive_elements'][0]['disabled']=True
        with self.assertRaises(ValueError):observed_control(self.snapshot,{'id':'name'})
    def test_guessed_label_and_extra_fields_refused(self):
        for locator in ({'label':'Full name'},{'id':'name','selector':'#name'},'#name',{}, {'id':''}):
            with self.subTest(locator=locator):
                with self.assertRaises(ValueError):observed_control(self.snapshot,locator)

class AIHawkExecutorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.profile=profile();self.packet=prepare_packet(self.profile,job(),None)
        self.command={'command_id':'synthetic','run_id':'run','application_id':'app','claim_token':'test-only',
            'action':'FILL','payload':{'locator':{'id':'name'},'value':'Test Candidate'}}
        self.queue=types.SimpleNamespace(root=Path('unused-synthetic-root'),validate_claim=Mock(),
            run=Mock(return_value={'phase':'fill','application_id':'app'}),validate_context=Mock(return_value={'packet':self.packet}))
        self.observation={'website_permits_automation':True,'website_policy_evidence':'Owned fixture only',
            'observed_url':'https://example.test/form','application_identity_verified':True,'application_identity_evidence':'Synthetic exact role',
            'fields':[{'question':'Full name','candidate_field':'full_name','locator':{'id':'name'}}]}
        self.snapshot={'url':'https://example.test/form','interactive_elements':[{'id':'name','selector':'#name','tag':'input','type':'text'}]}
        self.page=types.SimpleNamespace(input_value=AsyncMock(return_value='Test Candidate'))
        self.session=types.SimpleNamespace(page=Mock(return_value=self.page))
        self.actions=types.SimpleNamespace(snapshot=AsyncMock(),type_text=AsyncMock(),click=AsyncMock())
    async def execute(self):
        self.actions.snapshot.return_value=json.dumps(self.snapshot)
        executor=AIHawkExecutor(self.session,self.queue,AsyncMock(return_value=self.observation))
        with patch.dict('sys.modules',{'aihawk':types.ModuleType('aihawk'),'aihawk.mcp':types.SimpleNamespace(actions=self.actions)}),patch('backend.app.integrations.aihawk_executor.read_json',side_effect=[self.profile,[]]):
            return await executor.execute(self.command)
    async def test_verified_text_is_filled_once(self):
        self.assertTrue((await self.execute())['ok'])
        self.actions.type_text.assert_awaited_once_with(self.session,'#name','Test Candidate')
        self.assertGreaterEqual(self.queue.validate_claim.call_count,3)
    async def test_invented_value_refused(self):
        self.command['payload']['value']='Invented name'
        with self.assertRaises(ValueError):await self.execute()
        self.actions.type_text.assert_not_awaited()
    async def test_legal_field_refused(self):
        self.observation['fields'][0]['question']='I certify these details are correct'
        with self.assertRaises(ValueError):await self.execute()
        self.actions.type_text.assert_not_awaited()
    async def test_changed_page_refused(self):
        self.snapshot['url']='https://other.test'
        with self.assertRaises(ValueError):await self.execute()
        self.actions.type_text.assert_not_awaited()
    async def test_missing_identity_refused(self):
        self.observation['application_identity_verified']=False
        with self.assertRaises(ValueError):await self.execute()
    async def test_captcha_refused(self):
        self.observation['captcha']=True
        with self.assertRaises(ValueError):await self.execute()
    async def test_unknown_permission_refused(self):
        self.observation['website_permits_automation']=None
        with self.assertRaises(ValueError):await self.execute()
    async def test_unmeasurable_control_snapshot_refused(self):
        self.snapshot['unmeasurable']=1
        with self.assertRaises(ValueError):await self.execute()
    async def test_submit_and_arbitrary_navigation_are_unavailable(self):
        for action in ('SUBMIT_AND_OBSERVE_CONFIRMATION','NAVIGATE','EVALUATE','CLICK'):
            self.command['action']=action
            with self.assertRaises(ValueError):await self.execute()
        self.actions.click.assert_not_awaited()
    async def test_failed_value_confirmation_does_not_retry(self):
        self.page.input_value.return_value=''
        with self.assertRaises(ValueError):await self.execute()
        self.actions.type_text.assert_awaited_once()
