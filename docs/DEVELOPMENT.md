# CareerPilot Development Guide

## Environment Setup

1. Copy environment template: `cp .env.example .env`
2. Adjust values as needed (PostgreSQL credentials, `DJANGO_SECRET_KEY`, optional API keys)
3. For production-like runs, set `DJANGO_DEBUG=false` and use a secure `DJANGO_SECRET_KEY` (see [Production settings](#production-settings))

## Docker (recommended)

Start the full stack (database, Redis, backend, Celery worker, Celery beat, frontend):

```bash
docker compose up --build
```

| Service | Purpose |
|---------|---------|
| `db` | PostgreSQL 16 |
| `redis` | Celery broker and result backend |
| `backend` | Django API (`runserver` in dev compose) |
| `celery-worker` | Background workflow execution |
| `celery-beat` | Scheduled job search dispatcher |
| `frontend` | Next.js dev server |

Endpoints:

- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- Backend API: `http://localhost:8000/api/v1`
- Frontend: `http://localhost:3000`

Source code is bind-mounted into backend and frontend containers so edits auto-reload. **Exception:** the Celery worker does not auto-reload — run `docker compose restart celery-worker` after backend Python changes. After changing dependencies (`requirements.txt` or `package.json`), rebuild:

```bash
docker compose up --build
```

Frontend-only dependency changes:

```bash
docker compose build frontend
docker compose up frontend
```

Run a single service:

```bash
docker compose up celery-worker
docker compose logs -f celery-beat
```

Stop and remove containers:

```bash
docker compose down
```

### Production Docker notes

The repo ships production-ready Dockerfiles; the default `docker-compose.yml` targets **local development** (Django `runserver`, Next.js dev server). Use `docker-compose.prod.yml` for EC2 or other server deployments.

Production compose services:

| Service | Purpose |
|---------|---------|
| `caddy` | Public reverse proxy and automatic TLS on ports `80` / `443` |
| `frontend` | Next.js standalone production server, exposed only inside Compose on port `3000` |
| `backend` | Django + Gunicorn API, exposed only inside Compose on port `8000` |
| `celery-worker` | Background workflows, agent execution, scheduled job search |
| `celery-beat` | Scheduled job search polling |
| `db` | PostgreSQL 16 with `postgres_data` volume |
| `redis` | Celery broker/result backend |

For production deployments:

- **Caddy** (`Caddyfile`): routes `CADDY_APP_DOMAIN` to `frontend:3000` and `CADDY_API_DOMAIN` to `backend:8000`. Only ports `80` and `443` should be public.
- **Backend** (`backend/Dockerfile`): production compose runs migrations, `collectstatic`, then Gunicorn with two workers.
- **Frontend** (`frontend/Dockerfile`): build with `target: production`. Pass build args `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_GOOGLE_CLIENT_ID`. The image uses Next.js `standalone` output (`node server.js`).
- Set `DJANGO_DEBUG=false`, secure `DJANGO_SECRET_KEY`, and explicit `DJANGO_ALLOWED_HOSTS` / `DJANGO_CORS_ALLOWED_ORIGINS`.
- Ensure exactly **one** `celery-beat` instance per deployment.

Amazon Linux 2023 quick deploy:

```bash
sudo dnf update -y
sudo dnf install -y git docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
newgrp docker

git clone <repo-url> /opt/careerpilot
cd /opt/careerpilot
cp .env.example .env
```

Set production values in `.env`:

```env
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_ALLOWED_HOSTS=api.example.com,localhost,127.0.0.1,backend
DJANGO_CORS_ALLOWED_ORIGINS=https://app.example.com
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SECURE_HSTS_SECONDS=31536000

CADDY_APP_DOMAIN=app.example.com
CADDY_API_DOMAIN=api.example.com
# Optional. Leave blank if you do not want to provide a Let's Encrypt contact email.
CADDY_EMAIL=

NEXT_PUBLIC_API_URL=https://api.example.com/api/v1
GOOGLE_OAUTH_CLIENT_ID=<google-web-client-id>
NEXT_PUBLIC_GOOGLE_CLIENT_ID=<same-google-web-client-id>
```

Start production:

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
curl -f https://api.example.com/api/v1/health/ready/
```

### Updating production (after `git pull`)

**`git pull` and `docker compose restart` do not deploy new code.** Production images bake application source at **build time**. Unlike local dev (`docker-compose.yml`), production has **no bind mounts** for `backend/` or `frontend/` — containers keep running the code that was copied into the image when it was last built.

| Action | Updates running app? |
|--------|----------------------|
| `git pull` only | No — updates files on the host, not inside containers |
| `docker compose restart` | No — restarts containers from the **same** image |
| `docker compose up -d` (no `--build`) | No — reuses existing images unless you rebuilt separately |
| `docker compose up -d --build` | **Yes** — rebuilds changed layers and recreates containers |

**Recommended deploy on EC2** (from `/opt/careerpilot` or your clone path):

```bash
cd /opt/careerpilot
git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build backend celery-worker celery-beat frontend
docker compose -f docker-compose.prod.yml ps
curl -fsS https://api.example.com/api/v1/health/ready/
```

Or use the helper script (same steps, optional health check):

```bash
chmod +x scripts/deploy-prod.sh   # once
./scripts/deploy-prod.sh
```

**When to rebuild what**

| Change | Command |
|--------|---------|
| Backend Python (`backend/`) | `up -d --build backend celery-worker celery-beat` |
| Frontend (`frontend/`) | `up -d --build frontend` |
| Both | `up -d --build backend celery-worker celery-beat frontend` |
| `requirements.txt` | Rebuild backend services (`--build backend celery-worker celery-beat`) |
| `package.json` / lockfile | Rebuild frontend (`--build frontend`) |
| `NEXT_PUBLIC_*` in `.env` | `build --no-cache frontend` then `up -d frontend` (values are baked at build time) |
| `Caddyfile` only | `docker compose -f docker-compose.prod.yml restart caddy` |
| Database schema (migrations) | Included automatically — backend entrypoint runs `migrate` on start |

**Verify you are on the expected branch/commit before deploying:**

```bash
git branch --show-current
git log -1 --oneline
```

**Do not use** `docker compose restart` as a deploy step for application code. It is only appropriate for infra-only changes (e.g. reloading Caddy after editing `Caddyfile`).

Security group guidance for EC2:

- Allow `22` only from your IP.
- Allow `80` and `443` from the internet.
- Do not expose `3000`, `8000`, `5432`, or `6379`; those are internal to Docker Compose.

When `NEXT_PUBLIC_*` values change, rebuild the frontend image without cache:

```bash
docker compose -f docker-compose.prod.yml build --no-cache frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

Or: `./scripts/deploy-prod.sh --no-cache-frontend`

### S3 media storage (production)

Uploaded resume files (`Resume.file`) use **local `./media`** in development. For production, enable S3:

```env
USE_S3_STORAGE=true
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_REGION_NAME=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

Optional: `AWS_S3_CUSTOM_DOMAIN` (CloudFront), `AWS_S3_ENDPOINT_URL` (MinIO), `AWS_S3_MEDIA_PREFIX=media`.

**Bucket policy:** Block public access; django-storages serves private objects via signed URLs (`querystring_auth=True`). IAM user or task role needs `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on `arn:aws:s3:::your-bucket/media/*`.

When `USE_S3_STORAGE=true`, you do not need the `media_data` Docker volume on backend/celery services.

## Celery worker and beat

Workflow execution and scheduled job search depend on Celery. Docker Compose starts both processes automatically.

### Docker

```bash
# Worker + beat are started with docker compose up
docker compose logs -f celery-worker celery-beat
```

### Local (without Docker)

Requires Redis reachable at `CELERY_BROKER_URL` (default `redis://localhost:6379/0`):

```bash
cd backend
celery -A careerpilot worker --loglevel=info
# separate terminal:
celery -A careerpilot beat --loglevel=info
```

### Restarting Celery after backend changes

The Django `backend` service auto-reloads on code changes via bind mount + `runserver`. **Celery workers do not.** After editing backend Python (agents, tasks, scheduled search, workflow services), restart the worker:

```bash
docker compose restart celery-worker
```

Restart `celery-beat` only when changing Beat schedule configuration or the beat task module itself:

```bash
docker compose restart celery-beat
```

### Scheduled job search

Celery Beat runs `jobs.check_job_search_schedules` on a fixed interval (default every 5 minutes, controlled by `CELERY_BEAT_SCHEDULE_INTERVAL`). Before enqueueing, it calls `fail_stale_running_workflows()` globally. Each per-user run does the same check scoped to that user.

**Stale RUNNING workflows:** Workflows in `RUNNING` status for more than **120 minutes** (`DEFAULT_STALE_WORKFLOW_MINUTES` in `apps/workflows/repositories.py`) are marked `FAILED` with a timeout message. This prevents hung workflows from blocking scheduled search indefinitely.

**Enable a schedule (API):**

```bash
curl -X PATCH http://localhost:8000/api/v1/users/preferences/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"job_search_schedule_enabled": true, "job_search_schedule_interval_minutes": 60}'
```

Valid intervals: `60`, `240`, `720`, `1440` (minutes).

**Check status:**

```bash
curl http://localhost:8000/api/v1/opportunities/schedule-status/ \
  -H "Authorization: Bearer <token>"
```

Response includes `last_run_summary` (from `UserPreference.last_schedule_message`) — shown in Settings under **Last run**, including skip reasons like "Apify is not configured" or "A workflow is already running for this user."

**Pipeline:** Scheduled runs create a headless `WorkflowExecution` with `context.trigger = "scheduled"`, run job search with incremental `posted_since` (`last_job_search_at`, or `now - interval` on first run), then evaluate discoveries. On completion, a welcome chat message with action cards is seeded (same as manual workflows).

**Skip reasons:** `schedule_disabled`, `apify_not_configured`, `workflow_running`, `missing_preferences` (no target roles or career goals). Skipped runs still advance `next_scheduled_run_at` and record the reason in `last_schedule_message`.

**Evaluation scope:** `_evaluate_discovered_opportunities` only evaluates unevaluated opportunities linked to the current workflow. It excludes `source_agent = "custom_jd"` (pasted JDs and interview-prep synthetic opportunities). Opportunities from other workflows are never picked up.

**UI:** `jobDiscoveryCompletionMessage` in `frontend/src/lib/workflow-utils.ts` only shows "Found N high-match role(s)" when `discovered_count > 0`; zero-discovery runs show "Discovered 0 roles" or an evaluation summary instead.

### LangGraph workflow orchestration

All workflow intents run through a single **LangGraph** root graph (`apps/workflows/langgraph_runner.py`). The planner runs inside the graph (`planner_node` calls `PlannerAgent.plan()`), then routing branches by `workflow_intent`:

| Module | Responsibility |
|--------|----------------|
| `langgraph_runner.py` | Root graph compile + `LangGraphWorkflowRunner` |
| `langgraph_nodes.py` | Shared nodes: planner, tool_executor, replan, guided_finalize, pause, complete, fail |
| `langgraph_job_discovery.py` | Job discovery subgraph reference (tool loop + replan) |
| `langgraph_interview_prep.py` | Interview prep subgraph reference |
| `langgraph_guided.py` | Tailor / cover letter / application tracking subgraph reference |
| `langgraph_rerun.py` | Search rerun graph (`LangGraphRerunRunner`) |
| `langchain_tools.py` | LangChain `StructuredTool` wrappers around `WorkflowToolRegistry` |

**LLM providers:** OpenRouter calls use LangChain via `apps/providers/llm/openrouter_chat.py` (not direct `requests.post`).

**Troubleshooting:** After changing graph nodes or workflow services, restart the Celery worker (`make restart-celery` or `docker compose restart celery-worker`). `WorkflowExecution.result` remains the UI polling source of truth (not LangGraph checkpoints).

### Interview prep workflows

Interview prep goals (`classify_workflow_intent`) auto-run **planner → interview_prep** — no manual Applications step.

Scope is determined by `classify_interview_prep_scope` in `apps/workflows/intent.py`:

- **General / resume-based** — phrases like "general prep", "everything in my resume", or no company match → `_create_general_prep_opportunity` builds a synthetic job (`company="General interview prep"`, `source_agent="custom_jd"`).
- **Application-specific** — company name in goal, or phrases like "interview at …" → prefers interviewing applications, then saved opportunities.

General prep does **not** trigger web search for unknown companies; the synthetic opportunity has empty `company_research`. Application-specific prep uses the linked job's existing research when available.

The workspace shows `InterviewPlanDetail` inline when `interview_plan_id` is set (`workflow-mission-control.tsx`); the panel is dismissible and resets when the plan changes.

### Workspace chat interactivity

On workflow completion (manual or scheduled), `WorkflowService._seed_welcome_chat_message` creates an assistant message with contextual action cards from `build_contextual_actions`.

Chat routing lives in `apps/workflows/follow_up.py` (`classify_follow_up`) and `apps/workflows/chat_service.py`. Key intents:

| Intent | Example trigger |
|--------|-----------------|
| `list_applications` | "List my applications" |
| `generate_interview_prep` | "Generate interview prep" |
| `rerun_job_search` | "Rerun search", "find more jobs" |
| `tailor_resume` | "Tailor resume for best match" |
| `generate_cover_letter` | "Generate cover letter" |
| `show_borderline` / `show_rejected` | "Show borderline roles" |
| `research_company` | "Research top company" |
| `generate_decision` | "Generate decision recommendation" |
| `adjust_threshold` | "Lower match threshold" |
| `help` | "What can you do?", greetings |

The frontend derives quick-reply chips from the latest assistant message's actions (`deriveWorkflowQuickReplies` in `workflow-utils.ts`). Action cards require confirmation ("yes") before execution.

### Onboarding — flexible locations

The onboarding location step accepts work-style quick replies (Remote, Hybrid, etc.), typed cities, or both. Saving `remote_preference` and/or `target_locations` via `UserPreferenceRepository.update_preferences` sets `locations_configured=True`.

Profile completion treats locations as satisfied when `target_locations` is non-empty **or** `locations_configured` is true (`apps/memory/dashboard.py`), so Remote-only users can finish onboarding without listing cities.

### UI fixes

**Application stage dropdown:** `application-detail-panel.tsx` uses `NativeSelect` with `[color-scheme:dark]` for correct dark-theme rendering of native `<select>` elements.

## Local Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -r requirements-dev.txt
export POSTGRES_HOST=localhost  # or set in .env
export CELERY_BROKER_URL=redis://localhost:6379/0
python manage.py migrate
python manage.py runserver
```

## Local Frontend

```bash
cd frontend
npm install
cp ../.env.example .env.local
npm run dev
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` in `.env.local`.

For Docker bind mounts on Windows/macOS, the compose file sets `WATCHPACK_POLLING` and the frontend uses `dev:docker` (webpack polling) instead of Turbopack.

### Frontend Docker troubleshooting

**`non-standard NODE_ENV` warning:** Do not set `NODE_ENV` in `frontend/.env.local` to custom values (`dev`, `local`, etc.). Use `development`, `production`, or `test` only — or omit it (compose sets `NODE_ENV=development` for the dev container).

**`EACCES` on `/app/.next/...`:** The named volume `frontend_next_cache` can retain files from an old production build with wrong ownership. Reset it:

```bash
docker compose down
docker volume rm careerpilot_frontend_next_cache
docker compose build frontend
docker compose up frontend
```

The dev entrypoint clears an unwritable `.next` cache automatically on startup.


### Backend (Docker — recommended)

```bash
docker compose exec backend pytest
```

Run a single module:

```bash
docker compose exec backend pytest apps/jobs/tests/test_scheduled_search.py -v
docker compose exec backend pytest careerpilot/tests/test_phase9.py -v
```

### Backend (local)

```bash
cd backend
pytest
```

Uses `careerpilot.test_settings` when configured via `pytest.ini` / `conftest.py`.

### Frontend

```bash
cd frontend
npm run check       # typecheck + lint + vitest
npm run typecheck
npm run lint
npm run test
npm run build       # production build smoke test
```

### Root Makefile

```bash
make test           # backend pytest in Docker
make lint           # frontend eslint
make typecheck      # frontend tsc
make up             # docker compose up --build
```

## Health checks

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/health/live/` | Process is running (no dependency checks) |
| `GET /api/v1/health/ready/` | Database, Redis, and Celery broker connectivity |
| `GET /api/v1/health/` | Alias for readiness |

Docker healthchecks on `backend`, `redis`, and `celery-worker` use these probes.

## Production settings

When `DJANGO_DEBUG=false`:

- `DJANGO_SECRET_KEY` must not be the default `dev-insecure-change-me`
- `DJANGO_ALLOWED_HOSTS` must be non-empty
- Secure cookies and HSTS are enabled by default
- Optional: `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SECURE_HSTS_SECONDS`, `DJANGO_SECURE_HSTS_PRELOAD`

Observability:

- Structured JSON logging with request IDs (`careerpilot.middleware.RequestIdMiddleware`)
- Optional Sentry: set `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`

## Job discovery (LinkedIn-only Apify)

1. Create an Apify account and copy your API token into `APIFY_API_TOKEN`.
2. Add your LinkedIn Jobs scraper actor ID to `APIFY_JOB_ACTOR_IDS`:

```bash
# Recommended: explicit source prefix
APIFY_JOB_ACTOR_IDS=linkedin:your-actor-id-from-apify-console

# Or bare actor ID (defaults to LinkedIn)
APIFY_JOB_ACTOR_IDS=your-actor-id-from-apify-console
```

3. Optional: set `TAVILY_API_KEY` for company research snippets on discovered jobs.
   - Missing key → agent output `reason: not_configured`.
   - Invalid/expired key → `reason: auth_error` with Tavily error in `error` / `errors`.
   - Restart `backend` / `celery-worker` after changing `.env` so the key is loaded.
4. Start a workflow from the workspace or home page to trigger manual job search, or enable scheduled search in preferences.

Actor input for LinkedIn uses `keywords`, `location`, and `maxItems`. Add other boards later with comma-separated `source:actorId` entries.

## Verification Checklist

- [ ] `GET /api/v1/health/ready/` returns `status: ok` with database, redis, and celery_broker connected
- [ ] Production: `caddy`, `frontend`, `backend`, `celery-worker`, `celery-beat`, `db`, and `redis` are healthy in `docker compose -f docker-compose.prod.yml ps`
- [ ] Production: `https://api.<domain>/api/v1/health/ready/` succeeds through Caddy
- [ ] Production: only ports `80`, `443`, and restricted `22` are open in the EC2 security group
- [ ] Register at `/login` creates account and stores JWT
- [ ] `GET /api/v1/auth/me/` returns user when authenticated
- [ ] Protected routes redirect unauthenticated users to login
- [ ] Workspace shell loads with conversation + activity panels
- [ ] Completed workflow seeds welcome chat message with action cards
- [ ] Interview prep goal runs planner → interview_prep and shows inline plan panel
- [ ] Onboarding location step accepts Remote-only or typed cities (`locations_configured`)
- [ ] `docker compose exec backend pytest` passes
- [ ] `cd frontend && npm run check` passes
- [ ] Celery worker responds to `celery -A careerpilot inspect ping` (or worker healthcheck passes)
- [ ] After backend code changes, `docker compose restart celery-worker` picks up new task logic
- [ ] Scheduled search: enable 60-minute interval, confirm `next_scheduled_run_at` updates and beat logs enqueue tasks
- [ ] Settings shows `last_run_summary` after a scheduled run (including skip reasons)

## Architecture Notes

- DRF views delegate to `services.py`; persistence in `repositories.py`
- External integrations live under `apps/providers/`
- Job discovery: `ApifyJobsProvider` + `TavilyCompanyResearchProvider` under `apps/providers/jobs/`
- Background tasks: `apps/workflows/tasks.py`, `apps/jobs/tasks.py` via Celery
- Scheduled search: `apps/jobs/scheduled_search.py`
- Workflow chat: `apps/workflows/chat_service.py`, `apps/workflows/follow_up.py`
- Interview prep scope: `apps/workflows/intent.py` (`classify_interview_prep_scope`)
- Media storage: `careerpilot/storage.py` (`USE_S3_STORAGE` → django-storages S3 backend)
