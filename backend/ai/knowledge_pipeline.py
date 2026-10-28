"""
Knowledge pipeline — build LLM corpus and capture clinician-validated knowledge.

Flow:
  1. Doctor reviews recommendations → nodes saved to knowledge store
  2. Expert validates Q&A tickets → nodes saved automatically
  3. Doctor manually captures protocols / notes
  4. Corpus injected into patient/doctor chat at query time
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.storage.knowledge_store import CapturedNode, add_node, get_ticket, list_nodes, list_tickets
from backend.rules.protocol_library import list_protocol_catalog, protocol_record_text

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}", re.IGNORECASE)
_STOP = frozenset(
    {
        "the", "and", "for", "with", "what", "how", "can", "should", "this",
        "that", "from", "your", "you", "are", "have", "does", "about", "please",
        "just", "like", "would", "could", "them", "they", "their", "not", "but",
        "any", "get", "why", "when", "who", "was", "been", "into", "than",
        "then", "also", "more", "some", "our", "its", "ask", "joule", "help",
        "want", "need", "tell", "give", "make",
    }
)


@dataclass
class CorpusEntry:
    id: str
    title: str
    kind: str  # captured | validated-answer | doctor-review
    text: str
    excerpt: str
    locator: str
    created_at: str


def build_corpus(limit: int = 150) -> list[CorpusEntry]:
    """Assemble numbered corpus entries for LLM grounding."""
    entries: list[CorpusEntry] = []

    for protocol in list_protocol_catalog():
        entries.append(
            CorpusEntry(
                id=f"protocol:{protocol['key']}",
                title=protocol["title"],
                kind="ayun-protocol",
                text=protocol_record_text(protocol),
                excerpt=(protocol.get("description") or protocol_record_text(protocol))[:600],
                locator="knowledge/protocols_quick_reference.yml",
                created_at="",
            )
        )

    for node in list_nodes(limit=limit):
        passages = node.passages or []
        passage_text = " | ".join(
            f"[{p.get('locator', 'note')}] {p.get('excerpt', '')}" for p in passages
        )
        body = (
            f"Title: {node.title}\n"
            f"Category: {node.category}\n"
            f"Summary: {node.summary}\n"
            f"Passages: {passage_text}"
        ).strip()
        if node.member_context:
            body += f"\nMember context: {node.member_context[:800]}"
        entries.append(
            CorpusEntry(
                id=node.id,
                title=node.title,
                kind=node.source or "captured",
                text=body,
                excerpt=node.summary[:600],
                locator=f"captured by {node.captured_by}",
                created_at=node.created_at,
            )
        )

    for ticket in list_tickets(status="validated", limit=limit):
        if not ticket.draft_answer:
            continue
        q_a = f"Q: {ticket.question}\nA: {ticket.draft_answer}"
        entries.append(
            CorpusEntry(
                id=ticket.id,
                title=ticket.question[:100],
                kind="validated-answer",
                text=q_a,
                excerpt=q_a[:600],
                locator=f"validated by {ticket.validated_by or 'expert'}",
                created_at=ticket.updated_at,
            )
        )

    return entries[:limit]


def format_corpus_block(entries: list[CorpusEntry]) -> str:
    if not entries:
        return "(No validated knowledge captured yet — answers rely on rule engine context only.)"
    lines = []
    for i, e in enumerate(entries, start=1):
        lines.append(f"[{i}] ({e.kind}) {e.title}\n{e.text}")
    return "\n\n".join(lines)


def format_validated_chat_block(entries: list[CorpusEntry], *, spoken: bool = False) -> str:
    """Prompt block so Talk / typed chat can reuse clinic-validated answers."""
    if not entries:
        return ""
    if spoken:
        lines = [
            "Clinic-validated answers that match this question. Reuse them if they fit. "
            "Do not invent a conflicting programme. Do not say 'validated' or read citations aloud."
        ]
        for entry in entries[:2]:
            lines.append(entry.text[:500])
        return "\n".join(lines)
    lines = [
        "--- Clinic-validated answers (reuse these for similar questions) ---",
    ]
    for i, entry in enumerate(entries, start=1):
        lines.append(f"[Validated {i}] {entry.title}\n{entry.text}\nLocation: {entry.locator}")
    lines.append("--- End of clinic-validated answers ---")
    return "\n\n".join(lines)


def _query_tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")} - _STOP


def _overlap_score(query_tokens: set[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    doc = _query_tokens(text)
    if not doc:
        return 0.0
    overlap = query_tokens & doc
    if not overlap:
        return 0.0
    return len(overlap) / len(query_tokens)


def _entry_from_ticket(ticket) -> CorpusEntry:
    q_a = f"Q: {ticket.question}\nA: {ticket.draft_answer}"
    return CorpusEntry(
        id=ticket.id,
        title=(ticket.question or "")[:100],
        kind="validated-answer",
        text=q_a,
        excerpt=q_a[:600],
        locator=f"validated by {ticket.validated_by or 'expert'}",
        created_at=ticket.updated_at,
    )


def _entry_from_node(node: CapturedNode) -> CorpusEntry:
    passage_text = " | ".join(
        f"[{p.get('locator', 'note')}] {p.get('excerpt', '')}" for p in (node.passages or [])
    )
    body = (
        f"Title: {node.title}\n"
        f"Category: {node.category}\n"
        f"Summary: {node.summary}\n"
        f"Passages: {passage_text}"
    ).strip()
    return CorpusEntry(
        id=node.id,
        title=node.title,
        kind=node.source or "captured",
        text=body,
        excerpt=(node.summary or body)[:600],
        locator=f"captured by {node.captured_by}",
        created_at=node.created_at,
    )


def match_validated_corpus(
    question: str, *, limit: int = 3, member_user_id: str | None = None
) -> list[CorpusEntry]:
    """Question-matched validated tickets and captured nodes for Ask / Talk reuse.

    Answers to another member's own question are case-specific, so they are never
    reused for this member: a ticket (or a node captured from it) counts only when
    it belongs to no member or to `member_user_id`.
    """
    query = (question or "").strip()
    if not query or limit <= 0:
        return []
    qtok = _query_tokens(query)
    if not qtok:
        return []

    scored: dict[str, tuple[float, CorpusEntry]] = {}
    seen_tickets: set[str] = set()
    nodes = list(list_nodes(limit=500))
    nodes_by_id = {node.id: node for node in nodes}

    def _other_members(ticket) -> bool:
        owner = (getattr(ticket, "member_user_id", None) or "").strip()
        return bool(owner) and owner != (member_user_id or "")

    validated = list(list_tickets(status="validated", limit=500))
    by_question = {(t.question or "").strip().lower(): t for t in validated}

    def _node_from_other_member(node) -> bool:
        src = (node.source_ticket_id or "").strip()
        ticket = get_ticket(src) if src else by_question.get((node.title or "").strip().lower())
        if ticket:
            return _other_members(ticket)
        # A member's own question whose owner can no longer be traced: do not reuse it.
        return node.source == "validated_ticket" and "patient" in (node.tags or [])

    for ticket in validated:
        if not (ticket.draft_answer or "").strip() or _other_members(ticket):
            continue
        score = _overlap_score(qtok, f"{ticket.question} {ticket.draft_answer} {ticket.category}")
        if score < 0.12:
            continue
        seen_tickets.add(ticket.id)
        scored[f"qa:{ticket.id}"] = (score, _entry_from_ticket(ticket))

    for node in nodes:
        source_ticket = (node.source_ticket_id or "").strip()
        if source_ticket and source_ticket in seen_tickets:
            continue
        if _node_from_other_member(node):
            continue
        score = _overlap_score(qtok, f"{node.title} {node.summary} {node.category}")
        if score < 0.15:
            continue
        scored[f"node:{node.id}"] = (score, _entry_from_node(node))

    try:
        from backend.ai.knowledge_search import search_knowledge

        result = search_knowledge(query, limit=16)
        for hit in result.get("results") or []:
            kind = (hit.get("kind") or "").strip()
            if kind not in {"qa", "node"}:
                continue
            try:
                boost = float(hit.get("score") or 0)
            except (TypeError, ValueError):
                boost = 0.0
            raw_id = str(hit.get("id") or "")
            if kind == "qa":
                ticket_id = raw_id.removeprefix("qa:")
                ticket = get_ticket(ticket_id)
                if not ticket or ticket.status != "validated" or not (ticket.draft_answer or "").strip():
                    continue
                if _other_members(ticket):
                    continue
                key = f"qa:{ticket.id}"
                seen_tickets.add(ticket.id)
                prev = scored.get(key, (0.0, _entry_from_ticket(ticket)))
                scored[key] = (max(prev[0], boost), prev[1] if key in scored else _entry_from_ticket(ticket))
            else:
                node_id = raw_id.removeprefix("node:")
                node = nodes_by_id.get(node_id)
                if not node or _node_from_other_member(node):
                    continue
                source_ticket = (node.source_ticket_id or "").strip()
                if source_ticket and source_ticket in seen_tickets:
                    continue
                key = f"node:{node.id}"
                prev = scored.get(key, (0.0, _entry_from_node(node)))
                scored[key] = (max(prev[0], boost), prev[1] if key in scored else _entry_from_node(node))
    except Exception:
        pass

    ranked = sorted(scored.values(), key=lambda item: item[0], reverse=True)
    out: list[CorpusEntry] = []
    titles: set[str] = set()
    for score, entry in ranked:
        key = (entry.title or "").strip().lower()
        if score > 0 and key not in titles:  # a ticket and its captured node are one source
            titles.add(key)
            out.append(entry)
    return out[:limit]


def capture_from_doctor_review(
    export_payload: dict[str, Any],
    clinician_name: str,
) -> list[CapturedNode]:
    """
    Turn a signed doctor review export into knowledge nodes.
    Each active recommendation + clinician notes becomes one node.
    """
    saved: list[CapturedNode] = []
    member = export_payload.get("member") or {}
    profile = export_payload.get("personal_profile") or {}
    member_ctx_parts = [
        f"Age: {member.get('age')}, Sex: {member.get('sex')}, Group: {member.get('group')}",
    ]
    if profile.get("goals"):
        member_ctx_parts.append(f"Goals: {', '.join(profile['goals'])}")
    if profile.get("injuries"):
        member_ctx_parts.append(f"Injuries: {profile['injuries']}")
    member_context = "\n".join(member_ctx_parts)

    for rec in export_payload.get("recommendations") or []:
        title = (rec.get("title") or "Recommendation").strip()
        if not title:
            continue
        action_items = rec.get("action_items") or ""
        notes = rec.get("clinician_notes") or ""
        priority = rec.get("reviewed_priority") or rec.get("original_priority") or "Medium"
        category = rec.get("category") or "Clinical"
        summary = (
            f"Priority: {priority}\n"
            f"Action items:\n{action_items}"
        )
        if notes.strip():
            summary += f"\nClinician notes: {notes.strip()}"

        node = CapturedNode.create(
            title=title,
            category=category,
            summary=summary,
            passages=[{"excerpt": action_items[:1200], "locator": f"review by {clinician_name}"}],
            captured_by=clinician_name,
            source="doctor_review",
            member_context=member_context,
            tags=[priority.lower(), category.lower().replace(" ", "_")],
        )
        add_node(node)
        saved.append(node)

    return saved


def capture_manual_knowledge(
    title: str,
    category: str,
    content: str,
    captured_by: str,
    tags: list[str] | None = None,
) -> CapturedNode:
    node = CapturedNode.create(
        title=title.strip(),
        category=category.strip() or "General",
        summary=content.strip()[:2000],
        passages=[{"excerpt": content.strip(), "locator": "manual entry"}],
        captured_by=captured_by,
        source="manual",
        tags=tags or [],
    )
    return add_node(node)


def build_reviewed_recommendation_context(
    triggered: list[Any],
    doctor_edits: dict[str, dict],
    doctor_removed: set[int],
    doctor_custom_recs: list[dict],
) -> str:
    """Build chat context from clinician-reviewed recommendations (not raw engine output)."""
    lines = ["── CLINICIAN-REVIEWED RECOMMENDATIONS ──"]
    n = 0
    for i, rec in enumerate(triggered):
        if i in doctor_removed:
            continue
        key = f"rec_{i}"
        ed = doctor_edits.get(key, {})
        title = ed.get("title") or rec.title
        priority = ed.get("priority") or rec.priority
        items = ed.get("items") or "\n".join(f"• {a}" for a in rec.action_items)
        notes = ed.get("notes") or ""
        n += 1
        lines.append(f"\n{n}. [{priority}] {title}")
        if items.strip():
            lines.append(items.strip())
        if notes.strip():
            lines.append(f"Clinician note: {notes.strip()}")

    for ci, _ in enumerate(doctor_custom_recs):
        key = f"custom_{ci}"
        ed = doctor_edits.get(key, {})
        title = ed.get("title") or "Custom recommendation"
        priority = ed.get("priority") or "Medium"
        items = ed.get("items") or ""
        notes = ed.get("notes") or ""
        n += 1
        lines.append(f"\n{n}. [{priority}] {title} (clinician-added)")
        if items.strip():
            lines.append(items.strip())
        if notes.strip():
            lines.append(f"Clinician note: {notes.strip()}")

    if n == 0:
        return ""
    return "\n".join(lines)
