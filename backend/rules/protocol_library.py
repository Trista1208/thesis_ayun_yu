"""
AYUN protocol library — loads knowledge/protocols_quick_reference.yml
and formats matched condition protocols + training templates for the LLM.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import re
import yaml

_PROTOCOLS_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "protocols_quick_reference.yml"
NON_AYUN_SOURCE = "General exercise evidence (not covered by AYUN material)"


def source_of(entry: dict) -> str:
    """The AYUN document + section a protocol follows, shown as its source on the website."""
    return (entry.get("ayun_source") or "").strip() or NON_AYUN_SOURCE

# Same rule as the plan cards (rule_engine.ACTION_RATINGS): excellent / good /
# average are fine; below average, poor, elevated and high attach the protocol.
_BAD_RATINGS = {"elevated", "high", "poor", "below_average"}
_SEVERE_RATINGS = _BAD_RATINGS  # legacy alias for callers
_PROTOCOL_BAD_RATINGS: dict[str, set[str]] = {}

# A condition protocol is only attached when that metric was measured AND rated poorly.
_PROTOCOL_PARAMS = {
    "low_vo2max": ("Physiological::Vo2Max",),
    "high_body_fat": (
        "Body Composition::Fat percentage",
        "Body Composition::Visceral Fat Index (raw value from DEXA)",
    ),
    "low_bone_density": ("Body Composition::Bone mineral density",),
    "low_strength_muscle": (
        "Physiological::Gripstrength Rechts",
        "Physiological::Gripstrength Links",
        "Body Composition::Muscle Mass Index (LMI)",
        "Body Composition::ALMI",
    ),
    "elevated_hba1c": ("Blood Biomarkers::HbA1c",),
    "possible_fatty_liver": (
        "Blood Biomarkers::ALAT",
        "Blood Biomarkers::ASAT",
        "Blood Biomarkers::GGT",
    ),
}

_EXTRA_PARAM_MAP = {
    "Physiological::Vo2Max": "low_vo2max",
    "Body Composition::Fat percentage": "high_body_fat",
    "Body Composition::Visceral Fat Index (raw value from DEXA)": "high_body_fat",
    "Body Composition::Bone mineral density": "low_bone_density",
    "Physiological::Gripstrength Rechts": "low_strength_muscle",
    "Physiological::Gripstrength Links": "low_strength_muscle",
    "Body Composition::Muscle Mass Index (LMI)": "low_strength_muscle",
    "Body Composition::ALMI": "low_strength_muscle",
}

_CORE_TEMPLATE_KEYS = [
    "zone2_base",
    "polarized_hiit",
    "full_body_strength",
    "full_body_hypertrophy",
    "strength_bone_health",
    "balance_training",
    "fat_burn_workout",
]


@lru_cache(maxsize=1)
def load_protocols() -> dict:
    if not _PROTOCOLS_PATH.exists():
        return {}
    with open(_PROTOCOLS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _rating_value(rating) -> object:
    return getattr(rating, "value", None) if not isinstance(rating, dict) else rating.get("value")


def _rating_label(rating) -> str:
    raw = getattr(rating, "rating", None) if not isinstance(rating, dict) else rating.get("rating")
    return str(raw or "").lower()


def _rating_parameter(rating) -> str:
    raw = getattr(rating, "parameter", None) if not isinstance(rating, dict) else rating.get("parameter")
    return str(raw or "")


def protocol_is_indicated(protocol_key: str, ratings: list | None) -> bool:
    """True only when the protocol's metric was measured and rated below
    average / elevated or worse. Average never attaches a protocol."""
    params = _PROTOCOL_PARAMS.get(protocol_key)
    if not params:
        return True
    relevant = [
        r for r in (ratings or [])
        if _rating_parameter(r) in params and _rating_value(r) is not None
    ]
    if not relevant:
        return False

    allowed = _PROTOCOL_BAD_RATINGS.get(protocol_key, _BAD_RATINGS)
    return any(_rating_label(r) in allowed for r in relevant)


def match_protocol_keys(
    triggered: list | None = None,
    ratings: list | None = None,
    personal_context: str = "",
) -> list[str]:
    """Return protocol keys supported by this member's measured, poor ratings.

    Free-text goals and training questions must not diagnose a condition.
    Missing values (e.g. no VO2max) never attach that protocol.
    """
    data = load_protocols()
    cond = data.get("condition_protocols") or {}
    mapping = data.get("recommendation_mapping") or {}
    cat_map = mapping.get("category_to_protocol") or {}
    kw_map = mapping.get("title_keywords_to_protocol") or {}
    param_map = {**_EXTRA_PARAM_MAP, **(mapping.get("parameter_to_protocol") or {})}

    candidates: set[str] = set()

    for rec in triggered or []:
        cat = (getattr(rec, "category", None) or "").strip()
        if cat and cat in cat_map:
            candidates.add(cat_map[cat])
        title = (getattr(rec, "title", None) or "").lower()
        for kw, pk in kw_map.items():
            if kw.lower() in title:
                candidates.add(pk)

    for r in ratings or []:
        if _rating_label(r) in _BAD_RATINGS and _rating_parameter(r) in param_map:
            candidates.add(param_map[_rating_parameter(r)])

    return [k for k in cond.keys() if k in candidates and protocol_is_indicated(k, ratings)]


def _fmt_list(items: list | None, indent: str = "      ") -> list[str]:
    if not items:
        return []
    return [f"{indent}• {item}" for item in items]


def list_protocol_catalog() -> list[dict]:
    """Return the immutable AYUN protocol library as API-safe records."""
    data = load_protocols()
    protocols = data.get("condition_protocols") or {}
    templates = data.get("training_templates") or {}
    records: list[dict] = []

    for key, protocol in protocols.items():
        related = []
        for template_key in protocol.get("related_templates") or []:
            template = templates.get(template_key)
            if template:
                related.append({"key": template_key, **template})
        records.append(
            {
                "key": key,
                "kind": "condition_protocol",
                "title": protocol.get("title") or key,
                "description": protocol.get("description") or "",
                "training": protocol.get("training") or {},
                "nutrition_focus": protocol.get("nutrition_focus") or [],
                "recheck_interval": protocol.get("recheck_interval") or "",
                "evidence": protocol.get("evidence") or [],
                "related_templates": related,
                "source": source_of(protocol),
            }
        )

    for key, template in templates.items():
        records.append(
            {
                "key": key,
                "kind": "training_template",
                "title": template.get("title") or key,
                "description": template.get("description") or "",
                "training": {
                    field: template[field]
                    for field in ("frequency", "intensity", "duration", "volume", "rest", "daily_activity")
                    if template.get(field)
                },
                "exercises": template.get("exercises") or [],
                "structure": template.get("structure") or [],
                "zones": template.get("zones") or [],
                "tips": template.get("tips") or [],
                "modalities": template.get("modalities") or [],
                "evidence": template.get("evidence") or [],
                "related_templates": [],
                "source": source_of(template),
            }
        )
    return records


def protocol_record_text(record: dict) -> str:
    """Flatten a protocol record for search and LLM grounding."""
    lines = [
        f"Title: {record.get('title', '')}",
        f"Type: {record.get('kind', '').replace('_', ' ')}",
        f"Description: {record.get('description', '')}",
    ]
    training = record.get("training") or {}
    for field, value in training.items():
        if isinstance(value, list):
            lines.append(f"{field.replace('_', ' ').title()}: {'; '.join(map(str, value))}")
        elif value:
            lines.append(f"{field.replace('_', ' ').title()}: {value}")
    for field in (
        "nutrition_focus",
        "exercises",
        "structure",
        "zones",
        "tips",
        "modalities",
        "evidence",
    ):
        values = record.get(field) or []
        if values:
            lines.append(f"{field.replace('_', ' ').title()}: {'; '.join(map(str, values))}")
    related = record.get("related_templates") or []
    if related:
        lines.append(
            "Related templates: "
            + "; ".join(
                f"{row.get('title', row.get('key', ''))}: {row.get('description', '')}" for row in related
            )
        )
    if record.get("recheck_interval"):
        lines.append(f"Recheck interval: {record['recheck_interval']}")
    return "\n".join(line for line in lines if not line.endswith(": "))


def protocol_cards_for_keys(keys: list[str], max_templates: int = 4) -> list[dict]:
    """Turn protocol keys into the Plan-page card shape."""
    data = load_protocols()
    protocols = data.get("condition_protocols") or {}
    templates = data.get("training_templates") or {}
    cards: list[dict] = []

    for key in keys:
        protocol = protocols.get(key) or {}
        if not protocol:
            continue
        training = protocol.get("training") or {}
        actions: list[str] = []
        if training.get("frequency"):
            actions.append(f"Frequency: {training['frequency']}")
        if training.get("intensity"):
            actions.append(f"Intensity: {training['intensity']}")
        if training.get("duration"):
            actions.append(f"Duration: {training['duration']}")
        actions.extend(training.get("focus") or [])

        template_summaries: list[dict] = []
        for template_key in (protocol.get("related_templates") or [])[:max_templates]:
            template = templates.get(template_key)
            if not template:
                continue
            detail_parts = [
                str(template.get(field))
                for field in ("frequency", "intensity", "duration")
                if template.get(field)
            ]
            exercises = template.get("exercises") or []
            if exercises:
                detail_parts.append("Exercises: " + ", ".join(map(str, exercises)))
            template_summaries.append(
                {
                    "key": template_key,
                    "title": template.get("title") or template_key,
                    "summary": " · ".join(detail_parts),
                }
            )

        cards.append(
            {
                "key": key,
                "title": protocol.get("title") or key,
                "description": protocol.get("description") or "",
                "category": "AYUN Scientist Protocol",
                "priority": "Medium",
                "action_items": actions,
                "nutrition_focus": protocol.get("nutrition_focus") or [],
                "recheck_interval": protocol.get("recheck_interval") or "",
                "templates": template_summaries,
                "source": source_of(protocol),
            }
        )
    return cards


def protocol_card_by_title(title: str) -> dict | None:
    wanted = (title or "").strip().lower()
    if not wanted:
        return None
    data = load_protocols()
    protocols = data.get("condition_protocols") or {}
    for key, protocol in protocols.items():
        if (protocol.get("title") or key).strip().lower() == wanted:
            cards = protocol_cards_for_keys([key])
            return cards[0] if cards else None
    templates = data.get("training_templates") or {}
    for key, template in templates.items():
        if (template.get("title") or key).strip().lower() == wanted:
            actions: list[str] = []
            for field in ("frequency", "intensity", "duration"):
                if template.get(field):
                    actions.append(f"{field.capitalize()}: {template[field]}")
            exercises = template.get("exercises") or []
            return {
                "key": key,
                "title": template.get("title") or key,
                "description": template.get("description") or "",
                "category": "AYUN training template",
                "priority": "Medium",
                "action_items": actions,
                "nutrition_focus": [],
                "recheck_interval": "",
                "templates": [
                    {
                        "key": key,
                        "title": template.get("title") or key,
                        "summary": "Exercises: " + ", ".join(map(str, exercises)) if exercises else "",
                    }
                ]
                if exercises
                else [],
                "source": source_of(template),
            }
    return None


def matched_protocols_for_plan(
    triggered: list | None = None,
    ratings: list | None = None,
    personal_context: str = "",
    max_protocols: int = 4,
) -> list[dict]:
    """Return matched protocols as deterministic recommendation cards."""
    keys = match_protocol_keys(triggered, ratings, personal_context)[:max_protocols]
    return protocol_cards_for_keys(keys)


def format_protocols_for_llm(
    triggered: list | None = None,
    ratings: list | None = None,
    personal_context: str = "",
    max_protocols: int = 4,
    max_templates: int = 6,
) -> str:
    """
    Build a compact AYUN scientist protocol block for chatbot context.
    Only includes protocols matched to this member.
    """
    data = load_protocols()
    if not data:
        return ""

    cond = data.get("condition_protocols") or {}
    templates = data.get("training_templates") or {}
    keys = match_protocol_keys(triggered, ratings, personal_context)[:max_protocols]
    if not keys:
        return ""

    parts: list[str] = [
        "── AYUN SCIENTIST PROTOCOLS (authoritative clinic templates) ──",
        "Ground workout plans in these protocols and related templates.",
        "Prefer listed exercises, frequencies, and intensities over inventing new ones.",
        "Still fit any weekly plan into exactly 7 days.",
    ]

    template_keys: list[str] = []
    seen_tmpl: set[str] = set()

    for key in keys:
        p = cond.get(key) or {}
        title = p.get("title") or key
        desc = p.get("description") or ""
        training = p.get("training") or {}
        parts.append(f"\n### Protocol: {title}")
        if desc:
            parts.append(f"    {desc}")
        if training.get("frequency"):
            parts.append(f"    Frequency: {training['frequency']}")
        if training.get("intensity"):
            parts.append(f"    Intensity: {training['intensity']}")
        if training.get("duration"):
            parts.append(f"    Duration: {training['duration']}")
        focus = training.get("focus") or []
        if focus:
            parts.append("    Focus:")
            parts.extend(_fmt_list(focus))
        nutrition = p.get("nutrition_focus") or []
        if nutrition:
            parts.append("    Nutrition:")
            parts.extend(_fmt_list(nutrition))
        if p.get("recheck_interval"):
            parts.append(f"    Recheck: {p['recheck_interval']}")
        for tk in p.get("related_templates") or []:
            if tk not in seen_tmpl and tk in templates:
                seen_tmpl.add(tk)
                template_keys.append(tk)

    template_keys = template_keys[:max_templates]
    if template_keys:
        parts.append("\n### Related training templates")
        for tk in template_keys:
            parts.extend(_format_template(tk, templates[tk]))

    return "\n".join(parts)


def _format_template(key: str, template: dict) -> list[str]:
    parts = [f"\n  [{key}] {template.get('title', key)}"]
    if template.get("description"):
        parts.append(f"      {template['description']}")
    for field in ("frequency", "intensity", "duration", "volume", "rest"):
        if template.get(field):
            parts.append(f"      {field.capitalize()}: {template[field]}")
    for field in ("exercises", "structure", "zones", "tips", "modalities"):
        values = template.get(field) or []
        if values:
            parts.append(f"      {field.capitalize()}:")
            parts.extend(_fmt_list(values))
    if template.get("daily_activity"):
        parts.append(f"      Daily activity: {template['daily_activity']}")
    return parts


def format_core_templates_for_llm(keys: list[str] | None = None) -> str:
    """AYUN training templates relevant to this turn — keep the prompt small and fast."""
    data = load_protocols()
    templates = data.get("training_templates") or {}
    if not templates:
        return ""
    chosen = [key for key in (keys or []) if key in templates]
    if not chosen:
        return ""
    parts = [
        "── AYUN TRAINING TEMPLATES (authoritative clinic library) ──",
        "Answer from these templates. Use listed exercises, frequency, intensity,",
        "duration, and zone definitions. Do not invent a different programme.",
        "These templates are training methods, not diagnoses. Do not infer a",
        "condition (high body fat, low VO2max, etc.) from a template alone.",
    ]
    for key in chosen:
        parts.extend(_format_template(key, templates[key]))
    return "\n".join(parts)


def _templates_for_question(question: str) -> list[str]:
    q = (question or "").lower()
    hits: list[str] = []
    mapping = [
        (("zone 2", "zone2", "vt1", "endurance", "aerobic", "cardio", "running"), "zone2_base"),
        (("hiit", "interval", "intervals", "zone 4", "polarized", "4x4", "high-intensity", "hard sessions"), "polarized_hiit"),
        (("strength", "muscle", "hypertrophy", "gym", "lift"), "full_body_strength"),
        (("bone", "balance", "fall"), "strength_bone_health"),
        (("body fat", "weight loss", "recomp"), "fat_burn_workout"),
        (("hip mobility", "hips"), "hip_mobility"),
        (("shoulder"), "shoulder_mobility"),
    ]
    for keywords, key in mapping:
        if any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", q) for word in keywords) and key not in hits:
            hits.append(key)
    return hits[:3]


_PROTOCOL_BLOCK_RE = re.compile(
    r"\n?── AYUN SCIENTIST PROTOCOLS.*?(?=\n── [A-Z]|\Z)",
    re.DOTALL,
)
_TEMPLATE_BLOCK_RE = re.compile(
    r"\n?── AYUN TRAINING TEMPLATES.*?(?=\n── [A-Z]|\Z)",
    re.DOTALL,
)
# One rating line, e.g. "  Body Fat %: 36 % → high". Horizontal whitespace only,
# so a heading such as "Key Parameter Ratings (...):" cannot swallow the next line.
_RATING_LINE_RE = re.compile(
    r"^[ \t]*(.+?):[ \t]+[^\n]*?(-?\d+(?:\.\d+)?)[^\n]*→[ \t]*([a-z]+(?:[ _][a-z]+)?)",
    re.MULTILINE | re.IGNORECASE,
)
_LABEL_TO_PARAM = {
    "vo2max": "Physiological::Vo2Max",
    "body fat %": "Body Composition::Fat percentage",
    "visceral fat index": "Body Composition::Visceral Fat Index (raw value from DEXA)",
    "bone mineral density (z-score)": "Body Composition::Bone mineral density",
    "hba1c": "Blood Biomarkers::HbA1c",
    "alat (liver)": "Blood Biomarkers::ALAT",
    "asat (liver)": "Blood Biomarkers::ASAT",
    "ggt (liver)": "Blood Biomarkers::GGT",
    "lmi": "Body Composition::Muscle Mass Index (LMI)",
    "muscle mass index (lmi)": "Body Composition::Muscle Mass Index (LMI)",
    "grip strength (r)": "Physiological::Gripstrength Rechts",
    "grip strength (l)": "Physiological::Gripstrength Links",
    "almi": "Body Composition::ALMI",
}


def strip_protocol_blocks(context: str) -> str:
    text = _PROTOCOL_BLOCK_RE.sub("", context or "")
    text = _TEMPLATE_BLOCK_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def ratings_from_context(context: str) -> list:
    found: list[SimpleNamespace] = []
    for match in _RATING_LINE_RE.finditer(context or ""):
        label = match.group(1).strip().lower()
        parameter = _LABEL_TO_PARAM.get(label)
        if not parameter:
            continue
        found.append(
            SimpleNamespace(
                parameter=parameter,
                value=float(match.group(2)),
                rating=match.group(3).lower().replace(" ", "_"),
            )
        )
    return found


def enrich_member_context(
    context: str,
    question: str = "",
    ratings: list | None = None,
    member_data: dict | None = None,
) -> str:
    """
    Attach only clinically indicated AYUN protocols, plus question-matched
    training templates. Never diagnose from the question text.
    """
    ctx = strip_protocol_blocks(context or "")
    blocks: list[str] = []
    if ctx.strip():
        blocks.append(ctx.rstrip())

    resolved_ratings = ratings
    if resolved_ratings is None:
        snapshot_ratings: list = []
        if member_data:
            try:
                from backend.rules.rule_engine import rate_all_key_params

                snapshot_ratings = rate_all_key_params(member_data)
            except Exception:
                snapshot_ratings = []
        # The assessment context is what the Plan page shows, so its ratings win.
        # The member snapshot can be stale or the app default (age and sex only),
        # and fills in only parameters the context does not rate.
        context_ratings = ratings_from_context(ctx)
        rated = {_rating_parameter(r) for r in context_ratings}
        resolved_ratings = context_ratings + [
            r for r in snapshot_ratings if _rating_parameter(r) not in rated
        ]

    protocol_block = format_protocols_for_llm(
        ratings=resolved_ratings,
        personal_context="",
        max_protocols=4,
        max_templates=4,
    )
    if protocol_block:
        blocks.append(protocol_block)

    template_keys = _templates_for_question(question)
    if template_keys:
        template_block = format_core_templates_for_llm(template_keys)
        if template_block:
            blocks.append(template_block)
    return "\n\n".join(blocks)

