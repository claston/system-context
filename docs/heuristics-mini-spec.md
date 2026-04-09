# Heuristics Mini-Spec (MVP)

## 1. Purpose

Keep heuristics as the core product value while implementation stays simple.

For MVP, we prefer local and explicit rules over a generic heuristics framework.

## 2. MVP Implementation Style (Simple First)

Default rule:

- each normalization flow can have one or more heuristic classes in the same module as the normalizer
- no global registry, no plugin system, no cross-cutting framework yet
- normalizer orchestrates persistence and idempotency

Reference shape:

```python
class UnexpectedRestartHeuristic:
    def evaluate(self, payload: dict) -> dict | None:
        ...
```

`evaluate()` returns either:

- `None` when no signal should be emitted
- a small dict with only what persistence needs now (`issue_type`, `confidence`, `evidence_source`, `evidence_payload`, timestamps)

## 3. Responsibility Split

### 3.1 Heuristic class (inside normalizer module)

Responsibilities:

- apply deterministic rule logic
- return normalized signal data
- remain stateless and easy to unit test

### 3.2 Normalization service

Responsibilities:

- call heuristic class
- handle DB upsert/idempotency
- decide open/update behavior for existing issues

This keeps business interpretation close to the ingestion path, without introducing premature abstractions.

## 4. Current MVP Example

`RenderRuntimeNormalizationService` can delegate restart detection to a class like:

- `UnexpectedRestartHeuristic`

Flow:

1. normalizer reads raw runtime payload
2. heuristic evaluates restart candidates with deploy grace window
3. normalizer persists/updates `operational_issue` when needed

## 5. Query-Time Heuristics

For read-time heuristics, use simple service-level functions first (for example in context/log analysis services).

No shared engine is required until multiple services need the same rule execution model.

## 6. When To Introduce More Architecture

Only evolve to a generic heuristics layer if at least one is true:

1. 3+ heuristics are duplicated across modules
2. same heuristic must run both in normalization and query paths with identical contract
3. lifecycle/versioning of heuristics becomes operationally necessary

Until then, keep rules local and readable.

## 7. Minimal Acceptance Criteria

For each new heuristic in MVP:

1. Add/update unit tests for positive and negative cases.
2. Keep logic in a local class/function near the normalizer/service.
3. Preserve idempotent persistence behavior in the normalizer.
4. Expose enough evidence fields for operators to understand why the signal was emitted.
