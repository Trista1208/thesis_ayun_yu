"""Google OAuth for member sign-in — same third-party path as Garra Rufa."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

_LOCAL_ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
}
_PUBLIC_ORIGIN = "https://ayun-full.vercel.app"


def is_configured() -> bool:
    return bool(os.environ.get("GOOGLE_CLIENT_ID", "").strip() and os.environ.get("GOOGLE_CLIENT_SECRET", "").strip())


def allowed_origins() -> set[str]:
    origins = set(_LOCAL_ORIGINS)
    origins.add(_PUBLIC_ORIGIN)
    vercel = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL", "").strip() or os.environ.get("VERCEL_URL", "").strip()
    if vercel:
        origins.add(f"https://{vercel.removeprefix('https://').rstrip('/')}")
    for raw in (
        os.environ.get("APP_BASE_URL", ""),
        os.environ.get("FRONTEND_ORIGIN", ""),
        os.environ.get("CORS_ORIGIN", ""),
    ):
        for part in raw.split(","):
            origin = part.strip().rstrip("/")
            if origin:
                origins.add(origin)
    return origins


def _as_loopback(origin: str) -> str:
    """Google's local client is registered on 127.0.0.1, not localhost."""
    parsed = urllib.parse.urlparse(origin)
    host = (parsed.hostname or "").lower()
    if host not in {"localhost", "::1"}:
        return origin
    port = parsed.port
    if port and not ((parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443)):
        return f"{parsed.scheme}://127.0.0.1:{port}"
    return f"{parsed.scheme}://127.0.0.1"


def frontend_origin(requested: str | None = None) -> str:
    if requested:
        origin = requested.strip().rstrip("/")
        if origin in allowed_origins():
            return _as_loopback(origin)
    base = os.environ.get("APP_BASE_URL", "").strip().rstrip("/")
    if base and not _as_loopback(base).startswith("http://127.0.0.1"):
        return _as_loopback(base)
    if os.environ.get("VERCEL"):
        return _PUBLIC_ORIGIN
    return _as_loopback(os.environ.get("FRONTEND_ORIGIN", "http://127.0.0.1:5173").rstrip("/"))


def redirect_uri(origin: str | None = None) -> str:
    explicit = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
    loopback = "127.0.0.1" in explicit or "localhost" in explicit
    if explicit and not (os.environ.get("VERCEL") and loopback):
        return explicit
    return f"{frontend_origin(origin)}/login"


def _secret() -> bytes:
    for key in ("SESSION_SECRET", "EXPERT_PASSWORD", "GOOGLE_CLIENT_SECRET"):
        val = os.environ.get(key, "").strip()
        if val:
            return val.encode("utf-8")
    return b"ayun-dev-insecure-change-me"


def _sign_state(origin: str) -> str:
    body = json.dumps(
        {"exp": int(time.time()) + 600, "origin": origin, "redirect": redirect_uri(origin)},
        separators=(",", ":"),
    ).encode("utf-8")
    payload = urllib.parse.quote_from_bytes(body, safe="")
    sig = hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _read_state(state: str | None) -> dict:
    if not state or "." not in state:
        raise ValueError("Google sign-in expired. Try again.")
    payload, sig = state.rsplit(".", 1)
    expected = hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Google sign-in expired. Try again.")
    try:
        data = json.loads(urllib.parse.unquote(payload))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Google sign-in expired. Try again.") from exc
    if int(data.get("exp") or 0) < int(time.time()):
        raise ValueError("Google sign-in expired. Try again.")
    return data


def authorization_url(origin: str | None = None) -> str:
    dest = frontend_origin(origin)
    params = {
        "client_id": os.environ["GOOGLE_CLIENT_ID"].strip(),
        "redirect_uri": redirect_uri(dest),
        "response_type": "code",
        "scope": "openid email profile",
        "state": _sign_state(dest),
        "prompt": "select_account",
        "access_type": "online",
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def _post_form(url: str, data: dict[str, str]) -> dict:
    req = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(data).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def exchange_code(code: str, state: str | None) -> dict[str, str]:
    data = _read_state(state)
    redirect = str(data.get("redirect") or redirect_uri(data.get("origin")))
    try:
        tokens = _post_form(
            TOKEN_URL,
            {
                "code": code,
                "client_id": os.environ["GOOGLE_CLIENT_ID"].strip(),
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"].strip(),
                "redirect_uri": redirect,
                "grant_type": "authorization_code",
            },
        )
    except urllib.error.HTTPError as exc:
        raise ValueError("Google sign-in could not start. Please try again.") from exc
    access = tokens.get("access_token")
    if not access:
        raise ValueError("Google sign-in could not start. Please try again.")
    profile = _get_json(USERINFO_URL, access)
    email = str(profile.get("email") or "").strip()
    if not email or profile.get("email_verified") is False:
        raise ValueError("Google did not return a verified email.")
    name = str(profile.get("name") or profile.get("given_name") or email.split("@")[0]).strip()
    return {"email": email, "name": name[:100], "origin": frontend_origin(data.get("origin"))}
