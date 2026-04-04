# System Context API - MVP Spec and Current Status

## 1. Objective

Build a minimal API that provides structured system context for LLMs/agents.

Primary goals:
- Represent system components and related metadata in a clean domain model
- Expose this data through a simple API
- Keep the base ready for future integration with connectors, normalization, and MCP

## 2. Current Architecture (Implemented)

FastAPI (HTTP API)
-> SQLAlchemy ORM
-> PostgreSQL
-> Alembic migrations

Current modules:
- `app/main.py`: API endpoints
- `app/models.py`: ORM model(s)
- `app/schemas.py`: request/response schemas
- `app/db.py`: database engine/session config
- `alembic/versions/*`: schema migration(s)

## 3. Implemented Scope (As of 2026-04-03)

### Implemented now

- `SystemComponent` entity in database
- Alembic migration for `system_component` table rename
- `CodeRepo` entity in database
- Alembic migration for `code_repo` table
- Context entities in database:
  - `pull_request`
  - `commit`
  - `deployment`
  - `runtime_snapshot`
  - `api_contract`
  - `endpoint`
  - `dependency`
  - `sync_run`
  - `connector_raw_event`
- SystemComponent API endpoints:
  - `GET /health`
  - `POST /system-components`
  - `GET /system-components`
  - `GET /system-components/{system_component_id}`
- CodeRepo API endpoints:
  - `POST /code-repos`
  - `GET /code-repos`
  - `GET /code-repos/{code_repo_id}`
  - `GET /system-components/{system_component_id}/code-repos`
- Context CRUD/list endpoints:
  - `POST/GET /pull-requests`
  - `POST/GET /commits`
  - `POST/GET /deployments`
  - `POST/GET /runtime-snapshots`
  - `POST/GET /api-contracts`
  - `POST/GET /endpoints`
  - `POST/GET /dependencies`
  - `POST/GET /sync-runs`
- Sync orchestration endpoints:
  - `POST /sync-runs/{connector_name}`
  - `GET /sync-runs/{sync_run_id}`
- Normalization endpoint:
  - `POST /normalize/github/sync-runs/{sync_run_id}`
- Context aggregation endpoints:
  - `POST /agent/context`
  - `GET /context/system/current-state`
  - `GET /context/system-component/{name}`
  - `GET /context/system-component/{name}/changes`
  - `GET /context/system-component/{name}/runtime`
  - `GET /context/system-component/{name}/dependencies`
- Pydantic schemas for create and response payloads
- DB session dependency in FastAPI
- Persistence + Application layers with dependency injection
- Connector abstraction contracts (`ConnectorRunRequest`, `ConnectorBatch`, `Connector` protocol)
- First connector implementation (GitHub connector using real GitHub API requests)
- Async sync job dispatching via thread pool and sync run status lifecycle (`running/success/failed`)
- Generic sync execution pipeline (`trigger_sync`/`execute_sync`) with connector registry
- Background sync execution using isolated repository scope per job (separate DB session from request thread)
- Raw connector item persistence linked to sync runs (`connector_raw_event`)
- Automatic GitHub normalization on sync completion (plus manual reprocessing endpoint for retries/operations)

### Not implemented yet

- Additional connector implementations beyond initial GitHub flow (runtime/OpenAPI/K8s/etc.)
- Normalization layer
- MCP/RAG integration

## 4. Data Model

### SystemComponent (implemented)

Table: `system_component`

Fields:
- `id` (UUID, PK)
- `name` (string, unique, required)
- `description` (string, optional)
- `created_at` (datetime with timezone)
- `updated_at` (datetime with timezone)

### CodeRepo (implemented)

Table: `code_repo`

Fields:
- `id` (UUID, PK)
- `system_component_id` (UUID, FK -> `system_component.id`)
- `provider` (string, required)
- `name` (string, required)
- `url` (string, required)
- `default_branch` (string, optional)
- `created_at` (datetime with timezone)
- `updated_at` (datetime with timezone)

Constraints:
- unique (`provider`, `name`)

### Context Entities (implemented)

Tables:
- `pull_request`
- `commit`
- `deployment`
- `runtime_snapshot`
- `api_contract`
- `endpoint`
- `dependency`
- `sync_run`
- `connector_raw_event`

Note:
- All context entities currently have `POST` + `GET` list endpoints and are used by context aggregation APIs.

## 5. API Contract (Current)

### `GET /health`

Response:
```json
{ "status": "ok" }
```

### `POST /system-components`

Request:
```json
{
  "name": "payment-api",
  "description": "Handles payments"
}
```

Response:
- Returns created `SystemComponent` with `id`, `created_at`, `updated_at`

### `GET /system-components`

Response:
- List of `SystemComponentResponse`

### `GET /system-components/{system_component_id}`

Response:
- A single `SystemComponentResponse`
- `404` when system component does not exist

### `POST /code-repos`

Request:
```json
{
  "system_component_id": "UUID",
  "provider": "github",
  "name": "payment-api",
  "url": "https://github.com/org/payment-api",
  "default_branch": "main"
}
```

Response:
- Returns created `CodeRepo` with metadata/timestamps
- `404` when `system_component_id` does not exist
- `409` for duplicate (`provider`, `name`)

### `GET /code-repos`

Response:
- List of `CodeRepoResponse`

### `GET /code-repos/{code_repo_id}`

Response:
- A single `CodeRepoResponse`
- `404` when code repo does not exist

### `GET /system-components/{system_component_id}/code-repos`

Response:
- List of `CodeRepoResponse` linked to a system component
- `404` when system component does not exist

### Context CRUD/List APIs (current)

- `POST/GET /pull-requests`
- `POST/GET /commits`
- `POST/GET /deployments`
- `POST/GET /runtime-snapshots`
- `POST/GET /api-contracts`
- `POST/GET /endpoints`
- `POST/GET /dependencies`
- `POST/GET /sync-runs`

### Context Query APIs (current)

- `POST /agent/context`
- `GET /context/system/current-state`
- `GET /context/system-component/{name}`
- `GET /context/system-component/{name}/changes`
- `GET /context/system-component/{name}/runtime`
- `GET /context/system-component/{name}/dependencies`

## 6. Design Principles

- Keep the MVP small and understandable
- Prefer structured data for agent consumption
- Add complexity only after core domain is stable
- Separate future data collection from interpretation

## 7. Roadmap (Next Suggested Steps)

1. [Done] Harden `SystemComponent` validations (input rules and error semantics)
2. [Done] Harden `CodeRepo` validations (provider/name/url rules)
3. [Done] Expand unit/integration coverage for edge cases
4. [Done] Harden context-entity validation rules and error semantics
5. [Done] Introduce connector abstraction interface
6. [In progress] Introduce first connector implementations (Git/runtime/OpenAPI)
   - Current status: GitHub connector (real API integration) + generic sync pipeline + raw ingestion persistence implemented
   - Remaining scope: runtime/OpenAPI connectors
7. [In progress] Introduce minimal normalization pipeline
   - Current status: GitHub raw-event normalization to canonical `pull_request` and `commit` implemented via `POST /normalize/github/sync-runs/{sync_run_id}`
   - Remaining scope: extend normalization to additional connectors/entities and add richer traceability
8. [Next] Add MCP exposure as a thin layer on top of application services

## 11. Structured Backlog (MVP)

### Now

- `[BL-001]` Complete connector set for MVP:
  - status: in progress
  - scope: keep GitHub connector, add runtime connector, add OpenAPI connector
  - outcome: first multi-source context ingestion path
- `[BL-002]` Start minimal normalization pipeline:
  - status: in progress
  - scope: normalize GitHub raw connector payloads into canonical `pull_request`/`commit` entities with idempotent upsert behavior
  - outcome: first usable normalized context path for agent consumption (`sync -> normalize` automation implemented for GitHub)
- `[BL-007]` Make raw-event dedup insertion atomic at DB level:
  - status: pending
  - scope: replace select-then-insert dedup flow with `ON CONFLICT DO NOTHING` semantics for `connector_raw_event_identity_key`
  - outcome: remove race-condition risk under concurrent sync workers
- `[BL-008]` Add GitHub connector pagination for incremental completeness:
  - status: pending
  - scope: paginate PR/commit collection until cursor boundary (with safety caps/rate-limit awareness)
  - outcome: avoid data loss when delta volume exceeds one page (`GITHUB_PER_PAGE`)
- `[BL-009]` Align sync status semantics with partial failures:
  - status: pending
  - scope: set `sync_run.status=partial` when connector returns mixed success/errors and keep clear processed/inserted counters
  - outcome: better operational visibility and safer retry decisions

### Next

- `[BL-003]` Add MCP exposure on top of application services:
  - status: pending
  - scope: thin MCP layer for current-state and recent-change queries
  - outcome: direct agent toolability
- `[BL-004]` Add operational insights to context model:
  - status: pending
  - scope: represent CI/runtime warnings (e.g., deprecations), impact, action, status, and evidence
  - outcome: proactive maintenance signals available to agents
- `[BL-006]` Enrich GitHub sync payload with PR/commit context:
  - status: pending
  - scope: persist changed files, labels, review/merge metadata, and commit-to-PR linkage when available
  - outcome: higher-quality context for agents to reason about impact and where to change code
- `[BL-010]` Split context repository by bounded concern:
  - status: pending
  - scope: separate sync ingestion/cursor persistence from generic context CRUD repository
  - outcome: lower cognitive load and easier MVP evolution with clearer ownership boundaries

### Later

- `[BL-005]` Add sync freshness/scoring signals:
  - status: pending
  - scope: confidence/freshness metadata per normalized context artifact
  - outcome: better decision quality for agents

## 12. Completed Activities (Snapshot)

- `[DONE]` Task 1: harden `SystemComponent` validations and error semantics.
- `[DONE]` Task 2: harden `CodeRepo` validations.
- `[DONE]` Task 3: expand edge-case test coverage.
- `[DONE]` Task 4: harden context-entity validations and error semantics.
- `[DONE]` Task 5: introduce connector abstraction interface.
- `[DONE/ONGOING]` Task 6: implement GitHub connector path, async sync hardening, raw event persistence, and generic trigger flow; runtime/OpenAPI connectors still pending.
- `[DONE]` Automate environment validation:
  - local command `scripts/validate_environment.py`
  - CI migration/schema check job
  - PR checklist and AGENTS guidance update

### 7.1 Task 6 Hardening Plan (Implemented in this cycle)

1. [Done] Remove hardcoded sync orchestration internals by introducing generic dispatch (`dispatch_sync`) and generic service execution (`trigger_sync`/`execute_sync`).
2. [Done] Prevent background thread from reusing request-scoped repository/session by running worker updates inside a dedicated repository scope.
3. [Done] Persist raw connector payloads for auditability/future normalization via `connector_raw_event`.
4. [Done] Remove legacy sync wrappers and expose a single generic trigger endpoint (`POST /sync-runs/{connector_name}`).
5. [Done] Validate with tests and real HTTP calls:
   - Unit/integration test suite passed (current branch validation)
   - Lint passed (`ruff check`)
   - HTTP validation passed for sync endpoints (`create`, `list`, `get-by-id`, negative path `404`)

### 7.2 GitHub Connector Runtime Configuration

Environment variables used by `GithubConnector`:

- `GITHUB_TOKEN` (optional): GitHub token for authenticated requests (recommended to avoid low rate limits).
- `GITHUB_OWNER` (optional): default owner/org used when `system_component_name` is provided without owner prefix.
- `GITHUB_REPOS` (optional): comma-separated repository targets in `owner/repo` format.
- `GITHUB_PER_PAGE` (optional): number of items requested per endpoint call (default: `20`).
- `GITHUB_SYNC_LOOKBACK_MINUTES` (optional): overlap window applied to cursor cutoff to absorb out-of-order source timestamps (default: `60`).

Target resolution order:

1. `system_component_name` with `owner/repo` format.
2. `GITHUB_OWNER + system_component_name`.
3. Match `system_component_name` against configured `GITHUB_REPOS`.
4. Fallback to all configured `GITHUB_REPOS`.

### 7.3 Environment Validation Automation

To make migration state automatic and verifiable:

- Local command:
  - `venv\Scripts\python.exe scripts/validate_environment.py`
- What it checks:
  - runs `alembic upgrade head`
  - confirms current DB revision equals Alembic head
  - confirms required core tables exist (including `connector_raw_event`)
- CI enforcement:
  - workflow includes dedicated Postgres job to run the same validation script

### 7.4 Sync Lifecycle Guardrails

To reduce inconsistent sync state during app restarts/stops:

- Startup recovery:
  - application marks orphaned `sync_run` rows in `running` as `failed`
  - error summary: `recovered on startup after unclean stop`
- Graceful shutdown:
  - application stops accepting new sync triggers
  - waits for active sync workers until configured timeout
  - marks remaining `running` syncs as `failed`
  - error summary: `interrupted by shutdown`

Runtime configuration:

- `SYNC_RECOVERY_ENABLED` (default: `true`)
- `SYNC_SHUTDOWN_TIMEOUT_SECONDS` (default: `15`)

### 7.5 Phase 1 Security Guardrails (No Cost)

Implemented controls:

- `main` branch protection:
  - pull request required
  - 1 approving review required
  - required checks: `lint-and-test`, `migration-and-schema-check`
  - conversation resolution required
- Dependabot security:
  - vulnerability alerts enabled
  - automated security updates enabled
- Secret scanning:
  - secret scanning enabled
  - push protection enabled
- CI/workflow hardening:
  - least-privilege workflow permission baseline (`contents: read`) in CI
  - CodeQL workflow added for Python (`pull_request`, `main`, and weekly schedule)
  - Dependabot version update automation for `pip` and `github-actions`

## 8. Practical Direction To Keep Focus

1. Standardize a canonical context model (entities and relationships)
2. Prioritize high-value connectors first (Git, deploy/runtime, observability)
3. Implement normalization plus confidence/freshness scoring for ingested data
4. Expose APIs for current state, recent changes, and risk signals
5. Add autonomy guardrails (action limits, human approval, audit trail)

## 9. Gap Analysis vs PDF Specs

The PDFs in `docs/` define a broader MVP than the current codebase.

If we follow those PDF specs strictly, the main missing pieces are now platform capabilities (not base entities/endpoints):

### Missing platform capabilities (from PDFs)

- connector abstractions and first connector implementations (Git/Kubernetes/OpenAPI/Deploy)
- normalization layer turning source payloads into internal semantic models
- sync jobs and freshness tracking
- MCP server exposing application-layer context tools

Note:
- Current project scope intentionally focuses on `SystemComponent` first.
- The PDFs still use older names (`service`, `repository`), but this project
  standardizes on `system_component` and `code_repo`.
- The list above is the PDF-defined expansion path, normalized to current naming.

## 10. Future Concept (Planned)

### Connectors

Data collection adapters for external systems (Git, runtime, OpenAPI, CI/CD).

Responsibilities:
- Collect data
- Handle auth
- Sync incrementally when possible
- Persist raw/intermediate records

Should not:
- Apply business/domain meaning
- Correlate entities by inference

### Normalization Layer

Transforms raw connector data into clean domain context.

Examples:
- Git source metadata -> internal context model
- K8s deployment -> runtime snapshot
- OpenAPI spec -> API contract model

Key principle:
- Connectors describe what exists
- Normalization defines what it means
