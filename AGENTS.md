# AGENTS.md

## Cursor Cloud specific instructions

### Project Overview

Memoire is a full-stack knowledge management app. See `README.md` for structure and standard dev commands.

### Services

| Service | Port | Start Command (from repo root) |
|---------|------|-------------------------------|
| PostgreSQL | 5433 | `docker compose up -d db` |
| Auth API | 8001 | `cd apps/services && python -m uvicorn auth.main:app --reload --port 8001` |
| Memory API | 8000 | `cd apps/services/memory && python -m uvicorn app.main:app --reload --port 8000` |
| Frontend | 5173 | `cd apps/web && npm run dev` |
| Worker | N/A | `python -m apps.worker.worker` (optional, for document ingestion) |

### Non-obvious caveats

- **Docker daemon must be started manually** before `docker compose up`: run `sudo dockerd &>/tmp/dockerd.log &` and wait ~5s.
- **Docker socket permissions**: run `sudo chmod 666 /var/run/docker.sock` after starting dockerd.
- **SQL schemas must be applied manually** after the DB container starts (in order): `schema.sql` → `2_schema.sql` → `3_age_grounding.sql` from `apps/services/schemas/`. Use `docker compose exec -T db psql -U memoire -d memoire -f /dev/stdin < <schema_file>`.
- **Memory service requires `OPENAI_API_KEY` and `GROQ_API_KEY` at startup** — their client objects are instantiated at module import time. Use placeholder values (e.g. `sk-placeholder`) to start the service without real keys; actual embedding/chat features won't work without valid keys.
- **The `groq` Python package is not listed in any `requirements.txt`** but is needed by the memory service. Install it alongside other deps: `pip install groq`.
- **Auth service uses `psycopg` (v3)** driver (`postgresql+psycopg://`), while memory service uses `psycopg2-binary` (`postgresql+psycopg2://`). The `DATABASE_URL` scheme must match each service's driver.
- **Environment variables must be exported in the shell** before starting uvicorn with `--reload`; `.env` files in subdirectories are not reliably picked up by the reloader subprocess.
- **Lint**: `cd apps/web && npm run lint` (ESLint). No Python linter is configured.
- **Build**: `cd apps/web && npm run build`.
