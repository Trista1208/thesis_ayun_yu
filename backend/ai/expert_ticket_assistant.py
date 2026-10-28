"""Expert ticket assistant — LLM help for clinicians answering member questions."""

from __future__ import annotations

from typing import Any

from backend.ai import chatbot as cb
from backend.ai.evipedia_refs import search_evipedia
from backend.storage.knowledge_store import KnowledgeTicket
from backend.storage.plan_review_store import list_member_directory

from backend.storage import user_store


_EXPERT_ASSISTANT_INSTRUCTIONS = """
You are helping an AYUN sports scientist about one member. Speak to the clinician, not the member.

Write a short note they can scan in 20 seconds. About 120–180 words. Stop there.

Use this shape and nothing heavier:
Read
- 2 or 3 facts from the checkup that matter for this question. Plain numbers with units (22 kg, VO2max 22).

Do
- 2 or 3 concrete training actions. Name the exercise, dose, and one safety limit.
  When a numbered AYUN protocol or template is listed, use that dose and cite [n].

Say to the member
- 2 short sentences they can paste or adapt.

Sources
- Cite AYUN protocols/templates as [n] and Evipedia articles as [Web n], same as member Ask Joule.
- Cite [Member] at most once. Do not invent sources.

Rules:
- No LaTeX, no $...$, no \\text, no tables, no horizontal rules.
- No title like "Clinical breakdown" or "Patient Profile".
- Never invent values. Flag if something needs an in-person check.
"""


def _format_member_data(member_data: dict[str, Any]) -> str:
    lines = []
    for key, value in member_data.items():
        if value is None or value == "":
            continue
        label = key.split("::")[-1] if "::" in key else key
        lines.append(f"  {label}: {value}")
    return "\n".join(lines) if lines else "  (no checkup values recorded)"


def _format_personal_profile(profile: dict[str, Any]) -> str:
    if not profile:
        return "  (no personal profile recorded)"
    area = profile.get("geographic_area") or ""
    detail = (profile.get("location_detail") or "").strip()
    location = f"{area} ({detail})" if area and detail else (detail or area)
    rows = [
        ("Name", profile.get("name") or ""),
        ("Goals", ", ".join(profile.get("goals") or [])),
        ("Activity level", profile.get("activity_level") or ""),
        ("Sports", ", ".join(profile.get("sport_prefs") or [])),
        ("Location", location),
        ("Health status", profile.get("health_status") or ""),
        ("Existing conditions", profile.get("existing_conditions") or ""),
        ("Smoking", profile.get("smoking_status") or ""),
        ("Alcohol", profile.get("alcohol_use") or ""),
        ("Sleep", profile.get("sleep_hours") or ""),
        ("Diet", profile.get("diet") or ""),
        ("Stress", profile.get("stress") or ""),
        ("Depression", profile.get("depression") or ""),
        ("Optimism", profile.get("optimism") or ""),
        ("Injuries", profile.get("injuries") or ""),
        ("Notes", profile.get("notes") or ""),
    ]
    return "\n".join(
        f"  {label}: {value}"
        for label, value in rows
        if value and str(value) not in {"Not specified", "Not assessed"}
    ) or "  (no personal profile recorded)"


def _directory_entry_for_ticket(ticket: KnowledgeTicket) -> dict[str, Any] | None:
    uid = ticket.member_user_id
    name = (ticket.from_name or "").strip().lower()
    for entry in list_member_directory(limit=500):
        if uid and entry.get("member_user_id") == uid:
            return entry
        if not uid and name and (entry.get("member_name") or "").strip().lower() == name:
            return entry
    return None


def _resolved_member(ticket: KnowledgeTicket) -> dict[str, Any]:
    """Merge directory, account, ticket snapshot, and latest plan so checkup is not dropped."""
    entry = _directory_entry_for_ticket(ticket)
    user = user_store.get_user(ticket.member_user_id) if ticket.member_user_id else None
    profile: dict[str, Any] = {}
    data: dict[str, Any] = {}
    if ticket.member_snapshot:
        data.update(ticket.member_snapshot)
    if user:
        profile.update(user.personal_profile or {})
        data.update(user.member_data or {})
    if entry:
        profile.update(entry.get("personal_profile") or {})
        data.update(entry.get("member_data") or {})
    if not data and ticket.member_user_id:
        try:
            from backend.storage.plan_review_store import latest_assessment_for_member

            latest = latest_assessment_for_member(ticket.member_user_id)
            if latest:
                data.update(latest.member_data or {})
                profile.update(latest.personal_profile or {})
        except Exception:
            pass
    return {
        "entry": entry,
        "personal_profile": profile,
        "member_data": data,
        "email": (entry or {}).get("email") or (user.email if user else ""),
        "pseudonym": (entry or {}).get("pseudonym") or ((user.pseudonym if user else "") or ""),
        "member_name": (
            (entry or {}).get("member_name")
            or (user.display_name if user else "")
            or ticket.from_name
            or ""
        ),
    }


def build_ticket_member_context(ticket: KnowledgeTicket) -> str:
    """Assemble member profile + checkup + plan context for expert LLM."""
    sections: list[str] = []
    resolved = _resolved_member(ticket)

    if resolved["member_name"]:
        sections.append(f"Member name: {resolved['member_name']}")
    if ticket.category:
        sections.append(f"Ticket category: {ticket.category}")

    sections.append("── PERSONAL PROFILE ──")
    sections.append(_format_personal_profile(resolved["personal_profile"]))
    sections.append("── CHECKUP / ASSESSMENT VALUES ──")
    sections.append(_format_member_data(resolved["member_data"]))
    if resolved["email"]:
        sections.append(f"Account email: {resolved['email']}")
    entry = resolved["entry"]
    assessments = (entry or {}).get("assessments") or []
    if assessments:
        latest = assessments[0]
        sections.append(
            f"Latest saved assessment: {latest.get('id')} "
            f"({latest.get('triggered_count', 0)} recommendations, "
            f"{'published' if latest.get('has_published_plan') else 'not published'})"
        )

    if ticket.chat_context:
        sections.append("── CONTEXT FROM ASK AI / ASSESSMENT ──")
        sections.append(ticket.chat_context[:4000])

    sections.append("── MEMBER QUESTION ──")
    sections.append(ticket.question)
    if ticket.draft_answer:
        sections.append("── DRAFT ANSWER IN PROGRESS ──")
        sections.append(ticket.draft_answer)

    return "\n\n".join(sections)


def evipedia_matches_for_ticket(ticket: KnowledgeTicket, *, limit: int = 5) -> dict[str, Any]:
    query = " ".join(p for p in [ticket.question, ticket.chat_context or ""] if p).strip()
    return search_evipedia(query, category=ticket.category or "", limit=limit)


def _clinician_question(ticket: KnowledgeTicket, messages: list[dict[str, str]]) -> str:
    last = ""
    for m in reversed(messages):
        if m.get("role") == "user" and (m.get("content") or "").strip():
            last = m["content"].strip()
            break
    return " ".join(p for p in [last, ticket.question, ticket.chat_context or ""] if p).strip()


def _member_context_with_protocols(ticket: KnowledgeTicket) -> str:
    ctx = build_ticket_member_context(ticket)
    resolved = _resolved_member(ticket)
    data = resolved.get("member_data") or {}
    if not data:
        return ctx
    try:
        from backend.rules.recommendation_api import get_recommendations
        from backend.rules.protocol_library import format_protocols_for_llm

        result = get_recommendations(data)
        block = format_protocols_for_llm(result.triggered, result.ratings, "")
        if block:
            return f"{ctx}\n\n{block}"
    except Exception:
        pass
    return ctx


def _expert_sources(ticket: KnowledgeTicket, question: str) -> tuple[str, list, list[dict], str]:
    """Same numbered protocol + Evipedia list as member Ask Joule."""
    from backend.ai.ask_engine import _format_sources_for_llm, _grounded_corpus, _web_hits

    member_context = _member_context_with_protocols(ticket)
    corpus = _grounded_corpus(member_context, question)
    web_hits = _web_hits(question, corpus)
    return member_context, corpus, web_hits, _format_sources_for_llm(corpus, web_hits, member_context)


def _expert_ask_context(ticket: KnowledgeTicket, question: str = "") -> str:
    """Same member-context channel as Ask Joule, plus numbered sources."""
    member_context, _corpus, _web, source_block = _expert_sources(
        ticket, question or ticket.question
    )
    return "\n\n".join(
        [
            _EXPERT_ASSISTANT_INSTRUCTIONS.strip(),
            member_context,
            "Numbered sources (cite like member Ask Joule):",
            source_block,
        ]
    )


def expert_ticket_chat(
    ticket: KnowledgeTicket,
    messages: list[dict[str, str]],
) -> tuple[str, list[dict[str, Any]]]:
    cleaned: list[dict[str, str]] = []
    for m in messages[-12:]:
        role = m.get("role", "user")
        if role not in ("user", "assistant"):
            role = "user"
        content = (m.get("content") or "").strip()
        if content:
            cleaned.append({"role": role, "content": content})
    if not cleaned:
        raise ValueError("Ask a question about this member first.")
    question = _clinician_question(ticket, cleaned)
    member_context, corpus, web_hits, _sources = _expert_sources(ticket, question)
    reply = cb.chat(
        cleaned,
        _expert_ask_context(ticket, question),
        stream=False,
        max_tokens=700,
    )
    if not (reply or "").strip():
        raise RuntimeError("The Ask Joule model returned an empty answer. Try again.")
    from backend.ai.ask_engine import (
        _build_citations,
        _ensure_source_markers,
        _indices_from_answer,
        _token_key,
    )

    text = _ensure_source_markers(reply.strip(), corpus, web_hits)
    used = _indices_from_answer(text)
    keys = {_token_key(item) for item in used}
    citations = [
        row
        for row in _build_citations(used, corpus, web_hits, member_context)
        if row.get("index") in keys and row.get("family") in {"protocol", "web"}
    ]
    return text, citations


def polish_draft_answer(ticket: KnowledgeTicket, draft_answer: str) -> str:
    """Fix spelling, grammar, and clarity — member-facing tone preserved."""
    text = (draft_answer or ticket.draft_answer or "").strip()
    if not text:
        raise ValueError("No draft answer to polish")

    prompt = (
        "You are a clinical editor for AYUN sports health. "
        "Fix spelling, grammar, and clarity in the clinician's draft answer to a member. "
        "Keep the same meaning, length, and supportive tone. "
        "Do not add disclaimers or change clinical advice. "
        "Return ONLY the polished answer text — no quotes, labels, or explanation.\n\n"
        f"Member question: {ticket.question}\n\n"
        f"Draft answer:\n{text}"
    )
    return cb.complete([{"role": "user", "content": prompt}], temperature=0.2, max_tokens=800)


def suggest_draft_answer(ticket: KnowledgeTicket) -> str:
    """Suggest a member-facing draft answer using the same Ask Joule model."""
    user_msg = (
        "Draft a suggested answer the clinician can edit and send to the member. "
        "Write directly to the member in clear, supportive language (2–6 short paragraphs or bullets). "
        "Personalise using their profile and checkup data where relevant. "
        "Return ONLY the suggested answer text — no preamble."
    )
    reply, _citations = expert_ticket_chat(
        ticket, [{"role": "user", "content": user_msg}]
    )
    return reply


def ticket_context_summary(ticket: KnowledgeTicket) -> dict[str, Any]:
    resolved = _resolved_member(ticket)
    evipedia_result = evipedia_matches_for_ticket(ticket)
    return {
        "member_context_text": build_ticket_member_context(ticket),
        "personal_profile": resolved["personal_profile"],
        "member_data": resolved["member_data"],
        "email": resolved["email"],
        "pseudonym": resolved["pseudonym"],
        "member_name": resolved["member_name"],
        "has_directory_profile": bool(resolved["entry"] or resolved["member_data"] or resolved["personal_profile"]),
        "evipedia_matches": evipedia_result["matches"],
        "evipedia_match_mode": evipedia_result["mode"],
    }
