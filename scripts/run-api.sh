#!/usr/bin/env bash
# Start FastAPI backend on port 8000
cd "$(dirname "$0")/.."
source venv/bin/activate 2>/dev/null || true
exec uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
