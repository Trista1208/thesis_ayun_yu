"""Talk with Joule can file an AYUN expert ticket from the live conversation."""

from __future__ import annotations

import re

from urllib.parse import quote, unquote

TICKET_MARK = re.compile(r"(?:^|\n)\s*TICKET:\s*(.+?)\s*$", re.IGNORECASE | re.DOTALL)
TRAILER = "<!--ayun-ticket:{id}-->"
PROPOSE_TRAILER = "<!--ayun-ticket-propose:{question}-->"
_ALREADY_SENT = re.compile(
    r"\b(i(?:['’]?ve| have) sent|i(?:['’]?m| am) sending|ich habe .+ geschickt)\b[^.]*\.?",
    re.IGNORECASE,
)

_ASK_DOCTOR = re.compile(
    r"\b("
    r"ask (?:the |an )?(?:doctor|expert|clinician|sports scientist)|"
    r"send (?:this |it )?(?:to )?(?:the )?(?:doctor|expert|ayun|team)|"
    r"(?:open|create|file|raise) (?:a |an )?ticket|"
    r"talk to (?:a |the )?(?:doctor|expert)|"
    r"have (?:a |an )?(?:doctor|expert) (?:look|check|review)|"
    r"pass this (?:on |to )?(?:an? )?(?:expert|doctor)|"
    r"frag(?:e|en)? (?:den |einen )?(?:arzt|doktor|experten)|"
    r"an (?:das )?ayun|"
    r"ticket (?:erstellen|schicken|aufmachen)"
    r")\b",
    re.IGNORECASE,
)

_YES = re.compile(r"^\s*(yes|yeah|yep|ok|okay|please|do it|go ahead|sure|ja|bitte|mach\s+das)\s*[.!]?\s*$", re.I)
_NO = re.compile(r"\b(no|nope|don't|do not|not now|never|nein|nicht|lass\s+es)\b", re.I)
_OFFERED = re.compile(r"\b(doctor|expert|clinician|ticket|ayun|arzt|experte)\b", re.I)


def split_ticket_marker(reply: str) -> tuple[str, str]:
    text = (reply or "").strip()
    match = TICKET_MARK.search(text)
    if not match:
        return text, ""
    question = " ".join(match.group(1).split()).strip(" -–")
    spoken = TICKET_MARK.sub("", text).strip()
    return spoken, question


def last_user_text(messages: list[dict]) -> str:
    for item in reversed(messages):
        if item.get("role") == "user":
            return str(item.get("content") or "").strip()
    return ""


def prior_user_text(messages: list[dict]) -> str:
    seen = 0
    for item in reversed(messages):
        if item.get("role") != "user":
            continue
        seen += 1
        if seen == 2:
            return str(item.get("content") or "").strip()
    return ""


def assistant_offered_ticket(messages: list[dict]) -> bool:
    for item in reversed(messages):
        if item.get("role") == "assistant":
            return bool(_OFFERED.search(str(item.get("content") or "")))
    return False


def _enough_detail(text: str) -> bool:
    words = [w for w in text.split() if w]
    if len(words) >= 8:
        return True
    return bool(
        re.search(
            r"\b(vo2|hrv|heart|blood|sleep|pain|injury|zone|cholesterol|glucose|a1c)\b",
            text,
            re.I,
        )
    )


def ticket_question_from_talk(messages: list[dict], reply: str) -> tuple[str, str]:
    spoken, marked = split_ticket_marker(reply)
    if marked:
        return spoken, marked
    last = last_user_text(messages)
    if not last or _NO.search(last):
        return spoken, ""
    if _YES.match(last) and assistant_offered_ticket(messages):
        return spoken, prior_user_text(messages) or last
    if _ASK_DOCTOR.search(last) and _enough_detail(last):
        return spoken, last
    return spoken, ""


def encode_ticket_propose(question: str) -> str:
    return PROPOSE_TRAILER.format(question=quote((question or "").strip(), safe=""))


def decode_ticket_propose(raw: str) -> str:
    try:
        return unquote(raw or "").strip()
    except Exception:
        return (raw or "").strip()


def propose_ticket_spoken(spoken: str, language: str) -> str:
    text = _ALREADY_SENT.sub("", spoken or "").strip()
    if (language or "en").lower().startswith("de"):
        extra = "Bestätige unten, wenn ich das an das AYUN-Team schicken soll."
    else:
        extra = "Confirm below if you want me to send this to the AYUN team."
    lowered = text.lower()
    if "confirm" in lowered or "bestätig" in lowered:
        return text
    return f"{text} {extra}".strip() if text else extra


def confirm_ticket_spoken(spoken: str, language: str) -> str:
    text = (spoken or "").strip()
    lowered = text.lower()
    if any(token in lowered for token in ("ayun", "ticket", "arzt", "experte", "team")):
        return text
    if (language or "en").lower().startswith("de"):
        extra = "Ich habe das an das AYUN-Team geschickt. Ein Experte schaut es sich an."
    else:
        extra = "I've sent that to the AYUN team. An expert will look at it."
    return f"{text} {extra}".strip() if text else extra


def format_chat_context(messages: list[dict], limit: int = 8) -> str:
    lines = []
    for item in messages[-limit:]:
        role = "Member" if item.get("role") == "user" else "Joule"
        content = " ".join(str(item.get("content") or "").split())
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)
