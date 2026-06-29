# CareerPilot Frontend

Next.js 15 application for the CareerPilot career workspace. Talks to the Django API at `NEXT_PUBLIC_API_URL`.

## Stack

- **Next.js 15** (App Router, `standalone` output for production Docker)
- **React 19**, **TypeScript**
- **Tailwind CSS 4**, **shadcn/ui** (Radix primitives)
- **Vitest** for unit tests

## Getting Started

### Local

```bash
npm install
cp ../.env.example .env.local
npm run dev
```

Open http://localhost:3000. Set `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` in `.env.local`.

### Docker

The root `docker-compose.yml` runs the frontend with `npm run dev:docker` (webpack + file polling for bind mounts on Windows/macOS). Environment variables come from the repo `.env` file.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Dev server with Turbopack (local only) |
| `npm run dev:docker` | Dev server for Docker bind mounts |
| `npm run build` | Production build |
| `npm run start` | Serve production build |
| `npm run check` | `typecheck` + `lint` + `test` |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint |
| `npm run test` | Vitest unit tests |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API base URL (e.g. `http://localhost:8000/api/v1`) |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | For Google login | OAuth Web client ID (must match backend `GOOGLE_OAUTH_CLIENT_ID`) |

Server-side secrets (API keys, Celery, Sentry) live in the backend `.env` only — never prefix them with `NEXT_PUBLIC_`.

## Project Layout

```
src/
├── app/                    # App Router pages
│   ├── page.tsx            # Dashboard / home
│   ├── workspace/          # Workflow mission control + chat
│   ├── opportunities/      # Discovered jobs
│   ├── applications/       # Application board
│   ├── resume/             # Resume upload and analysis
│   ├── settings/           # Career preferences
│   ├── companies/          # Company research
│   ├── interviews/         # Interview prep plans
│   └── agent-runs/         # Agent execution history
├── components/             # UI by domain (workflows, opportunities, etc.)
├── contexts/               # Auth context
├── hooks/                  # e.g. workflow polling
└── lib/
    ├── api.ts              # Typed API client
    ├── config.ts           # Env-derived constants
    └── workflow-utils.ts   # Workflow helpers
```

## API Client

`src/lib/api.ts` centralizes fetch calls with JWT handling. Types such as `UserPreferences` include scheduled search fields (`job_search_schedule_enabled`, `job_search_schedule_interval_minutes`, run timestamps). Extend this file when adding new backend endpoints.

## Auth

JWT tokens are stored in `localStorage` under `careerpilot_auth` (`AUTH_STORAGE_KEY`). `ProtectedRoute` wraps authenticated pages. Google Sign-In uses `NEXT_PUBLIC_GOOGLE_CLIENT_ID` via `@/components/auth/google-sign-in-button`.

## Production Build

```bash
npm run build
npm run start
```

The multi-stage `Dockerfile` builds with `target: production`, producing a minimal `standalone` image. Build args `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_GOOGLE_CLIENT_ID` must be set at image build time.

## Testing

```bash
npm run check
```

Test files live next to source (e.g. `workflow-chat-utils.test.ts`, `api.test.ts`). Config: `vitest.config.ts`.
