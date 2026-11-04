# Job Application Agent

A local job-search and application-preparation workspace that brings job discovery, candidate profiles, document preparation and application progress into one place.

Built around a Python workflow engine, a persistent SQLite database and a React/Vite dashboard, the project preserves state between sessions so applications can be resumed without starting over.

## Features

- Import and normalise job listings from supported sources and reviewed search results.
- Detect duplicates and retain application history.
- Check eligibility against verified candidate information.
- Score relevance using skills, experience, education and location preferences.
- Import master resumes and prepare job-specific DOCX/PDF documents.
- Validate document facts, identity, file integrity and recorded layout-review evidence.
- Reuse verified application answers while keeping candidate profiles separate.
- Coordinate browser form filling, document uploads and pause/resume through a guarded workflow.
- View jobs, documents and preparation progress in a local dashboard.

## Current scope

The current scope covers finding jobs and preparing applications up to the final Submit button. Gmail, recruitment-response tracking and post-application follow-ups are user-managed and disabled under the active project scope.

Isolated browser tests cover navigation, filling, uploads and pause/resume with an Edge session adapter. Employer-specific integration remains in development. Live application preparation requires a supported browser controller, verified candidate information and permission to automate the target website; universal unattended operation is not implemented.

See [Current Scope](docs/CURRENT_SCOPE.md) and [Acceptance Notes](docs/ACCEPTANCE.md) for implementation boundaries. Reuse the existing workspace and database when continuing work.

## Architecture

One main orchestrator coordinates ordinary Python modules.

```text
backend/app/
  orchestrator.py   Workflow coordination
  agents/           Discovery, analysis, scoring and document modules
  integrations/     Job sources, browser adapters and database access
  services/         Preparation lifecycle, records and review gates
  models/           Data contracts
  utils/            Configuration and shared validation
frontend/           React/Vite dashboard
schemas/            JSON schemas
tests/              Unit tests and synthetic browser fixtures
scripts/            Integration checks and development utilities
data/               Local configuration and SQLite database
master_resume/      Original resume snapshots
generated/          Prepared documents and reports
logs/               Local execution logs
```

The dashboard uses durable backend records. Candidate changes invalidate affected preparation and reviews without deleting submitted history. Uncertain submission outcomes remain reserved to prevent automatic duplicate retries.

## Setup

Use Python 3.11 or later and a Node.js version compatible with the Vite version in `frontend/package.json`.

For a new installation in PowerShell:

```powershell
python -m venv .venv/app
& .venv/app/Scripts/python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
& .venv/app/Scripts/python.exe -m backend.app.cli init
Push-Location frontend
npm ci
npm run build
Pop-Location
& .venv/app/Scripts/python.exe -m backend.app.cli serve
```

Open **http://127.0.0.1:8766**. Preserve an existing `.env` and database when resuming a workspace. Configure preferences and verified candidate information locally before preparing personal applications.

The core installation does not configure every browser integration. Consult the [Browser Runbook](docs/BROWSER_BRIDGE.md) and integration documentation under `docs/` for additional runtime requirements.

## Usage

With the project environment activated:

```powershell
python -m backend.app.cli run
python -m backend.app.cli run --offline
python -m backend.app.cli report
python -m backend.app.cli daily-report
python -m backend.app.cli import-resume path/to/resume.pdf
python -m backend.app.cli ingest-jobs path/to/reviewed-jobs.json
python -m backend.app.cli serve
```

On the configured Windows workstation, the convenience launcher also supports:

```powershell
./run-job-agent.ps1
./run-job-agent.ps1 -Offline
./run-job-agent.ps1 -Dashboard
```

Resume imports produce review proposals. Extraction alone does not verify a fact. Confirm candidate information before using it in applications, and complete factual validation and layout review before uploading generated documents.

## Configuration and controls

The example configuration starts with:

```dotenv
DRY_RUN=true
AUTOMATION_LEVEL=2
PRODUCTION_APPROVED=false
HOST=127.0.0.1
PORT=8766
DATABASE_PATH=data/job_agent.sqlite3
```

Dry-run mode blocks submission. Submission-capable code uses validation, approval and duplicate-prevention gates. Unknown required answers, login challenges, CAPTCHA and failed uploads pause the affected workflow.

Only verified information may be used. The system must not invent qualifications, employment, dates, work rights or other candidate facts. Relevance scores are matching heuristics, not hiring predictions or scores supplied by an employer's ATS.

## Privacy

Candidate details, resumes, answer memory, application records, databases, generated documents, logs and secrets remain local and are excluded from version control. This repository contains source code, tests, schemas and example settings.

Store secrets in `.env` or environment variables. The local SQLite database is not encrypted. The dashboard is intended for loopback access; public deployment requires a separate authentication and hosting design.

See [Repository Contents](docs/REPOSITORY_CONTENTS.md) for the code-only publishing policy.

## Testing

```powershell
python -m unittest discover -s tests -q
Push-Location frontend
node --test tests/relevance.test.mjs
npm run build
Pop-Location
```

Tests use synthetic candidates and isolated databases. Browser fixtures exercise integrations without sending applications to real employers. The configured Windows workstation can run the local browser smoke check with `./test-browser.ps1`.

## Documentation

- [Current Scope](docs/CURRENT_SCOPE.md)
- [Browser Runbook](docs/BROWSER_BRIDGE.md)
- [Acceptance Notes](docs/ACCEPTANCE.md)
- [Repository Contents](docs/REPOSITORY_CONTENTS.md)
- [Third-Party Notices](THIRD_PARTY_NOTICES.md)
