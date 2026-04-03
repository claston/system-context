# Real Test Bugs and Mitigations

Last updated: 2026-04-03

## Purpose

Track bugs found during real or near-real validation, with root cause and concrete mitigation actions.

## Bug 1 - `repository_scope` context handling crash

- First observed: 2026-04-03
- Area: `app/application/sync_service.py`
- Symptom:
  - Runtime error in sync flow:
  - `TypeError: '_GeneratorContextManager' object is not iterable`
- Real impact:
  - Sync execution fails before processing connector data.

### Root Cause

- `_repository_context` used `yield from self.repository_scope()`.
- `repository_scope()` returns a context manager, not an iterable generator.
- Test doubles were permissive and did not enforce the same contract shape as runtime.

### Mitigation Actions

- Code fix:
  - Use context manager semantics:
  - `with self.repository_scope() as repo: yield repo`
- Test hardening:
  - Update fake scope in tests to return an actual context manager via `@contextmanager`.
- Prevention:
  - Add explicit contract test for repository scope behavior.
  - Prefer protocol/type checks for dependency boundaries in service constructors.

### Status

- Fixed in code and covered by tests.

## Bug 2 - Missing `connector_raw_event` table in local database

- First observed: 2026-04-03
- Area: database migration/environment state
- Symptom:
  - Table expected by code was missing in local runtime database.
- Real impact:
  - Runtime behavior diverged from expected schema; connector persistence/reads can fail.

### Root Cause

- Environment drift: local DB schema not aligned with latest Alembic migration head.
- CI validated code/tests but local environment validation did not always run before manual tests.

### Mitigation Actions

- Environment validation automation:
  - Keep `scripts/validate_environment.py` in the pipeline and local workflow.
  - Validate Alembic head vs current DB revision before real tests.
- Process guardrail:
  - Add a pre-flight checklist for real connector tests:
  - `.venv` active, migrations applied, app running once, correct `.env` values.
- Prevention:
  - Run migration + environment validation in CI and before local end-to-end runs.

### Status

- Mitigated with validation script and CI integration; requires team discipline to run pre-flight locally.

## Bug 3 - Duplicate local app instances during manual run

- First observed: 2026-04-03
- Area: local runtime process management
- Symptom:
  - A previous app instance kept running while a new one started.
- Real impact:
  - Confusing behavior and inconsistent test results (requests may hit unexpected process).

### Root Cause

- Manual start/stop sequence without process verification.

### Mitigation Actions

- Add local run hygiene:
  - Before starting app, check if another process is bound to service port.
  - Use a single command path for start/stop during manual tests.
- Runtime guardrail in application lifecycle:
  - On shutdown, stop accepting new sync runs and finalize leftover `running` syncs as failed.
  - On startup, recover orphaned `running` syncs from previous unclean stop.
- Documentation:
  - Keep this in AGENTS/docs runbook for future contributors.

### Status

- Mitigated in code with graceful shutdown + startup recovery flow.

## Consolidated Action Items (MVP)

1. Keep dependency contract tests for service boundaries (`repository_scope`, connector interfaces).
2. Enforce environment pre-flight (`.venv`, alembic head, required tables) before real tests.
3. Standardize local app lifecycle commands to avoid duplicate instances.
4. Update this document whenever a real-test issue is found, with date, root cause and fix status.
