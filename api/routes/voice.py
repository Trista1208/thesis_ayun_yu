from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.deps import load_env

load_env()

from backend.voice.elevenlabs_voice import VoiceError, stream_speech, voice_catalog  # noqa: E402

router = APIRouter(prefix="/voice", tags=["voice"])


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    voice_id: str | None = None


@router.get("/voices")
def voices():
    return voice_catalog()


@router.post("/speak")
def speak(body: SpeakRequest):
    try:
        audio = stream_speech(body.text, body.voice_id)
        return StreamingResponse(
            audio,
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store"},
        )
    except VoiceError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
