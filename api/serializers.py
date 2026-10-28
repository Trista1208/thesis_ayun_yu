"""Convert backend dataclasses to JSON-serializable dicts."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from api.deps import load_env

load_env()

from backend.rules.recommendation_api import RecommendationResult  # noqa: E402
from backend.workflow.experts import Expert  # noqa: E402
from backend.storage.knowledge_store import CapturedNode, KnowledgeTicket  # noqa: E402


def recommendation_to_dict(result: RecommendationResult) -> dict[str, Any]:
    from backend.rules.training_zones import zones_as_dict

    return {
        "triggered": [asdict(r) for r in result.triggered],
        "ratings": [asdict(r) for r in result.ratings],
        "training_zones": zones_as_dict(result.training_zones) if result.training_zones else None,
        "protocol_recommendations": result.protocol_recommendations,
        "context_for_llm": result.context_for_llm,
        "member_summary": result.member_summary,
        "sex_group": result.sex_group,
        "age_group": result.age_group,
        "personal_context": result.personal_context,
    }


def ticket_to_dict(ticket: KnowledgeTicket) -> dict[str, Any]:
    return asdict(ticket)


def ticket_to_member_dict(ticket: KnowledgeTicket) -> dict[str, Any]:
    """Member-safe view — no other members' health snapshots or chat context."""
    return {
        "id": ticket.id,
        "question": ticket.question,
        "status": ticket.status,
        "draft_answer": ticket.draft_answer,
        "validated_by": ticket.validated_by,
        "category": ticket.category,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "source": ticket.source,
    }


def ticket_to_expert_dict(ticket: KnowledgeTicket) -> dict[str, Any]:
    return asdict(ticket)


def node_to_member_dict(node: CapturedNode) -> dict[str, Any]:
    """Public-safe knowledge node — no member-specific context."""
    return {
        "id": node.id,
        "title": node.title,
        "category": node.category,
        "summary": node.summary,
        "captured_by": node.captured_by,
        "source": node.source,
        "tags": node.tags,
        "created_at": node.created_at,
    }


def node_to_expert_dict(node: CapturedNode) -> dict[str, Any]:
    return asdict(node)


def node_to_dict(node: CapturedNode) -> dict[str, Any]:
    return node_to_expert_dict(node)


def expert_to_dict(expert: Expert) -> dict[str, Any]:
    return {
        "id": expert.id,
        "name": expert.name,
        "role": expert.role,
        "specialties": expert.specialties,
        "default_hours": expert.default_hours,
        "status": expert.status,
        "status_label": expert.status_label,
        "is_available": expert.is_available,
    }


def dataclass_list(items: list[Any]) -> list[dict[str, Any]]:
    return [asdict(x) if is_dataclass(x) else x for x in items]
