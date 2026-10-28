"""
Member memory API — three-tier memory management.

Tier 1 (working):  ephemeral, client-side only, no routes needed
Tier 2 (episodic): GET/DELETE per-user; POST session close; admin purge
Tier 3 (semantic): knowledge library (knowledge.py routes)

All routes require member auth except the expert purge endpoint.
"""

from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter, HTTPException

from api.routes.auth import ExpertSession, MemberSession
from api.deps import load_env

load_env()

from backend.ai.memory_store import (  # noqa: E402
    RETENTION_OPTIONS,
    delete_user_memory,
    list_user_memory,
    purge_expired_memory,
    store_session_memory,
    summarise_session,
)
from backend.storage import user_store  # noqa: E402

router = APIRouter(prefix="/memory", tags=["memory"])


# ── Request schemas ───────────────────────────────────────────────────────────

class CloseSessionRequest(BaseModel):
    session_id: str
    messages: list[dict]
    member_name: str = ""


class PrivacySettingsRequest(BaseModel):
    memory_enabled: bool = True
    memory_retention_days: int = 30


# ── Member endpoints ──────────────────────────────────────────────────────────

@router.get("")
def get_my_memory(session: MemberSession):
    """List the current user's episodic memory records (non-expired)."""
    user = user_store.ensure_from_session(session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    records = list_user_memory(user.id, limit=20)
    return {
        "user_id": user.id,
        "records": [r.to_dict() for r in records],
        "total": len(records),
    }


@router.delete("")
def delete_my_memory(session: MemberSession):
    """Permanently delete all memory records for the current user (Right to Erasure, GDPR Art.17)."""
    user = user_store.ensure_from_session(session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    deleted = delete_user_memory(user.id)
    return {"ok": True, "deleted": deleted, "message": f"Deleted {deleted} memory record(s)."}


@router.post("/session/close")
def close_session(body: CloseSessionRequest, session: MemberSession):
    """
    Called by the frontend when a chat session ends.
    Summarises the conversation and stores an episodic record respecting the user's retention setting.
    """
    user = user_store.ensure_from_session(session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    privacy = user.privacy_settings or {}
    retention_days = int(privacy.get("memory_retention_days", 30))

    if retention_days == 0 or not privacy.get("memory_enabled", True):
        return {"stored": False, "reason": "Memory disabled by user preference"}

    msgs = [m for m in body.messages if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
    if len(msgs) < 2:
        return {"stored": False, "reason": "Session too short to summarise"}

    result = summarise_session(msgs, member_name=body.member_name or session.get("name", ""))
    if not result:
        return {"stored": False, "reason": "AI summarisation unavailable"}

    record = store_session_memory(
        user_id=user.id,
        session_id=body.session_id or "",
        summary=result["summary"],
        topics=result["topics"],
        turn_count=sum(1 for m in msgs if m.get("role") == "user"),
        confidence_avg=result["confidence_avg"],
        retention_days=retention_days,
    )
    return {
        "stored": record is not None,
        "record": record.to_dict() if record else None,
    }


@router.put("/privacy")
def update_privacy_settings(body: PrivacySettingsRequest, session: MemberSession):
    """Update memory consent and retention preference."""
    valid_days = {o["days"] for o in RETENTION_OPTIONS}
    if body.memory_retention_days not in valid_days:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid retention days. Allowed: {sorted(valid_days)}",
        )

    from backend.ai.memory_store import _now_iso
    privacy = {
        "memory_enabled": body.memory_enabled,
        "memory_retention_days": body.memory_retention_days,
        "consented_at": _now_iso(),
    }
    # Resolve by JWT id or email (cold start / new account), then update that row.
    user = user_store.ensure_from_session(session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user = user_store.update_user_profile(user.id, privacy_settings=privacy)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "privacy_settings": user.privacy_settings}


@router.get("/retention-options")
def get_retention_options():
    """Public — list of available retention tiers shown in the UI."""
    return {"options": RETENTION_OPTIONS}


# ── Expert / admin endpoint ───────────────────────────────────────────────────

@router.post("/admin/purge-expired")
def admin_purge_expired(session: ExpertSession):
    """Purge all expired memory records across all users. Expert-only."""
    deleted = purge_expired_memory()
    return {"ok": True, "deleted": deleted}
