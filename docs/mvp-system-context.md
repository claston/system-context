# System Context API - MVP Spec and Current Status

## 1. Objective

Build a minimal API that provides structured system context for LLMs/agents.

Primary goals:
- Represent services and related metadata in a clean domain model
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

## 3. Implemented Scope (As of 2026-03-29)

### Implemented now

- `Service` entity in database
- Alembic migration for `service` table
- Service API endpoints:
  - `GET /health`
  - `POST /services`
  - `GET /services`
  - `GET /services/{service_id}`
- Pydantic schemas for create and response payloads
- DB session dependency in FastAPI

### Not implemented yet

- `Repository` entity and endpoints
- Relationships (`Service <-> Repository`)
- Context endpoint (`/context/service/{id}`)
- Connectors layer (Git/K8s/OpenAPI/etc.)
- Normalization layer
- MCP/RAG integration

## 4. Data Model

### Service (implemented)

Table: `service`

Fields:
- `id` (UUID, PK)
- `name` (string, unique, required)
- `description` (string, optional)
- `created_at` (datetime with timezone)
- `updated_at` (datetime with timezone)

### Repository (planned)

Not implemented in code yet.

Proposed fields:
- `id` (UUID)
- `name` (string)
- `url` (string)
- `service_id` (FK -> service.id)
- `created_at` (datetime)
- `updated_at` (datetime)

## 5. API Contract (Current)

### `GET /health`

Response:
```json
{ "status": "ok" }
```

### `POST /services`

Request:
```json
{
  "name": "payment-api",
  "description": "Handles payments"
}
```

Response:
- Returns created `Service` with `id`, `created_at`, `updated_at`

### `GET /services`

Response:
- List of `ServiceResponse`

### `GET /services/{service_id}`

Response:
- A single `ServiceResponse`
- `404` when service does not exist

## 6. Design Principles

- Keep the MVP small and understandable
- Prefer structured data for agent consumption
- Add complexity only after core domain is stable
- Separate future data collection from interpretation

## 7. Roadmap (Next Suggested Steps)

1. Implement `Repository` model and migration
2. Add `Service <-> Repository` relationship in ORM
3. Create Repository CRUD endpoints
4. Add first basic context endpoint
5. Introduce connector abstraction interface
6. Introduce minimal normalization pipeline

## 8. Future Concept (Planned)

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
- Git repo -> `Repository`
- K8s deployment -> runtime snapshot
- OpenAPI spec -> API contract model

Key principle:
- Connectors describe what exists
- Normalization defines what it means
