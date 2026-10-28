from __future__ import annotations

import urllib.parse
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import RedirectResponse

from api.schemas import (
    ExpertLoginRequest,
    GoogleExchangeRequest,
    GoogleStartRequest,
    MemberLoginRequest,
    MemberProfileUpdate,
    MemberRegisterRequest,
)
from api.deps import load_env

load_env()

from backend.auth import expert_auth  # noqa: E402
from backend.workflow.experts import load_experts  # noqa: E402
from backend.auth import google_oauth  # noqa: E402
from backend.auth import session_tokens  # noqa: E402
from backend.storage import user_store  # noqa: E402

router = APIRouter(prefix="/auth", tags=["auth"])


def _resolve_expert_id(name: str) -> str:
    needle = (name or "").strip().lower()
    if not needle:
        return "general_pool"
    for expert in load_experts(include_pool=False):
        if expert.name.strip().lower() == needle:
            return expert.id
    return "general_pool"


def _parse_bearer(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip()


def _session_from_token(token: str | None) -> dict | None:
    if not token:
        return None
    return session_tokens.verify_token(token)


def get_expert_session(authorization: Annotated[str | None, Header()] = None) -> dict:
    token = _parse_bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Expert login required")
    session = _session_from_token(token)
    if not session or session.get("role") != "doctor":
        raise HTTPException(status_code=401, detail="Invalid or expired expert session")
    return session


def get_member_session(authorization: Annotated[str | None, Header()] = None) -> dict:
    token = _parse_bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Member login required")
    session = _session_from_token(token)
    if not session or session.get("role") != "member":
        raise HTTPException(status_code=401, detail="Invalid or expired member session")
    return session


ExpertSession = Annotated[dict, Depends(get_expert_session)]
MemberSession = Annotated[dict, Depends(get_member_session)]


def get_optional_member_session(authorization: Annotated[str | None, Header()] = None) -> dict | None:
    session = _session_from_token(_parse_bearer(authorization))
    if session and session.get("role") == "member":
        return session
    return None


OptionalMemberSession = Annotated[dict | None, Depends(get_optional_member_session)]


# ── Member auth ───────────────────────────────────────────────────────────────

@router.post("/member/register")
def member_register(body: MemberRegisterRequest):
    try:
        user = user_store.register_user(body.email, body.password, body.display_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    token = session_tokens.issue_member_token(
        user_id=user.id,
        email=user.email,
        name=user.display_name,
    )
    return {"token": token, "user": user.public_dict()}


@router.post("/member/login")
def member_login(body: MemberLoginRequest):
    user = user_store.authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = session_tokens.issue_member_token(
        user_id=user.id,
        email=user.email,
        name=user.display_name,
    )
    return {"token": token, "user": user.public_dict()}


@router.get("/member/google/status")
def member_google_status(request: Request, origin: str | None = None):
    raw = origin or request.headers.get("origin") or request.headers.get("referer")
    if raw and "://" in raw:
        parsed = urllib.parse.urlparse(raw)
        raw = f"{parsed.scheme}://{parsed.netloc}"
    dest = google_oauth.frontend_origin(raw)
    return {
        "googleEnabled": google_oauth.is_configured(),
        "javascriptOrigin": dest,
        "redirectUri": google_oauth.redirect_uri(dest),
    }


@router.post("/member/google")
def member_google_start(request: Request, body: GoogleStartRequest | None = None):
    if not google_oauth.is_configured():
        raise HTTPException(status_code=503, detail="Google sign-in is not available yet. Please use email and password.")
    origin = (body.origin if body else "") or request.headers.get("origin") or request.headers.get("referer")
    if origin and "://" in origin:
        parsed = urllib.parse.urlparse(origin)
        origin = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "url": google_oauth.authorization_url(origin),
        "redirectUri": google_oauth.redirect_uri(origin),
    }


@router.post("/member/google/exchange")
def member_google_exchange(body: GoogleExchangeRequest):
    if not google_oauth.is_configured():
        raise HTTPException(status_code=503, detail="Google sign-in is not available yet. Please use email and password.")
    code = body.code.strip()
    state = body.state.strip()
    if not code or not state:
        raise HTTPException(status_code=400, detail="Google sign-in could not finish. Try again.")
    try:
        profile = google_oauth.exchange_code(code, state)
        user = user_store.upsert_google_user(profile["email"], profile.get("name") or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    token = session_tokens.issue_member_token(
        user_id=user.id,
        email=user.email,
        name=user.display_name,
    )
    return {"token": token, "user": user.public_dict()}


@router.get("/member/google/callback")
def member_google_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    dest = google_oauth.frontend_origin()
    if error or not code or not state:
        return RedirectResponse(f"{dest}/login?google=error", status_code=302)
    return RedirectResponse(
        f"{dest}/login?{urllib.parse.urlencode({'code': code, 'state': state})}",
        status_code=302,
    )


@router.get("/member/me")
def member_me(session: MemberSession):
    user = user_store.ensure_from_session(session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.public_dict()


@router.put("/member/profile")
def member_update_profile(body: MemberProfileUpdate, session: MemberSession):
    resolved = user_store.ensure_from_session(session)
    if not resolved:
        raise HTTPException(status_code=404, detail="User not found")
    user = user_store.update_user_profile(
        resolved.id,
        display_name=body.display_name,
        pseudonym=body.pseudonym,
        member_data=body.member_data,
        personal_profile=body.personal_profile.model_dump() if body.personal_profile else None,
        enabled_sections=body.enabled_sections,
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.public_dict()


# ── Expert auth ───────────────────────────────────────────────────────────────

@router.get("/expert/status")
def expert_status():
    return {"configured": expert_auth.is_configured()}


@router.post("/expert/login")
def expert_login(body: ExpertLoginRequest):
    if not expert_auth.is_configured():
        raise HTTPException(status_code=503, detail="Expert login not configured on server")
    if not expert_auth.verify(body.password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    name = body.name.strip() or "Clinician"
    expert_id = _resolve_expert_id(name)
    token = session_tokens.issue_expert_token(name=name, expert_id=expert_id)
    return {"token": token, "name": name, "role": "doctor", "expert_id": expert_id}


@router.post("/expert/logout")
def expert_logout():
    return {"ok": True}


@router.get("/expert/me")
def expert_me(session: ExpertSession):
    return session


@router.get("/session")
def current_sessions(authorization: Annotated[str | None, Header()] = None):
    """Check which session type a bearer token belongs to (for client bootstrap)."""
    session = _session_from_token(_parse_bearer(authorization))
    if not session:
        return {"member": False, "expert": False}
    return {
        "member": session.get("role") == "member",
        "expert": session.get("role") == "doctor",
    }
