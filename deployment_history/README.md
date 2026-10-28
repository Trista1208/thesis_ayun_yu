# Deployment history

**Record only.** These files are not the deployment to review. The live deployment is Vercel, configured by `vercel.json` and `api/index.py` at the repository root.

The files here record the earlier Railway and Fly.io attempts described in the thesis. They are no longer used by any live deployment.

| File | Period | Use |
|---|---|---|
| `Procfile` | March 2026 | Started the Streamlit prototype (`frontend/app.py`) on Railway |
| `railway.toml` | March to June 2026 | Railway build and health-check settings |
| `Dockerfile` | June 2026 | Single-container build of the React application and FastAPI service, tried on Railway |
| `fly.toml` | June 2026 | Fly.io configuration generated during a trial launch; not taken further |

Railway and Fly.io read these files from the repository root, so they must be moved back
there to be used again. The container can still be built locally from the repository root:

```bash
docker build -f deployment_history/Dockerfile -t ayun .
docker run -p 8000:8000 --env-file .env ayun
```
