# Job Application Agent

Current scope: AIHawk-powered preparation up to the final Submit button. Gmail, response tracking and post-application follow-ups are user-managed and disabled. See docs/CURRENT_SCOPE.md; it supersedes older full-lifecycle descriptions below. Existing history is preserved. Installed AIHawk now passes an isolated application-queue pause/resume/upload test with the Edge session adapter. Employer-specific integration remains unfinished.

Persistent, local job-search and application workspace. One Python orchestrator, ordinary modules, a SQLite tracker, and a React/Vite dashboard. This project continues in place when you say **Run my job agent**; do not recreate the database.

## Current operating mode

- `DRY_RUN=true`, `AUTOMATION_LEVEL=2`, `PRODUCTION_APPROVED=false`.
- Candidate intake is deferred at the user's request. The active profile is empty. Previously located, unconfirmed data is archived locally, not treated as the user's identity. Originals are preserved.
- Discovery, deduplication, source tracking, listing analysis, dashboard and reports work now. Personal match scores, candidate documents, Gmail reads and applications wait for later verified intake.
- Nothing has been submitted to a real employer. Synthetic tests cannot reach real employers.

## Run the existing project

From this directory in PowerShell:

```powershell
./run-job-agent.ps1                 # Read-only discovery and the permitted pipeline
./run-job-agent.ps1 -Offline        # Reprocess captured listings without network discovery
./run-job-agent.ps1 -Dashboard      # http://127.0.0.1:8766
```

The launcher uses the bundled Python runtime on this computer. On another machine, create a Python 3.11+ virtual environment and install `requirements.txt`; then use:

```text
python -m backend.app.cli init
python -m backend.app.cli run
python -m backend.app.cli mail-only
python -m backend.app.cli daily-report
python -m backend.app.cli report
python -m backend.app.cli serve
python -m backend.app.cli ingest-jobs path/to/reviewed-jobs.json
python -m backend.app.cli ingest-emails path/to/recruitment-messages.json
python -m backend.app.cli import-resume path/to/supplied-resume.pdf
python -m backend.app.cli export-schemas
python -m backend.app.cli review-artifact ARTIFACT_ID path/to/observed-layout-review.json
```

`import-resume` preserves and hash-checks the input snapshot, extracts text and writes structured sections, source spans and review proposals under `data/resume_imports/`. Every extracted proposal is unverified; the active candidate profile remains untouched. Confirm supplied facts and identity in Settings after reviewing source evidence. Unknown legal, work-rights, visa, clearance, salary and date information stays unknown. The original master resume is never overwritten. Synthetic TXT parser tests do not guarantee DOCX/PDF reading order or visual layout.

Dashboard development: run `npm ci` and `npm run build` in `frontend/`, then serve through the Python backend. The production build is served on loopback only. Do not publicly deploy this personal-data application or expose the API to the network without a separate authentication and hosting design.

## Architecture

`backend/app/orchestrator.py` owns the workflow. `agents/` contains deterministic discovery, eligibility, scoring, resume, email and deadline modules, not independently running AI agents. `integrations/` handles read-only jobs/Gmail, SQLite and the controlled browser protocol. `services/` handles persistence lifecycle, reporting, notifications and approvals. `models/` and `schemas/` define contracts. The dashboard reads the same durable database, not browser storage.

Jobs, sources, applications, status history, artifact versions, emails, deadlines, answer memory, notifications, runs, approvals and unique submission reservations are stored in `data/job_agent.sqlite3`. A database reservation survives uncertain submission outcomes; automatic retries are forbidden. Candidate changes invalidate preparatory packets and approvals without deleting submitted history. Existing generated documents are archived, not silently reused for a different candidate.

## Discovery and AIHawk

The current live Python providers are a scoped read-only AI Dev Jobs MCP client and public employer ATS APIs. `data/discovery_sources.json` contains reviewed board tokens; the nCino Greenhouse board has been exercised live. Greenhouse and Lever adapters are covered by isolated tests. No ATS submission API is used. Broad discovery across SEEK, Indeed, GradConnection, Prosple, official employers, government and other accessible sources uses the connected search workflow in this conversation. Captures are ingested through the CLI with source evidence; unsupported boards are not represented as direct API integrations.

Employer listings take canonical priority. Older captures cannot replace newer official observations. A target-role-family check rejects unrelated search results from shortlisting and top jobs without deleting their audit records; ambiguous graduate programs require review. Targets remain editable in preferences. Unreviewed requirements remain `NEEDS_REVIEW`; scores are transparent relevance heuristics, not acceptance predictions or an ATS vendor's score.

Work-location eligibility is separate from location preference points. Remote does not imply worldwide eligibility; Australian residence and the listed jurisdiction must be supported. Different-city attendance, uncertain jurisdiction and qualified residency restrictions require review. General willingness to relocate is not a confirmed plan for that role. The matcher uses a bounded location vocabulary, not geocoding; unsupported localities remain reviewable. Editable preferred locations and remote/hybrid preferences determine location points only after compatibility passes. Location changes invalidate stale preparation and approval.

AIHawk is retained under `vendor/AIHawk` at commit `afe1f66dd3f1572d59a78ea67688a0d0e49e8b25` and installed with its dependencies in `.venv/aihawk`. Its actual navigation, snapshot, selector and typing actions now pass the durable application-queue fixture using an Edge startup/shutdown adapter and guarded upload extension. The original Firefox backend was tested but still has an upload compatibility failure. The unrestricted upstream LLM executor is not enabled. See `docs/AIHAWK_RUNTIME.md` and `THIRD_PARTY_NOTICES.md`. This is not yet a working universal employer controller.

Source contracts: [AIHawk](https://github.com/feder-cr/AIHawk), [Greenhouse public Job Board API](https://docs.greenhouse.io/job-board.html), [Lever postings API](https://github.com/lever/postings-api). The MCP publisher, endpoint, permissions and privacy review are recorded in `data/integrations.json`; only the explicit read allowlist is callable. The second requested MCP remains disabled without its required key and completed privacy review.

## Application safety and browser execution

`application_workflow.py` implements the prepare/fill/upload/review/reserve/receipt sequence against a browser adapter. `browser_queue.py` connects it to a durable, one-action-at-a-time browser bridge with expiring leases, exact-state checks and one-use acknowledgements. A real isolated Edge smoke test exercised navigation, observation, filling, file selection and approval readiness through this bridge. No employer was used. The local test controller cannot submit or navigate to an employer; a currently available permitted browser controller is still needed for real sites. A prepared action plan is not a completed form.

See [the browser runbook](docs/BROWSER_BRIDGE.md) for `browser-run`, `browser-next`, `browser-reply`, `browser-status` and the repeatable `./test-browser.ps1` check. The earlier in-app connector is not exposed in the current session; do not infer live browser access from an old integration check. The bundled isolated browser-test runtime is available.

Only verified fields and safe verified answers may be filled. Unknown questions, declarations, CAPTCHA, login, MFA, unclear website permission and upload failures stop readiness. `record_form_review` accepts actual observed evidence, invalidates older approvals, and moves complete packets to `WAITING_FOR_APPROVAL`. The dashboard approval is bound to the exact packet and expires after two hours.

Unknown questions can pause an application without inventing an answer. After a safe verified answer is supplied, rerun the fill workflow for that same application and inspect the form again. Changed answers used by an already reviewed form revoke that review; unrelated answer entries do not. Listing, candidate, document and preference changes also invalidate stale preparation. Original files and submitted history remain preserved, and an uncertain submission's exact packet must not be regenerated.

Every actual submit must call `reserve_submission` with current state before clicking and `confirm_submission` only after an observed employer receipt. Dry-run and level 1 block the submit driver. Level 2 additionally requires exact approval. Level 3 requires a score strictly above the larger of the application threshold and auto-submit threshold (currently 80), plus every safety gate. Listing checks expire after 24 hours; form checks after two hours. Changed documents, profile, job requirements or packet data invalidate readiness. A production-mode change alone is never individual level-2 approval.

The API intentionally has no unrestricted submit endpoint. Do not bypass the gate with browser clicks, direct HTTP submissions, arbitrary status edits, upstream AIHawk, or mail sends.

## Documents and verified facts

The generator creates job-specific DOCX/PDF pairs and claim manifests using verified source content only. The validator checks identity, target role/company, source claims, extracted document text and file hashes. Layout review is a separate required checkpoint; programmatically readable text is not proof of visually correct layout. Real documents must be rendered and visually inspected before `PASS`. Earlier unconfirmed drafts are archived and are not application-ready.

Cover letters have the same exact-content, profile/version, readability and visual-review checks. `review-artifact` requires an explicit reviewer, review notes, a recent timezone-aware `reviewed_at`, `result: PASS`, matching `docx_sha256` and `pdf_sha256`, a `docx_page_count`, and `page_images` lists for both `docx` and `pdf`. All PNG pages must be under this project's generated directory. This records a review actually performed by the operator; it does not perform or invent visual inspection. Missing page evidence or changed files are rejected. Uploading any attached cover letter requires its validation to pass.

There is no fabricated work-rights inference, invented experience, automatic legal declaration, dishonest keyword stuffing, or inferred candidate identity from a connected mailbox. Personal data is excluded from Git. Secrets belong in the ignored `.env` or environment, never logs. The local database itself is not encrypted; protect the Windows account and backups accordingly.

## Gmail, deadlines and scheduling

Gmail supports the connected read-only capture bridge and optional OAuth `gmail.readonly`. No send action is implemented. A connected mailbox must be explicitly confirmed for the later candidate before monitoring; no mailbox is inferred from a resume or account owner. Deferred intake or zero submitted applications prevents mail reads. Matching requires known application context and dates; ambiguous events and deadlines go to review. Classification is conservative rules-based context matching, not a guaranteed semantic classifier.

One native thread heartbeat is active under `job-agent-morning-discovery`, displayed as **Job agent — daily workflow**. It chooses stages at 08:00 discovery, 10:00/13:00/16:00 mail, and 18:00 report in Australia/Sydney. See `data/schedule_status.json`. Scheduled execution needs the host, connections and available usage; this is not an always-on cloud service. The schedule is managed through the app, not by editing scheduler files. [Official scheduling documentation](https://learn.chatgpt.com/docs/automations?surface=app).

Daily reports distinguish listing observations from unique new jobs and use Australian calendar dates. Notification records and scheduled conversation reports cover recruitment changes and upcoming deadlines. Ambiguous interview dates never become invented calendar bookings.

## Tests and release checks

```text
python -m unittest discover -s tests -q
```

Tests use temporary databases and synthetic `example.test` identities. They cover normalization, duplicates, eligibility, scoring, document generation and validation, answer memory, status history, read-only provider contracts, email context, deadlines, deferred intake, exact approvals, stale reviews, changed documents, simulated filling/uploading, dry-run and level-1 blocking, uncertain receipts and duplicate prevention.

The browser bridge tests additionally cover one-use claims, lost worker heartbeats, uncertain actions, profile/document/validation changes, newly appearing final-page questions and changed website permission. `./test-browser.ps1` separately runs the actual local-browser test; it is not a mock browser or a live employer test.

The backend suite and dashboard build are tested. Live discovery is tested. See `docs/ACCEPTANCE.md` for the current integration boundary and remaining production checks. Never mark a mock test as a live employer test.
