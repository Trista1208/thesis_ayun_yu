from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from api.schemas import ExpertMemberContextUpdate, PlanPdfRequest, PlanPublishRequest, PlanReviewDraftRequest
from api.routes.auth import ExpertSession, MemberSession, OptionalMemberSession
from api.deps import load_env

load_env()

from backend.storage.plan_review_store import (  # noqa: E402
    archive_assessment,
    assessment_to_api_dict,
    get_assessment,
    get_member_directory_entry,
    get_published_plan_by_assessment,
    get_published_plan_for_member,
    latest_assessment_for_member,
    list_assessments,
    list_member_directory,
    publish_review,
    recommendations_from_triggered,
    save_draft_review,
    update_assessment_member_context,
)

router = APIRouter(tags=["reviews", "plan"])


def _recommendations_payload(record) -> list[dict]:
    if record.draft_recommendations:
        return record.draft_recommendations
    return recommendations_from_triggered(record.assessment.get("triggered") or [])


def _full_assessment_dict(record) -> dict:
    data = assessment_to_api_dict(record)
    data["assessment"] = record.assessment
    data["draft_recommendations"] = _recommendations_payload(record)
    data["published"] = record.published
    data["personal_profile"] = record.personal_profile or {}
    data["member_data"] = record.member_data or {}
    return data


@router.get("/reviews/members")
def expert_list_members(session: ExpertSession, limit: int = 100):
    """All member profiles with personal context and checkup data from saved assessments."""
    return {"members": list_member_directory(limit=limit)}


@router.get("/reviews/members/{member_key}")
def expert_get_member(member_key: str, session: ExpertSession):
    entry = get_member_directory_entry(member_key)
    if not entry:
        raise HTTPException(status_code=404, detail="Member not found")
    return entry


@router.put("/reviews/members/{member_key}/context")
def expert_update_member_context(
    member_key: str,
    body: ExpertMemberContextUpdate,
    session: ExpertSession,
):
    """Update member profile/checkup on the member's latest assessment."""
    entry = get_member_directory_entry(member_key)
    if not entry:
        raise HTTPException(status_code=404, detail="Member not found")
    updated = update_assessment_member_context(
        entry["latest_assessment_id"],
        member_data=body.member_data,
        personal_profile=body.personal_profile.model_dump() if body.personal_profile else None,
        member_name=body.member_name,
        updated_by=session["name"],
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Assessment not found")
    refreshed = get_member_directory_entry(member_key)
    return refreshed or entry


@router.put("/reviews/assessments/{assessment_id}/context")
def expert_update_assessment_context(
    assessment_id: str,
    body: ExpertMemberContextUpdate,
    session: ExpertSession,
):
    updated = update_assessment_member_context(
        assessment_id,
        member_data=body.member_data,
        personal_profile=body.personal_profile.model_dump() if body.personal_profile else None,
        member_name=body.member_name,
        updated_by=session["name"],
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return _full_assessment_dict(updated)


@router.get("/reviews/assessments")
def expert_list_assessments(
    session: ExpertSession,
    limit: int = 50,
    status: str = Query(default="pending", pattern="^(pending|published|all)$"),
):
    published_only: bool | None = None
    if status == "pending":
        published_only = False
    elif status == "published":
        published_only = True
    records = list_assessments(limit=limit, published_only=published_only)
    return {"assessments": [assessment_to_api_dict(r) for r in records]}


@router.get("/reviews/assessments/{assessment_id}")
def expert_get_assessment(assessment_id: str, session: ExpertSession):
    record = get_assessment(assessment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return _full_assessment_dict(record)


@router.put("/reviews/assessments/{assessment_id}/draft")
def expert_save_draft(assessment_id: str, body: PlanReviewDraftRequest, session: ExpertSession):
    updated = save_draft_review(assessment_id, body.recommendations, session["name"])
    if not updated:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return _full_assessment_dict(updated)


@router.post("/reviews/assessments/{assessment_id}/publish")
def expert_publish(assessment_id: str, body: PlanPublishRequest, session: ExpertSession):
    record = get_assessment(assessment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")
    recs = body.recommendations
    if not recs:
        recs = record.draft_recommendations or recommendations_from_triggered(
            record.assessment.get("triggered") or []
        )
    updated = publish_review(
        assessment_id,
        recs,
        session["name"],
        clinician_note=body.clinician_note or "",
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return _full_assessment_dict(updated)


@router.delete("/reviews/assessments/{assessment_id}")
def expert_archive_assessment(assessment_id: str, session: ExpertSession):
    """Remove a published assessment from the expert inbox (member plan unchanged)."""
    record = get_assessment(assessment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if not record.published:
        raise HTTPException(
            status_code=400,
            detail="Only published assessments can be removed from the inbox",
        )
    updated = archive_assessment(assessment_id, session["name"])
    if not updated:
        raise HTTPException(status_code=400, detail="Could not remove assessment")
    return {"ok": True, "id": assessment_id}


@router.get("/plan/published")
def member_published_plan(
    session: OptionalMemberSession,
    assessment_id: str | None = Query(default=None),
):
    if session:
        published = get_published_plan_for_member(session["user_id"])
        if published:
            return {"published": published}
    if assessment_id:
        published = get_published_plan_by_assessment(assessment_id)
        if published:
            return {"published": published}
    return {"published": None}


def _pdf_response(report: dict) -> Response:
    from backend.documents.sports_protocol_pdf import pdf_filename, sports_performance_pdf

    try:
        payload = sports_performance_pdf(report)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not build the protocol PDF") from exc
    filename = pdf_filename(report.get("member_name") or "member")
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/plan/pdf")
def member_protocol_pdf(session: MemberSession):
    """The member's protocol: the clinician-confirmed plan when one exists."""
    published = get_published_plan_for_member(session["user_id"])
    record = None
    if published:
        record = get_assessment(published["assessment_id"])
    if not record:
        record = latest_assessment_for_member(session["user_id"])
    if not record:
        raise HTTPException(status_code=404, detail="No protocol yet")
    from backend.documents.sports_protocol_pdf import build_member_report

    return _pdf_response(build_member_report(record))


@router.post("/reviews/assessments/{assessment_id}/pdf")
def expert_protocol_pdf(assessment_id: str, body: PlanPdfRequest, session: ExpertSession):
    """Clinician copy of the protocol, using the review currently on screen."""
    record = get_assessment(assessment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")
    from backend.documents.sports_protocol_pdf import build_clinician_report

    report = build_clinician_report(record, body.recommendations, body.clinician_note)
    return _pdf_response(report)
