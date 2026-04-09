# Staging Secrets Setup

This repository supports a dedicated `staging` GitHub Environment for secure pipeline execution.

## Where to configure

1. Open GitHub repository settings.
2. Go to `Settings -> Environments -> staging`.
3. Add secrets and variables below.

## Required environment secrets

- `STAGING_DATABASE_URL`
  - Example format:
  - `postgresql://<user>:<password>@<host>/<database>?sslmode=require`
- `STAGING_MCP_API_TOKEN`
  - Random token used by MCP auth guardrail.

## Optional environment secret

- `STAGING_GITHUB_TOKEN`
  - Needed only if staging sync uses authenticated GitHub API requests.

## Optional environment variables

- `STAGING_GITHUB_OWNER`
- `STAGING_GITHUB_REPOS`
  - Comma-separated values, for example:
  - `claston/micro-cardservice`

## Render deploy secrets (for CD | Deploy to Render (Staging))

- `RENDER_API_KEY`
- `RENDER_STAGING_SERVICE_ID`

## Render deploy toggle (recommended while setup is incomplete)

- `RENDER_DEPLOY_ENABLED` (Environment variable in `staging`)
  - Set to `false` while GHCR image/Render service is not ready.
  - Set to `true` only when you want `deploy-render-staging.yml` to run.

`deploy-render-staging.yml` uses these secrets to call Render API and trigger a deploy for the staging service.
If `RENDER_DEPLOY_ENABLED` is not set to a truthy value (`true`, `1`, `yes`, `on`), the workflow exits with a notice and does not call Render.

## Local env file strategy

Keep local credentials out of git:

- `.env.local` for local PostgreSQL
- `.env.staging` for remote staging database

Only one `DATABASE_URL` should be active when running commands.

## Workflow

`deploy-staging.yml` (`Staging | Environment Validation`) uses:

- `environment: staging`
- `${{ secrets.STAGING_DATABASE_URL }}`
- `${{ secrets.STAGING_MCP_API_TOKEN }}`

Pipeline steps include migration validation and MCP smoke checks before considering staging healthy.
