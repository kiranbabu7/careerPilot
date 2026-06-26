# CareerPilot Development Guide

## Environment Setup

1. Copy environment template: `cp .env.example .env`
2. Adjust values as needed (PostgreSQL credentials, `DJANGO_SECRET_KEY`, optional `GOOGLE_OAUTH_CLIENT_ID`)

## Docker (recommended)

```bash
docker compose up --build
```

Services:
- PostgreSQL: `localhost:5432`
- Backend API: `http://localhost:8000/api/v1`
- Frontend: `http://localhost:3000`

Source code is bind-mounted into the backend and frontend containers so edits on your host auto-reload inside Docker. After changing dependencies (`requirements.txt` or `package.json`), rebuild:

```bash
docker compose up --build
```

For frontend-only dependency changes:

```bash
docker compose build frontend
docker compose up frontend
```

## Local Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -r requirements.txt
export POSTGRES_HOST=localhost  # or set in .env
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

## Verification Checklist

- [ ] `GET /api/v1/health/` returns `status: ok`
- [ ] Register at `/login` creates account and stores JWT
- [ ] `GET /api/v1/auth/me/` returns user when authenticated
- [ ] Protected routes redirect unauthenticated users to login
- [ ] Workspace shell loads with conversation + activity panels
- [ ] `pytest` passes in `backend/`
- [ ] `npm run lint` and `npm run typecheck` pass in `frontend/`

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
4. Start a workflow from the workspace or home page to trigger job search.

Actor input for LinkedIn uses `keywords`, `location`, and `maxItems`. Add other boards later with comma-separated `source:actorId` entries.

## Architecture Notes

- DRF views delegate to `services.py`; persistence in `repositories.py`
- External integrations live under `apps/providers/`
- Job discovery: `ApifyJobsProvider` + `TavilyCompanyResearchProvider` under `apps/providers/jobs/`
