"""Persist assessments and clinician-reviewed plans (local JSON; Supabase optional)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.storage import ayun_db
from backend.storage.data_paths import writable_json

_ASSESSMENTS_FILE = writable_json("plan_reviews/assessments.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_store() -> None:
    writable_json("plan_reviews/assessments.json")


def _read_rows() -> list[dict[str, Any]]:
    _ensure_store()
    try:
        data = json.loads(_ASSESSMENTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_rows(rows: list[dict[str, Any]]) -> None:
    _ensure_store()
    _ASSESSMENTS_FILE.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    for row in rows:
        ayun_db.upsert_plan_review(row)


def _merged_rows() -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in _read_rows():
        if row.get("id"):
            by_id[row["id"]] = row
    remote = ayun_db.list_plan_reviews(limit=200)
    if remote:
        for row in remote:
            rid = row.get("id")
            if not rid:
                continue
            existing = by_id.get(rid)
            if not existing or (row.get("created_at") or "") >= (existing.get("created_at") or ""):
                by_id[rid] = row
    rows = list(by_id.values())
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def _parse_action_items(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if not raw:
        return []
    lines = []
    for line in str(raw).splitlines():
        line = line.strip()
        if line.startswith("•"):
            line = line[1:].strip()
        elif line.startswith("-"):
            line = line[1:].strip()
        if line:
            lines.append(line)
    return lines


def recommendations_from_triggered(
    triggered: list[dict[str, Any]],
    *,
    id_prefix: str = "rec",
    source: str = "ai_generated",
) -> list[dict[str, Any]]:
    return [
        {
            "id": f"{id_prefix}_{i}",
            "title": item.get("title", ""),
            "category": item.get("category", "General"),
            "original_priority": item.get("priority", "Medium"),
            "reviewed_priority": item.get("priority", "Medium"),
            "action_items": item.get("action_items") or [],
            "clinician_notes": "",
            "source": source,
            "removed": False,
        }
        for i, item in enumerate(triggered)
    ]


def recommendations_from_assessment(assessment: dict[str, Any]) -> list[dict[str, Any]]:
    """Build an expert-editable draft from rules plus matched AYUN protocols."""
    recommendations = recommendations_from_triggered(assessment.get("triggered") or [])
    recommendations.extend(
        recommendations_from_triggered(
            assessment.get("protocol_recommendations") or [],
            id_prefix="protocol",
            source="ayun_protocol",
        )
    )
    return recommendations


def normalize_recommendation(row: dict[str, Any]) -> dict[str, Any]:
    items = row.get("action_items")
    if isinstance(items, str):
        items = _parse_action_items(items)
    elif not isinstance(items, list):
        items = []
    return {
        "id": row.get("id") or str(uuid.uuid4())[:8],
        "title": (row.get("title") or "").strip(),
        "category": row.get("category") or "General",
        "original_priority": row.get("original_priority") or row.get("reviewed_priority") or "Medium",
        "reviewed_priority": row.get("reviewed_priority") or row.get("original_priority") or "Medium",
        "action_items": items,
        "clinician_notes": row.get("clinician_notes") or "",
        "source": row.get("source") or "ai_generated",
        "removed": bool(row.get("removed")),
    }


@dataclass
class SavedAssessment:
    id: str
    member_user_id: str | None
    member_name: str
    pseudonym: str
    member_data: dict[str, Any]
    personal_profile: dict[str, Any]
    assessment: dict[str, Any]
    draft_recommendations: list[dict[str, Any]] = field(default_factory=list)
    draft_updated_by: str = ""
    draft_updated_at: str = ""
    published: dict[str, Any] | None = None
    created_at: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> SavedAssessment:
        draft = row.get("draft_recommendations") or []
        return cls(
            id=row["id"],
            member_user_id=row.get("member_user_id"),
            member_name=row.get("member_name") or "",
            pseudonym=row.get("pseudonym") or "",
            member_data=row.get("member_data") or {},
            personal_profile=row.get("personal_profile") or {},
            assessment=row.get("assessment") or {},
            draft_recommendations=[normalize_recommendation(r) for r in draft],
            draft_updated_by=row.get("draft_updated_by") or "",
            draft_updated_at=row.get("draft_updated_at") or "",
            published=row.get("published"),
            created_at=row.get("created_at") or "",
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def active_draft_recommendations(self) -> list[dict[str, Any]]:
        if self.draft_recommendations:
            return [r for r in self.draft_recommendations if not r.get("removed")]
        return recommendations_from_assessment(self.assessment)


def save_assessment(
    assessment_payload: dict[str, Any],
    *,
    member_data: dict[str, Any],
    personal_profile: dict[str, Any] | None = None,
    member_user_id: str | None = None,
    member_name: str = "",
    pseudonym: str = "",
) -> SavedAssessment:
    record = SavedAssessment(
        id=str(uuid.uuid4())[:12],
        member_user_id=member_user_id,
        member_name=member_name.strip(),
        pseudonym=pseudonym.strip(),
        member_data=member_data,
        personal_profile=personal_profile or {},
        assessment=assessment_payload,
        draft_recommendations=recommendations_from_assessment(assessment_payload),
        created_at=_now_iso(),
    )
    return upsert_assessment(record)


def upsert_assessment(record: SavedAssessment, extra: dict[str, Any] | None = None) -> SavedAssessment:
    row = record.to_dict()
    if extra:
        row.update(extra)
    rows = [r for r in _read_rows() if r.get("id") != record.id]
    rows.insert(0, row)
    _write_rows(rows[:200])
    return record


def get_assessment(assessment_id: str) -> SavedAssessment | None:
    remote = ayun_db.get_plan_review(assessment_id)
    if remote:
        return SavedAssessment.from_row(remote)
    for row in _read_rows():
        if row.get("id") == assessment_id:
            return SavedAssessment.from_row(row)
    return None


def list_assessments(
    limit: int = 50,
    *,
    include_archived: bool = False,
    published_only: bool | None = None,
) -> list[SavedAssessment]:
    rows = _merged_rows()
    if not include_archived:
        rows = [r for r in rows if not r.get("archived_from_inbox")]
    if published_only is True:
        rows = [r for r in rows if r.get("published")]
    elif published_only is False:
        rows = [r for r in rows if not r.get("published")]
    return [SavedAssessment.from_row(r) for r in rows[:limit]]


def archive_assessment(assessment_id: str, archived_by: str) -> SavedAssessment | None:
    """Hide a finished (published) assessment from the expert inbox — member plan is kept."""
    rows = _merged_rows()
    found = None
    for i, row in enumerate(rows):
        if row.get("id") != assessment_id:
            continue
        if not row.get("published"):
            return None
        row["archived_from_inbox"] = True
        row["archived_by"] = archived_by
        row["archived_at"] = _now_iso()
        found = SavedAssessment.from_row(row)
        rows[i] = row
        break
    if not found:
        return None
    _write_rows(rows)
    return found


def list_assessments_for_member(member_user_id: str, limit: int = 20) -> list[SavedAssessment]:
    uid = (member_user_id or "").strip()
    if not uid:
        return []
    rows = [r for r in _merged_rows() if r.get("member_user_id") == uid]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return [SavedAssessment.from_row(r) for r in rows[:limit]]


def latest_assessment_for_member(member_user_id: str) -> SavedAssessment | None:
    rows = list_assessments_for_member(member_user_id, limit=1)
    return rows[0] if rows else None


def _member_directory_key(row: dict[str, Any]) -> str:
    uid = row.get("member_user_id")
    if uid:
        return f"user:{uid}"
    name = (row.get("member_name") or "Guest").strip() or "Guest"
    return f"guest:{name.lower()}"


def list_member_directory(limit: int = 100) -> list[dict[str, Any]]:
    """Aggregate saved assessments by member — profile + checkup data for expert view."""
    from backend.storage import user_store

    groups: dict[str, dict[str, Any]] = {}
    for row in _merged_rows():
        key = _member_directory_key(row)
        created = row.get("created_at") or ""
        assessment = row.get("assessment") or {}
        triggered = assessment.get("triggered") or []
        entry = {
            "id": row["id"],
            "created_at": created,
            "has_published_plan": bool(row.get("published")),
            "triggered_count": len(triggered),
            "archived_from_inbox": bool(row.get("archived_from_inbox")),
        }
        if key not in groups:
            groups[key] = {
                "member_key": key,
                "member_user_id": row.get("member_user_id"),
                "member_name": row.get("member_name") or "Guest",
                "pseudonym": row.get("pseudonym") or "",
                "email": "",
                "personal_profile": row.get("personal_profile") or {},
                "member_data": row.get("member_data") or {},
                "assessment_count": 0,
                "latest_assessment_id": row["id"],
                "latest_created_at": created,
                "has_published_plan": bool(row.get("published")),
                "assessments": [],
            }
        group = groups[key]
        group["assessment_count"] += 1
        group["assessments"].append(entry)
        if row.get("published"):
            group["has_published_plan"] = True
        if created >= (group.get("latest_created_at") or ""):
            group["latest_created_at"] = created
            group["latest_assessment_id"] = row["id"]
            group["personal_profile"] = row.get("personal_profile") or {}
            group["member_data"] = row.get("member_data") or {}
            group["member_name"] = row.get("member_name") or group["member_name"]
            group["pseudonym"] = row.get("pseudonym") or group["pseudonym"]

    result = list(groups.values())
    for group in result:
        group["assessments"].sort(key=lambda a: a["created_at"], reverse=True)
        uid = group.get("member_user_id")
        if uid:
            user = user_store.get_user(uid)
            if user:
                group["email"] = user.email
                if user.display_name:
                    group["member_name"] = user.display_name
                if user.personal_profile:
                    group["personal_profile"] = {
                        **group["personal_profile"],
                        **user.personal_profile,
                    }
                if user.member_data:
                    merged = {**group["member_data"], **user.member_data}
                    group["member_data"] = merged

    result.sort(key=lambda g: g.get("latest_created_at") or "", reverse=True)
    return result[:limit]


def get_member_directory_entry(member_key: str) -> dict[str, Any] | None:
    for entry in list_member_directory(limit=500):
        if entry["member_key"] == member_key:
            return entry
    return None


def save_draft_review(
    assessment_id: str,
    recommendations: list[dict[str, Any]],
    updated_by: str,
) -> SavedAssessment | None:
    rows = _merged_rows()
    found = None
    normalized = [normalize_recommendation(r) for r in recommendations]
    for i, row in enumerate(rows):
        if row.get("id") != assessment_id:
            continue
        row["draft_recommendations"] = normalized
        row["draft_updated_by"] = updated_by
        row["draft_updated_at"] = _now_iso()
        found = SavedAssessment.from_row(row)
        rows[i] = found.to_dict()
        break
    if not found:
        return None
    _write_rows(rows)
    return found


def publish_review(
    assessment_id: str,
    recommendations: list[dict[str, Any]],
    published_by: str,
    clinician_note: str = "",
) -> SavedAssessment | None:
    rows = _merged_rows()
    found = None
    normalized = [normalize_recommendation(r) for r in recommendations]
    active = [r for r in normalized if not r.get("removed") and r.get("title")]
    removed_titles = [r["title"] for r in normalized if r.get("removed") and r.get("title")]
    for i, row in enumerate(rows):
        if row.get("id") != assessment_id:
            continue
        row["draft_recommendations"] = normalized
        row["published"] = {
            "recommendations": active,
            "removed_titles": removed_titles,
            "published_by": published_by,
            "published_at": _now_iso(),
            "clinician_note": clinician_note.strip(),
        }
        row["draft_updated_by"] = published_by
        row["draft_updated_at"] = _now_iso()
        found = SavedAssessment.from_row(row)
        rows[i] = found.to_dict()
        break
    if not found:
        return None
    _write_rows(rows)

    if ayun_db.is_configured():
        ayun_db.persist_expert_review(
            assessment_id=None,
            reviewed_by=published_by,
            recommendations=active,
            export_meta={"assessment_id": assessment_id, "clinician_note": clinician_note},
            knowledge_saved=False,
        )
    return found


def update_assessment_member_context(
    assessment_id: str,
    *,
    member_data: dict[str, Any] | None = None,
    personal_profile: dict[str, Any] | None = None,
    member_name: str | None = None,
    updated_by: str = "",
) -> SavedAssessment | None:
    """Update stored member profile/checkup on an assessment; sync linked app user if present."""
    from backend.storage import user_store

    rows = _merged_rows()
    found = None
    for i, row in enumerate(rows):
        if row.get("id") != assessment_id:
            continue
        if member_data is not None:
            row["member_data"] = member_data
        if personal_profile is not None:
            row["personal_profile"] = {**(row.get("personal_profile") or {}), **personal_profile}
        if member_name is not None and member_name.strip():
            row["member_name"] = member_name.strip()
        if updated_by:
            row["context_updated_by"] = updated_by
            row["context_updated_at"] = _now_iso()
        found = SavedAssessment.from_row(row)
        rows[i] = found.to_dict()
        break
    if not found:
        return None
    _write_rows(rows)

    uid = found.member_user_id
    if uid:
        user_store.update_user_profile(
            uid,
            display_name=member_name.strip() if member_name and member_name.strip() else None,
            member_data=member_data,
            personal_profile=personal_profile,
        )
    return found


def get_published_plan_for_member(member_user_id: str) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_at = ""
    for row in _merged_rows():
        if row.get("member_user_id") != member_user_id:
            continue
        published = row.get("published")
        if not published:
            continue
        at = published.get("published_at") or ""
        if not best or at > best_at:
            best_at = at
            best = {
                "assessment_id": row["id"],
                "member_name": row.get("member_name") or "",
                **published,
            }
    return best


def get_published_plan_by_assessment(assessment_id: str) -> dict[str, Any] | None:
    row = next((r for r in _merged_rows() if r.get("id") == assessment_id), None)
    if not row or not row.get("published"):
        return None
    return {
        "assessment_id": row["id"],
        "member_name": row.get("member_name") or "",
        **row["published"],
    }


def assessment_to_api_dict(record: SavedAssessment) -> dict[str, Any]:
    published = record.published
    return {
        "id": record.id,
        "member_user_id": record.member_user_id,
        "member_name": record.member_name,
        "pseudonym": record.pseudonym,
        "created_at": record.created_at,
        "has_published_plan": bool(published),
        "published_at": (published or {}).get("published_at"),
        "published_by": (published or {}).get("published_by"),
        "triggered_count": len(record.assessment.get("triggered") or []),
        "draft_count": len(record.active_draft_recommendations()),
    }
