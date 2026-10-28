from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    from backend.storage import ayun_db
    from backend.ai import chatbot as cb
    from backend.auth import expert_auth
    from backend.storage.data_paths import backend_label as data_backend, data_root, is_ephemeral_store

    elevenlabs = False
    try:
        from backend.voice import elevenlabs_voice as el_voice

        elevenlabs = el_voice.is_configured()
    except Exception:
        elevenlabs = False

    supabase = ayun_db.is_configured()
    ephemeral = is_ephemeral_store()
    return {
        "status": "ok",
        "service": "ayun-api",
        "ai_configured": cb.is_configured(),
        "expert_configured": expert_auth.is_configured(),
        "elevenlabs": elevenlabs,
        "db_backend": ayun_db.backend_label(),
        "data_store": data_backend(),
        "data_path": str(data_root()),
        "persistent_storage": supabase or not ephemeral,
        "storage_hint": (
            None
            if supabase or not ephemeral
            else (ayun_db.config_hint() or (
                "Vercel uses temporary storage — set SUPABASE_URL and SUPABASE_SECRET_KEY "
                "(sb_secret_…, not Public) and run database/migrations/004_plan_reviews.sql "
                "so tickets and plans persist."
            ))
        ),
    }
