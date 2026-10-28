# Deployment

The application is deployed on Vercel at [https://ayun-full.vercel.app](https://ayun-full.vercel.app)
for testing. The React application is built as a static site and
the FastAPI service runs as a Python serverless function on the same origin, so no
cross-origin configuration is needed. Configuration: `vercel.json` and `api/index.py`.

Earlier deployments of the Streamlit prototype on Railway, and a trial on Fly.io, are
documented in [`deployment_history/`](../deployment_history/README.md) (Section 4).

## 1. Environment variables

`.env.example` lists all variables. The ones relevant to a deployment are:

| Variable | Required | Purpose |
|---|---|---|
| `EXPERT_PASSWORD` | Yes | Password for the expert (clinician) area |
| `SESSION_SECRET` | Recommended | Key for signing session tokens (defaults to `EXPERT_PASSWORD`) |
| `APP_BASE_URL` | Recommended | Public URL, `https://ayun-full.vercel.app`. Google sign-in also needs that origin and `https://ayun-full.vercel.app/login` in the Google Cloud client |
| `GEMINI_API_KEY` | For LLM features | Hosted model for Ask Joule; locally `OLLAMA_HOST` can be used instead |
| `SUPABASE_URL`, `SUPABASE_SECRET_KEY` | Recommended | Persistent Postgres storage (see below) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Optional | Google sign-in for members |
| `ELEVENLABS_API_KEY` | Optional | Server-side voice for Talk mode |
| `AYUN_DATA_DIR` | Optional | Overrides the JSON data directory |

Secrets are provided through the hosting platform's environment settings and are never
committed.

## 2. Persistence

Without Supabase, accounts, assessments, tickets and memory are stored as JSON files under
`backend/data/` (or `/tmp/ayun-data` on Vercel). Container and serverless file systems are
ephemeral, so this data is lost on redeploy. On first start the stores are seeded with the
fictional demo cases from `database/demo/`.

For persistent storage, create a Supabase project, run the migrations in
`database/migrations/` in numerical order, and set `SUPABASE_URL` and
`SUPABASE_SECRET_KEY`. See [`database/README.md`](../database/README.md).

## 3. Vercel

Import the repository with the root directory set to `.` and the framework preset set to
*Other*, so that `vercel.json` controls the build. `vercel.json` builds `web/` into
`web/dist`, bundles `backend/`, `knowledge/` and `database/demo/` with the function in
`api/index.py`, and rewrites `/api/*` to that function. Python 3.12 is selected by
`.python-version`. Because serverless instances do not share a file system, Supabase is
required for tickets and memory to persist.

## 4. Earlier deployments

The Streamlit prototype (`frontend/app.py`) was first deployed on Railway using the
`Procfile`. A single-container build of the React application and API (`Dockerfile`,
`railway.toml`) and a Fly.io launch (`fly.toml`) were tried before the move to Vercel.
These files are kept in `deployment_history/` as a record. The Streamlit console can still
be run locally with `streamlit run frontend/app.py`, using `.streamlit/secrets.toml.example`
as a template for secrets.

## 5. Verification

| Request | Expected |
|---|---|
| `GET /` | React application |
| `GET /api/health` | `{"status": "ok", ...}`, including whether AI and persistent storage are configured |
| `GET /docs` | OpenAPI documentation |
