"""Stateless signed session tokens — works on Vercel/serverless (no shared memory)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

_TTL_SECONDS = 7 * 86400


def _secret() -> str:
    for key in ("SESSION_SECRET", "EXPERT_PASSWORD", "GITHUB_TOKEN"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return "ayun-dev-insecure-change-me"


def _sign(payload: dict) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    sig = hmac.new(_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"v1.{body}.{sig}"


def verify_token(token: str) -> dict | None:
    if not token or not token.startswith("v1."):
        return None
    try:
        _, body, sig = token.split(".", 2)
        expected = hmac.new(_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        pad = "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body + pad))
        if int(payload.get("exp") or 0) < time.time():
            return None
        return payload
    except (ValueError, json.JSONDecodeError, TypeError):
        return None


def issue_expert_token(*, name: str, expert_id: str) -> str:
    return _sign(
        {
            "name": name,
            "role": "doctor",
            "expert_id": expert_id,
            "exp": int(time.time()) + _TTL_SECONDS,
        }
    )


def issue_member_token(*, user_id: str, email: str, name: str) -> str:
    return _sign(
        {
            "user_id": user_id,
            "email": email,
            "name": name or email,
            "role": "member",
            "exp": int(time.time()) + _TTL_SECONDS,
        }
    )
