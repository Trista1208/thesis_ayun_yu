"""
Free-text intake: turn a member's pasted notes into structured fields.

Measured values (DEXA, CPET, strength, labs) reuse the report extractor
(regex + LLM). Profile fields (goals, diet, sports, lifestyle) come from one
extra LLM pass constrained to the same option lists the profile form uses.

This only proposes values for the member to review. It never decides
recommendations — the rule engine still does that from the saved fields.
"""

from __future__ import annotations

import json
import re

from backend.documents.pdf_extractor import _smart_extract, to_member_dict

MAX_TEXT_CHARS = 20000

# Keep in sync with web/src/lib/profileFields.ts
GOAL_OPTIONS = [
    "Weight management",
    "Build muscle / hypertrophy",
    "Improve endurance & VO2max",
    "Reduce cardiovascular risk",
    "Improve bone health",
    "Reduce stress & mental wellbeing",
    "Improve sleep quality",
    "Longevity & disease prevention",
    "Improve mobility & flexibility",
    "Rehabilitation / recovery",
    "General wellbeing",
    "Athletic performance",
]
SPORT_OPTIONS = [
    "Running / jogging",
    "Cycling",
    "Swimming",
    "Hiking",
    "Gym / weight training",
    "CrossFit / HIIT",
    "Yoga / Pilates",
    "Team sports (football, basketball…)",
    "Tennis / racket sports",
    "Dancing",
    "Martial arts",
    "Rowing",
    "Climbing",
    "Golf",
]
SELECT_OPTIONS: dict[str, list[str]] = {
    "activity_level": [
        "Sedentary (< 1h/week)",
        "Lightly Active (1–2h/week)",
        "Moderately Active (2–4h/week)",
        "Very Active (4–7h/week)",
        "Athlete (daily training)",
    ],
    "geographic_area": [
        "Switzerland — urban",
        "Switzerland — rural / alpine",
        "Central Europe",
        "Northern Europe",
        "Southern Europe",
        "United Kingdom & Ireland",
        "North America",
        "Asia-Pacific",
        "Other",
    ],
    "health_status": [
        "Good health — no known conditions",
        "Generally healthy — minor issues only",
        "Managing chronic condition(s)",
        "Recovering from illness or injury",
    ],
    "smoking_status": ["Non-smoker", "Former smoker", "Occasional smoker", "Daily smoker"],
    "alcohol_use": [
        "None",
        "Occasional (social)",
        "1–3 drinks / week",
        "4–7 drinks / week",
        "More than 7 drinks / week",
    ],
    "sleep_hours": [
        "Less than 5 hours",
        "5–6 hours",
        "6–7 hours",
        "7–8 hours",
        "8–9 hours",
        "More than 9 hours",
    ],
    "stress": ["Low", "Moderate", "High", "Very High"],
}
TEXT_FIELDS = ["diet", "existing_conditions", "injuries", "location_detail"]


def _profile_prompt() -> str:
    lines = [
        "You read a person's free-text notes about themselves and fill a profile form.",
        "Return ONLY a JSON object with these keys. Use null (or [] for lists) when the",
        "notes do not say. Do NOT guess. For choice fields, copy one option exactly.",
        "",
        '"height_cm": number or null',
        '"weight_kg": number or null',
        f'"goals": list, each one of {json.dumps(GOAL_OPTIONS, ensure_ascii=False)}',
        f'"sport_prefs": list, each one of {json.dumps(SPORT_OPTIONS, ensure_ascii=False)}',
    ]
    for key, opts in SELECT_OPTIONS.items():
        lines.append(f'"{key}": one of {json.dumps(opts, ensure_ascii=False)} or null')
    lines += [
        '"diet": short summary of what and how they eat, or null',
        '"existing_conditions": medical conditions or medications mentioned, or null',
        '"injuries": current or past injuries / pain, or null',
        '"location_detail": city or region if mentioned, or null',
        "",
        "Notes:",
    ]
    return "\n".join(lines)


def _parse_json(raw: str) -> dict:
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    return json.loads(m.group(0) if m else raw)


def _num(v, lo: float, hi: float) -> float | None:
    try:
        f = float(str(v).replace(",", ".").split()[0])
    except (ValueError, TypeError, IndexError):
        return None
    return round(f, 1) if lo <= f <= hi else None


def _clean_profile(data: dict) -> tuple[dict, dict]:
    """Keep only values that match the form's options. Returns (profile, demographics)."""
    profile: dict = {}
    demo: dict = {}

    h = _num(data.get("height_cm"), 100, 250)
    if h is not None:
        demo["Demographic::Height (cm)"] = round(h)
    w = _num(data.get("weight_kg"), 30, 300)
    if w is not None:
        demo["Demographic::Weight (kg)"] = w

    for key, opts in (("goals", GOAL_OPTIONS), ("sport_prefs", SPORT_OPTIONS)):
        vals = data.get(key) or []
        if isinstance(vals, list):
            picked = [v for v in vals if v in opts]
            if picked:
                profile[key] = list(dict.fromkeys(picked))

    for key, opts in SELECT_OPTIONS.items():
        if data.get(key) in opts:
            profile[key] = data[key]

    for key in TEXT_FIELDS:
        v = data.get(key)
        if isinstance(v, str) and v.strip() and v.strip().lower() not in ("null", "none"):
            profile[key] = v.strip()[:500]

    return profile, demo


def _regex_demographics(text: str) -> dict:
    """Height/weight without AI, for simple notes like '180 cm, 78 kg'."""
    out: dict = {}
    m = re.search(r"\b(1\d{2}|2[0-4]\d)(?:[.,]\d)?\s*cm\b", text, re.IGNORECASE)
    if m:
        out["Demographic::Height (cm)"] = int(m.group(1))
    m = re.search(r"\b(\d{2,3}(?:[.,]\d)?)\s*kg\b(?!\s*/)", text, re.IGNORECASE)
    if m:
        w = _num(m.group(1), 30, 300)
        if w is not None:
            out["Demographic::Weight (kg)"] = w
    return out


def parse_free_text(text: str) -> dict:
    from backend.ai import chatbot as cb

    text = (text or "").strip()[:MAX_TEXT_CHARS]
    warnings: list[str] = []
    ai = cb.is_configured()

    extracted = _smart_extract(text, [text])
    member_data = to_member_dict(extracted)
    if any(w.startswith("_llm_error") for w in extracted.warnings):
        warnings.append("AI could not read part of the text — check the values below.")

    profile: dict = {}
    demo = _regex_demographics(text)
    if ai:
        try:
            raw = cb.complete(
                [{"role": "user", "content": _profile_prompt() + "\n" + text}],
                temperature=0,
                max_tokens=700,
            )
            profile, llm_demo = _clean_profile(_parse_json(raw))
            demo = {**llm_demo, **demo}
        except Exception:
            warnings.append("AI could not read goals, diet or lifestyle from the text.")
    else:
        warnings.append(
            "AI is not configured, so only numbers like age, height, weight and DEXA values were read."
        )

    for k, v in demo.items():
        member_data.setdefault(k, v)

    return {
        "member_data": member_data,
        "personal_profile": profile,
        "warnings": warnings,
        "ai_used": ai,
    }
