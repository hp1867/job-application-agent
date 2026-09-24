# Acceptance boundaries

Current scope override: stop at final application review/Submit. Gmail, response tracking, interviews and follow-ups are user-managed and excluded from acceptance. Older mail and submission checklist items below are historical, not instructions to execute them. Actual installed AIHawk now passes both single-page and multi-page local queue tests; employer-site acceptance remains pending.

## Implemented and exercised

- One persistent orchestrator, SQLite tracking and status history.
- Active candidate profile reset to unknown/deferred, with previous local data preserved separately.
- Read-only MCP discovery and nCino public Greenhouse discovery; ten records retained after the latest run, with two excluded from top jobs by eligibility/role scope.
- Eligibility, transparent scoring, exact-fact DOCX/PDF generation, source and extraction validation.
- Configurable target-role scope independent of source search keywords; unrelated roles cannot shortlist, while ambiguous graduate programs require review. Excluded records remain auditable.
- Captured verified answer memory; legal and unknown questions require review.
- Controlled browser workflow tested with fake drivers, durable queue tests, and an actual isolated Edge session filling/selecting a file on the local test form. The actual browser run reached approval readiness and refused submission; no real employer receives fixture data.
- Changed-profile/document/job checks, exact expiring approval, unique submission reservation and observed-receipt requirement.
- Read-only Gmail architecture, contextual classification, deadline extraction and local notifications.
- React dashboard compiled and loopback API health checked; browser smoke testing performed during the build.
- JSON schemas, mail-only and daily-report CLI stages, and one active time-routed native heartbeat.
- The isolated suite covers loopback Host/CSRF/Origin enforcement, path traversal, fresh-workspace defaults, no-submit-endpoint checks, cross-record duplicate targets, cover-letter validation, explicit-timezone deadlines and idempotent reminders. Test counts and the final execution result are recorded in BUILD_STATUS.md.

## Not claimed as completed

- Candidate intake and master resume confirmation: intentionally deferred by the user.
- Candidate match scores: unavailable while intake is deferred, not zero-percent matches.
- Real employer application fill/upload/submit: not performed. The durable browser bridge is implemented, but the earlier in-app connector is not currently exposed. The isolated local test controller cannot navigate to employers or submit. Verify a permitted controller and the actual employer form before live use.
- Real document visual validation: no candidate-approved documents exist; render/inspect before readiness.
- Recruitment mail end-to-end against the candidate's account: awaits explicit mailbox confirmation and real submitted applications.
- Uninterrupted 24/7 operation: the schedule depends on host availability, permissions, tool connections and usage.
- Cloud database, authentication and hosted dashboard: not configured; unrelated existing Firebase resources were deliberately left untouched.
- Automatic broad job-board crawling: unsupported boards use the connected search/capture workflow, not bypassed website restrictions.

## Production checklist after later intake

1. Confirm the supplied candidate and exact verified facts, including rights, dates and availability.
2. Preserve/import the supplied master resume and review extraction; resolve missing facts only as needed.
3. Review the employer's current full requirements and website automation permission.
4. Generate documents, validate facts, render every page, inspect DOCX/PDF layout and approve the exact artifacts.
5. Inspect the actual browser form; fill only safe verified information and confirm uploads. Resolve unknowns, declarations, login/MFA or CAPTCHA manually.
6. Save current form evidence, review the exact packet, then obtain the user's production-mode and level-2 application approval separately.
7. Reserve once, submit through the allowed browser, verify receipt, and record APPLIED only with evidence. Never retry an uncertain result automatically.
8. Confirm the candidate mailbox and exercise receipt matching, status updates and deadline notifications.
