from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from pydantic import BaseModel, Field

from api.schemas import ChatRequest, AskRequest
from api.deps import load_env
from api.routes.auth import MemberSession

load_env()

from backend.ai import chatbot as cb  # noqa: E402
from backend.ai.ask_engine import ask_with_knowledge  # noqa: E402
from backend.rules.protocol_library import enrich_member_context  # noqa: E402
from backend.rules.member_signals import read_signals, signals_block  # noqa: E402
from backend.voice.talk_agent import (  # noqa: E402
    encode_ticket_propose,
    propose_ticket_spoken,
    ticket_question_from_talk,
)
from backend.storage import user_store  # noqa: E402

router = APIRouter(prefix="/chat", tags=["chat"])


class AskHistorySave(BaseModel):
    question: str
    answer: str
    mode: str = "cited"
    citations: list = Field(default_factory=list)
    confidence: str = ""


def _maybe_file_talk_ticket(
    reply: str,
    messages: list[dict],
    body: ChatRequest,
    session: dict | None,
) -> str:
    spoken, question = ticket_question_from_talk(messages, reply)
    if not question:
        return spoken
    spoken = propose_ticket_spoken(spoken, body.language)
    return f"{spoken}\n\n{encode_ticket_propose(question)}"


def _with_validated_corpus(
    context: str, question: str, *, spoken: bool = False, member_user_id: str | None = None
) -> str:
    try:
        from backend.ai.knowledge_pipeline import format_validated_chat_block, match_validated_corpus

        hits = match_validated_corpus(question, limit=2 if spoken else 3, member_user_id=member_user_id)
        block = format_validated_chat_block(hits, spoken=spoken)
        if not block:
            return context
        return f"{context}\n\n{block}".strip()
    except Exception:
        return context


def _with_web_sources(context: str, question: str) -> str:
    try:
        from backend.ai.ask_engine import _web_hits
        from backend.ai.evipedia_refs import format_evipedia_block

        hits = _web_hits(question)
        if not hits:
            return context
        return f"{context}\n\n{format_evipedia_block(hits)}".strip()
    except Exception:
        return context


def _ai_error_message(exc: Exception) -> str:
    msg = str(exc).strip() or exc.__class__.__name__
    if "OPENAI_API_KEY" in msg or "GitHub token" in msg or "GITHUB_TOKEN" in msg or "not configured" in msg.lower():
        return cb._deployment_hint() or msg
    lowered = msg.lower()
    if (
        "401" in msg
        or "unauthorized" in lowered
        or "invalid api key" in lowered
        or "incorrect api key" in lowered
        or "authentication" in lowered
    ):
        return "The local model rejected the request. Confirm Ollama is running and try again."
    if "Connection error" in msg or "ProxyError" in msg or "connect" in lowered:
        if not cb.is_configured():
            return cb._deployment_hint() or "AI is not configured on the server."
        return "Could not reach the model. Start Ollama on this computer, or add a free Gemini key on a remote host."
    if "Read-only file system" in msg or "Errno 30" in msg:
        return "Server storage is read-only — redeploy latest main (uses /tmp on Vercel) or set Supabase keys."
    if any(
        token in lowered
        for token in ("high demand", "unavailable", "overloaded", "rate limit", "too many requests", "try again later")
    ):
        return "Joule is busy right now. Please try again in a moment."
    return "Joule couldn't answer just now. Please try again."


@router.get("/status")
def chat_status():
    return cb.ai_config()


@router.get("/history")
def ask_history(session: MemberSession):
    from backend.ai.ask_history import list_ask_history

    user_id = (session or {}).get("user_id") or ""
    if not user_id:
        raise HTTPException(status_code=401, detail="Sign in to see saved questions.")
    return {"exchanges": list_ask_history(user_id)}


@router.post("/history")
def save_ask_history(body: AskHistorySave, session: MemberSession):
    from backend.ai.ask_history import save_ask_exchange

    user_id = (session or {}).get("user_id") or ""
    if not user_id:
        raise HTTPException(status_code=401, detail="Sign in to save this conversation.")
    saved = save_ask_exchange(
        user_id,
        question=body.question,
        answer=body.answer,
        mode=body.mode,
        citations=body.citations,
        confidence=body.confidence,
    )
    if not saved:
        raise HTTPException(status_code=400, detail="Nothing to save.")
    return {"exchange": saved}


@router.delete("/history")
def clear_ask_history(session: MemberSession):
    from backend.ai.ask_history import delete_ask_history

    user_id = (session or {}).get("user_id") or ""
    if not user_id:
        raise HTTPException(status_code=401, detail="Sign in to clear saved questions.")
    deleted = delete_ask_history(user_id)
    return {"ok": True, "deleted": deleted}


@router.post("")
def chat(body: ChatRequest, session: MemberSession):
    if not cb.is_configured():
        return {"error": cb._deployment_hint() or "AI is not configured", "reply": ""}
    try:
        messages = [{"role": m.role, "content": m.content} for m in body.messages][-8:]
        question = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        context = enrich_member_context(body.context, question=question)
        context += "\n\n" + signals_block(read_signals(body.context))
        context = _with_validated_corpus(
            context, question, spoken=body.spoken, member_user_id=(session or {}).get("user_id")
        )
        if not body.spoken:
            context = _with_web_sources(context, question)
        reply = cb.chat(messages, context, stream=False, spoken=body.spoken, language=body.language)
        if body.spoken:
            reply = _maybe_file_talk_ticket(reply, messages, body, session)
        return {"reply": reply}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=_ai_error_message(exc)) from exc


@router.post("/stream")
def chat_stream(body: ChatRequest, session: MemberSession):
    if not cb.is_configured():
        return StreamingResponse(iter([cb._deployment_hint() or "AI is not configured"]), media_type="text/plain")

    messages = [{"role": m.role, "content": m.content} for m in body.messages][-8:]
    question = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    context = enrich_member_context(body.context, question=question)
    context += "\n\n" + signals_block(read_signals(body.context))
    context = _with_validated_corpus(
        context, question, spoken=body.spoken, member_user_id=(session or {}).get("user_id")
    )
    if not body.spoken:
        context = _with_web_sources(context, question)

    def generate():
        gen = cb.chat(messages, context, stream=True, spoken=body.spoken, language=body.language)
        if not body.spoken:
            for chunk in gen:
                yield chunk
            return
        reply = "".join(gen)
        yield _maybe_file_talk_ticket(reply, messages, body, session)

    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/ask")
def ask_knowledge(body: AskRequest, session: MemberSession):
    if not cb.is_configured():
        return {
            "error": "AI not configured",
            "answer": cb._deployment_hint() or "AI is not configured. Start Ollama (free) and restart the API.",
            "confidence": "low",
            "citations": [],
            "should_route_as_ticket": False,
            "ticket_id": None,
        }
    member_user_id = session["user_id"] if session else None
    viewer_name = body.from_name
    if session and session.get("name"):
        viewer_name = session.get("name") or viewer_name
    retention_days = 30
    if member_user_id:
        user = user_store.get_user(member_user_id)
        if user:
            privacy = user.privacy_settings or {}
            if not privacy.get("memory_enabled", True):
                retention_days = 0
            else:
                retention_days = int(privacy.get("memory_retention_days", 30))
    try:
        resp = ask_with_knowledge(
            question=body.question,
            member_context=enrich_member_context(
                body.context,
                question=body.question,
                member_data=body.member_snapshot,
            ),
            member_snapshot=body.member_snapshot,
            viewer_name=viewer_name,
            viewer_role=body.from_role,
            member_user_id=member_user_id,
            auto_ticket=body.auto_ticket,
            retention_days=retention_days,
        )
        return {
            "answer": resp.answer,
            "confidence": resp.confidence,
            "citations": resp.citations,
            "should_route_as_ticket": resp.should_route_as_ticket,
            "ticket_id": resp.ticket_id,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=_ai_error_message(exc)) from exc
