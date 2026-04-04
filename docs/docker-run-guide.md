# Docker Run Guide

## Build image

```bash
docker build -t system-context:local .
```

## Run container

```bash
docker run --rm -p 8000:8000 \
  -e DATABASE_URL="postgresql://<user>:<password>@<host>/<db>?sslmode=require" \
  -e MCP_API_TOKEN="<token>" \
  system-context:local
```

The container startup command runs migrations first:

- `alembic upgrade head`
- `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`

## Health check

```bash
curl http://127.0.0.1:8000/health
```
