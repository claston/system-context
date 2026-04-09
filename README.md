# System Context API

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](#)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?logo=sqlalchemy&logoColor=white)](#)
[![Alembic](https://img.shields.io/badge/Alembic-Migrations-4B5563)](#)
[![MCP](https://img.shields.io/badge/MCP-JSON--RPC-111827)](#)

Context platform for agents and LLM workflows.  
This service ingests operational/software context, normalizes key signals, and exposes them through HTTP and MCP-compatible interfaces.

---

## Why this project exists

`system-context` gives agents reliable context to answer questions like:

- "What changed recently in this component?"
- "What is the latest runtime/deploy state?"
- "Which dependencies matter for this service?"
- "Are there recent Render errors that should block a rollout?"

The goal is to keep context structured, queryable, and automation-friendly.

---

## Core capabilities

- FastAPI API with persistence via SQLAlchemy + PostgreSQL
- Alembic-driven schema management and environment validation
- Generic sync pipeline for connectors (current: GitHub + Render runtime path)
- Normalization flow for connector raw events
- MCP endpoint (`POST /mcp`) with tools/resources for agent consumption
- Optional MCP audit logging with redaction controls

---

## Architecture snapshot

```text
Connectors (GitHub, Render runtime/logs)
            |
            v
       Sync pipeline
            |
            v
   Raw events + normalized entities
            |
            v
 FastAPI HTTP APIs + MCP JSON-RPC endpoint
            |
            v
      Agents / IDE copilots / ops flows
```

---

## Repository layout

```text
app/
  application/      # use-case services and orchestration
  connectors/       # external source integrations
  observability/    # MCP audit logging helpers
  repositories/     # SQLAlchemy repositories
  routers/          # FastAPI route handlers, including /mcp
  main.py           # app composition + lifespan hooks

alembic/            # migration scripts
scripts/            # smoke checks, manual MCP tests, env validation
tests/              # unit and integration tests
docs/               # implementation and deployment docs
```

---

## Quick start (local)

### 1. Install dependencies

```powershell
venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.local.example` to `.env` and set at least:

- `DATABASE_URL`
- `MCP_API_TOKEN` (optional but recommended)
- connector vars you plan to use (`GITHUB_*`, `RENDER_*`)

### 3. Validate DB + migration state

```powershell
venv\Scripts\python.exe scripts/validate_environment.py
```

### 4. Run API

```powershell
venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

API docs: `http://localhost:8000/docs`

---

## MCP usage

Primary endpoint:

- `POST /mcp`

Useful scripts:

- smoke validation: `venv\Scripts\python.exe scripts/mcp_smoke_check.py`
- manual requests: `powershell -File scripts/test_mcp_manual.ps1`

### MCP audit logs

Set these env vars when you need request/tool flow visibility:

- `MCP_AUDIT_LOG_ENABLED=true`
- `MCP_AUDIT_LOG_INCLUDE_RESULT_BODY=false|true`
- `MCP_AUDIT_MAX_PAYLOAD_CHARS=4000`

Auth/token fields are automatically redacted in audit payloads.

---

## Quality gates

```powershell
venv\Scripts\python.exe -m ruff check .
venv\Scripts\python.exe -m pytest -q
venv\Scripts\python.exe scripts/validate_environment.py
```

---

## Deploy notes

- Dockerfile runs `alembic upgrade head` before starting Uvicorn.
- Staging setup guidance: `docs/staging-secrets-setup.md`
- Docker run guidance: `docs/docker-run-guide.md`
- Key GitHub workflows:
  - `CI | Quality Gates`
  - `Staging | Environment Validation`
  - `CD | Publish Container (GHCR)`
  - `CD | Deploy to Render (Staging)`
  - `Release | Versioned Publish` (tag trigger `v*.*.*`)
- Image build sets `APP_RELEASE` so `GET /release-check` can expose release identity.
- Quick release verification after deploy: `GET /release-check` should return the expected `APP_RELEASE` value.

---

## Roadmap references

- Product/implementation snapshot: `docs/mvp-system-context.md`
- Real test bugs + mitigations: `docs/real-test-bugs-and-mitigations.md`

---

## Contribution workflow

This repository uses a strict working agreement in `AGENTS.md`:

- sync local `main` from `origin/main`
- always create a focused branch
- prefer TDD and run full validation before delivery
- use Conventional Commits
- open PR with test evidence and risk/rollback note
