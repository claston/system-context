# Heuristics Mini-Spec (MVP)

## 1. Purpose

Define a practical and implementation-ready contract for heuristics so the MVP delivers value through interpreted context, not only collected data.

Heuristics are the product core:

- connectors collect raw facts
- normalization heuristics convert facts into durable signals
- query-time heuristics compose recent state into actionable context

## 2. Scope (MVP)

In scope:

- deterministic heuristics for runtime/reliability signals
- simple query-time heuristics to summarize risk at request time
- explicit evidence and confidence metadata in every heuristic output
- stable payload shape for API and MCP consumers

Out of scope (for now):

- ML-based anomaly detection
- cross-service graph inference that requires offline batch jobs
- automatic remediation execution

## 3. Heuristic Stages

### 3.1 Normalization-time heuristics (persisted)

Use during `sync -> normalize` when the rule is deterministic and idempotent from connector payloads.

Persisted output target:

- `operational_issue` rows (current table)
- supporting evidence in `evidence_source` and `evidence_payload`

Use this stage when the signal must survive restarts and be queryable historically.

### 3.2 Query-time heuristics (computed on read)

Use during context queries/MCP tools when the rule depends on current windowing or aggregation.

Output target:

- response-only signal data merged into context payloads
- no new row required unless promoted later to durable signal

Use this stage for low-cost, quickly evolving heuristics.

## 4. Canonical Heuristic Signal Contract

Every heuristic (persisted or query-time) should emit this logical contract:

```json
{
  "heuristic_id": "H-RUN-001",
  "heuristic_version": "1",
  "system_component": "payment-api",
  "environment": "staging",
  "issue_type": "unexpected_restart",
  "status": "open",
  "severity": "high",
  "confidence": "high",
  "summary": "Unexpected restart outside deploy grace window",
  "impact": "possible runtime instability",
  "recommended_action": "check recent logs and dependency latency",
  "first_seen_at": "2026-04-09T18:09:09+00:00",
  "last_seen_at": "2026-04-09T18:09:09+00:00",
  "evidence": [
    {
      "source": "render-runtime",
      "source_key": "runtime_snapshot:srv-123:2026-04-09T18:09:09Z",
      "occurred_at": "2026-04-09T18:09:09+00:00",
      "event_type": "service.restarted"
    }
  ]
}
```

Mapping to current persistence model:

- `issue_type`, `status`, `first_seen_at`, `last_seen_at`, `confidence` map directly to `operational_issue`
- `heuristic_id`, `heuristic_version`, `severity`, `summary`, `impact`, `recommended_action`, and evidence array should live in `evidence_payload` until dedicated columns are introduced

## 5. Rule Template (for every new heuristic)

Each heuristic must be specified with:

1. `heuristic_id` and `version`
2. Stage (`normalization` or `query`)
3. Required inputs and source connectors
4. Rule logic and thresholds
5. False-positive guardrails
6. Output contract mapping
7. Test cases (positive, negative, idempotency)

## 6. Initial Heuristic Catalog

### 6.1 H-RUN-001 Unexpected restart outside deploy window

- Stage: normalization
- Inputs: Render runtime restart candidates + `last_deploy_at`
- Rule:
  - detect restart candidate
  - ignore candidate inside deploy grace window (default: 10 minutes)
  - open/update `operational_issue` with `issue_type=unexpected_restart`
- Confidence:
  - `events` source -> `high`
  - `instances` source -> `medium`
  - fallback -> `low`
- Current implementation reference:
  - `app/application/render_runtime_normalization_service.py`

### 6.2 H-LOG-001 Recent repeated error signature burst

- Stage: query
- Inputs: recent Render logs in a rolling window
- Rule:
  - group by normalized error signature
  - if same signature count crosses threshold, surface as top issue
- Output:
  - include severity, likely causes, suggested actions, sample lines
- Current implementation reference:
  - `app/application/render_logs_analysis_service.py`

### 6.3 H-SYNC-001 Stale context freshness warning

- Stage: query
- Inputs: last successful sync timestamp by connector/component
- Rule:
  - if staleness exceeds threshold, emit warning signal
- Status: planned

## 7. Stage Boundary Rules (Normalization vs Query)

Persist the heuristic when:

- outcome is deterministic for a connector payload
- idempotency can be guaranteed
- historical traceability matters for operators

Keep it query-time when:

- rule depends on moving windows
- threshold tuning is still volatile
- persistence cost is not justified yet

## 8. Config Baseline (proposed env vars)

- `HEUR_RESTART_DEPLOY_GRACE_MINUTES=10`
- `HEUR_LOG_ERROR_BURST_THRESHOLD=5`
- `HEUR_LOG_ANALYSIS_WINDOW_MINUTES=30`
- `HEUR_STALE_SYNC_MINUTES=90`

## 9. Acceptance Criteria for Heuristic Work

Every heuristic PR should include:

1. Rule spec update in this document
2. Unit tests for true/false paths
3. Idempotency test when persisted
4. API/MCP exposure validation showing evidence and confidence
5. Short rollback note (feature flag, threshold rollback, or disable path)

