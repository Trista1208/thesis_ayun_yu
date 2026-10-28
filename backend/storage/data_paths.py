"""Writable data directory for JSON stores (local dev vs serverless)."""

from __future__ import annotations

import json
import os
from pathlib import Path

_REPO_DATA = Path(__file__).resolve().parents[1] / "data"
_DEMO_DATA = Path(__file__).resolve().parents[2] / "database" / "demo"


def _use_tmp_data() -> bool:
    """Vercel/Lambda deploy bundles are read-only under /var/task."""
    if os.environ.get("AYUN_DATA_DIR", "").strip():
        return False
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
        return True
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return True
    return False


def data_root() -> Path:
    override = os.environ.get("AYUN_DATA_DIR", "").strip()
    if override:
        root = Path(override)
    elif _use_tmp_data():
        root = Path("/tmp/ayun-data")
    else:
        root = _REPO_DATA
    root.mkdir(parents=True, exist_ok=True)
    return root


def subdir(name: str) -> Path:
    path = data_root() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def writable_json(relative_path: str, *, default: str = "[]") -> Path:
    """
    Path to a JSON file under the writable data root.

    On Vercel/Lambda, seed from the committed repo snapshot (backend/data/…)
    the first time the file is missing so bundled accounts/tickets are available.
    """
    dest = data_root() / relative_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    repo = _REPO_DATA / relative_path
    demo = _DEMO_DATA / relative_path
    if not dest.exists():
        seed = repo if repo.is_file() and repo.resolve() != dest.resolve() else None
        if seed is None and demo.is_file():
            seed = demo
        if seed is not None:
            dest.write_bytes(seed.read_bytes())
        else:
            dest.write_text(default, encoding="utf-8")
    _merge_demo_records(dest, relative_path)
    return dest


def _merge_demo_records(dest: Path, relative_path: str) -> None:
    """Keep fictional manual cases present on Vercel even when /tmp starts empty."""
    demo = _DEMO_DATA / relative_path
    if not demo.is_file():
        return
    try:
        current = json.loads(dest.read_text(encoding="utf-8"))
        extras = json.loads(demo.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(current, list) or not isinstance(extras, list):
        return
    have = {row.get("id") for row in current if isinstance(row, dict)}
    added = [row for row in extras if isinstance(row, dict) and row.get("id") not in have]
    if not added:
        return
    dest.write_text(
        json.dumps(added + current, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def is_ephemeral_store() -> bool:
    return _use_tmp_data() and not os.environ.get("AYUN_DATA_DIR", "").strip()


def backend_label() -> str:
    if os.environ.get("AYUN_DATA_DIR", "").strip():
        return "json_files"
    if _use_tmp_data():
        return "json_files_tmp"
    return "json_files"
