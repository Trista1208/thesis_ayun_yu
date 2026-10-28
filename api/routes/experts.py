from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import ExpertAvailabilityRequest
from api.serializers import expert_to_dict
from api.routes.auth import ExpertSession
from api.deps import load_env

load_env()

from backend.workflow.experts import load_experts, set_expert_availability, get_expert  # noqa: E402

router = APIRouter(prefix="/experts", tags=["experts"])


@router.get("")
def list_all():
    experts = load_experts(include_pool=True)
    return {"experts": [expert_to_dict(e) for e in experts]}


@router.patch("/{expert_id}/availability")
def set_availability(expert_id: str, body: ExpertAvailabilityRequest, session: ExpertSession):
    if body.status not in ("available", "busy", "away"):
        raise HTTPException(status_code=400, detail="Invalid status")
    set_expert_availability(expert_id, body.status)
    expert = get_expert(expert_id)
    if not expert:
        raise HTTPException(status_code=404, detail="Expert not found")
    return expert_to_dict(expert)
