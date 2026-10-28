from __future__ import annotations

from fastapi import APIRouter

from api.schemas import AssessmentRequest
from api.serializers import recommendation_to_dict
from api.routes.auth import MemberSession
from api.deps import load_env

load_env()

from backend.rules.recommendation_api import get_recommendations  # noqa: E402
from backend.storage import ayun_db  # noqa: E402
from backend.storage.plan_review_store import (  # noqa: E402
    latest_assessment_for_member,
    save_assessment as persist_plan_assessment,
)

router = APIRouter(prefix="/assessments", tags=["assessments"])


def _build_personal_context(profile) -> str:
    if not profile:
        return ""
    parts = []
    if profile.name:
        parts.append(f"Member name: {profile.name}")
    if profile.geographic_area and profile.geographic_area != "Not specified":
        location = profile.geographic_area
        if profile.location_detail and profile.location_detail.strip():
            location = f"{location} ({profile.location_detail.strip()})"
        parts.append(f"Geographic area: {location}")
    elif profile.location_detail and profile.location_detail.strip():
        parts.append(f"Geographic area: {profile.location_detail.strip()}")
    if profile.health_status and profile.health_status != "Not specified":
        parts.append(f"General health status: {profile.health_status}")
    if profile.existing_conditions and profile.existing_conditions.strip():
        parts.append(f"Existing conditions / diagnoses: {profile.existing_conditions.strip()}")
    if profile.smoking_status and profile.smoking_status != "Not specified":
        parts.append(f"Smoking status: {profile.smoking_status}")
    if profile.alcohol_use and profile.alcohol_use != "Not specified":
        parts.append(f"Alcohol use: {profile.alcohol_use}")
    if profile.sleep_hours and profile.sleep_hours != "Not specified":
        parts.append(f"Typical sleep: {profile.sleep_hours}")
    if profile.diet and profile.diet.strip():
        parts.append(f"Diet / dietary notes: {profile.diet.strip()}")
    if profile.goals:
        parts.append(f"Health goals: {', '.join(profile.goals)}")
    if profile.activity_level:
        parts.append(f"Current activity level: {profile.activity_level}")
    if profile.sport_prefs:
        parts.append(f"Preferred activities: {', '.join(profile.sport_prefs)}")
    for label, value in (
        ("Stress level", profile.stress),
        ("Depression level", profile.depression),
        ("Optimism level", profile.optimism),
    ):
        if value and value != "Not assessed":
            parts.append(f"{label}: {value}")
    if profile.injuries:
        parts.append(f"Injuries / limitations: {profile.injuries}")
    if profile.notes:
        parts.append(f"Additional notes: {profile.notes}")
    return "\n".join(parts)


def _member_plan_payload(record) -> dict:
    payload = dict(record.assessment or {})
    payload["assessment_id"] = record.id
    if (payload.get("context_for_llm") or "").strip() or not record.member_data:
        return payload
    rebuilt = recommendation_to_dict(
        get_recommendations(record.member_data, personal_context="")
    )
    rebuilt["assessment_id"] = record.id
    return rebuilt


@router.get("/latest")
def latest_assessment(session: MemberSession):
    record = latest_assessment_for_member(session["user_id"])
    if not record:
        return {"assessment": None}
    return {"assessment": _member_plan_payload(record)}


@router.post("")
def create_assessment(body: AssessmentRequest, session: MemberSession):
    ctx = body.personal_context or _build_personal_context(body.personal_profile)
    result = get_recommendations(body.member_data, personal_context=ctx)
    payload = recommendation_to_dict(result)

    member_user_id = session["user_id"] if session else None
    member_name = ""
    if body.personal_profile and body.personal_profile.name:
        member_name = body.personal_profile.name
    elif session:
        member_name = session.get("name") or ""

    record = persist_plan_assessment(
        payload,
        member_data=body.member_data,
        personal_profile=body.personal_profile.model_dump() if body.personal_profile else {},
        member_user_id=member_user_id,
        member_name=member_name,
        pseudonym=body.pseudonym,
    )

    assessment_id = record.id
    if ayun_db.is_configured():
        profile_dict = body.personal_profile.model_dump() if body.personal_profile else {}
        ayun_db.persist_assessment(
            body.member_data,
            result,
            personal_profile=profile_dict,
            pseudonym=body.pseudonym,
        )
    return {"assessment_id": assessment_id, **payload}
