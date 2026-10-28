"""
Supabase Postgres backend (WearAware-inspired).

Uses service-role client from Streamlit/Railway — same pattern as WearAware backend.
Falls back silently when SUPABASE_URL is not configured; knowledge_store keeps JSON files.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

_client = None


def _raw_service_key() -> str:
    return (
        os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )


def _service_key() -> str:
    """Secret key in the current dashboard; service_role is the older name."""
    key = _raw_service_key()
    if key.startswith("sb_publishable_"):
        return ""
    return key


def config_hint() -> str:
    if is_configured():
        return ""
    if not os.environ.get("SUPABASE_URL", "").strip():
        return "Set SUPABASE_URL to https://<project-ref>.supabase.co"
    if _raw_service_key().startswith("sb_publishable_"):
        return (
            "SUPABASE_SECRET_KEY is the Public key (sb_publishable_…). "
            "Replace it with Secret (sb_secret_…) from Settings → API Keys, "
            "or the legacy service_role key."
        )
    if not _raw_service_key():
        return (
            "Set SUPABASE_SECRET_KEY to the Secret key (sb_secret_…) "
            "from Settings → API Keys. Do not use Public."
        )
    return "Supabase is not configured."


def is_configured() -> bool:
    return bool(os.environ.get("SUPABASE_URL", "").strip() and _service_key())


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not is_configured():
        return None
    try:
        from supabase import create_client
    except ImportError:
        return None
    url = os.environ["SUPABASE_URL"].strip()
    _client = create_client(url, _service_key())
    return _client


def backend_label() -> str:
    return "supabase" if is_configured() and _get_client() else "json_files"


# ── App users (member login) ─────────────────────────────────────────────────

def get_app_user_by_email(email: str) -> dict[str, Any] | None:
    sb = _get_client()
    if not sb:
        return None
    needle = email.strip().lower()
    resp = sb.table("app_users").select("*").eq("email", needle).limit(1).execute()
    if resp.data:
        return get_app_user(resp.data[0]["id"])
    return None


def get_app_user(user_id: str) -> dict[str, Any] | None:
    sb = _get_client()
    if not sb:
        return None
    try:
        resp = sb.table("app_users").select("*").eq("id", user_id).limit(1).execute()
    except Exception:
        return None
    if resp.data:
        row = resp.data[0]
        return {
            "id": row["id"],
            "email": row["email"],
            "password_hash": row["password_hash"],
            "display_name": row.get("display_name") or "",
            "pseudonym": row.get("pseudonym") or "",
            "member_data": row.get("member_data") or {},
            "personal_profile": row.get("personal_profile") or {},
            "enabled_sections": row.get("enabled_sections") or {},
            "privacy_settings": row.get("privacy_settings") or {},
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }
    return None


def upsert_app_user(public: dict[str, Any], *, password_hash: str) -> bool:
    sb = _get_client()
    if not sb:
        return False
    payload = {
        "id": public["id"],
        "email": public["email"],
        "password_hash": password_hash,
        "display_name": public.get("display_name") or "",
        "pseudonym": public.get("pseudonym") or "",
        "member_data": public.get("member_data") or {},
        "personal_profile": public.get("personal_profile") or {},
        "enabled_sections": public.get("enabled_sections") or {},
        "privacy_settings": public.get("privacy_settings") or {},
        "updated_at": public.get("updated_at"),
    }
    try:
        sb.table("app_users").upsert(payload).execute()
        return True
    except Exception:
        payload.pop("privacy_settings", None)
        try:
            sb.table("app_users").upsert(payload).execute()
            return True
        except Exception:
            return False


# ── Knowledge nodes ───────────────────────────────────────────────────────────

def list_knowledge_nodes(limit: int = 200) -> list[dict[str, Any]] | None:
    sb = _get_client()
    if not sb:
        return None
    resp = (
        sb.table("knowledge_nodes")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def insert_knowledge_node(row: dict[str, Any]) -> bool:
    sb = _get_client()
    if not sb:
        return False
    try:
        sb.table("knowledge_nodes").upsert(row).execute()
        return True
    except Exception:
        slim = {k: v for k, v in row.items() if k != "source_ticket_id"}
        try:
            sb.table("knowledge_nodes").upsert(slim).execute()
            return True
        except Exception:
            return False


def delete_knowledge_node(node_id: str) -> bool:
    sb = _get_client()
    if not sb:
        return False
    sb.table("knowledge_nodes").delete().eq("id", node_id).execute()
    return True


# ── Expert tickets ────────────────────────────────────────────────────────────

def list_expert_tickets(status: str | None = None, limit: int = 200) -> list[dict[str, Any]] | None:
    sb = _get_client()
    if not sb:
        return None
    q = sb.table("expert_tickets").select("*").order("updated_at", desc=True).limit(limit)
    if status:
        q = q.eq("status", status)
    return q.execute().data or []


def upsert_expert_ticket(row: dict[str, Any]) -> bool:
    sb = _get_client()
    if not sb:
        return False
    try:
        sb.table("expert_tickets").upsert(row).execute()
        return True
    except Exception:
        slim = {k: v for k, v in row.items() if k != "member_user_id"}
        try:
            sb.table("expert_tickets").upsert(slim).execute()
            return True
        except Exception:
            return False


def update_expert_ticket(ticket_id: str, updates: dict[str, Any]) -> bool:
    sb = _get_client()
    if not sb:
        return False
    resp = sb.table("expert_tickets").update(updates).eq("id", ticket_id).execute()
    return bool(resp.data)


# ── Assessments & reviews (digital twin / longitudinal) ─────────────────────

def get_expert_ticket(ticket_id: str) -> dict[str, Any] | None:
    sb = _get_client()
    if not sb:
        return None
    resp = sb.table("expert_tickets").select("*").eq("id", ticket_id).limit(1).execute()
    if resp.data:
        return resp.data[0]
    return None


def delete_expert_ticket(ticket_id: str) -> bool:
    sb = _get_client()
    if not sb:
        return False
    sb.table("expert_tickets").delete().eq("id", ticket_id).execute()
    return True


# ── Member episodic memory ────────────────────────────────────────────────────

def list_member_memory(user_id: str, *, limit: int = 20) -> list[dict[str, Any]] | None:
    sb = _get_client()
    if not sb:
        return None
    resp = (
        sb.table("member_memory")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def upsert_member_memory(row: dict[str, Any]) -> bool:
    sb = _get_client()
    if not sb:
        return False
    sb.table("member_memory").upsert(row).execute()
    return True


def delete_member_memory_for_user(user_id: str) -> int | None:
    sb = _get_client()
    if not sb:
        return None
    existing = sb.table("member_memory").select("id").eq("user_id", user_id).execute()
    count = len(existing.data or [])
    if count:
        sb.table("member_memory").delete().eq("user_id", user_id).execute()
    return count


def list_ask_history(user_id: str, *, limit: int = 40) -> list[dict[str, Any]] | None:
    sb = _get_client()
    if not sb:
        return None
    try:
        resp = (
            sb.table("ask_history")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        return None
    return resp.data or []


def upsert_ask_history(row: dict[str, Any]) -> bool:
    sb = _get_client()
    if not sb:
        return False
    try:
        sb.table("ask_history").upsert(row).execute()
    except Exception:
        return False
    return True


def delete_ask_history_for_user(user_id: str) -> int | None:
    sb = _get_client()
    if not sb:
        return None
    try:
        existing = sb.table("ask_history").select("id").eq("user_id", user_id).execute()
        count = len(existing.data or [])
        if count:
            sb.table("ask_history").delete().eq("user_id", user_id).execute()
    except Exception:
        return None
    return count


def delete_ask_history_ids(ids: list[str]) -> None:
    sb = _get_client()
    if not sb or not ids:
        return
    try:
        sb.table("ask_history").delete().in_("id", ids).execute()
    except Exception:
        return


def purge_expired_member_memory() -> int | None:
    sb = _get_client()
    if not sb:
        return None
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    resp = sb.table("member_memory").select("id").lt("expires_at", now).execute()
    rows = resp.data or []
    if rows:
        ids = [r["id"] for r in rows]
        sb.table("member_memory").delete().in_("id", ids).execute()
    return len(rows)


def upsert_member(
    pseudonym: str,
    sex: str | None = None,
    birth_year: int | None = None,
) -> str | None:
    """Create or update a pseudonymized member row. Returns member UUID."""
    sb = _get_client()
    if not sb or not pseudonym.strip():
        return None
    row = {"pseudonym": pseudonym.strip(), "sex": sex, "birth_year": birth_year}
    resp = sb.table("members").upsert(row, on_conflict="pseudonym").execute()
    if resp.data:
        return resp.data[0].get("id")
    lookup = sb.table("members").select("id").eq("pseudonym", pseudonym.strip()).limit(1).execute()
    if lookup.data:
        return lookup.data[0].get("id")
    return None


def persist_assessment(
    member_data: dict[str, Any],
    result: Any,
    personal_profile: dict[str, Any] | None = None,
    pseudonym: str = "",
    source: str = "app",
) -> str | None:
    """Save one assessment snapshot from a RecommendationResult. Returns assessment UUID."""
    from dataclasses import asdict

    member_id = None
    if pseudonym.strip():
        birth_year = None
        age = member_data.get("Demographic::Age")
        if age is not None:
            try:
                from datetime import datetime
                birth_year = int(datetime.now().year - float(age))
            except (TypeError, ValueError):
                pass
        member_id = upsert_member(
            pseudonym.strip(),
            str(member_data.get("Demographic::Sex") or "") or None,
            birth_year,
        )

    age_val = member_data.get("Demographic::Age")
    payload = {
        "member_id": member_id,
        "age": int(float(age_val)) if age_val is not None else None,
        "sex": member_data.get("Demographic::Sex"),
        "member_data": member_data,
        "personal_profile": personal_profile or {},
        "triggered_recommendations": [asdict(r) for r in result.triggered],
        "parameter_ratings": [asdict(r) for r in result.ratings],
        "training_zones": asdict(result.training_zones) if result.training_zones else {},
        "context_for_llm": result.context_for_llm,
        "source": source,
    }
    return save_assessment(payload)


def persist_expert_review(
    assessment_id: str | None,
    reviewed_by: str,
    recommendations: list[dict[str, Any]],
    export_meta: dict[str, Any] | None = None,
    knowledge_saved: bool = False,
) -> str | None:
    """Save clinician sign-off linked to an assessment when available."""
    from datetime import date

    payload = {
        "assessment_id": assessment_id,
        "reviewed_by": reviewed_by,
        "review_date": date.today().isoformat(),
        "recommendations": recommendations,
        "export_meta": export_meta or {},
        "knowledge_saved": knowledge_saved,
    }
    return save_expert_review(payload)


def save_assessment(payload: dict[str, Any]) -> str | None:
    """Persist one assessment snapshot. Returns assessment UUID or None."""
    sb = _get_client()
    if not sb:
        return None
    resp = sb.table("assessments").insert(payload).execute()
    if resp.data:
        return resp.data[0].get("id")
    return None


def save_expert_review(payload: dict[str, Any]) -> str | None:
    sb = _get_client()
    if not sb:
        return None
    resp = sb.table("expert_reviews").insert(payload).execute()
    if resp.data:
        return resp.data[0].get("id")
    return None


def list_assessments_for_member(member_id: str, limit: int = 20) -> list[dict[str, Any]] | None:
    sb = _get_client()
    if not sb:
        return None
    resp = (
        sb.table("assessments")
        .select("*")
        .eq("member_id", member_id)
        .order("assessed_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def _plan_review_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "payload": row,
        "published": bool(row.get("published")),
        "archived_from_inbox": bool(row.get("archived_from_inbox")),
        "created_at": row.get("created_at") or "",
        "member_user_id": row.get("member_user_id"),
        "member_name": row.get("member_name") or "",
    }


def list_plan_reviews(limit: int = 200) -> list[dict[str, Any]] | None:
    sb = _get_client()
    if not sb:
        return None
    try:
        resp = (
            sb.table("plan_reviews")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        return None
    out: list[dict[str, Any]] = []
    for row in resp.data or []:
        payload = row.get("payload")
        if isinstance(payload, dict) and payload.get("id"):
            out.append(payload)
    return out


def upsert_plan_review(row: dict[str, Any]) -> bool:
    sb = _get_client()
    if not sb or not row.get("id"):
        return False
    try:
        sb.table("plan_reviews").upsert(_plan_review_row(row)).execute()
        return True
    except Exception:
        return False


def get_plan_review(review_id: str) -> dict[str, Any] | None:
    sb = _get_client()
    if not sb:
        return None
    try:
        resp = sb.table("plan_reviews").select("*").eq("id", review_id).limit(1).execute()
    except Exception:
        return None
    if not resp.data:
        return None
    payload = resp.data[0].get("payload")
    return payload if isinstance(payload, dict) else None


def import_batch(batch_name: str, rows: list[dict[str, Any]], source_file: str = "", imported_by: str = "") -> int | None:
    """Bulk import AYUN historical rows. Returns row count or None if DB unavailable."""
    sb = _get_client()
    if not sb:
        return None
    batch = (
        sb.table("ayun_import_batches")
        .insert({
            "batch_name": batch_name,
            "source_file": source_file,
            "imported_by": imported_by,
            "row_count": len(rows),
        })
        .execute()
    )
    batch_id = batch.data[0]["id"] if batch.data else None
    if not batch_id:
        return None
    chunk_size = 100
    inserted = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        payload = [
            {"batch_id": batch_id, "pseudonym": r.get("pseudonym"), "row_data": r.get("row_data", r)}
            for r in chunk
        ]
        sb.table("ayun_import_rows").insert(payload).execute()
        inserted += len(payload)
    return inserted
