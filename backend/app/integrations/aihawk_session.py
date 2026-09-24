"""AIHawk session-management and actions with a standard Edge browser backend.

Only browser startup/shutdown is adapted. AIHawk's own actions, snapshots,
selector generation and tab management remain in use. No stealth/identity
spoofing, CAPTCHA preparation, personal profile or proxy is configured.
"""
from aihawk.mcp.session import StealthSession

class AIHawkEdgeSession(StealthSession):
    def __init__(self,headless=True):
        super().__init__()
        self.headless=headless;self._standard_driver=None

    async def start(self):
        from playwright.async_api import async_playwright
        self._standard_driver=await async_playwright().start()
        try:
            self._browser=await self._standard_driver.chromium.launch(channel='msedge',headless=self.headless)
            self._context=await self._browser.new_context(service_workers='block',accept_downloads=False)
        except BaseException:
            await self.close();raise

    async def close(self):
        browser=self._browser
        try:
            await super().close()
        finally:
            try:
                if browser:await browser.close()
            finally:
                self._browser=None
                if self._standard_driver:
                    await self._standard_driver.stop();self._standard_driver=None
