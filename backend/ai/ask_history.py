"""Saved Ask Joule questions and answers for a signed-in member.

JSON is the local store. Supabase is used as well when `ask_history` exists,
so a deploy keeps the conversation after the serverless disk is wiped.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.storage import ayun_db
from backend.storage.data_paths import writable_json

_STORE_FILE = writable_json("knowledge/ask_history.json")
_MAX_EXCHANGES = 40
_MAX_ANSWER = 12000
_MAX_QUESTION = 4000


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def _trim(user_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mine = [row for row in rows if row.get("user_id") == user_id]
    others = [row for row in rows if row.get("user_id") != user_id]
    mine.sort(key=lambda row: row.get("created_at") or "")
    if len(mine) > _MAX_EXCHANGES:
        dropped = {row["id"] for row in mine[:-_MAX_EXCHANGES]}
        mine = mine[-_MAX_EXCHANGES:]
        for item_id in dropped:
            ayun_db.delete_ask_history_ids([item_id])
    return others + mine


def _public(row: dict[str, Any]) -> dict[str, Any]:
    citations = row.get("citations") if isinstance(row.get("citations"), list) else []
    return {
        "id": row.get("id") or "",
        "question": row.get("question") or "",
        "answer": row.get("answer") or "",
        "mode": row.get("mode") or "cited",
        "citations": citations[:8],
        "confidence": row.get("confidence") or "",
        "created_at": row.get("created_at") or "",
    }


def list_ask_history(user_id: str, *, limit: int = _MAX_EXCHANGES) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in _read_rows():
        if row.get("user_id") == user_id and row.get("id"):
            by_id[row["id"]] = row
    remote = ayun_db.list_ask_history(user_id, limit=limit)
    if remote is not None:
        for row in remote:
            if row.get("id"):
                by_id[row["id"]] = row
    rows = list(by_id.values())
    rows.sort(key=lambda row: row.get("created_at") or "")
    return [_public(row) for row in rows[-limit:]]


def save_ask_exchange(
    user_id: str,
    *,
    question: str,
    answer: str,
    mode: str = "cited",
    citations: list | None = None,
    confidence: str = "",
) -> dict[str, Any] | None:
    question = (question or "").strip()
    answer = (answer or "").strip()
    if not user_id or not question or not answer:
        return None
    record = {
        "id": str(uuid.uuid4())[:12],
        "user_id": user_id,
        "question": question[:_MAX_QUESTION],
        "answer": answer[:_MAX_ANSWER],
        "mode": "talk" if mode == "talk" else "cited",
        "citations": (citations or [])[:8],
        "confidence": (confidence or "")[:32],
        "created_at": _now_iso(),
    }
    rows = _trim(user_id, _read_rows() + [record])
    _write_rows(rows)
    ayun_db.upsert_ask_history(record)
    return _public(record)


def delete_ask_history(user_id: str) -> int:
    rows = _read_rows()
    kept = [row for row in rows if row.get("user_id") != user_id]
    deleted = len(rows) - len(kept)
    _write_rows(kept)
    remote = ayun_db.delete_ask_history_for_user(user_id)
    if remote is not None:
        deleted = max(deleted, remote)
    return deleted
