# Code-only repository

This repository contains application source, tests with synthetic fixtures, schemas, dependency manifests, documentation and example settings.

Candidate profiles, answer memory, application histories, databases, resumes, cover letters, generated documents, screenshots, browser sessions, logs, local dependencies and secrets are local-only. Do not force-add ignored files. Copy `.env.example` to `.env` locally and supply your own verified candidate information.

The vendored AIHawk checkout and installed environment are not committed. To obtain the inspected source, clone https://github.com/feder-cr/AIHawk into `vendor/AIHawk` and check out commit `afe1f66dd3f1572d59a78ea67688a0d0e49e8b25`. Follow `AIHAWK_RUNTIME.md` and `THIRD_PARTY_NOTICES.md` for the integration boundary and dependency information.

The code defaults to dry-run mode. Private profile-specific authorizations and live application records are intentionally absent from this repository. Historical milestone documentation describes local development, not a configured installation for a new user.
