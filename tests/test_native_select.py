import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock
from backend.app.integrations.native_select import select_verified_label

class NativeSelectTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.items=[self.option('Melbourne','MEL'),self.option('Sydney','SYD')]
        self.options=SimpleNamespace(count=AsyncMock(side_effect=lambda:len(self.items)),nth=lambda i:self.items[i])
        self.control=SimpleNamespace(count=AsyncMock(return_value=1),get_attribute=AsyncMock(return_value=None),locator=Mock(return_value=self.options))
        self.page=SimpleNamespace(locator=Mock(return_value=self.control),select_option=AsyncMock(return_value=['MEL']),input_value=AsyncMock(return_value='MEL'))
        self.check=Mock()
    def option(self,label,value,disabled=False):
        return SimpleNamespace(get_attribute=AsyncMock(side_effect=lambda key:label if key=='label' else value),is_disabled=AsyncMock(return_value=disabled))
    async def call(self,answer='Melbourne'):return await select_verified_label(self.page,'#location',answer,self.check)
    async def test_exact_label_selected_once(self):
        self.assertTrue((await self.call())['selected']);self.check.assert_called_once()
        self.page.select_option.assert_awaited_once_with('#location',value='MEL',timeout=15000)
    async def test_missing_label_does_not_guess(self):
        with self.assertRaises(ValueError):await self.call('Melb')
        self.page.select_option.assert_not_awaited()
    async def test_duplicate_labels_refused(self):
        self.items.append(self.option('Melbourne','OTHER'))
        with self.assertRaises(ValueError):await self.call()
        self.page.select_option.assert_not_awaited()
    async def test_disabled_matching_option_refused(self):
        self.items[0]=self.option('Melbourne','MEL',True)
        with self.assertRaises(ValueError):await self.call()
    async def test_implicit_option_values_require_review(self):
        self.items[0]=self.option('Melbourne',None)
        with self.assertRaises(ValueError):await self.call()
    async def test_multiple_dropdown_refused(self):
        self.control.get_attribute.return_value=''
        with self.assertRaises(ValueError):await self.call()
    async def test_revoked_context_blocks_selection(self):
        self.check.side_effect=ValueError('Revoked')
        with self.assertRaises(ValueError):await self.call()
        self.page.select_option.assert_not_awaited()
    async def test_failed_confirmation_does_not_retry(self):
        self.page.input_value.return_value='SYD'
        with self.assertRaises(ValueError):await self.call()
        self.page.select_option.assert_awaited_once()
