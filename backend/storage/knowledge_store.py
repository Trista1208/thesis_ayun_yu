"""
Persistent store for clinical knowledge nodes and expert Q&A tickets.

Backends (WearAware-inspired):
  - Supabase Postgres when SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are set
  - Local JSON files otherwise (data/knowledge/)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.storage import ayun_db
from backend.storage.data_paths import writable_json

_NODES_FILE = writable_json("knowledge/captured_nodes.json")
_TICKETS_FILE = writable_json("knowledge/tickets.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_store() -> None:
    writable_json("knowledge/captured_nodes.json")
    writable_json("knowledge/tickets.json")


def _read_json(path: Path) -> list[dict[str, Any]]:
    _ensure_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    _ensure_store()
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


@dataclass
class CapturedNode:
    id: str
    title: str
    category: str
    summary: str
    passages: list[dict[str, str]]
    captured_by: str
    source: str  # doctor_review | manual | protocol | validated_ticket
    member_context: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    source_ticket_id: str = ""

    @classmethod
    def create(
        cls,
        title: str,
        category: str,
        summary: str,
        passages: list[dict[str, str]],
        captured_by: str,
        source: str,
        member_context: str = "",
        tags: list[str] | None = None,
        source_ticket_id: str = "",
    ) -> CapturedNode:
        return cls(
            id=str(uuid.uuid4())[:8],
            title=title,
            category=category,
            summary=summary,
            passages=passages,
            captured_by=captured_by,
            source=source,
            member_context=member_context,
            tags=tags or [],
            created_at=_now_iso(),
            source_ticket_id=source_ticket_id,
        )


@dataclass
class KnowledgeTicket:
    id: str
    question: str
    from_role: str  # patient | doctor
    from_name: str
    status: str  # open | answered | validated
    draft_answer: str
    validated_by: str
    member_snapshot: dict[str, Any]
    chat_context: str
    created_at: str
    updated_at: str
    assigned_expert_id: str = "general_pool"
    category: str = "General"
    source: str = "ai_auto"  # ai_auto | patient_direct | doctor_direct
    member_user_id: str | None = None

    @classmethod
    def create(
        cls,
        question: str,
        from_role: str,
        from_name: str,
        member_snapshot: dict[str, Any] | None = None,
        chat_context: str = "",
        assigned_expert_id: str = "general_pool",
        category: str = "General",
        source: str = "ai_auto",
        member_user_id: str | None = None,
    ) -> KnowledgeTicket:
        ts = _now_iso()
        return cls(
            id=str(uuid.uuid4())[:8],
            question=question,
            from_role=from_role,
            from_name=from_name,
            status="open",
            draft_answer="",
            validated_by="",
            member_snapshot=member_snapshot or {},
            chat_context=chat_context,
            created_at=ts,
            updated_at=ts,
            assigned_expert_id=assigned_expert_id or "general_pool",
            category=category or "General",
            source=source,
            member_user_id=member_user_id or None,
        )


def _ticket_from_row(row: dict[str, Any]) -> KnowledgeTicket:
    """Load ticket from JSON with defaults for older records."""
    defaults = {
        "assigned_expert_id": "general_pool",
        "category": "General",
        "source": "ai_auto",
        "member_user_id": None,
    }
    merged = {**defaults, **row}
    return KnowledgeTicket(**{k: merged[k] for k in KnowledgeTicket.__dataclass_fields__})


# ── Captured nodes ────────────────────────────────────────────────────────────

def _node_from_row(row: dict[str, Any]) -> CapturedNode:
    defaults = {
        "member_context": "",
        "tags": [],
        "created_at": "",
        "source_ticket_id": "",
    }
    merged = {**defaults, **row}
    if merged.get("created_at") and not isinstance(merged["created_at"], str):
        merged["created_at"] = str(merged["created_at"])
    return CapturedNode(**{k: merged[k] for k in CapturedNode.__dataclass_fields__})


def _node_identity_key(row: dict[str, Any]) -> tuple[str, str]:
    ticket_id = (row.get("source_ticket_id") or "").strip()
    if ticket_id:
        return ("ticket", ticket_id)
    title = (row.get("title") or "").strip().lower()
    summary = (row.get("summary") or "").strip()
    return ("content", f"{title}\n{summary}")


def _dedupe_node_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the newest row for each ticket id or identical Q&A content."""
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: r.get("created_at", ""), reverse=True):
        key = _node_identity_key(row)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def list_nodes(limit: int = 200) -> list[CapturedNode]:
    rows = ayun_db.list_knowledge_nodes(limit)
    if rows is not None:
        nodes = [_node_from_row(r) for r in _dedupe_node_rows(rows)]
        return nodes[:limit]
    json_rows = _dedupe_node_rows(_read_json(_NODES_FILE))
    nodes = [_node_from_row(r) for r in json_rows[:limit]]
    return sorted(nodes, key=lambda n: n.created_at, reverse=True)


def add_node(node: CapturedNode) -> CapturedNode:
    row = asdict(node)
    key = _node_identity_key(row)

    def _merge_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filtered = [r for r in rows if _node_identity_key(r) != key]
        filtered.insert(0, row)
        return filtered[:500]

    if ayun_db.insert_knowledge_node(row):
        _write_json(_NODES_FILE, _merge_rows(_read_json(_NODES_FILE)))
        return node
    _write_json(_NODES_FILE, _merge_rows(_read_json(_NODES_FILE)))
    return node


def delete_node(node_id: str) -> bool:
    if ayun_db.is_configured() and ayun_db.delete_knowledge_node(node_id):
        rows = _read_json(_NODES_FILE)
        new_rows = [r for r in rows if r.get("id") != node_id]
        if len(new_rows) != len(rows):
            _write_json(_NODES_FILE, new_rows)
        return True
    rows = _read_json(_NODES_FILE)
    new_rows = [r for r in rows if r.get("id") != node_id]
    if len(new_rows) == len(rows):
        return False
    _write_json(_NODES_FILE, new_rows)
    return True


def delete_nodes_for_ticket(ticket_id: str) -> int:
    """Remove knowledge nodes created from a validated ticket."""
    tid = (ticket_id or "").strip()
    if not tid:
        return 0
    rows = _read_json(_NODES_FILE)
    to_delete = [r for r in rows if (r.get("source_ticket_id") or "").strip() == tid]
    removed = 0
    for row in to_delete:
        if delete_node(row["id"]):
            removed += 1
    return removed


# ── Tickets ───────────────────────────────────────────────────────────────────

def list_tickets(status: str | None = None, limit: int = 200) -> list[KnowledgeTicket]:
    by_id: dict[str, KnowledgeTicket] = {}
    for row in _read_json(_TICKETS_FILE):
        ticket = _ticket_from_row(row)
        by_id[ticket.id] = ticket

    sb_rows = ayun_db.list_expert_tickets(status, limit=500)
    if sb_rows is not None:
        for row in sb_rows:
            ticket = _ticket_from_row(row)
            existing = by_id.get(ticket.id)
            if not existing or ticket.updated_at >= existing.updated_at:
                by_id[ticket.id] = ticket

    tickets = list(by_id.values())
    if status:
        tickets = [t for t in tickets if t.status == status]
    tickets.sort(key=lambda t: t.updated_at, reverse=True)
    return tickets[:limit]


def get_ticket(ticket_id: str) -> KnowledgeTicket | None:
    row = ayun_db.get_expert_ticket(ticket_id)
    if row is not None:
        return _ticket_from_row(row)
    for row in _read_json(_TICKETS_FILE):
        if row.get("id") == ticket_id:
            return _ticket_from_row(row)
    return None


def add_ticket(ticket: KnowledgeTicket) -> KnowledgeTicket:
    row = asdict(ticket)
    rows = _read_json(_TICKETS_FILE)
    rows = [r for r in rows if r.get("id") != ticket.id]
    rows.insert(0, row)
    _write_json(_TICKETS_FILE, rows[:500])
    ayun_db.upsert_expert_ticket(row)
    return ticket


def delete_ticket(ticket_id: str) -> bool:
    if ayun_db.is_configured() and ayun_db.delete_expert_ticket(ticket_id):
        rows = _read_json(_TICKETS_FILE)
        new_rows = [r for r in rows if r.get("id") != ticket_id]
        if len(new_rows) != len(rows):
            _write_json(_TICKETS_FILE, new_rows)
        return True
    rows = _read_json(_TICKETS_FILE)
    new_rows = [r for r in rows if r.get("id") != ticket_id]
    if len(new_rows) == len(rows):
        return False
    _write_json(_TICKETS_FILE, new_rows)
    return True


def update_ticket(ticket_id: str, **updates: Any) -> KnowledgeTicket | None:
    updates = {**updates, "updated_at": _now_iso()}
    found: KnowledgeTicket | None = None
    rows = _read_json(_TICKETS_FILE)
    for i, row in enumerate(rows):
        if row.get("id") == ticket_id:
            row.update(updates)
            found = _ticket_from_row(row)
            rows[i] = asdict(found)
            _write_json(_TICKETS_FILE, rows)
            break

    sb_ok = ayun_db.update_expert_ticket(ticket_id, updates)
    if found and ayun_db.is_configured() and not sb_ok:
        ayun_db.upsert_expert_ticket(asdict(found))
        sb_ok = True

    if found:
        return found
    if sb_ok:
        return get_ticket(ticket_id)
    return None


def save_draft_answer(ticket_id: str, draft_answer: str) -> KnowledgeTicket | None:
    return update_ticket(ticket_id, draft_answer=draft_answer, status="answered")


def remove_validated_qa_from_library(ticket_id: str) -> bool:
    """Drop a validated Q&A from the knowledge library (node + unvalidate ticket)."""
    ticket = get_ticket(ticket_id)
    if not ticket or ticket.status != "validated":
        return False
    delete_nodes_for_ticket(ticket_id)
    updated = update_ticket(ticket_id, status="answered", validated_by="")
    return updated is not None


def list_tickets_for_member_user(member_user_id: str, limit: int = 200) -> list[KnowledgeTicket]:
    uid = (member_user_id or "").strip()
    if not uid:
        return []
    tickets = list_tickets(limit=limit)
    return [t for t in tickets if (t.member_user_id or "") == uid]


def claim_tickets_for_member(
    ticket_ids: list[str],
    member_user_id: str,
    *,
    display_names: list[str] | None = None,
) -> list[KnowledgeTicket]:
    """Attach guest or legacy name-only tickets to a logged-in member account."""
    uid = (member_user_id or "").strip()
    if not uid:
        return []
    ids = {(i or "").strip() for i in ticket_ids if (i or "").strip()}
    names = {(n or "").strip().lower() for n in (display_names or []) if (n or "").strip()}
    claimed: list[KnowledgeTicket] = []
    rows = _read_json(_TICKETS_FILE)
    changed = False
    for i, row in enumerate(rows):
        ticket = _ticket_from_row(row)
        if ticket.member_user_id:
            continue
        by_id = ticket.id in ids if ids else False
        by_name = (
            bool(names)
            and (ticket.from_name or "").strip().lower() in names
            and ticket.from_role == "patient"
        )
        if not by_id and not by_name:
            continue
        row["member_user_id"] = uid
        row["updated_at"] = _now_iso()
        claimed.append(_ticket_from_row(row))
        rows[i] = row
        changed = True
        if ayun_db.is_configured():
            ayun_db.update_expert_ticket(ticket.id, {"member_user_id": uid, "updated_at": row["updated_at"]})
    if changed:
        _write_json(_TICKETS_FILE, rows)
    return claimed


def lookup_guest_tickets(ticket_ids: list[str]) -> list[KnowledgeTicket]:
    """Return unclaimed tickets the guest saved locally (by id only)."""
    ids = {(i or "").strip() for i in ticket_ids if (i or "").strip()}
    if not ids:
        return []
    tickets = list_tickets(limit=500)
    return [t for t in tickets if t.id in ids and not t.member_user_id]


def validate_ticket(ticket_id: str, validated_by: str, final_answer: str | None = None) -> KnowledgeTicket | None:
    ticket = get_ticket(ticket_id)
    if not ticket:
        return None
    answer = (final_answer or ticket.draft_answer or "").strip()
    if not answer:
        return None
    already_validated = ticket.status == "validated"
    updated = update_ticket(
        ticket_id,
        draft_answer=answer,
        status="validated",
        validated_by=validated_by,
    )
    if updated and not already_validated:
        add_node(
            CapturedNode.create(
                title=ticket.question[:120],
                category=ticket.category or "Validated Q&A",
                summary=f"Q: {ticket.question}\nA: {answer}",
                passages=[
                    {"excerpt": answer, "locator": f"validated by {validated_by}"},
                ],
                captured_by=validated_by,
                source="validated_ticket",
                member_context=ticket.chat_context[:2000] if ticket.chat_context else "",
                tags=["qa", ticket.from_role],
                source_ticket_id=ticket_id,
            )
        )
    return updated


def store_stats() -> dict[str, int | str]:
    nodes = list_nodes(limit=500)
    tickets = list_tickets(limit=500)
    return {
        "backend": ayun_db.backend_label(),
        "nodes": len(nodes),
        "tickets_open": sum(1 for t in tickets if t.status == "open"),
        "tickets_answered": sum(1 for t in tickets if t.status == "answered"),
        "tickets_validated": sum(1 for t in tickets if t.status == "validated"),
    }
