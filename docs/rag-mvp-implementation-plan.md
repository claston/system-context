# RAG MVP Implementation Plan (Technical Slice)

## 1. Objective

Add a technical RAG slice that improves context retrieval quality and demo value, without changing the product core.

Primary goal:

- retrieve evidence-rich context chunks by semantic similarity + structured filters

Constraints for MVP:

- local-first embeddings (no paid API required)
- keep current HTTP/MCP behavior stable
- incremental and reversible rollout

## 2. Scope

In scope:

- vector-ready storage for context chunks
- chunk ingestion from existing normalized entities
- local embedding provider abstraction
- semantic retrieval service and one MCP tool

Out of scope:

- autonomous answer generation in the API
- cross-tenant ranking optimization
- full observability dashboards

## 3. Architecture Slice

```text
Normalized entities (PR, Commit, OperationalIssue, optional logs)
                |
                v
        Chunk builder + embedder
                |
                v
        context_chunk (Postgres + pgvector)
                |
                v
       Retrieval service (hybrid filtering)
                |
                v
     MCP tool: context.semantic_search
```

## 4. Data Model (MVP)

New table: `context_chunk`

- `id` (UUID, PK)
- `source_type` (string, required) e.g. `pull_request`, `commit`, `operational_issue`
- `source_id` (UUID/string, required)
- `system_component_name` (string, required)
- `environment` (string, optional)
- `chunk_text` (string, required)
- `chunk_hash` (string, required, unique for idempotency)
- `embedding` (vector, required)
- `metadata` (JSON, optional)
- `captured_at` (datetime, required)
- `created_at` / `updated_at`

Indexes:

- `ivfflat` (or equivalent) index on `embedding`
- btree on `(system_component_name, environment, captured_at)`
- unique index on `chunk_hash`

## 5. Implementation Phases

### Phase 1 - Foundations

1. Add migration for `context_chunk` and enable `pgvector`.
2. Add ORM model + repository methods:
   - upsert chunk by `chunk_hash`
   - search by vector similarity with optional filters
3. Add `EmbeddingProvider` interface with:
   - `LocalEmbeddingProvider` (default)
   - `OpenAIEmbeddingProvider` (optional, disabled by default)
4. Env vars:
   - `EMBEDDING_PROVIDER=local|openai` (default `local`)
   - `EMBEDDING_MODEL_NAME` (local model identifier)
   - `OPENAI_API_KEY` (optional)
   - `RAG_TOP_K` (default 8)

Exit criteria:

- can insert and retrieve chunks by similarity in an integration test.

### Phase 2 - Ingestion

1. Create `ChunkIngestionService` to build chunks from:
   - pull requests
   - commits
   - operational issues
2. Hook ingestion after normalization completion (initially GitHub + runtime normalization paths).
3. Ensure idempotent ingestion via `chunk_hash`.

Exit criteria:

- running sync + normalization populates `context_chunk` deterministically.

### Phase 3 - Retrieval API/MCP

1. Create `RetrievalService.semantic_search(...)`:
   - query embedding
   - structured filters: `system_component_name`, `environment`, `since_minutes`
   - return top-k with score + source citation
2. Expose one MCP tool:
   - `context.semantic_search`
3. Keep response explainable:
   - chunk text snippet
   - score
   - source_type/source_id
   - component/environment

Exit criteria:

- MCP call returns grounded, cited chunks for real data.

### Phase 4 - Hardening

1. Add freshness fallback:
   - if no vector hit above threshold, return structured message + suggest broader filters.
2. Add basic audit logs for retrieval latency and hit count.
3. Add smoke script for semantic search.

Exit criteria:

- stable demo flow and predictable failure mode.

## 6. Testing Plan

Unit tests:

- chunk builder from PR/commit/issue payloads
- embedding provider contract behavior (local + stub openai)
- retrieval ranking + filtering logic

Integration tests:

- sync/normalize -> chunk ingestion
- MCP `context.semantic_search` happy path + empty-result path

Validation commands:

- `venv\Scripts\python.exe -m ruff check .`
- `venv\Scripts\python.exe -m pytest -q`
- `venv\Scripts\python.exe scripts/validate_environment.py`

## 7. Delivery Plan (Suggested PR Split)

1. PR A: schema + repository + provider abstraction
2. PR B: ingestion service + normalization hooks
3. PR C: retrieval service + MCP tool + tests/docs

## 8. Risks and Mitigations

- Risk: local embedding model heavy/slow on some machines
  - Mitigation: small default model + configurable provider + precomputed chunk updates only on changed data
- Risk: poor relevance in early ranking
  - Mitigation: hybrid filters and small curated chunk templates first
- Risk: migration/env drift with pgvector
  - Mitigation: include extension check in `scripts/validate_environment.py`

## 9. Definition of Done (MVP Technical)

Done when all are true:

1. `context_chunk` storage and retrieval work in CI/local tests.
2. At least one end-to-end MCP semantic search path works with citations.
3. Local-first run works without `OPENAI_API_KEY`.
4. Docs describe setup and demo commands clearly.

