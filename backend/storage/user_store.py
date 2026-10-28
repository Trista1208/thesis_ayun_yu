"""App user accounts — local JSON store (Supabase optional via ayun_db)."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.storage import ayun_db
from backend.storage.data_paths import is_ephemeral_store, writable_json

_STORE_FILE = writable_json("users/app_users.json")
_PBKDF2_ITERS = 120_000


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_store() -> None:
    writable_json("users/app_users.json")


def _read_rows() -> list[dict[str, Any]]:
    _ensure_store()
    try:
        data = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_rows(rows: list[dict[str, Any]]) -> None:
    _ensure_store()
    _STORE_FILE.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ITERS,
    ).hex()
    return f"pbkdf2_sha256${_PBKDF2_ITERS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        check = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iters),
        ).hex()
        return secrets.compare_digest(check, digest)
    except (ValueError, TypeError):
        return False


@dataclass
class AppUser:
    id: str
    email: str
    password_hash: str
    display_name: str
    pseudonym: str = ""
    member_data: dict[str, Any] = field(default_factory=dict)
    personal_profile: dict[str, Any] = field(default_factory=dict)
    enabled_sections: dict[str, bool] = field(default_factory=dict)
    privacy_settings: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> AppUser:
        from backend.ai.memory_store import default_privacy_settings
        return cls(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            display_name=row.get("display_name") or "",
            pseudonym=row.get("pseudonym") or "",
            member_data=row.get("member_data") or {},
            personal_profile=row.get("personal_profile") or {},
            enabled_sections=row.get("enabled_sections") or {},
            privacy_settings=row.get("privacy_settings") or default_privacy_settings(),
            created_at=row.get("created_at") or "",
            updated_at=row.get("updated_at") or "",
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "pseudonym": self.pseudonym,
            "member_data": self.member_data,
            "personal_profile": self.personal_profile,
            "enabled_sections": self.enabled_sections,
            "privacy_settings": self.privacy_settings,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _default_privacy() -> dict[str, Any]:
    from backend.ai.memory_store import default_privacy_settings
    return default_privacy_settings()


def _find_by_email(email: str) -> AppUser | None:
    needle = email.strip().lower()
    for row in _read_rows():
        if (row.get("email") or "").strip().lower() == needle:
            return AppUser.from_row(row)
    return None


def _find_by_id(user_id: str) -> AppUser | None:
    for row in _read_rows():
        if row.get("id") == user_id:
            return AppUser.from_row(row)
    return None


def _write_local_user(user: AppUser) -> None:
    """Insert or replace by id/email in the JSON store."""
    rows = _read_rows()
    replaced = False
    for i, row in enumerate(rows):
        same_id = row.get("id") == user.id
        same_email = (row.get("email") or "").strip().lower() == user.email
        if same_id or same_email:
            rows[i] = asdict(user)
            replaced = True
            break
    if not replaced:
        rows.insert(0, asdict(user))
    _write_rows(rows)


def _sync_remote(user: AppUser) -> bool:
    if not ayun_db.is_configured():
        return False
    return ayun_db.upsert_app_user(user.public_dict(), password_hash=user.password_hash)


def register_user(email: str, password: str, display_name: str = "") -> AppUser:
    email_clean = email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise ValueError("Valid email required")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")
    if get_user_by_email(email_clean):
        raise ValueError("An account with this email already exists")

    now = _now_iso()
    user = AppUser(
        id=str(uuid.uuid4()),
        email=email_clean,
        password_hash=_hash_password(password),
        display_name=(display_name or email_clean.split("@")[0]).strip(),
        member_data={"Demographic::Age": 35, "Demographic::Sex": "Male"},
        personal_profile={
            "name": "",
            "goals": [],
            "activity_level": "Moderately Active (2–4h/week)",
            "sport_prefs": [],
            "stress": "Not assessed",
            "depression": "Not assessed",
            "optimism": "Not assessed",
            "injuries": "",
            "notes": "",
        },
        enabled_sections={},
        privacy_settings=_default_privacy(),
        created_at=now,
        updated_at=now,
    )
    _write_local_user(user)
    remote_ok = _sync_remote(user)
    if is_ephemeral_store() and not remote_ok:
        raise ValueError(
            "Could not save the account. Set SUPABASE_URL and SUPABASE_SECRET_KEY on the host."
        )
    return user


def authenticate_user(email: str, password: str) -> AppUser | None:
    user = get_user_by_email(email)
    if not user or not verify_password(password, user.password_hash):
        return None
    upsert_user(user)
    return user


def get_user_by_email(email: str) -> AppUser | None:
    local = _find_by_email(email)
    if local:
        return local
    if ayun_db.is_configured():
        row = ayun_db.get_app_user_by_email(email)
        if row:
            return AppUser.from_row(row)
    return None


def upsert_google_user(email: str, display_name: str = "") -> AppUser:
    email_clean = email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise ValueError("Google did not return a valid email")
    existing = get_user_by_email(email_clean)
    if existing:
        return existing
    return register_user(email_clean, secrets.token_urlsafe(32), display_name)


def get_user(user_id: str) -> AppUser | None:
    local = _find_by_id(user_id)
    remote = None
    if ayun_db.is_configured():
        row = ayun_db.get_app_user(user_id)
        if row:
            merged = {**row}
            if local and not merged.get("privacy_settings"):
                merged["privacy_settings"] = local.privacy_settings
            remote = AppUser.from_row(merged)
    user = remote or local
    if user and remote and not local:
        _write_local_user(user)
    return user


def ensure_from_session(session: dict[str, Any]) -> AppUser | None:
    """Resolve a member from a valid JWT, including email fallback after a cold start."""
    user_id = str(session.get("user_id") or "").strip()
    email = str(session.get("email") or "").strip().lower()
    name = str(session.get("name") or "").strip()
    user = get_user(user_id) if user_id else None
    if user:
        return user
    if email:
        user = get_user_by_email(email)
        if user:
            return user
    if not user_id or not email:
        return None
    now = _now_iso()
    user = AppUser(
        id=user_id,
        email=email,
        password_hash=_hash_password(secrets.token_urlsafe(32)),
        display_name=name or email.split("@")[0],
        member_data={"Demographic::Age": 35, "Demographic::Sex": "Male"},
        personal_profile={
            "name": name,
            "goals": [],
            "activity_level": "Moderately Active (2–4h/week)",
            "sport_prefs": [],
            "stress": "Not assessed",
            "depression": "Not assessed",
            "optimism": "Not assessed",
            "injuries": "",
            "notes": "",
        },
        enabled_sections={},
        privacy_settings=_default_privacy(),
        created_at=now,
        updated_at=now,
    )
    return upsert_user(user)


def upsert_user(user: AppUser) -> AppUser:
    """Create or replace an account by id or email (demo seed / sync)."""
    _write_local_user(user)
    if ayun_db.is_configured():
        ayun_db.upsert_app_user(user.public_dict(), password_hash=user.password_hash)
        if user.pseudonym:
            ayun_db.upsert_member(user.pseudonym)
    return user


def update_user_profile(
    user_id: str,
    *,
    display_name: str | None = None,
    pseudonym: str | None = None,
    member_data: dict[str, Any] | None = None,
    personal_profile: dict[str, Any] | None = None,
    enabled_sections: dict[str, bool] | None = None,
    privacy_settings: dict[str, Any] | None = None,
) -> AppUser | None:
    user = get_user(user_id)
    if not user:
        return None
    if display_name is not None:
        user.display_name = display_name.strip()
    if pseudonym is not None:
        user.pseudonym = pseudonym.strip()
    if member_data is not None:
        user.member_data = member_data
    if personal_profile is not None:
        user.personal_profile = {**user.personal_profile, **personal_profile}
    if enabled_sections is not None:
        user.enabled_sections = enabled_sections
    if privacy_settings is not None:
        user.privacy_settings = {**user.privacy_settings, **privacy_settings}
    user.updated_at = _now_iso()
    return upsert_user(user)
