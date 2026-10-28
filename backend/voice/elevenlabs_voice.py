"""ElevenLabs TTS for Talk with Joule. The API key stays on the server."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator

_ROOT = Path(__file__).resolve().parents[2]

ELEVEN_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
DEFAULT_MODEL = "eleven_multilingual_v2"
MAX_CHARS = 2500

# Jiaqi is a personal clone. Coaches are conversational premade voices.
# German male coach so Talk can run in Deutsch.
JOULE_VOICES: list[dict[str, str]] = [
    {
        "id": "6q2fEVEF7Uvhqy2k7Ep5",
        "name": "Jiaqi",
        "vibe": "Talk to a real person",
        "lang": "en",
        "greeting": (
            "Hey... I'm Joule, your sports scientist. "
            "This is Jiaqi — an Asian woman speaking English. "
            "Feel free to talk with me, I'm right here."
        ),
    },
    {
        "id": "iP95p4xoKVk53GoZ742B",
        "name": "Male coach",
        "vibe": "Warm, calm American — conversational",
        "lang": "en",
        "greeting": (
            "Hey... I'm Joule, your sports scientist. "
            "This is a calm English-speaking male coach. "
            "Feel free to talk with me whenever you're ready."
        ),
    },
    {
        "id": "pFZP5JQG7iQjIQuC4Bku",
        "name": "Female coach",
        "vibe": "Light British — warm, not a narrator",
        "lang": "en",
        "greeting": (
            "Hey... I'm Joule, your sports scientist. "
            "This is a warm English-speaking female coach. "
            "Feel free to talk with me, I'm listening."
        ),
    },
    {
        "id": "Cqbq4nsuUe1we6J45miU",
        "name": "German male coach",
        "vibe": "Deutsch — talk in German",
        "lang": "de",
        "greeting": (
            "Hey... ich bin Joule, dein Sports Scientist. "
            "Du hörst einen deutschen männlichen Coach. "
            "Sprich einfach mit mir, ich bin da."
        ),
    },
]

_ALLOWED = {voice["id"] for voice in JOULE_VOICES}
DEFAULT_VOICE_ID = JOULE_VOICES[0]["id"]


def _key_from_dotenv() -> str:
    env_path = _ROOT / ".env"
    if not env_path.is_file():
        return ""
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("ELEVENLABS_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def api_key() -> str:
    from_file = _key_from_dotenv()
    from_env = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    for candidate in (from_file, from_env):
        if candidate.startswith("sk_"):
            os.environ["ELEVENLABS_API_KEY"] = candidate
            return candidate
    return from_file or from_env


def is_configured() -> bool:
    # ElevenLabs secrets start with sk_. A 64-char hex value is the key *id*,
    # which the API rejects with api_key_id_used_as_api_key.
    return api_key().startswith("sk_")


def setup_hint() -> str | None:
    if is_configured():
        return None
    if api_key():
        return "That ElevenLabs value is a key ID. Create a key and copy the secret that starts with sk_."
    return "Connect ElevenLabs with a secret key (starts with sk_)."


def model_id() -> str:
    return (os.environ.get("ELEVENLABS_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def resolve_voice_id(voice_id: str | None) -> str:
    requested = (voice_id or os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE_ID).strip()
    if requested in _ALLOWED:
        return requested
    return DEFAULT_VOICE_ID


def voice_catalog() -> dict:
    return {
        "configured": is_configured(),
        "model": model_id() if is_configured() else None,
        "default_voice_id": DEFAULT_VOICE_ID,
        "hint": setup_hint(),
        "voices": JOULE_VOICES,
    }


class VoiceError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _prepare_text(text: str) -> str:
    spoken = " ".join((text or "").split()).strip()
    if not spoken:
        raise VoiceError("Nothing to speak.", 400)
    if len(spoken) > MAX_CHARS:
        spoken = spoken[: MAX_CHARS - 1].rsplit(" ", 1)[0] + "."
    return spoken


def stream_speech(text: str, voice_id: str | None = None) -> Iterator[bytes]:
    if not is_configured():
        raise VoiceError("ElevenLabs is not configured on the server.", 503)
    spoken = _prepare_text(text)
    vid = resolve_voice_id(voice_id)
    url = ELEVEN_TTS_URL.format(voice_id=vid) + "?output_format=mp3_44100_128"
    payload = json.dumps(
        {
            "text": spoken,
            "model_id": model_id(),
            "voice_settings": {
                "stability": 0.52,
                "similarity_boost": 0.78,
                "style": 0.15,
                "use_speaker_boost": True,
                "speed": 0.88,
            },
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "xi-api-key": api_key(),
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=90)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        lowered = (detail or str(exc)).lower()
        if "api_key_id_used_as_api_key" in lowered or "start with 'sk_'" in lowered:
            raise VoiceError(
                "That ElevenLabs value is a key ID. Create a key and copy the secret that starts with sk_.",
                401,
            ) from exc
        if exc.code in (400, 401, 403):
            raise VoiceError("The ElevenLabs key was rejected. Check ELEVENLABS_API_KEY.", 401) from exc
        if exc.code == 429 or "quota" in lowered or "credits" in lowered:
            raise VoiceError("ElevenLabs is out of credits right now. Try again later.", 429) from exc
        raise VoiceError("Joule’s voice could not be generated just now.", 502) from exc
    except urllib.error.URLError as exc:
        raise VoiceError("Could not reach ElevenLabs. Check the server connection.", 503) from exc

    def chunks() -> Iterator[bytes]:
        try:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                yield chunk
        finally:
            resp.close()

    return chunks()
