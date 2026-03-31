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

## 3. Implemented Scope (As of 2026-03-31)

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

### Not implemented yet

- Connectors layer (Git/K8s/OpenAPI/etc.)
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

1. Harden `SystemComponent` validations (input rules and error semantics)
2. Harden `CodeRepo` validations (provider/name/url rules)
3. Expand unit/integration coverage for edge cases
4. Harden context-entity validation rules and error semantics
5. Introduce connector abstraction interface
6. Introduce first connector implementations (Git/runtime/OpenAPI)
7. Introduce minimal normalization pipeline
8. Add MCP exposure as a thin layer on top of application services

## 8. Gap Analysis vs PDF Specs

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

## 9. Future Concept (Planned)

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
