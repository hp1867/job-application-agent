# AIHawk runtime integration

## Verified update - 9 September 2026

Native dropdown regression: add `--native-dropdown` to the queue smoke command to run the two-page native-select fixture. It passed at 2026-09-09T11:15:13 UTC, including unknown-answer pause and same-page resume. Selection uses a bounded native Playwright extension on AIHawk's existing session, not AIHawk's value-or-label fallback retry. The rest of navigation, snapshots, typing and continuation uses installed AIHawk actions. Report: tmp/browser-fixture-tta8tjia/aihawk-queue-report.json.

The local queue fixture now uses the reusable backend/app/integrations/aihawk_executor.py rather than its former inline action handler. The executor independently validates the live claim and safe source values. Employer-specific live observers must supply current page, identity, permission and upload evidence; the executor does not manufacture any of those. scripts/aihawk_inspect.py performs read-only inspection of exact public Greenhouse job URLs and saves a conservative mapping proposal. It cannot fill or submit. Unreviewed sites, complex controls and missing candidate information remain explicit acceptance gates.

Multi-page follow-up: add `--multi-page` to the queue test command below. Actual AIHawk navigation, typing, guarded file upload and the exact non-submitting fixture Next passed through the durable workflow at 00:18:17 UTC. The same application resumed on page two after a synthetic verified answer was supplied and reached WAITING_FOR_APPROVAL. Report: `tmp/browser-fixture-z26fvciq/aihawk-queue-report.json`. The controller cannot navigate to employers or submit. Single-page regression also passed after claim-token argument hardening at 00:20:17 UTC.

The pinned Firefox engine downloaded successfully. Its first run failed on request routing; the local page-session fix is documented in AIHAWK_ROUTE_FIX.md. After that fix, AIHawk navigation and three field fills succeeded, but Firefox's native file-input handler failed. Do not claim Firefox upload acceptance.

The explicit `AIHawkEdgeSession` compatibility adapter retains installed AIHawk actions, snapshots, selector generation and tab management, and changes browser startup/shutdown to standard Playwright 1.62.0 with Edge. `scripts/aihawk_browser_smoke.py --backend edge` passed at 2026-09-09T00:02:57.751253+00:00, including navigation, three fills and the guarded upload extension. Submit was disabled and no external page requests occurred. Report: `tmp/aihawk-browser-z_9mjksf/report.json`. This is genuine AIHawk action-layer execution with an adapted browser backend, not the upstream Firefox engine and not a completed employer workflow.

The durable application queue is now exercised with this adapter by `scripts/aihawk_queue_smoke.py`. Its real browser run at 2026-09-09T00:12:28 UTC passed thirteen acknowledged commands: pause on an unknown answer, resume using synthetic verified answer memory, upload confirmation and WAITING_FOR_APPROVAL. Report: `tmp/browser-fixture-qw372akc/aihawk-queue-report.json`. The controller is intentionally fixture-only; employer-specific observation and permitted control adapters remain unfinished. Older pending-download/unexecuted-test notes below describe the initial installation milestone and are superseded by this update.

Repeat the queue test from this project directory (no real candidate or employer is used):

```powershell
& .venv/aihawk/Scripts/python.exe scripts/aihawk_queue_smoke.py --workflow-python (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
```

The actual AIHawk 0.11.1 package is installed in `.venv/aihawk` from the retained upstream checkout at commit `afe1f66dd3f1572d59a78ea67688a0d0e49e8b25`. This is separate from the earlier formatter-only adapter.

Verified: installation completed, `pip check` passed, and `scripts/aihawk_health.py` started the real installed MCP server and listed 18 tools. That check invoked no browser tools, opened no employer pages and submitted nothing. Its subprocess receives a minimal environment and runs outside the application's `.env` directory.

Reproduce from PowerShell:

```powershell
& .venv/aihawk/Scripts/python.exe scripts/aihawk_health.py
& .venv/aihawk/Scripts/python.exe -m pip check
```

`requirements-aihawk-lock.txt` records installed dependency versions. Install the inspected local AIHawk source with those constraints; do not silently upgrade the engine. The standalone OpenRouter-powered chat UI is not configured, and no API key is required for the MCP integration route.

## Remaining runtime acceptance

- The pinned browser-engine fetch was started using a cache under `.venv/aihawk/engine-cache`; completion must be verified from the running process before launching a test. Never restart a download merely because observation timed out.
- `scripts/aihawk_browser_smoke.py` uses AIHawk's installed session and actions on the existing synthetic loopback form. It is not a mocked AIHawk implementation. Run it only after the engine download succeeds. At creation, it has been syntax-checked but not executed.
- The upstream server has no file-upload tool. `integrations/aihawk_upload.py` adds an upload operation using its real browser session, with document-path/hash checks and an observed file-input requirement. The caller must still enforce the candidate, eligibility, document-validation and website-permission gates.
- The full application's queued fill workflow is NOT yet wired to this runtime. The old Edge transport test is not evidence of AIHawk execution. Finish binding the guarded actions and testing pause/resume, uploads, and final-submit blocking.
- Do not register the unrestricted upstream tool surface globally. Coordinate clicks, arbitrary page evaluation, key presses, CAPTCHA preparation and submission are not authorised substitutes for guarded operations. Keep CAPTCHA preparation disabled and stop on website protection or policy uncertainty.

Gmail and follow-up work remain disabled under CURRENT_SCOPE.md.
