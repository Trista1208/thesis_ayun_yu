from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import (
    ExpertTicketChatRequest,
    ExpertTicketPolishRequest,
    GuestTicketLookupRequest,
    TicketClaimRequest,
    TicketCreateRequest,
    TicketUpdateRequest,
)
from api.serializers import ticket_to_expert_dict, ticket_to_member_dict
from api.routes.auth import ExpertSession, MemberSession
from api.routes.chat import _ai_error_message
from api.deps import load_env

load_env()

from backend.workflow.ticket_service import (  # noqa: E402
    claim_member_tickets,
    create_expert_ticket,
    list_tickets_for_expert,
    list_tickets_for_member_user,
    lookup_guest_tickets,
)
from backend.storage.knowledge_store import get_ticket, save_draft_answer, validate_ticket, delete_ticket  # noqa: E402
from backend.ai.expert_ticket_assistant import (  # noqa: E402
    expert_ticket_chat,
    polish_draft_answer,
    suggest_draft_answer,
    ticket_context_summary,
)
from backend.workflow.experts import get_expert  # noqa: E402
from backend.storage import user_store  # noqa: E402

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _expert_id(session: dict) -> str:
    return session.get("expert_id") or "general_pool"


def _member_display_names(user, session: dict) -> list[str]:
    return [
        user.display_name,
        user.personal_profile.get("name", ""),
        session.get("name", ""),
        session.get("email", "").split("@")[0],
    ]


@router.get("/mine")
def my_tickets(session: MemberSession):
    """Member view: only questions linked to this account."""
    user = user_store.ensure_from_session(session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    claim_member_tickets(
        session["user_id"],
        [],
        display_names=_member_display_names(user, session),
    )
    tickets = list_tickets_for_member_user(session["user_id"])
    return {"tickets": [ticket_to_member_dict(t) for t in tickets]}


@router.post("/claim")
def claim_tickets(body: TicketClaimRequest, session: MemberSession):
    """Link guest-submitted tickets to the logged-in member account."""
    user = user_store.ensure_from_session(session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    claimed = claim_member_tickets(
        session["user_id"],
        body.ticket_ids,
        display_names=_member_display_names(user, session),
    )
    tickets = list_tickets_for_member_user(session["user_id"])
    return {
        "claimed": len(claimed),
        "tickets": [ticket_to_member_dict(t) for t in tickets],
    }


@router.post("/guest")
def guest_tickets(body: GuestTicketLookupRequest):
    """Guest view: only tickets saved locally on this device (unclaimed ids)."""
    tickets = lookup_guest_tickets(body.ticket_ids)
    return {"tickets": [ticket_to_member_dict(t) for t in tickets]}


@router.get("")
def expert_inbox(session: ExpertSession, status: str | None = None):
    """Expert-only: all member questions across the platform."""
    expert_id = _expert_id(session)
    tickets = list_tickets_for_expert(expert_id, status=status)
    return {"tickets": [ticket_to_expert_dict(t) for t in tickets], "expert_id": expert_id}


@router.post("")
def create_ticket(body: TicketCreateRequest, session: MemberSession):
    """Submit a question — linked to the signed-in member account."""
    member_user_id = session["user_id"]
    from_name = body.from_name
    if session.get("name"):
        from_name = session.get("name") or from_name
    try:
        ticket = create_expert_ticket(
            question=body.question,
            from_role=body.from_role,
            from_name=from_name,
            category=body.category,
            assigned_expert_id=body.assigned_expert_id,
            member_snapshot=body.member_snapshot,
            chat_context=body.chat_context,
            source=body.source,
            member_user_id=member_user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ticket_to_member_dict(ticket)


@router.get("/{ticket_id}")
def get_one(ticket_id: str, session: ExpertSession):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    expert = get_expert(ticket.assigned_expert_id)
    data = ticket_to_expert_dict(ticket)
    data["assigned_expert_name"] = expert.name if expert else "Team"
    data.update(ticket_context_summary(ticket))
    return data


@router.post("/{ticket_id}/assist/chat")
def expert_ticket_assist_chat(ticket_id: str, body: ExpertTicketChatRequest, session: ExpertSession):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        messages = [{"role": m.role, "content": m.content} for m in body.messages]
        reply, citations = expert_ticket_chat(ticket, messages)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=_ai_error_message(exc)) from exc
    return {"reply": reply, "citations": citations}


@router.post("/{ticket_id}/assist/polish")
def expert_ticket_assist_polish(ticket_id: str, body: ExpertTicketPolishRequest, session: ExpertSession):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        polished = polish_draft_answer(ticket, body.draft_answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=_ai_error_message(exc)) from exc
    return {"polished": polished}


@router.post("/{ticket_id}/assist/suggest")
def expert_ticket_assist_suggest(ticket_id: str, session: ExpertSession):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        suggestion = suggest_draft_answer(ticket)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=_ai_error_message(exc)) from exc
    return {"suggestion": suggestion}


@router.patch("/{ticket_id}")
def update_one(ticket_id: str, body: TicketUpdateRequest, session: ExpertSession):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if body.action == "validate":
        updated = validate_ticket(ticket_id, session["name"], body.draft_answer or None)
    else:
        updated = save_draft_answer(ticket_id, body.draft_answer)
    if not updated:
        raise HTTPException(status_code=400, detail="Could not update ticket")
    return ticket_to_expert_dict(updated)


@router.delete("/{ticket_id}")
def remove_one(ticket_id: str, session: ExpertSession):
    """Expert-only: dismiss / delete a ticket from the inbox."""
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if not delete_ticket(ticket_id):
        raise HTTPException(status_code=400, detail="Could not delete ticket")
    return {"ok": True, "id": ticket_id}
