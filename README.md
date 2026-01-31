# Memoire

Memoire is a small full-stack app that combines:
- A web UI (Vite + React)
- An auth/core API service (FastAPI)
- A memory/chat service (FastAPI)

This repo is organized as a monorepo under `apps/`.

## Repo Structure

- `apps/web/` - Frontend (Vite + React + Tailwind v4)
- `apps/services/auth/` - Core/auth API (FastAPI)
- `apps/services/memory/` - Memory + chat API (FastAPI)
- `apps/services/schemas/` - SQL schema + seed scripts

## Requirements

- Node.js 18+ (for the frontend)
- Python 3.11+ (for the API services)
- A Postgres database (for auth + memory)

## Quick Start (Local Dev)

### 1) Setup Python environment

From the repo root:

```bash
python -m venv venv
.\venv\Scripts\activate
```

Install dependencies for each service:

```bash
pip install -r apps/services/auth/requirements.txt
pip install -r apps/services/memory/requirements.txt
```

### 2) Configure environment

Create a `.env` file in each service folder if required:

- `apps/services/auth/.env`
- `apps/services/memory/.env`

Common variables:

- `DATABASE_URL`
- `JWT_SECRET`
- `JWT_ALG` (optional, default: HS256)
- `OPENAI_API_KEY` (for chat, if using OpenAI)
- `GROQ_API_KEY` (for chat, if using Groq)
- `OPENAI_CHAT_MODEL` (optional)
- `GROQ_CHAT_MODEL` (optional)

### 3) Start backend services

Auth service (port 8001):

```bash
cd apps/services
python -m uvicorn auth.main:app --reload --port 8001
```

Memory service (port 8000):

```bash
cd apps/services/memory
python -m uvicorn app.main:app --reload --port 8000
```

### 4) Start frontend

```bash
cd apps/web
npm install
npm run dev
```

Frontend runs at:
- `http://localhost:5173`

## API Overview

Auth service (port 8001):
- `GET /health`
- `POST /auth/signup`
- `POST /auth/login`
- `GET /me` (requires Bearer token)
- `GET /spaces` (requires Bearer token)

Memory service (port 8000):
- `GET /health`
- `POST /chats` (requires Bearer token)
- `POST /search` (requires Bearer token)
- `POST /notes` (requires Bearer token)

## Notes

- The frontend proxies:
  - `/api/*` -> `http://localhost:8000`
  - `/chat-api/*` -> `http://localhost:8001`
- If you see 403 on `/spaces`, you are not logged in yet.
- If you see 404 on `/api/spaces`, check Vite proxy rewrite.

## Troubleshooting

### Common issues

- **Vite cannot resolve imports**: check the file path or rename the import.
- **403 on `/spaces`**: add a Bearer token (login required).
- **404 on `/api/spaces`**: ensure Vite rewrites `/api` to the backend.
- **500 from chat**: verify `OPENAI_API_KEY` or `GROQ_API_KEY` is set.

## Scripts

Frontend:
- `npm run dev` - Start dev server
- `npm run build` - Production build
- `npm run preview` - Preview build

## License

MIT (or update this section if you use a different license)
