# Build status - 9 September 2026

## Current scope and latest verification

Latest resumed run: **237 Python tests passed in 32.145 seconds**. The interrupted document-revision fix is verified: the orchestrator, resume generator and cover-letter generator share the same content revision; raw qualification/work-arrangement changes invalidate preparation, while a closed listing preserves its existing document history.

Native dropdown support is now integrated into the fill-only AIHawk executor. It selects exactly one enabled option whose label matches a verified answer, requires an explicit option value, rechecks the queue context, and confirms selection without retrying. Ambiguous, disabled, implicit-value, multi-select and custom combobox controls remain reviewable. Eight focused unit tests and an actual AIHawk two-page dropdown fixture passed. Real-browser report at 2026-09-09T11:15:13 UTC: tmp/browser-fixture-tta8tjia/aihawk-queue-report.json; final WAITING_FOR_APPROVAL, zero external page requests, zero submissions. This is local acceptance, not employer permission.

Latest engineering pass: shared fill-only AIHawkExecutor with exact live-claim checks; real two-page test passed at 2026-09-09T05:45:29 UTC (tmp/browser-fixture-oehmmg69/aihawk-queue-report.json). Word/PDF source-provenance extraction and conservative qualification checks are integrated. The relevance dashboard compiled and its four component tests passed. Local dashboard health returned HTTP 200 with dry_run=true. This does not establish real resume visual QA.

Live read-only AIHawk inspection of the saved nCino Greenhouse application succeeded, with 61 visible controls and zero blocked requests on the second run. The mapping proposal is retained in data/browser_inspections/c1e58c69-92fb-419d-9828-d85ac93be0c4.json. Website permission and application readiness remain unknown; no fields were filled and no files uploaded.

Saved-job dry run 1d72994d-1337-4895-88cb-309c1dfa2c73 completed at 2026-09-09T05:50:14 UTC: seven captured listings reprocessed, seven duplicates, zero errors, zero submissions, Gmail USER_MANAGED_POST_APPLICATION. Personal scores and documents remain deferred. NEXT_WORK.md contains the authoritative remaining acceptance boundaries; older milestone notes below are historical.

Latest complete suite after relevance integration: **191 tests passed in 38.908 seconds** on 9 September 2026.

This section supersedes older lifecycle requirements below: Gmail, response tracking, interviews and follow-ups are user-managed and excluded. Candidate intake is deferred. Keep dry run and level 2; nothing has been submitted.

- The multi-page milestone passed all 183 isolated tests in 32.503 seconds on 9 September. Fifteen new multi-page cases cover unknown answers, legal declarations, interruptions, loops and upload evidence. A CLI regression covers dash-prefixed claim tokens.
- Actual AIHawk multi-page queue test passed at 00:18:17 UTC with twelve acknowledged commands, one non-submitting Next, and same-page resumption to WAITING_FOR_APPROVAL. Evidence: tmp/browser-fixture-z26fvciq/aihawk-queue-report.json. No employer pages or submission were involved.
- Fixed dash-prefixed claim-token argument handling in both local browser controllers. Single-page AIHawk regression passed at 00:20:17 UTC; evidence: tmp/browser-fixture-ou0h4g3c/aihawk-queue-report.json.
- Detailed ATS relevance reporting is now attached to resume validation. Required and preferred skill coverage are separate; education and experience/project terms are section-specific. Unsupported conditions remain NEEDS_REVIEW; unprovided dimensions remain unscored. Eight focused tests passed. This is lexical coverage, not a vendor ATS score or eligibility proof.
- Installed AIHawk's direct Edge-adapter test passed at 00:09:07 UTC, including observed file selection.
- NEW: actual AIHawk actions now pass through the durable application queue and existing application workflow. At 00:12:28 UTC, the synthetic run paused on an unknown preferred name, resumed with a synthetic verified answer, and reached WAITING_FOR_APPROVAL. All thirteen commands were acknowledged, with zero external page requests or submissions. Evidence: tmp/browser-fixture-qw372akc/aihawk-queue-report.json.
- The AIHawk environment passes pip dependency checks. Original Firefox upload compatibility remains unresolved; the passing route uses the explicitly adapted Edge backend.
- Remaining engineering: employer-specific permitted observation/control adapters, broader document import/QA, expanded requirement interpretation and final candidate-backed acceptance. The local controller deliberately cannot handle employer URLs, unknown commands or submission. The new relevance report still needs a dedicated dashboard presentation; the backend already persists it with validation.

Older milestone details below are historical; do not resume out-of-scope mailbox tasks.

## Verified milestone

- **159 isolated tests passed** (`python -m unittest discover -s tests -q`, latest run 27.697 seconds).
- Work-location checks are integrated with eligibility, preference scoring and the existing fresh submission gate. Seventeen synthetic tests cover remote jurisdiction, foreign/ambiguous location text, relocation, editable preferences, pipeline readiness and approval invalidation. Unsupported places and role-specific attendance plans still need review; this is not a universal geocoder. The offline run `2033e68f-b3af-40f1-b408-655a64043fc2` re-analysed the tracker with zero new jobs, errors or submissions; Gmail remained skipped because intake is deferred.
- The actual local browser pause/resume test also passed again at `2026-09-08T06:16:27.697Z` after location checks were integrated: thirteen acknowledged actions, zero external page requests/errors, final `WAITING_FOR_APPROVAL`, submission refused. Its report is retained under `tmp/browser-fixture-kq3ql_4i/`. This is a synthetic loopback transport test, not an employer acceptance test.
- Structured resume text import now preserves extracted lines, sections and source spans, with reviewable education, employment, project and skill entries. All extracted proposals remain unverified and the active profile is untouched. Ten synthetic-text tests cover source preservation, ambiguous values, conflicting contacts and reference/project identity boundaries. This does not establish DOCX/PDF reading-order fidelity or visual QA.
- **Actual local browser pause/resume test passed.** The run at `2026-09-08T00:53:23.904Z` used a fresh headless Edge session and the durable Python workflow. Phase one left the unknown preferred-name field blank and recorded the unresolved question. After a deliberately synthetic verified answer was added, phase two reused the same application and reached `WAITING_FOR_APPROVAL`. All thirteen actions were observed and acknowledged; submission was explicitly refused. No external page requests or page errors occurred. The report and both inspected screenshots are retained under `tmp/browser-fixture-6g_0288r/`; `./test-browser.ps1` reproduces this check.
- Listing, preference, profile, document and relevant-answer changes now revoke stale reviews and reconcile preparation status. Claimed stale actions become uncertain rather than being replayed. An existing submission attempt keeps its exact packet and reservation; reprocessing does not regenerate or overwrite it. Tests cover these changes through services, the orchestrator and the HTTP API.
- React/Vite production build passed. Browser smoke checks exercised job search, application detail, settings, answer-memory visibility and dashboard tools. No application browser errors were reported during those checks.
- Live read-only discovery again exercised the audited MCP and nCino public employer API. The tracker now retains ten records, with eight pending candidate/eligibility review and two excluded from top jobs. The live run revealed an unrelated voice-talent result; a configurable role-family guard now prevents unrelated listings from shortlisting, even when their descriptions contain matching technology keywords. Ambiguous graduate tracks go to review. The final offline rerun produced zero new jobs, zero errors and zero submission attempts.
- The active profile has 29 unknown fields, no verified candidate facts, and `intake_deferred: true`.
- Mail-only checks skipped Gmail. The daily report recorded zero prepared active applications and zero submitted applications. Earlier unconfirmed drafts remain archived and are excluded from readiness and current prepared counts.
- The native time-routed heartbeat is active. Local execution was interrupted by approval-review usage limits during the build; those checks resumed after access became available. Scheduling therefore must not be described as guaranteed uninterrupted cloud execution.
- A Git repository was initialized locally. `.env`, the active candidate profile, the database and private archives were verified ignored. No commit, push or public deployment was performed.

## End-to-end boundary

The software milestone is not a claim that the user's full job-application objective is complete. Candidate intake, real document visual QA, candidate mailbox confirmation, and employer-specific permitted form filling/upload/submission still require the later inputs and live checks described in ACCEPTANCE.md. Additional engineering gaps identified in source inspection are recorded in NEXT_WORK.md; they are not all blocked on candidate details.

The Python browser workflow has a durable command bridge, isolated unit tests and an actual local-browser transport test. The generic employer controller is not an unattended universal driver. The earlier in-app browser connector is not exposed in the current session; the bundled Playwright/Edge runtime can run the strictly local test. See BROWSER_BRIDGE.md. The AIHawk adaptation does not run its unrestricted upstream executor. Public job-board search outside supported APIs depends on connected search tools and reviewed captures. A second requested MCP still lacks its required key and completed privacy review.

## Resume next time

1. Read AGENTS.md, README.md, current profile/preferences, integration status and the latest reports. Preserve the database and original resumes.
2. Keep dry run and level 2. Do not use archived candidate data or ask repeated candidate questions while intake remains deferred.
3. Continue permitted discovery and tracking. During mail/report schedule stages, do not launch an unnecessary new job search.
4. When the user later supplies their details and resume, review the extraction and confirm only sourced facts. Generate and validate documents, then render and inspect every DOCX/PDF page before recording review evidence.
5. Use current employer-page observations and exact verified answers. Stop on policy uncertainty, CAPTCHA, MFA, legal declarations or unknown questions. Obtain production authorisation and exact level-2 submission approval separately.
6. Reserve a submission once, confirm the employer receipt, then monitor the explicitly confirmed candidate mailbox. An uncertain reservation remains blocked against retry.
