# CareerPilot

AI-powered career workspace for job search, resume tailoring, interview prep, and application tracking.

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | Next.js 15, React 19, TypeScript, Tailwind CSS 4, shadcn/ui (Radix UI), Vitest |
| **Backend** | Django 5.1, Django REST Framework, PostgreSQL 16, Redis 7, Celery 5 (worker + beat), Gunicorn, JWT + Google OAuth |
| **Agentic AI** | LangGraph (workflow graphs), LangChain (`langchain-core`, `langchain-openai`), structured workflow tools |
| **LLM** | OpenRouter (OpenAI-compatible API; default model `google/gemini-2.5-flash`) |
| **External APIs** | Apify (job scrapers), Tavily (company research) |
| **Infrastructure** | Docker Compose, Caddy (TLS reverse proxy), EC2 deploy path, optional AWS S3 media (django-storages), optional Sentry |
| **Documents** | pypdf, python-docx, fpdf2 (resume parse + PDF/LaTeX export) |

**Agentic architecture:** Workflow intents (job discovery, interview prep, tailor, cover letter, application tracking, search rerun) compile to **LangGraph** `StateGraph` runners in `backend/apps/workflows/langgraph_*.py`. The planner runs as a graph node; routing branches by intent into subgraphs with tool-executor loops and replanning. LLM calls go through **LangChain** `ChatOpenAI` configured for OpenRouter (`apps/providers/llm/openrouter_chat.py`). Celery workers execute graphs asynchronously; `WorkflowExecution.result` remains the UI polling source of truth.

## Architecture

Monorepo: `frontend/` (Next.js app) and `backend/` (Django API, agents, Celery tasks).

```
Frontend → DRF Views → Services → Repositories → PostgreSQL
                              ↘ Agents / Providers → External APIs
                              ↘ Celery workers → Background workflows & scheduled search
```

Background work (workflow execution, scheduled job discovery) runs on **Celery workers** backed by **Redis**. **Celery Beat** polls user schedules every five minutes (configurable) and enqueues incremental job searches.

## Prerequisites

- Docker and Docker Compose
- Node.js 20+ (local frontend development)
- Python 3.12+ (local backend development)

## Quick Start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Services started:

| Service | URL / port |
|---------|------------|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000/api/v1 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |
| Celery worker | (no HTTP port) |
| Celery beat | (no HTTP port) |

Health checks:

- Liveness: http://localhost:8000/api/v1/health/live/
- Readiness (DB + Redis + Celery broker): http://localhost:8000/api/v1/health/ready/

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for local setup, production notes, and testing.

## Production Deployment

The production stack is defined in `docker-compose.prod.yml` and includes:

| Service | Purpose |
|---------|---------|
| `caddy` | Public TLS reverse proxy on ports 80/443 |
| `frontend` | Next.js standalone production server, internal port 3000 |
| `backend` | Django + Gunicorn API, internal port 8000 |
| `celery-worker` | Background workflows, agent runs, scheduled search |
| `celery-beat` | Scheduled job search dispatcher |
| `db` | PostgreSQL 16 |
| `redis` | Celery broker/result backend |

Minimal EC2/Amazon Linux flow:

```bash
sudo dnf update -y
sudo dnf install -y git docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
newgrp docker

git clone <repo-url> /opt/careerpilot
cd /opt/careerpilot
cp .env.example .env
# edit .env with production secrets and domains
docker compose -f docker-compose.prod.yml up -d --build
```

Set `CADDY_APP_DOMAIN`, `CADDY_API_DOMAIN`, `NEXT_PUBLIC_API_URL`, `DJANGO_ALLOWED_HOSTS`, and `DJANGO_CORS_ALLOWED_ORIGINS` in `.env` before building. See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#production-docker-notes) for the full production checklist.

**Deploying updates:** `git pull` and `docker compose restart` do **not** update production — images must be rebuilt. On the server:

```bash
cd /opt/careerpilot
git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build backend celery-worker celery-beat frontend
```

Or run `./scripts/deploy-prod.sh`. Details: [Updating production](docs/DEVELOPMENT.md#updating-production-after-git-pull).

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env
python manage.py migrate
python manage.py runserver
```

Run Celery locally (requires Redis):

```bash
celery -A careerpilot worker --loglevel=info
celery -A careerpilot beat --loglevel=info
```

After changing backend Python code in Docker, restart the worker — unlike Django `runserver`, Celery does not auto-reload:

```bash
docker compose restart celery-worker
```

### Frontend

```bash
cd frontend
npm install
cp ../.env.example .env.local
npm run dev
```

Ensure PostgreSQL and Redis are running (via Docker or locally) and `DATABASE_URL` / `POSTGRES_*` / `CELERY_*` vars are set.

### Google OAuth

1. Create an OAuth 2.0 Web client in [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Add authorized JavaScript origins: `http://localhost:3000`
3. Set the same client ID in both env vars:

```bash
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

If you only set `GOOGLE_OAUTH_CLIENT_ID`, Docker Compose copies it to the frontend automatically.

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

### Scheduled job search (Phase 9)

Users can enable recurring job discovery that runs the full search + evaluation pipeline on a preset interval. Configure via the preferences API (`PATCH /api/v1/users/preferences/`) or **Settings → Scheduled job search**.

| Interval preset | Minutes |
|-----------------|---------|
| Every 1 hour | 60 |
| Every 4 hours | 240 |
| Every 12 hours | 720 |
| Every 24 hours | 1440 |

**Requirements:**

- `celery-beat` and `celery-worker` services running (included in `docker compose up`)
- `APIFY_API_TOKEN` and `APIFY_JOB_ACTOR_IDS` configured
- User has target roles or career goals and an active resume

**How it works:** Celery Beat polls every `CELERY_BEAT_SCHEDULE_INTERVAL` minutes (default 5) and enqueues `jobs.run_scheduled_job_search` for due users. Each run creates a headless workflow with `context.trigger = "scheduled"`, searches with incremental `posted_since` filtering, then evaluates only new discoveries linked to that workflow.

**Incremental behavior:** Scheduled runs only ingest listings posted since `last_job_search_at`. On the first run, the cutoff is `now - interval`. LinkedIn searches also pass an `f_TPR` time filter when supported.

**Skip visibility:** When a run is skipped (Apify not configured, another workflow running, missing preferences, etc.), the reason is stored in `last_schedule_message` and surfaced in Settings as **Last run** summary via `GET /api/v1/opportunities/schedule-status/`.

**Stale workflows:** Workflows stuck in `RUNNING` for more than 120 minutes are auto-failed before scheduled search runs, so a hung workflow does not block future scheduled searches indefinitely.

**Evaluation scope:** Scheduled evaluation only processes unevaluated opportunities linked to the current workflow's job search. Opportunities from other workflows, pasted JDs (`custom_jd`), and interview-prep synthetic targets are excluded.

Check schedule status: `GET /api/v1/opportunities/schedule-status/`

### Interview prep workflows

Interview prep goals auto-run **planner → interview_prep** (no manual Applications step).

| Scope | How it is detected | Target |
|-------|-------------------|--------|
| General / resume-based | Phrases like "general prep", "everything in my resume" | Synthetic opportunity (`General interview prep`) built from preferences + goal |
| Application-specific | Company name in goal, or phrases like "interview at …" | Highest-priority active application, or saved opportunity |

General prep does not run web search for unknown companies — the synthetic job has no company research. Application-specific prep uses existing job data and any stored company research.

Completed prep workflows show the interview plan inline in the workspace (dismissible panel).

### Workspace chat

When a workflow completes (including scheduled search), the backend seeds a welcome assistant message with contextual **action cards**. The chat panel also offers **quick-reply chips** derived from those actions.

Supported follow-up intents include: list applications, interview prep, rerun search, tailor resume, cover letter, show borderline/rejected roles, research company, generate decision, adjust match threshold, update opportunity status, and help (`FOLLOW_UP_HELP`).

Type **"What can you do?"** or greet the assistant to see contextual next steps.

### Onboarding

Location preference is flexible: users can pick a work-style option (Remote, Hybrid, etc.), type cities, or both. Saving either `remote_preference` or `target_locations` sets `locations_configured`, so onboarding can complete without listing specific cities (e.g. Remote-only).

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
npm run check    # typecheck + lint + unit tests
```

Or individually:

```bash
npm run lint
npm run typecheck
npm run test
```

### Root Makefile

```bash
make up          # docker compose up --build
make test        # backend pytest in Docker (requires `docker compose up -d backend`)
make lint        # frontend eslint
make typecheck   # frontend tsc
```

## API Endpoints (selected)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health/live/` | Liveness probe |
| GET | `/api/v1/health/ready/` | Readiness (DB, Redis, Celery) |
| POST | `/api/v1/auth/register/` | User registration |
| POST | `/api/v1/auth/login/` | Email/password login |
| POST | `/api/v1/auth/google/` | Google OAuth login |
| POST | `/api/v1/auth/refresh/` | Refresh JWT |
| GET | `/api/v1/auth/me/` | Current user |
| GET/PATCH | `/api/v1/users/preferences/` | Career + schedule preferences |
| GET | `/api/v1/opportunities/schedule-status/` | Scheduled search status + last run summary |
| GET/POST | `/api/v1/workflows/` | Workflow execution |
| GET/POST | `/api/v1/workflows/{id}/messages/` | Workflow chat messages |
| GET | `/api/v1/opportunities/` | Discovered opportunities |

## Phase Scope

| Phase | Status | Features |
|-------|--------|----------|
| 1 | Done | Project setup, auth, database models, workspace UI shell |
| 2 | Done | Resume upload/analysis, preferences, dashboard |
| 3 | Done | Profile enrichment, LangGraph workflow orchestration, agent planner |
| 4 | Done | Apify job discovery, Tavily enrichment, opportunities UI |
| 5 | Done | Job evaluation, company research, workflow integration |
| 6 | Done | Resume tailoring, cover letters, application materials, PDF/LaTeX export |
| 7 | Done | Application board, interview prep |
| 8 | Done | Agent run inspection, workflow timeline, decision recommendations |
| 9 | Done | Celery/Redis workers, scheduled job search, production hardening, observability |

**Not yet implemented:** Cloud provisioning (AWS/K8s), Greenhouse/Lever direct integrations, push/email notifications.

## Project Structure

```
CareerPilot/
├── backend/
│   ├── apps/
│   │   ├── users/
│   │   ├── workflows/
│   │   ├── agents/
│   │   ├── jobs/
│   │   ├── applications/
│   │   ├── resumes/
│   │   ├── providers/
│   │   ├── memory/
│   │   └── prompts/
│   └── careerpilot/
├── frontend/
│   └── src/
├── docs/
│   └── DEVELOPMENT.md
├── docker-compose.yml
├── Makefile
└── .env.example
```

## License

Proprietary — all rights reserved.
