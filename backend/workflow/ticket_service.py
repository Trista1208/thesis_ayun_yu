"""Unified ticket creation with expert assignment."""

from __future__ import annotations

from typing import Any

from backend.workflow.experts import get_expert, list_available_experts
from backend.storage.knowledge_store import KnowledgeTicket, add_ticket


def create_expert_ticket(
    question: str,
    from_role: str,
    from_name: str,
    *,
    category: str = "General",
    assigned_expert_id: str = "general_pool",
    member_snapshot: dict[str, Any] | None = None,
    chat_context: str = "",
    source: str = "patient_direct",
    member_user_id: str | None = None,
) -> KnowledgeTicket:
    """Create a ticket for the expert queue. Falls back to general pool if expert away."""
    q = question.strip()
    if not q:
        raise ValueError("Question is required")

    expert_id = assigned_expert_id or "general_pool"
    expert = get_expert(expert_id)
    if expert and not expert.is_available and expert_id != "general_pool":
        available = list_available_experts(include_pool=False)
        matched = next(
            (e for e in available if category in e.specialties or category == "General"),
            None,
        )
        expert_id = matched.id if matched else "general_pool"

    ticket = KnowledgeTicket.create(
        question=q,
        from_role=from_role,
        from_name=from_name or ("Member" if from_role == "patient" else "Clinician"),
        member_snapshot=member_snapshot or {},
        chat_context=chat_context[:3000] if chat_context else "",
        assigned_expert_id=expert_id,
        category=category,
        source=source,
        member_user_id=member_user_id,
    )
    add_ticket(ticket)
    return ticket


def list_tickets_for_expert(expert_id: str, status: str | None = None) -> list[KnowledgeTicket]:
    """Experts see every member question — used to build the validated knowledge base."""
    from backend.storage.knowledge_store import list_tickets

    _ = expert_id  # kept for API compatibility
    return list_tickets(status=status, limit=200)


def list_tickets_for_member_user(member_user_id: str) -> list[KnowledgeTicket]:
    from backend.storage.knowledge_store import list_tickets_for_member_user

    return list_tickets_for_member_user(member_user_id)


def list_tickets_for_member(from_name: str) -> list[KnowledgeTicket]:
    """Legacy name-based lookup (Streamlit). Prefer member_user_id via the API."""
    from backend.storage.knowledge_store import list_tickets

    name = (from_name or "").strip().lower()
    tickets = list_tickets(limit=200)
    if not name:
        return []
    return [t for t in tickets if (t.from_name or "").strip().lower() == name and not t.member_user_id]


def claim_member_tickets(
    member_user_id: str,
    ticket_ids: list[str],
    *,
    display_names: list[str] | None = None,
) -> list[KnowledgeTicket]:
    from backend.storage.knowledge_store import claim_tickets_for_member

    return claim_tickets_for_member(
        ticket_ids,
        member_user_id,
        display_names=display_names,
    )


def lookup_guest_tickets(ticket_ids: list[str]) -> list[KnowledgeTicket]:
    from backend.storage.knowledge_store import lookup_guest_tickets as _lookup

    return _lookup(ticket_ids)
