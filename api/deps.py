"""Shared path setup so API routes can import the backend package."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def load_env() -> None:
    env_path = _ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip()
            if not key:
                continue
            # Fill blanks from .env so adding ELEVENLABS_API_KEY later is picked up
            # on reload, instead of keeping an empty value from the first start.
            if not (os.environ.get(key) or "").strip():
                os.environ[key] = val
