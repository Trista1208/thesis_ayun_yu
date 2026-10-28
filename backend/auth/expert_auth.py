"""Expert login — password gate for clinician / expert features."""

from __future__ import annotations

import hmac
import os


def _normalize_secret(value: str) -> str:
    """Strip whitespace and accidental surrounding quotes from env/UI paste."""
    text = (value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    return text


def expert_password() -> str:
    return _normalize_secret(os.environ.get("EXPERT_PASSWORD", ""))


def is_configured() -> bool:
    return bool(expert_password())


def verify(attempt: str) -> bool:
    expected = expert_password()
    if not expected:
        return False
    return hmac.compare_digest(_normalize_secret(attempt), expected)
