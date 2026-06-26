# CareerPilot

AI-powered career workspace for job search, resume tailoring, interview prep, and application tracking.

## Architecture

Monorepo with:

- `frontend/` — Next.js 15, TypeScript, Tailwind, shadcn/ui
- `backend/` — Django, DRF, PostgreSQL, JWT + Google OAuth

```
Frontend → DRF Views → Services → Repositories → PostgreSQL
                              ↘ Providers → External APIs
```

## Prerequisites

- Docker and Docker Compose
- Node.js 20+ (local frontend development)
- Python 3.12+ (local backend development)

## Quick Start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api/v1
- Health check: http://localhost:8000/api/v1/health/

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env
python manage.py migrate
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
cp ../.env.example ../.env.local
npm run dev
```

Ensure PostgreSQL is running (via Docker or locally) and `DATABASE_URL` / `POSTGRES_*` vars are set.

### Google OAuth

1. Create an OAuth 2.0 Web client in [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Add authorized JavaScript origins: `http://localhost:3000`
3. Set the same client ID in both env vars:

```bash
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

If you only set `GOOGLE_OAUTH_CLIENT_ID`, Docker Compose will copy it to the frontend automatically.

Restart the frontend after changing `NEXT_PUBLIC_GOOGLE_CLIENT_ID`.

### Resume AI analysis

Resume analysis calls **Google Gemini 2.5 Flash** (`google/gemini-2.5-flash`) through [OpenRouter](https://openrouter.ai/). The model is hardcoded in `backend/apps/resumes/providers.py` and is not configurable via environment variables.

Set these in `.env` (see `.env.example`):

```bash
OPENAI_API_KEY=your-openrouter-api-key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

`OPENAI_API_KEY` holds your OpenRouter API key (OpenRouter uses an OpenAI-compatible API). If the key or base URL is missing, or the API call fails, analysis falls back to a local deterministic heuristic.

### Job discovery (Apify + Tavily)

Job search runs configured [Apify](https://apify.com/) actors and optionally enriches companies with [Tavily](https://tavily.com/). Set these in `.env` (see `.env.example`):

```bash
APIFY_API_TOKEN=your-apify-api-token
# LinkedIn-only: paste the actor ID from Apify Console, or prefix with linkedin:
APIFY_JOB_ACTOR_IDS=linkedin:your-linkedin-actor-id
APIFY_DEFAULT_DATASET_LIMIT=50
TAVILY_API_KEY=your-tavily-api-key
JOB_SEARCH_MAX_RESULTS=30
```

**LinkedIn-only setup:** If you have only a LinkedIn Jobs scraper actor, set `APIFY_JOB_ACTOR_IDS` to either:

- `your-actor-id` — bare Apify actor ID (treated as LinkedIn), or
- `linkedin:your-actor-id` — explicit source prefix (recommended), or
- `username~linkedin-jobs-scraper` — Apify username/actor-name format (source inferred from name).

The provider sends LinkedIn actors `keywords`, `location`, and `maxItems` (plus `searchQuery` when supported). Naukri, Foundit, Indeed, and Google actors can be added later as comma-separated entries, e.g. `linkedin:actor1,indeed:actor2`.

## Testing & Quality

### Backend

```bash
docker compose exec backend pytest
```

Local (without Docker):

```bash
cd backend
pytest
```

### Frontend

```bash
cd frontend
npm run lint
npm run typecheck
```

## API Endpoints (Phase 1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health/` | Service health |
| POST | `/api/v1/auth/register/` | User registration |
| POST | `/api/v1/auth/login/` | Email/password login |
| POST | `/api/v1/auth/google/` | Google OAuth login |
| POST | `/api/v1/auth/refresh/` | Refresh JWT |
| GET | `/api/v1/auth/me/` | Current user |

## Phase Scope

| Phase | Status | Features |
|-------|--------|----------|
| 1 | Done | Project setup, auth, database models, workspace UI shell |
| 2 | Done | Resume upload/analysis, preferences, dashboard |
| 3 | Done | Profile enrichment, workflow planner |
| 4 | Done | Apify job discovery, Tavily enrichment, opportunities UI |

**Not yet implemented:** LangGraph agents, Celery, Greenhouse/Lever direct integrations, application tracking automation.

## Project Structure

```
CareerPilot/
├── backend/
│   ├── apps/
│   │   ├── users/
│   │   ├── workflows/
│   │   ├── agents/
│   │   ├── providers/
│   │   ├── memory/
│   │   └── prompts/
│   └── careerpilot/
├── frontend/
│   └── src/
├── docker-compose.yml
└── .env.example
```

## License

Proprietary — all rights reserved.
