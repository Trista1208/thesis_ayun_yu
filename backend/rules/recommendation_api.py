"""
Recommendation API — core business logic layer.

Takes a structured member data dict, runs the rule engine,
computes training zones, and returns a formatted context string
ready for the chatbot plus a structured result for the UI.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.rules.rule_engine import (
    TriggeredRecommendation,
    RatingResult,
    evaluate_member,
    evaluate_clinical_rules,
    evaluate_target_gaps,
    rate_all_key_params,
    load_rules,
    PRIORITY_ORDER,
)
from backend.rules.training_zones import TrainingZones, compute_zones, format_zones
from backend.rules.protocol_library import format_protocols_for_llm, matched_protocols_for_plan


PRIORITY_COLOUR = {
    "Critical": "#c0392b",
    "High":     "#e67e22",
    "Medium":   "#2980b9",
    "Low":      "#27ae60",
}

PRIORITY_EMOJI = {
    "Critical": "🔴",
    "High":     "🟠",
    "Medium":   "🔵",
    "Low":      "🟢",
}

RATING_COLOUR = {
    "excellent":    "#27ae60",
    "good":         "#2ecc71",
    "average":      "#f39c12",
    "below_average":"#e67e22",
    "poor":         "#c0392b",
    "elevated":     "#e67e22",
    "low":          "#e67e22",
    "high":         "#c0392b",
    "unknown":      "#aaa",
}

RATING_EMOJI = {
    "excellent":    "🟢",
    "good":         "🟢",
    "average":      "🟡",
    "below_average":"🟠",
    "poor":         "🔴",
    "elevated":     "🟠",
    "low":          "🟠",
    "high":         "🔴",
    "unknown":      "⚪",
}

_PARAM_LABELS = {
    # Physical performance
    "Physiological::Vo2Max":                                      "VO2max",
    "Physiological::Gripstrength Rechts":                         "Grip Strength (R)",
    "Physiological::Gripstrength Links":                          "Grip Strength (L)",
    "Physiological::Counter movement jump":                       "Counter Movement Jump",
    "Physiological::Y-Balance Composite Score":                   "Y-Balance Score",
    "Physiological::Biceps Strength Rechts":                      "Biceps Strength (R)",
    "Physiological::Biceps Strength Links":                       "Biceps Strength (L)",
    "Physiological::Triceps Strength Rechts":                     "Triceps Strength (R)",
    "Physiological::Triceps Strength Links":                      "Triceps Strength (L)",
    "Physiological::Shoulder Flexion Right":                      "Shoulder Flexion (R)",
    "Physiological::Shoulder Flexion Left":                       "Shoulder Flexion (L)",
    "Physiological::Hip Flexion Right":                           "Hip Flexion (R)",
    "Physiological::Hip Flexion Left":                            "Hip Flexion (L)",
    # Body composition
    "Body Composition::Muscle Mass Index (LMI)":                  "Muscle Mass Index (LMI)",
    "Body Composition::ALMI":                                     "ALMI",
    "Body Composition::Fat percentage":                           "Body Fat %",
    "Body Composition::Visceral Fat Index (raw value from DEXA)": "Visceral Fat Index",
    "Body Composition::Bone mineral density":                     "Bone Mineral Density (Z-score)",
    # Blood biomarkers
    "Blood Biomarkers::LDL":                                      "LDL Cholesterol",
    "Blood Biomarkers::HbA1c":                                    "HbA1c",
    "Blood Biomarkers::ALAT":                                     "ALAT (Liver)",
    "Blood Biomarkers::ASAT":                                     "ASAT (Liver)",
    "Blood Biomarkers::GGT":                                      "GGT (Liver)",
}


@dataclass
class RecommendationResult:
    triggered: list[TriggeredRecommendation]
    ratings: list[RatingResult]
    training_zones: TrainingZones | None
    protocol_recommendations: list[dict]
    context_for_llm: str
    member_summary: str
    sex_group: str
    age_group: str
    personal_context: str = ""   # enriched by Personal Profile tab


def _member_summary(member: dict) -> str:
    age  = member.get("Demographic::Age", "?")
    sex  = member.get("Demographic::Sex", "?")

    lines = [f"Member: {sex}, age {age}"]

    # Physical performance
    _add = lambda label, key, unit="": \
        lines.append(f"  {label}: {member[key]} {unit}".rstrip()) \
        if member.get(key) is not None else None

    _add("VO2max",                "Physiological::Vo2Max",                "ml/min/kg")
    _add("Grip (R)",              "Physiological::Gripstrength Rechts",    "kg")
    _add("Grip (L)",              "Physiological::Gripstrength Links",     "kg")
    _add("Biceps (R)",            "Physiological::Biceps Strength Rechts", "kg")
    _add("Biceps (L)",            "Physiological::Biceps Strength Links",  "kg")
    _add("Triceps (R)",           "Physiological::Triceps Strength Rechts","kg")
    _add("Triceps (L)",           "Physiological::Triceps Strength Links", "kg")
    _add("CMJ",                   "Physiological::Counter movement jump",  "cm")
    _add("Y-Balance",             "Physiological::Y-Balance Composite Score", "%")
    _add("Shoulder Flex R",       "Physiological::Shoulder Flexion Right", "°")
    _add("Shoulder Flex L",       "Physiological::Shoulder Flexion Left",  "°")
    _add("Hip Flex R",            "Physiological::Hip Flexion Right",      "°")
    _add("Hip Flex L",            "Physiological::Hip Flexion Left",       "°")

    # Body composition
    _add("LMI",                   "Body Composition::Muscle Mass Index (LMI)",                  "kg/m²")
    _add("ALMI",                  "Body Composition::ALMI",                                     "kg/m²")
    _add("Body fat",              "Body Composition::Fat percentage",                            "%")
    _add("Visceral fat",          "Body Composition::Visceral Fat Index (raw value from DEXA)",  "")
    _add("BMD Z-score",           "Body Composition::Bone mineral density",                     "")

    # Blood biomarkers
    _add("LDL",                   "Blood Biomarkers::LDL",   "mmol/L")
    _add("HbA1c",                 "Blood Biomarkers::HbA1c", "%")
    _add("ALAT",                  "Blood Biomarkers::ALAT",  "U/L")
    _add("ASAT",                  "Blood Biomarkers::ASAT",  "U/L")
    _add("GGT",                   "Blood Biomarkers::GGT",   "U/L")

    # Genetics
    bone_risk = member.get("Genetics::Bone Health Risk")
    if bone_risk and str(bone_risk).lower() not in ("none", ""):
        lines.append(f"  Genetic bone risk: {bone_risk}")

    return "\n".join(lines)


def _format_context(
    member: dict,
    triggered: list[TriggeredRecommendation],
    ratings: list[RatingResult],
    zones: TrainingZones | None,
    personal_context: str = "",
) -> str:
    parts: list[str] = []

    parts.append("── MEMBER PROFILE ──────────────────────────────────")
    parts.append(_member_summary(member))

    if personal_context.strip():
        parts.append("\n── PERSONAL PROFILE & GOALS ────────────────────────")
        parts.append(personal_context.strip())

    # Ratings
    rating_lines = [
        f"  {_PARAM_LABELS.get(r.parameter, r.parameter)}: "
        f"{r.value} {r.unit} → {r.rating.replace('_', ' ')}"
        for r in ratings if r.value is not None
    ]
    if rating_lines:
        parts.append("\nKey Parameter Ratings (vs. age/gender norms):")
        parts.extend(rating_lines)

    # Training zones
    if zones:
        parts.append("\n── TRAINING ZONES ──────────────────────────────────")
        parts.append(format_zones(zones))

    # Recommendations
    parts.append("── RECOMMENDATIONS ─────────────────────────────────")
    if not triggered:
        parts.append("All measured values are within reference ranges.")
    else:
        for i, rec in enumerate(triggered, 1):
            parts.append(
                f"\n[{i}] [{rec.priority.upper()}] {rec.title}"
            )
            parts.append(f"    Category: {rec.category}")
            for item in rec.action_items:
                parts.append(f"    • {item}")

    protocols_block = format_protocols_for_llm(triggered, ratings, personal_context)
    if protocols_block:
        parts.append("\n" + protocols_block)

    return "\n".join(parts)


def get_recommendations(member_data: dict, personal_context: str = "") -> RecommendationResult:
    rules_data = load_rules()

    yaml_triggered     = evaluate_member(member_data, rules_data)
    clinical_triggered = evaluate_clinical_rules(member_data)

    # Merge: clinical rules go first (Critical flags), then YAML-based
    seen_titles = {r.title for r in clinical_triggered}
    for r in yaml_triggered:
        if r.title not in seen_titles:
            clinical_triggered.append(r)
            seen_titles.add(r.title)

    ratings   = rate_all_key_params(member_data, rules_data)
    # Every measured marker below the good range gets a concrete next step.
    for r in evaluate_target_gaps(member_data, ratings, rules_data, clinical_triggered):
        if r.title not in seen_titles:
            clinical_triggered.append(r)
            seen_titles.add(r.title)
    # Without age and sex most markers cannot be rated: ask for them, never guess.
    from backend.rules.rule_engine import _sex_group as _sg
    missing = [label for label, ok in (
        ("age", member_data.get("Demographic::Age") not in (None, "")),
        ("sex", bool(_sg(str(member_data.get("Demographic::Sex", ""))))),
    ) if not ok]
    measured = [k for k, v in member_data.items() if not k.startswith("Demographic::") and v not in (None, "", 0)]
    if missing and measured:
        clinical_triggered.append(TriggeredRecommendation(
            title=f"Add your {' and '.join(missing)} to rate your results",
            category="Missing data",
            priority="High",
            action_items=[
                f"Your {' and '.join(missing)} {'are' if len(missing) > 1 else 'is'} missing, so results that depend on "
                "age and sex were not rated",
                "Add it in the Assessment form and generate the plan again",
            ],
            sex_group="",
            age_group="",
        ))

    # A reported injury comes before any training card (read from the profile text).
    from backend.rules.member_signals import injury

    hurt = injury(personal_context)
    if hurt:
        text, acute = hurt
        hold = "Until your injury has been checked, skip exercises that load the injured area"
        for rec in clinical_triggered:
            if hold not in rec.action_items:
                rec.action_items.insert(0, hold)
        clinical_triggered.append(TriggeredRecommendation(
            title="Have your injury checked before training" if acute else "Train around your injury",
            category="Injury",
            priority="Critical" if acute else "High",
            action_items=[
                f'Your injury: "{text}"',
                *(["This sounds recent and limits movement: see a doctor or physiotherapist before you train the affected area"]
                  if acute else ["Avoid loading the affected area until it is pain-free"]),
                "Send it to an AYUN expert so your plan can be adapted",
                "Only train what does not load the injured area, e.g. upper body or seated work",
            ],
            sex_group=clinical_triggered[0].sex_group if clinical_triggered else "",
            age_group=clinical_triggered[0].age_group if clinical_triggered else "",
        ))
    triggered = sorted(clinical_triggered, key=lambda r: PRIORITY_ORDER.get(r.priority, 99))

    hr_max = member_data.get("Physiological::HR max")
    vt1    = member_data.get("Physiological::HR at VT1")
    vt2    = member_data.get("Physiological::HR at VT2")
    zones  = compute_zones(hr_max, vt1, vt2)

    protocol_recommendations = matched_protocols_for_plan(triggered, ratings, personal_context)
    context = _format_context(member_data, triggered, ratings, zones, personal_context)
    summary = _member_summary(member_data)

    from backend.rules.rule_engine import _sex_group, _age_group
    sex_grp = _sex_group(str(member_data.get("Demographic::Sex", ""))) or ""
    age = member_data.get("Demographic::Age")
    age_grp = (_age_group(float(age)) if age is not None else "") or ""

    return RecommendationResult(
        triggered=triggered,
        ratings=ratings,
        training_zones=zones,
        protocol_recommendations=protocol_recommendations,
        context_for_llm=context,
        member_summary=summary,
        sex_group=sex_grp,
        age_group=age_grp,
        personal_context=personal_context,
    )
