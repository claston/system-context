# AGENTS.md

## Working Agreement

This document defines the default execution rules for this repository.

## Branching Rules

1. Always update local `main` from `origin/main` before starting a new task.
2. Always create a new branch for any code or documentation change.
3. Branches should be focused on one objective.

## Development Rules

1. Prefer TDD for implementation work:
   - write or update tests first
   - run tests and confirm failure when appropriate
   - implement the change
   - run tests again and confirm success
2. Keep refactors incremental and verifiable.
3. Use Conventional Commits for every commit.
4. Always run Python tooling through the project virtual environment (`venv\Scripts\python.exe`) instead of global Python.
   - Examples:
     - `venv\Scripts\python.exe -m pytest -q`
     - `venv\Scripts\python.exe -m pip install -r requirements.txt`

## Validation Rules

1. Always run the full test suite before finalizing work.
2. Always run lint checks when configured in the project.
3. For API changes, always run the application and validate endpoints with real HTTP calls.
4. Always validate DB migration state before finalizing work:
   - run `venv\Scripts\python.exe scripts/validate_environment.py`
   - confirm Alembic current revision equals head
   - confirm required schema tables exist

Minimum API validation:
- one create request
- one list request
- one get-by-id request
- one negative-path request when relevant (for example, fake id or duplicate name)

## Delivery Rules

1. Push the branch after tests pass.
2. Open a Pull Request with:
   - concise summary
   - test evidence
   - risk/rollback note
3. Do not merge directly into `main`.
