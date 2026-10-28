"""
Vercel serverless entry — re-exports the FastAPI app from api.main.

Railway/Docker use: uvicorn api.main:app
Vercel uses this file as the Python function handler.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.main import app  # noqa: F401
