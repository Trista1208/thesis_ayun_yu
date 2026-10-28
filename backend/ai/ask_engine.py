"""
Grounded Q&A engine — member context + validated knowledge corpus + ticket routing.

Inspired by institutional ask flows: answer from corpus when possible,
route to human expert when confidence is low.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from backend.ai.knowledge_pipeline import CorpusEntry, match_validated_corpus
from backend.ai.memory_store import (
    build_episodic_memory_block,
    build_working_memory_block,
    store_session_memory,
    summarise_session,
)
from backend.workflow.ticket_service import create_expert_ticket

from backend.ai import chatbot as cb
from backend.rules.member_signals import read_signals, signals_block


@dataclass
class AskResponse:
    answer: str
    confidence: str  # high | medium | low
    citations: list[dict]
    should_route_as_ticket: bool
    ticket_id: str | None = None


_ASK_INSTRUCTIONS = """
You are the AYUN AI Sports Scientist. Cite sources with compact markers only:
- [Member] this member's assessment values, ratings, and labs only
- [n] AYUN protocols, training templates, or expert-validated Q&A from the numbered source list
- [Web n] Evipedia evidence reviews from the web list

Citation policy (required):
- Training advice MUST be cited with [n] when numbered protocols/templates exist.
  Do not fold protocol content into [Member].
- Cite [n] on expert-validated Q&A when you reuse a clinic-validated answer.
- Cite [Web n] when evidence reviews are listed and you mention why a protocol
  exists, supporting research, or clinical background.
- Never cite only [Member] if numbered protocol, validated Q&A, or web sources are listed.
- Do not invent citations. Do not print banners such as MEMBER CONTEXT.

Rules:
- Answer from MATCHED AYUN PROTOCOLS and training templates first.
- If expert-validated Q&A is listed and it answers this question, reuse it
  (do not invent a conflicting programme).
- Copy frequency, intensity, duration, and exercises from those templates.
  Do not invent a different programme.
- Never diagnose high body fat, low VO2max, low bone density, or any other
  condition unless that protocol is in the matched list below.
- If a measurement is missing, say it was not measured. Do not invent a value
  or assume it is poor.
- If a rating is excellent, good, or average, do not prescribe the problem
  protocol for that metric.
- If the question cannot be answered safely from available data, say so clearly.
- Structure the answer for a chat UI: short summary, ## headings, bullet actions,
  concrete numbers (sets/reps/zones), and a single "Next step" at the end.

Respond ONLY with valid JSON (no markdown fences):
{
  "answer": "your markdown answer for the member",
  "confidence": "high" | "medium" | "low",
  "citation_indices": [1, 2, "Member", "Web 1"],
  "should_route_as_ticket": false,
  "route_reason": "optional short reason if routing"
}
"""

_PROTOCOL_MARK_RE = re.compile(r"\[(?:Protocol(?:\s+(\d+))?|(\d+))\]", re.IGNORECASE)
_WEB_MARK_RE = re.compile(r"\[(?:Web\s*(\d+)|E(\d+))\]", re.IGNORECASE)
_MEMBER_MARK_RE = re.compile(r"\[Member(?:\s+Context)?\]", re.IGNORECASE)

_BANNER_RE = re.compile(
    r"(?:=+\s*)?\[?\s*MEMBER[\s_]+CONTEXT(?:\s*\([^)]*\))?\s*\]?:?\s*(?:=+\s*)?",
    re.IGNORECASE,
)
_CORPUS_BANNER_RE = re.compile(
    r"(?:=+\s*)?VALIDATED KNOWLEDGE CORPUS[^\n]*\n?(?:=+\s*)?",
    re.IGNORECASE,
)


def _citation_family(kind: str) -> str:
    k = (kind or "").lower().replace("_", "-")
    if k in {"member", "member-context"}:
        return "member"
    if k in {"evipedia", "web", "evidence"}:
        return "web"
    return "protocol"


def _pretty_locator(kind: str, locator: str, url: str = "") -> str:
    if url:
        clean = url.replace("https://", "").replace("http://", "").rstrip("/")
        if "/" in clean:
            host, path = clean.split("/", 1)
            return f"{host} · /{path}"
        return clean
    loc = (locator or "").strip()
    if loc.startswith("AYUN ") or loc.startswith("General exercise evidence"):
        return loc
    if "protocols_quick_reference" in loc:
        return "AYUN protocol library"
    if loc.startswith("knowledge/"):
        return f"AYUN clinic · {loc}"
    return loc or "AYUN clinic"


def _origin_for_family(family: str, kind: str = "") -> str:
    k = (kind or "").lower().replace("_", "-")
    if family == "member":
        return "From your data"
    if family == "web":
        return "From evidence · Evipedia"
    if k in {"validated-answer", "validated-ticket"}:
        return "Validated Q&A"
    if kind == "ayun-protocol":
        return "AYUN protocol"
    return "AYUN clinic"


def _source_row(
    *,
    index: str,
    title: str,
    family: str,
    kind: str,
    excerpt: str,
    locator: str,
    url: str = "",
    used: bool = False,
    protocol: dict | None = None,
) -> dict:
    row = {
        "index": str(index),
        "marker": str(index),
        "title": title,
        "family": family,
        "kind": kind,
        "excerpt": (excerpt or "")[:300],
        "locator": _pretty_locator(kind, locator, url),
        "url": url,
        "origin": _origin_for_family(family, kind),
        "used": "1" if used else "0",
    }
    if protocol:
        row["protocol"] = protocol
    return row


_BASELINE_TEMPLATE_KEYS = ("zone2_base", "full_body_strength")


def _template_keys_from_context(member_context: str) -> set[str]:
    return set(re.findall(r"\[([a-z][a-z0-9_]{2,})\]", member_context or ""))


def _grounded_corpus(member_context: str, question: str, member_user_id: str | None = None) -> list[CorpusEntry]:
    """Only protocols/templates actually attached for this member and question."""
    from backend.rules.protocol_library import _templates_for_question, list_protocol_catalog, protocol_record_text

    titles = {t.strip().lower() for t in _protocol_titles_from_context(member_context)}
    template_keys = set(_templates_for_question(question))
    template_keys.update(_template_keys_from_context(member_context))
    catalog = list_protocol_catalog()
    for rec in catalog:
        if rec.get("kind") != "condition_protocol":
            continue
        if (rec.get("title") or "").strip().lower() not in titles:
            continue
        for rel in rec.get("related_templates") or []:
            key = rel.get("key") if isinstance(rel, dict) else rel
            if key:
                template_keys.add(str(key))
    if not titles and not template_keys:
        # No protocol matched and the question names no topic: still ground the
        # answer in AYUN's baseline programme (endurance + strength) so it cites AYUN.
        template_keys.update(_BASELINE_TEMPLATE_KEYS)
    entries: list[CorpusEntry] = []
    for rec in catalog:
        kind = rec.get("kind") or ""
        keep = False
        if kind == "condition_protocol" and (rec.get("title") or "").strip().lower() in titles:
            keep = True
        if kind == "training_template" and rec.get("key") in template_keys:
            keep = True
        if not keep:
            continue
        entries.append(
            CorpusEntry(
                id=f"protocol:{rec.get('key')}",
                title=rec.get("title") or rec.get("key") or "Protocol",
                kind="ayun-protocol" if kind == "condition_protocol" else "ayun-template",
                text=protocol_record_text(rec),
                excerpt=(rec.get("description") or protocol_record_text(rec))[:600],
                locator=rec.get("source") or "knowledge/protocols_quick_reference.yml",
                created_at="",
            )
        )
    entries.extend(match_validated_corpus(question, limit=4, member_user_id=member_user_id))
    return entries


def _web_hits(question: str, corpus: list[CorpusEntry] | None = None) -> list[dict]:
    try:
        from backend.ai.evipedia_refs import match_evipedia

        parts = [question or ""]
        if corpus:
            parts.extend(entry.title for entry in corpus[:4])
        query = " ".join(part for part in parts if part).strip()
        if not query:
            return []
        return match_evipedia(query, limit=3)
    except Exception:
        return []


def _format_sources_for_llm(
    corpus: list[CorpusEntry],
    web_hits: list[dict],
    member_context: str,
) -> str:
    # AYUN protocols come first so the model grounds the answer in them.
    parts: list[str] = []
    for i, entry in enumerate(corpus, start=1):
        family = _citation_family(entry.kind)
        label = _origin_for_family(family, entry.kind)
        parts.append(
            f"[{i}] ({label}) {entry.title}\n"
            f"Location: {_pretty_locator(entry.kind, entry.locator)}\n"
            f"{entry.text}"
        )
    if (member_context or "").strip():
        parts.append(
            "[Member] (From your data) This member's own assessment, profile, and labs. Not external evidence.\n"
            "Location: AYUN rule engine · latest assessment"
        )
    for i, row in enumerate(web_hits, start=1):
        summary = row.get("summary") or row.get("snippet") or ""
        parts.append(
            f"[Web {i}] (Evipedia evidence) {row.get('title', 'Evidence review')}\n"
            f"Location: {row.get('url', '')}\n"
            f"{summary}"
        )
    if not parts:
        return "(No validated knowledge captured yet — answers rely on rule engine context only.)"
    return "\n\n".join(parts)


def _member_excerpt(member_context: str) -> str:
    lines: list[str] = []
    for raw in (member_context or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if "──" in line or "AYUN SCIENTIST" in line or line.startswith("###"):
            break
        lines.append(line.rstrip("."))
        if len(lines) >= 3:
            break
    return " · ".join(lines)[:220] or "Latest assessment, labs, and recommendations"


def _protocol_titles_from_context(member_context: str) -> list[str]:
    titles = re.findall(r"### Protocol:\s*(.+)", member_context or "")
    seen: list[str] = []
    for title in titles:
        clean = title.strip()
        if clean and clean not in seen:
            seen.append(clean)
    return seen[:4]


def _scrub_source_banners(answer: str) -> str:
    text = _BANNER_RE.sub("[Member] ", answer or "")
    text = _CORPUS_BANNER_RE.sub("", text)
    text = re.sub(r"\[MEMBER CONTEXT\]", "[Member]", text, flags=re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _token_key(value: object) -> str:
    if isinstance(value, int):
        return str(value)
    text = str(value or "").strip()
    text = text.replace("[", "").replace("]", "")
    lower = text.lower()
    if lower in {"member", "member context", "member-context"}:
        return "Member"
    web = re.match(r"(?:web\s*)?(\d+)$", lower)
    if lower.startswith("web") and web:
        return f"Web {web.group(1)}"
    eweb = re.match(r"e(\d+)$", lower)
    if eweb:
        return f"Web {eweb.group(1)}"
    return text


def _indices_from_answer(answer: str) -> list:
    found: list = []
    if _MEMBER_MARK_RE.search(answer or ""):
        found.append("Member")
    for match in _PROTOCOL_MARK_RE.finditer(answer or ""):
        number = match.group(1) or match.group(2)
        found.append(int(number) if number else 1)
    for match in _WEB_MARK_RE.finditer(answer or ""):
        number = match.group(1) or match.group(2)
        if number:
            found.append(f"Web {number}")
    return found


def _ensure_source_markers(
    answer: str,
    corpus: list[CorpusEntry],
    web_hits: list[dict],
) -> str:
    """Surface matched protocol and Evipedia sources even if the model only cited [Member]."""
    text = (answer or "").rstrip()
    if not text:
        return text
    if corpus and not _PROTOCOL_MARK_RE.search(text):
        protocol_nums = [
            i
            for i, entry in enumerate(corpus, start=1)
            if entry.kind in {"ayun-protocol", "ayun-template"}
        ]
        if protocol_nums:
            marks = " ".join(f"[{i}]" for i in protocol_nums[:3])
            text = f"{text} {marks}"
    if web_hits and not _WEB_MARK_RE.search(text):
        text = f"{text} [Web 1]"
    return text


def _build_citations(
    citation_indices: list,
    corpus: list[CorpusEntry],
    web_hits: list[dict],
    member_context: str,
) -> list[dict]:
    from backend.rules.protocol_library import protocol_card_by_title

    used_keys = {_token_key(idx) for idx in (citation_indices or [])}
    citations: list[dict] = []
    seen: set[str] = set()

    def add(row: dict) -> None:
        key = row["index"]
        if key in seen:
            return
        seen.add(key)
        citations.append(row)

    # Matched AYUN protocols first, then the member's own data, then Evipedia.
    for i, entry in enumerate(corpus, start=1):
        used = str(i) in used_keys or entry.kind == "ayun-protocol"
        # Matched protocols and cited training templates open as a card in "Open the protocol".
        card = protocol_card_by_title(entry.title) if used and entry.kind in {"ayun-protocol", "ayun-template"} else None
        add(
            _source_row(
                index=str(i),
                title=entry.title,
                family="protocol",
                kind=entry.kind,
                excerpt=entry.excerpt,
                locator=entry.locator,
                used=used,
                protocol=card,
            )
        )

    if (member_context or "").strip():
        add(
            _source_row(
                index="Member",
                title="Your data",
                family="member",
                kind="member-context",
                excerpt=_member_excerpt(member_context),
                locator="AYUN rule engine · latest assessment",
                used="Member" in used_keys,
            )
        )

    for i, row in enumerate(web_hits, start=1):
        key = f"Web {i}"
        if key not in used_keys:
            continue
        add(
            _source_row(
                index=key,
                title=row.get("title") or "Evidence review",
                family="web",
                kind="evipedia",
                excerpt=row.get("summary") or row.get("snippet") or "",
                locator=row.get("url") or "evipedia.ai",
                url=row.get("url") or "",
                used=True,
            )
        )

    return citations


def _parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # A long answer can be cut off mid-JSON: keep the answer text, drop the wrapper.
        m = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)', raw, re.S)
        if m:
            try:
                answer = json.loads(f'"{m.group(1)}"')
            except json.JSONDecodeError:
                answer = m.group(1).replace("\\n", "\n").replace('\\"', '"')
            conf = re.search(r'"confidence"\s*:\s*"(high|medium|low)"', raw)
            return {
                "answer": answer,
                "confidence": conf.group(1) if conf else "medium",
                "citation_indices": [],
                "should_route_as_ticket": False,
                "route_reason": "",
            }
        return {
            "answer": raw,
            "confidence": "medium",
            "citation_indices": [],
            "should_route_as_ticket": False,
            "route_reason": "",
        }


def ask_with_knowledge(
    question: str,
    member_context: str,
    messages: list[dict] | None = None,
    viewer_role: str = "patient",
    viewer_name: str = "",
    member_snapshot: dict | None = None,
    member_user_id: str | None = None,
    auto_ticket: bool = True,
    retention_days: int = 30,
) -> AskResponse:
    """
    Single-turn grounded Q&A with structured confidence + optional ticket creation.

    Three-tier memory:
      Tier 1 (working):  last-N messages from `messages` arg (ephemeral)
      Tier 2 (episodic): past session summaries from memory_store (per-user, TTL)
      Tier 3 (semantic): validated corpus from knowledge_store (shared)
    """
    if not cb.is_configured():
        raise RuntimeError(cb._deployment_hint() or "AI is not configured")

    from backend.rules.protocol_library import strip_protocol_blocks

    corpus = _grounded_corpus(member_context, question, member_user_id)
    web_hits = _web_hits(question, corpus)
    corpus_block = _format_sources_for_llm(corpus, web_hits, member_context)
    plan_only = strip_protocol_blocks(member_context)
    signals = read_signals(member_context, member_snapshot)

    # Tier 1 — working memory: last N turns in this session
    working_block = ""
    if messages:
        working_block = build_working_memory_block(messages)

    # Tier 2 — episodic memory: summaries of past sessions (if user opted in)
    episodic_block = ""
    if member_user_id and retention_days != 0:
        episodic_block = build_episodic_memory_block(member_user_id, limit=5)

    # Build layered system prompt
    memory_section = ""
    if episodic_block:
        memory_section += "\n\n" + "=" * 60 + "\n" + episodic_block + "\n" + "=" * 60
    if working_block:
        memory_section += "\n\n── CURRENT SESSION (last turns) ──\n" + working_block

    system = (
        cb.build_system_prompt(plan_only)
        + memory_section
        + "\n\n"
        + "=" * 60
        + "\nSOURCES (cite as [Member], [n], or [Web n]):\n"
        + "=" * 60
        + "\n"
        + corpus_block
        + "\n\n"
        + signals_block(signals)
        + "\n\n"
        + _ASK_INSTRUCTIONS
        + f"\nViewer role: {viewer_role}"
    )

    user_content = question

    client = cb._build_client()
    create_kwargs: dict = {
        "model": cb.MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.35,
        "max_tokens": cb._max_tokens(1100),  # room for the watch-outs section
        **cb.request_extras(),
    }
    if cb.ai_config().get("provider") != "ollama":
        create_kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**create_kwargs)
    raw = cb._message_text(response.choices[0].message) or "{}"
    parsed = _parse_json_response(raw)

    confidence = str(parsed.get("confidence") or "medium").lower()
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"
    # Confidence has to be earned: cap it when key data domains are missing.
    capped = signals.confidence_cap == "medium" and confidence == "high"
    if capped:
        confidence = "medium"

    should_route = bool(parsed.get("should_route_as_ticket")) or confidence == "low"
    ticket_id = None

    if should_route and auto_ticket:
        ticket = create_expert_ticket(
            question=question,
            from_role=viewer_role,
            from_name=viewer_name or ("Member" if viewer_role == "patient" else "Clinician"),
            member_snapshot=member_snapshot or {},
            chat_context=member_context[:3000],
            category="General",
            assigned_expert_id="general_pool",
            source="ai_auto",
            member_user_id=member_user_id,
        )
        ticket_id = ticket.id

    answer = _ensure_source_markers(
        _scrub_source_banners(str(parsed.get("answer") or "").strip()),
        corpus,
        web_hits,
    )
    citation_indices = list(parsed.get("citation_indices") or [])
    citation_indices.extend(_indices_from_answer(answer))
    citations = _build_citations(citation_indices, corpus, web_hits, member_context)
    if capped:
        answer += f"\n\n**Why medium confidence:** {signals.cap_reason()}."
    if should_route and ticket_id:
        reason = parsed.get("route_reason") or "This needs clinician review."
        answer += (
            f"\n\n---\n"
            f"**Expert review requested** (ticket `{ticket_id}`): {reason} "
            f"A sports scientist will validate an answer — it will then improve future responses."
        )

    return AskResponse(
        answer=answer,
        confidence=confidence,
        citations=citations,
        should_route_as_ticket=should_route,
        ticket_id=ticket_id,
    )


def close_session(
    messages: list[dict[str, str]],
    *,
    user_id: str,
    session_id: str,
    member_name: str = "",
    retention_days: int = 30,
) -> bool:
    """
    Called when a member ends a chat session.
    Summarises the conversation and stores it as an episodic memory record.
    Returns True if a memory record was created.
    """
    if retention_days == 0 or not user_id:
        return False
    if len([m for m in messages if m.get("role") in ("user", "assistant")]) < 2:
        return False

    result = summarise_session(messages, member_name=member_name)
    if not result:
        return False

    stored = store_session_memory(
        user_id=user_id,
        session_id=session_id,
        summary=result["summary"],
        topics=result["topics"],
        turn_count=sum(1 for m in messages if m.get("role") == "user"),
        confidence_avg=result["confidence_avg"],
        retention_days=retention_days,
    )
    return stored is not None
