# Local AIHawk browser compatibility fix

Applies to invisible-playwright 0.13.2 with invisible-core 29.19.0 / sealed Firefox 29, build 20260905223043.

The initial local test failed with `Network.resumeInterceptedRequest: Handler for does not implement method`. The Python `RouteDispatcher._send` used `self.conn.send` without a page session. Inspection of the sealed engine's `omni.ja` shows `Network.resumeInterceptedRequest`, `Network.abortInterceptedRequest` and `Network.fulfillInterceptedRequest` implemented in `chrome/juggler/content/protocol/PageHandler.js`, not BrowserHandler.js.

The local compatibility patch changes only RouteDispatcher's dispatch to `self.request.page.send(command, params)`. PageDispatcher.send supplies the exact page session and existing 30-second timeout. The one-answer guard, request ID, disposal and exception behavior remain intact. Do not remove routing restrictions to get the test to pass.

This edits the isolated Python dependency, not the sealed browser binary or other environments. Reinstallation replaces the edit, so reapply this exact compatibility change only after confirming package and engine versions and inspecting the implementation. Full browser acceptance must still be verified by the real local smoke test; this document alone is not a passing test.
