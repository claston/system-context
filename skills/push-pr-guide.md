# Push and Pull Request Guide

## Goal

Use a standard flow to keep history clean and PRs easy to review.

## Branch naming

Use descriptive branch names, for example:
- `feat/repository-crud`
- `fix/service-validation`
- `docs/update-pr-template`
- `chore/ci-setup`

## Conventional Commit format

Pattern:

`<type>(<scope>): <short description>`

Examples:
- `feat(service): add service creation endpoint`
- `fix(db): handle missing DATABASE_URL`
- `docs(skills): add push and pr guide`
- `chore(ci): add lint workflow`

## Recommended local workflow

1. Sync main:
   - `git checkout main`
   - `git pull origin main`
2. Create a branch:
   - `git checkout -b feat/your-change`
3. Make your changes.
4. Stage files:
   - `git add .`
5. Commit with Conventional Commits:
   - `git commit -m "feat(scope): short message"`
6. Push branch:
   - `git push -u origin feat/your-change`
7. Open PR to `main`.

## Open PR with GitHub CLI

After pushing your branch:

`gh pr create --base main --head <your-branch> --title "feat(scope): short message" --body-file .github/pull_request_template.md`

## Before requesting review

- Run tests locally when available.
- Confirm migrations are included when schema changes.
- Update docs when behavior changes.
- Keep PR focused on one objective.
