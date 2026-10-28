"""
Three-tier memory store for AYUN per-member episodic context.

Tier 1 — Working memory:   Ephemeral, lives only in the request (last-N turns).
Tier 2 — Episodic memory:  Per-user session summaries with TTL + consent controls.
                            Stored here in JSON (or Supabase when configured).
Tier 3 — Semantic memory:  Shared validated knowledge corpus (knowledge_store.py).

Privacy:
- Every record carries an `expires_at` ISO timestamp.
- Records with `expires_at < now` are treated as deleted.
- `DELETE /api/memory` purges all records for a user immediately.
- Users choose their retention tier in `privacy_settings.memory_retention_days`:
    0  → no episodic memory stored (opt-out)
    7  → 7-day rolling window
    30 → 30-day rolling window  (GDPR default)
    90 → 90-day rolling window
    -1 → indefinite (explicit long-term consent)
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.ai import chatbot as cb
from backend.storage import ayun_db
from backend.storage.data_paths import writable_json

_STORE_FILE = writable_json("knowledge/member_memory.json")
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

_RETENTION_DAYS_DEFAULT = 30
_MAX_SUMMARY_CHARS = 800
_WORKING_MEMORY_TURNS = 6


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class MemoryRecord:
    id: str
    user_id: str
    session_id: str
    summary: str              # compact text summary of the conversation
    topics: list[str]         # inferred topic tags (for retrieval + display)
    turn_count: int           # number of exchanges in the session
    confidence_avg: str       # high | medium | low — avg confidence across turns
    created_at: str
    expires_at: str | None    # None = indefinite

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return exp < datetime.now(timezone.utc)
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> MemoryRecord:
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            session_id=row.get("session_id") or "",
            summary=row.get("summary") or "",
            topics=row.get("topics") or [],
            turn_count=int(row.get("turn_count") or 0),
            confidence_avg=str(row.get("confidence_avg") or "medium"),
            created_at=row.get("created_at") or "",
            expires_at=row.get("expires_at"),
        )


# ── Persistence helpers ───────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _expires_iso(days: int) -> str | None:
    if days < 0:
        return None
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat()


def _read_rows() -> list[dict[str, Any]]:
    if not _STORE_FILE.exists():
        return []
    try:
        data = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_rows(rows: list[dict[str, Any]]) -> None:
    _STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STORE_FILE.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Core API ──────────────────────────────────────────────────────────────────

def _merge_user_memory_rows(user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Merge JSON + Supabase rows for a user, preferring the newest created_at."""
    by_id: dict[str, dict[str, Any]] = {}
    for row in _read_rows():
        if row.get("user_id") != user_id:
            continue
        by_id[row["id"]] = row
    sb_rows = ayun_db.list_member_memory(user_id, limit=limit)
    if sb_rows is not None:
        for row in sb_rows:
            existing = by_id.get(row["id"])
            if not existing or (row.get("created_at") or "") >= (existing.get("created_at") or ""):
                by_id[row["id"]] = row
    rows = list(by_id.values())
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows[:limit]


def store_session_memory(
    user_id: str,
    session_id: str,
    summary: str,
    topics: list[str],
    turn_count: int,
    confidence_avg: str,
    *,
    retention_days: int = _RETENTION_DAYS_DEFAULT,
) -> MemoryRecord | None:
    """
    Persist an episodic summary for a completed session.
    Returns None if user has opted out (retention_days == 0).
    """
    if retention_days == 0:
        return None

    record = MemoryRecord(
        id=str(uuid.uuid4())[:12],
        user_id=user_id,
        session_id=session_id,
        summary=summary[:_MAX_SUMMARY_CHARS],
        topics=topics[:10],
        turn_count=turn_count,
        confidence_avg=confidence_avg,
        created_at=_now_iso(),
        expires_at=_expires_iso(retention_days),
    )
    rows = _read_rows()
    rows = [r for r in rows if r.get("id") != record.id]
    rows.insert(0, record.to_dict())
    _write_rows(rows)
    ayun_db.upsert_member_memory(record.to_dict())
    return record


def list_user_memory(user_id: str, *, limit: int = 10) -> list[MemoryRecord]:
    """Return non-expired episodic records for a user, newest first."""
    results: list[MemoryRecord] = []
    for row in _merge_user_memory_rows(user_id, limit=limit * 2):
        rec = MemoryRecord.from_row(row)
        if not rec.is_expired():
            results.append(rec)
        if len(results) >= limit:
            break
    return results


def delete_user_memory(user_id: str) -> int:
    """Permanently delete all memory records for a user. Returns count deleted."""
    rows = _read_rows()
    kept = [r for r in rows if r.get("user_id") != user_id]
    deleted = len(rows) - len(kept)
    _write_rows(kept)
    sb_deleted = ayun_db.delete_member_memory_for_user(user_id)
    if sb_deleted is not None:
        deleted = max(deleted, sb_deleted)
    return deleted


def purge_expired_memory() -> int:
    """Remove all records past their expires_at. Call from a cron/admin endpoint."""
    sb_deleted = ayun_db.purge_expired_member_memory()
    rows = _read_rows()
    kept = []
    now = datetime.now(timezone.utc)
    for row in rows:
        exp = row.get("expires_at")
        if exp is None:
            kept.append(row)
            continue
        try:
            if datetime.fromisoformat(exp) >= now:
                kept.append(row)
        except (ValueError, TypeError):
            kept.append(row)
    deleted = len(rows) - len(kept)
    _write_rows(kept)
    if sb_deleted is not None:
        deleted += sb_deleted
    return deleted


# ── Working memory (Tier 1) ───────────────────────────────────────────────────

def build_working_memory_block(messages: list[dict[str, str]]) -> str:
    """Last-N turns for the current session — ephemeral, never stored raw."""
    recent = [m for m in messages if m.get("role") in ("user", "assistant")]
    recent = recent[-_WORKING_MEMORY_TURNS:]
    if not recent:
        return ""
    lines = []
    for m in recent:
        role = "Member" if m["role"] == "user" else "AI"
        lines.append(f"{role}: {(m.get('content') or '')[:300]}")
    return "\n".join(lines)


# ── Episodic memory (Tier 2) — prompt injection ───────────────────────────────

def build_episodic_memory_block(user_id: str, *, limit: int = 5) -> str:
    """
    Retrieve recent non-expired summaries and format them for prompt injection.
    Returns empty string if user has no stored memory or opted out.
    """
    records = list_user_memory(user_id, limit=limit)
    if not records:
        return ""

    lines = [
        "── YOUR PREVIOUS SESSIONS (from memory) ──",
        "These are summaries of recent conversations you had with AYUN AI.",
        "Use them to personalise your response — do not repeat them verbatim.",
        "",
    ]
    for rec in records:
        date = rec.created_at[:10] if rec.created_at else "?"
        topics_str = ", ".join(rec.topics) if rec.topics else "General"
        lines.append(f"[{date}] Topics: {topics_str}")
        lines.append(f"  {rec.summary}")
        lines.append("")
    return "\n".join(lines).rstrip()


# ── Session summarisation (called after a conversation ends) ──────────────────

_SUMMARY_PROMPT = """Summarise this health coaching conversation in 2-4 sentences for future reference.
Focus on:
- What the member was concerned about or wanted to learn
- Key advice or insights given
- Any follow-up actions or open questions

Return ONLY valid JSON (no fences):
{
  "summary": "...",
  "topics": ["...", "..."],
  "confidence_avg": "high" | "medium" | "low"
}
Topics should be 1-4 word labels (e.g. "bone density", "zone 2 training", "supplements").
Be concise — max 4 topics, summary under 200 words.
"""


def summarise_session(
    messages: list[dict[str, str]],
    *,
    member_name: str = "",
) -> dict[str, Any] | None:
    """
    Ask the LLM to produce a compact summary of the session.
    Returns {"summary": str, "topics": list, "confidence_avg": str} or None if AI unavailable.
    """
    if not cb.is_configured():
        return None

    recent = [m for m in messages if m.get("role") in ("user", "assistant")]
    if len(recent) < 2:
        return None

    transcript = "\n".join(
        f"{'Member' if m['role'] == 'user' else 'AI'}: {(m.get('content') or '')[:400]}"
        for m in recent[-12:]
    )
    name_hint = f"Member name: {member_name}\n\n" if member_name else ""
    user_content = f"{name_hint}Conversation transcript:\n{transcript}"

    try:
        raw = cb.complete(
            [
                {"role": "system", "content": _SUMMARY_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        return {
            "summary": str(parsed.get("summary") or "")[:_MAX_SUMMARY_CHARS],
            "topics": [str(t) for t in (parsed.get("topics") or [])[:6]],
            "confidence_avg": str(parsed.get("confidence_avg") or "medium"),
        }
    except (json.JSONDecodeError, Exception):
        return None


# ── Privacy settings helpers ──────────────────────────────────────────────────

RETENTION_OPTIONS = [
    {"days": 0, "label": "No memory (every session starts fresh)"},
    {"days": 7, "label": "7 days"},
    {"days": 30, "label": "30 days (default, GDPR compliant)"},
    {"days": 90, "label": "90 days"},
    {"days": -1, "label": "Indefinite (until I delete it)"},
]


def default_privacy_settings() -> dict[str, Any]:
    return {
        "memory_enabled": True,
        "memory_retention_days": _RETENTION_DAYS_DEFAULT,
        "consented_at": _now_iso(),
    }
