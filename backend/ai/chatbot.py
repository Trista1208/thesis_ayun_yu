"""
Chatbot layer for Ask Joule, expert assist, and extract.

Uses a free model: Gemini Flash when a free key is set (local and remote).
Otherwise local Ollama (Qwen 2.5, then DeepSeek). Kimi/OpenAI are not used
unless AYUN_ALLOW_PAID_LLM=1.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from openai import OpenAI

DEFAULT_MODEL = "qwen2.5:7b"
LOCAL_FALLBACK_MODEL = "deepseek-r1:7b"
GEMINI_DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_EMBED_MODEL = "text-embedding-3-small"
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_ollama_found: tuple[str, str] | None = None
_ollama_fallback: str | None = None


@dataclass(frozen=True)
class LlmSettings:
    base_url: str | None
    api_key: str
    model: str
    embed_model: str
    provider: str


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _cloud_host() -> bool:
    return bool(
        _env("VERCEL")
        or _env("VERCEL_ENV")
        or _env("RAILWAY_ENVIRONMENT")
        or _env("RAILWAY_PUBLIC_DOMAIN")
    )


def _azure_base(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    if "/openai" in base:
        return base
    return f"{base}/openai/v1"


def _probe_ollama() -> tuple[str, str] | None:
    if _env("OLLAMA_DISABLED").lower() in {"1", "true", "yes"}:
        return None
    host = _env("OLLAMA_HOST")
    if not host:
        if _cloud_host():
            return None
        host = "http://127.0.0.1:11434"
    try:
        req = urllib.request.Request(
            f"{host.rstrip('/')}/api/tags",
            headers={"User-Agent": "ayun"},
        )
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    names = [
        str(item.get("name") or item.get("model") or "").strip()
        for item in (data.get("models") or [])
    ]
    names = [name for name in names if name]
    if not names:
        return None
    local = [
        name
        for name in names
        if "cloud" not in name.lower() and "kimi" not in name.lower()
    ]
    preferred = _env("OLLAMA_MODEL") or DEFAULT_MODEL
    model = None
    if preferred:
        for name in local:
            if name == preferred or name.startswith(f"{preferred}:") or preferred in name:
                model = name
                break
    if not model:
        for needle in ("qwen2.5", "qwen", "llama3.1", "llama3", LOCAL_FALLBACK_MODEL, "deepseek"):
            hit = next((name for name in local if needle in name.lower()), None)
            if hit:
                model = hit
                break
    if not model:
        model = local[0] if local else None
    if not model:
        return None
    global _ollama_fallback
    _ollama_fallback = next((name for name in local if name != model), None)
    return f"{host.rstrip('/')}/v1", model


def _ollama_settings() -> tuple[str, str] | None:
    global _ollama_found
    if _ollama_found:
        return _ollama_found
    found = _probe_ollama()
    if found:
        _ollama_found = found
    return found


def _paid_allowed() -> bool:
    return _env("AYUN_ALLOW_PAID_LLM").lower() in {"1", "true", "yes"}


def _free_cloud_settings(embed: str) -> LlmSettings | None:
    gemini_key = _env("GEMINI_API_KEY") or _env("GOOGLE_GENERATIVE_AI_API_KEY")
    if gemini_key:
        return LlmSettings(
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            gemini_key,
            _env("GEMINI_MODEL") or GEMINI_DEFAULT_MODEL,
            embed,
            "gemini",
        )
    return None


def _llm() -> LlmSettings | None:
    model = _env("OLLAMA_MODEL") or DEFAULT_MODEL
    embed = _env("OPENAI_EMBED_MODEL") or _env("GITHUB_EMBED_MODEL") or DEFAULT_EMBED_MODEL

    cloud = _free_cloud_settings(embed)
    if cloud:
        return cloud

    if not _cloud_host():
        ollama = _ollama_settings()
        if ollama:
            base, omodel = ollama
            return LlmSettings(base, "ollama", omodel, embed, "ollama")
        return None

    if not _paid_allowed():
        return None

    openai_key = _env("OPENAI_API_KEY")
    if openai_key:
        return LlmSettings(
            _env("OPENAI_BASE_URL") or None,
            openai_key,
            _env("OPENAI_MODEL") or DEFAULT_MODEL,
            embed,
            "openai",
        )

    azure_key = _env("AZURE_OPENAI_API_KEY") or _env("AZURE_AI_API_KEY")
    azure_ep = _env("AZURE_OPENAI_ENDPOINT") or _env("AZURE_AI_ENDPOINT")
    if azure_key and azure_ep:
        azure_model = _env("AZURE_OPENAI_MODEL") or _env("AZURE_OPENAI_DEPLOYMENT") or model
        return LlmSettings(_azure_base(azure_ep), azure_key, azure_model, embed, "azure")
    return None


def __getattr__(name: str):
    if name == "MODEL":
        cfg = _llm()
        return cfg.model if cfg else (_env("OPENAI_MODEL") or _env("GITHUB_MODEL") or DEFAULT_MODEL)
    if name == "ENDPOINT":
        cfg = _llm()
        return cfg.base_url or ""
    if name == "EMBED_MODEL":
        cfg = _llm()
        return cfg.embed_model if cfg else DEFAULT_EMBED_MODEL
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _deployment_hint() -> str:
    if _llm():
        return ""
    if _cloud_host():
        return (
            "Remote Ask Joule uses a free Gemini key. "
            "Add GEMINI_API_KEY from aistudio.google.com/app/apikey "
            "(no credit card) on the host, then redeploy."
        )
    return (
        "Ask Joule uses a free local model. Start Ollama "
        "(https://ollama.com) — Qwen 2.5 or DeepSeek R1."
    )


def ai_config() -> dict[str, str | bool]:
    cfg = _llm()
    out: dict[str, str | bool] = {
        "configured": bool(cfg),
        "model": cfg.model if cfg else DEFAULT_MODEL,
        "provider": cfg.provider if cfg else "none",
        "mode": "remote" if _cloud_host() else "local",
    }
    if cfg and cfg.provider == "ollama" and _ollama_fallback:
        out["fallback"] = _ollama_fallback
    if not cfg:
        out["hint"] = _deployment_hint()
    return out


def _strip_think(text: str) -> str:
    return _THINK_RE.sub("", text or "").strip()


def _coerce_content(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(getattr(item, "text", None) or getattr(item, "content", None) or ""))
        return "".join(parts)
    return str(content)


def _message_text(message: object) -> str:
    content = _strip_think(_coerce_content(getattr(message, "content", None)))
    if content:
        return content
    return _strip_think(_coerce_content(getattr(message, "reasoning", None)))


def _max_tokens(requested: int, spoken: bool = False) -> int:
    if spoken:
        return requested
    cfg = _llm()
    if cfg and cfg.provider == "ollama" and "r1" in cfg.model.lower():
        return max(requested, 1600)
    return requested


def request_extras() -> dict:
    """Provider-specific chat.completions.create kwargs."""
    return {}


class _OllamaChatCompletions:
    def __init__(self, host: str):
        self.host = host.rstrip("/")

    def create(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float = 0.4,
        max_tokens: int = 1024,
        stream: bool = False,
        **_ignored: object,
    ):
        models = [model]
        if _ollama_fallback and _ollama_fallback not in models:
            models.append(_ollama_fallback)
        last_error: Exception | None = None
        for candidate in models:
            body = {
                "model": candidate,
                "messages": messages,
                "stream": bool(stream),
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "num_ctx": 16384,
                },
            }
            try:
                req = self._request(body)
                if stream:
                    return self._stream(req)
                data = self._read_json(req)
                message = data.get("message") or {}
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content=message.get("content") or "",
                                reasoning=message.get("thinking") or message.get("reasoning") or "",
                            )
                        )
                    ]
                )
            except PermissionError as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        raise RuntimeError("Ollama returned no model")

    def _request(self, body: dict) -> urllib.request.Request:
        return urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "ayun"},
            method="POST",
        )

    def _read_json(self, req: urllib.request.Request) -> dict:
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode() if exc.fp else str(exc)
            if exc.code in {401, 403} or "unauthorized" in raw.lower():
                raise PermissionError(raw) from exc
            raise
        data = json.loads(raw) if raw else {}
        if isinstance(data, dict) and data.get("error"):
            err = str(data["error"])
            if "unauthorized" in err.lower() or "sign in" in err.lower():
                raise PermissionError(err)
            raise RuntimeError(err)
        return data

    def _stream(self, req: urllib.request.Request):
        with urllib.request.urlopen(req, timeout=180) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = data.get("message") or {}
                piece = message.get("content") or ""
                if piece:
                    yield SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content=piece))]
                    )


class _OllamaClient:
    def __init__(self, host: str):
        self.chat = SimpleNamespace(completions=_OllamaChatCompletions(host))


def complete(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 1024,
) -> str:
    """Single completion — same client and model as all app AI features."""
    if not is_configured():
        raise RuntimeError(_deployment_hint() or "AI is not configured")
    client = _build_client()
    response = client.chat.completions.create(
        model=__getattr__("MODEL"),
        messages=messages,
        temperature=temperature,
        max_tokens=_max_tokens(max_tokens),
        **request_extras(),
    )
    return _message_text(response.choices[0].message)


_PROMPT_PATH = Path(__file__).parent / "prompts" / "sports_scientist.txt"


def _base_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def _build_client():
    cfg = _llm()
    if not cfg:
        raise RuntimeError(_deployment_hint() or "AI is not configured")
    if cfg.provider == "ollama":
        host = (cfg.base_url or "http://127.0.0.1:11434/v1").rstrip("/")
        if host.endswith("/v1"):
            host = host[:-3]
        return _OllamaClient(host)
    kwargs: dict[str, object] = {"api_key": cfg.api_key, "timeout": 90.0}
    if cfg.base_url:
        kwargs["base_url"] = cfg.base_url
    return OpenAI(**kwargs)


_TALK_MODE = """
You are on a live voice call. Speak like a coach, not a report.
- 2 to 4 short sentences. About 40–70 words. Stop there.
- One idea only, then a brief question so they can answer.
- No markdown, headings, bullet lists, "Next step", or citation markers.
- Do not read a full weekly plan unless they ask. Give one thing to do now.
- If they want more, they will say so on the next turn.
- If clinic-validated answers are in the prompt and they match the question, reuse them instead of inventing a new programme.

You can offer to send a question to an AYUN doctor / sports scientist without the member leaving this call.
- If they ask you to tell a doctor, create a ticket, or send something to the AYUN team, and you know what to ask: say you can send it after they confirm, then end with one machine line exactly:
TICKET: <one clear question for the doctor>
- If they only say "ask a doctor" with no topic, ask what to send. Do not write TICKET yet.
- If they confirm (yes / please send it) after you offered, write TICKET with the topic from the conversation. Do not say it is already sent — they still confirm on screen.
- Never write TICKET for ordinary training chat. Never read the TICKET line out loud as a label. Never claim a ticket was filed.
""".strip()

_TALK_MODE_DE = """
Du bist in einem Live-Gespräch. Sprich wie ein Coach, nicht wie ein Bericht.
- Antworte auf Deutsch.
- 2 bis 4 kurze Sätze. Etwa 40–70 Wörter. Dann Schluss.
- Eine Idee, dann eine kurze Frage zurück.
- Kein Markdown, keine Listen, keine Zitate.
- Keinen ganzen Wochenplan vorlesen, ausser sie fragen danach.
- Wenn klinik-validierte Antworten im Prompt stehen und zur Frage passen, diese wiederverwenden statt ein neues Programm zu erfinden.

Du kannst anbieten, eine Frage an einen AYUN-Arzt / Sports Scientist zu schicken, ohne dass die Person die App wechseln muss.
- Wenn sie dich bittet, das einem Arzt zu sagen oder ein Ticket zu erstellen, und das Thema klar ist: sage, dass sie unten bestätigen kann, und beende mit genau einer Maschinenzeile:
TICKET: <eine klare Frage an den Arzt, auf Deutsch oder Englisch>
- Wenn nur "frag den Arzt" kommt ohne Thema, frage nach dem Inhalt. Noch kein TICKET.
- Bei Bestätigung (ja / bitte schicken) nach deinem Angebot: TICKET mit dem Thema aus dem Gespräch. Nicht sagen, es sei schon abgeschickt — sie bestätigt noch auf dem Bildschirm.
- Kein TICKET bei normalem Training-Chat. Die TICKET-Zeile nicht vorlesen. Nie behaupten, ein Ticket sei schon erstellt.
""".strip()


def build_system_prompt(context: str, spoken: bool = False, language: str = "en") -> str:
    """
    Inject member-specific context (recommendations, training zones, values)
    into the sports scientist system prompt.
    """
    cite_rules = (
        "Cite sources with compact markers only: [Member] for this member's plan, "
        "[Protocol] or [n] for AYUN clinic protocols, [Web n] for evidence reviews. "
        "If clinic-validated answers are in the prompt, reuse them for similar questions. "
        "Never print banners such as MEMBER CONTEXT or 'use this data when answering'."
    )
    if spoken:
        cite_rules = (
            "Do not speak citation markers. Stay with this member's matched plan. "
            "If clinic-validated answers are in the prompt, reuse them when they fit."
        )
    parts = [_base_system_prompt(), cite_rules]
    if (context or "").strip():
        parts.append("--- This member's plan ---\n" + context + "\n--- End of member plan ---")
    if spoken:
        parts.append(_TALK_MODE_DE if (language or "en").lower().startswith("de") else _TALK_MODE)
    return "\n\n".join(parts)


def _chat_sync(
    messages: list[dict],
    context: str,
    spoken: bool = False,
    language: str = "en",
    max_tokens: int | None = None,
) -> str:
    client = _build_client()
    system_msg = {"role": "system", "content": build_system_prompt(context, spoken=spoken, language=language)}
    full_messages = [system_msg] + messages
    limit = max_tokens if max_tokens is not None else (200 if spoken else 700)
    response = client.chat.completions.create(
        model=__getattr__("MODEL"),
        messages=full_messages,
        stream=False,
        temperature=0.55 if spoken else 0.4,
        max_tokens=_max_tokens(limit, spoken=spoken),
        **request_extras(),
    )
    return _message_text(response.choices[0].message)


def _chat_stream(messages: list[dict], context: str, spoken: bool = False, language: str = "en"):
    client = _build_client()
    system_msg = {"role": "system", "content": build_system_prompt(context, spoken=spoken, language=language)}
    full_messages = [system_msg] + messages
    response = client.chat.completions.create(
        model=__getattr__("MODEL"),
        messages=full_messages,
        stream=True,
        temperature=0.55 if spoken else 0.4,
        max_tokens=_max_tokens(200 if spoken else 700, spoken=spoken),
        **request_extras(),
    )
    pending = ""
    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        piece = getattr(delta, "content", None) or ""
        if not piece:
            continue
        pending += piece
        pending = _THINK_RE.sub("", pending)
        open_at = pending.lower().find("<think>")
        if open_at >= 0:
            visible, pending = pending[:open_at], pending[open_at:]
            if visible:
                yield visible
            continue
        keep = min(8, len(pending))
        visible, pending = pending[:-keep], pending[-keep:]
        if visible:
            yield visible
    leftover = _strip_think(pending)
    if leftover:
        yield leftover


def chat(
    messages: list[dict],
    context: str,
    stream: bool = True,
    spoken: bool = False,
    language: str = "en",
    max_tokens: int | None = None,
):
    """
    Send a conversation to the configured LLM.

    stream=False → returns full response string.
    stream=True  → returns a generator of text chunks.
    spoken=True  → short coach-on-a-call replies for Talk with Joule.
    """
    if stream:
        return _chat_stream(messages, context, spoken=spoken, language=language)
    return _chat_sync(
        messages, context, spoken=spoken, language=language, max_tokens=max_tokens
    )


def is_configured() -> bool:
    """Return True if a working LLM provider is available."""
    return _llm() is not None


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """Return embedding vectors for semantic search, or None if unavailable."""
    if not is_configured() or not texts:
        return None
    try:
        client = _build_client()
        response = client.embeddings.create(model=__getattr__("EMBED_MODEL"), input=texts)
        return [item.embedding for item in response.data]
    except Exception:
        return None
