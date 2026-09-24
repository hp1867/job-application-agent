import hashlib,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import AsyncMock,Mock,patch
from backend.app.integrations.aihawk_upload import upload_document

class AIHawkUploadTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='job-aihawk-upload-');self.root=Path(self.temp.name)
        folder=self.root/'generated';folder.mkdir();self.file=folder/'fixture.txt';self.file.write_bytes(b'SYNTHETIC_TEST')
        self.packet={'documents':{'resume':str(self.file)},'document_hashes':{'resume':hashlib.sha256(self.file.read_bytes()).hexdigest()}}
        self.observation={'website_permits_automation':True,'website_policy_evidence':'Synthetic fixture permission','observed_url':'https://example.test/form'}
        self.page=types.SimpleNamespace(set_input_files=AsyncMock());self.session=types.SimpleNamespace(page=Mock(return_value=self.page))
        self.snapshot={'url':'https://example.test/form','interactive_elements':[{'selector':'#resume','tag':'input','type':'file'}]}
    def tearDown(self):self.temp.cleanup()
    async def call(self):
        actions=types.SimpleNamespace(snapshot=AsyncMock(return_value=json.dumps(self.snapshot)))
        with patch.dict('sys.modules',{'aihawk':types.ModuleType('aihawk'),'aihawk.mcp':types.SimpleNamespace(actions=actions)}):
            return await upload_document(self.session,'#resume',self.packet,'resume',self.root,self.observation)
    async def test_exact_document_and_observed_control_selected_once(self):
        result=await self.call();self.assertTrue(result['selected']);self.assertTrue(result['requires_observed_upload_confirmation'])
        self.page.set_input_files.assert_awaited_once_with('#resume',str(self.file),timeout=15000)
    async def test_unknown_permission_or_protection_blocks(self):
        for change in ({'website_permits_automation':False},{'captcha':True},{'mfa':True},{'login_required':True}):
            original=dict(self.observation);self.observation.update(change)
            with self.assertRaises(ValueError):await self.call()
            self.observation=original
        self.page.set_input_files.assert_not_awaited()
    async def test_changed_file_is_not_uploaded(self):
        self.file.write_bytes(b'CHANGED_SYNTHETIC_TEST')
        with self.assertRaisesRegex(ValueError,'changed'):await self.call()
        self.page.set_input_files.assert_not_awaited()
    async def test_file_outside_generated_directory_is_not_uploaded(self):
        outside=self.root/'outside.txt';outside.write_bytes(b'SYNTHETIC_TEST');self.packet['documents']['resume']=str(outside)
        with self.assertRaisesRegex(ValueError,'generated'):await self.call()
        self.page.set_input_files.assert_not_awaited()
    async def test_changed_page_or_non_file_control_blocks(self):
        self.snapshot['url']='https://different.test/form'
        with self.assertRaisesRegex(ValueError,'Page changed'):await self.call()
        self.snapshot['url']=self.observation['observed_url'];self.snapshot['interactive_elements'][0]['type']='text'
        with self.assertRaisesRegex(ValueError,'file-input'):await self.call()
        self.page.set_input_files.assert_not_awaited()

if __name__=='__main__':unittest.main()
