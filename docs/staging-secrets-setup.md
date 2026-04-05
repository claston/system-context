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

## Render deploy secrets (for deploy-render-staging workflow)

- `RENDER_API_KEY`
- `RENDER_STAGING_SERVICE_ID`

`deploy-render-staging.yml` uses these secrets to call Render API and trigger a deploy for the staging service.

## Local env file strategy

Keep local credentials out of git:

- `.env.local` for local PostgreSQL
- `.env.staging` for remote staging database

Only one `DATABASE_URL` should be active when running commands.

## Workflow

`deploy-staging.yml` uses:

- `environment: staging`
- `${{ secrets.STAGING_DATABASE_URL }}`
- `${{ secrets.STAGING_MCP_API_TOKEN }}`

Pipeline steps include migration validation and MCP smoke checks before considering staging healthy.
