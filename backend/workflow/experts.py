"""AYUN expert roster and live availability (stored in data/knowledge/)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from backend.storage.data_paths import subdir

_EXPERTS_YAML = Path(__file__).parent / "experts.yaml"
_AVAIL_FILE = subdir("knowledge") / "expert_availability.json"

VALID_STATUSES = ("available", "busy", "away")


@dataclass
class Expert:
    id: str
    name: str
    role: str
    specialties: list[str]
    default_hours: str
    status: str = "available"

    @property
    def is_available(self) -> bool:
        return self.status == "available"

    @property
    def status_label(self) -> str:
        return {"available": "Available", "busy": "Busy", "away": "Away"}.get(
            self.status, self.status
        )

    @property
    def status_emoji(self) -> str:
        return {"available": "🟢", "busy": "🟡", "away": "🔴"}.get(self.status, "⚪")


def _ensure_avail_file() -> None:
    try:
        _AVAIL_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not _AVAIL_FILE.exists():
            _AVAIL_FILE.write_text("{}", encoding="utf-8")
    except OSError:
        return


def _load_availability_map() -> dict[str, str]:
    try:
        _ensure_avail_file()
        if not _AVAIL_FILE.exists():
            return {}
        data = json.loads(_AVAIL_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_availability_map(data: dict[str, str]) -> None:
    try:
        _ensure_avail_file()
        _AVAIL_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        return


def load_experts(include_pool: bool = True) -> list[Expert]:
    try:
        raw = yaml.safe_load(_EXPERTS_YAML.read_text(encoding="utf-8")) or {}
    except OSError:
        raw = {}
    avail = _load_availability_map()
    experts: list[Expert] = []
    for row in raw.get("experts") or []:
        if not include_pool and row.get("id") == "general_pool":
            continue
        eid = row["id"]
        status = avail.get(eid, "available")
        if status not in VALID_STATUSES:
            status = "available"
        experts.append(
            Expert(
                id=eid,
                name=row["name"],
                role=row["role"],
                specialties=list(row.get("specialties") or []),
                default_hours=row.get("default_hours", ""),
                status=status,
            )
        )
    return experts


def get_expert(expert_id: str) -> Expert | None:
    for e in load_experts():
        if e.id == expert_id:
            return e
    return None


def set_expert_availability(expert_id: str, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    avail = _load_availability_map()
    avail[expert_id] = status
    _save_availability_map(avail)


def list_available_experts(include_pool: bool = False) -> list[Expert]:
    return [e for e in load_experts(include_pool=include_pool) if e.is_available]


def expert_options_for_select(include_any: bool = True) -> list[tuple[str, str]]:
    """Return (label, id) pairs for selectbox."""
    opts: list[tuple[str, str]] = []
    for e in load_experts(include_pool=False):
        label = f"{e.status_emoji} {e.name} — {e.status_label}"
        opts.append((label, e.id))
    if include_any:
        pool = get_expert("general_pool")
        if pool:
            opts.append((f"{pool.status_emoji} Any Available Expert", "general_pool"))
    return opts
