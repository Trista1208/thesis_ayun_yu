"""
Rule Engine — evaluates sports_health_recommendations.yml
against a member's data dictionary and returns triggered recommendations.

Supports the AYUN v2.1 YAML format:
  - age_gender_reference_ranges  (for rating a value as excellent/good/etc.)
  - recommendation_paths         (sex → age_group → list of recommendations,
                                  each with optional condition / any_of)
"""

from __future__ import annotations

import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
YAML_PATH = str(_ROOT / "knowledge" / "sports_health_recommendations.yml")

PRIORITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TriggeredRecommendation:
    title: str
    category: str
    priority: str
    action_items: list[str]
    sex_group: str
    age_group: str
    # Measured parameters that made this card fire (one card per marker).
    parameters: list[str] = field(default_factory=list)


@dataclass
class RatingResult:
    parameter: str
    value: float | None
    rating: str        # excellent / good / average / below_average / poor / unknown
    unit: str


# ── YAML loader ───────────────────────────────────────────────────────────────

_RULES_CACHE: dict | None = None


def load_rules(yml_path: str = YAML_PATH) -> dict:
    global _RULES_CACHE
    if _RULES_CACHE is None:
        with open(yml_path, encoding="utf-8") as f:
            _RULES_CACHE = yaml.safe_load(f)
    return _RULES_CACHE


# ── Age / sex group helpers ───────────────────────────────────────────────────

def _age_group(age: int | float) -> str | None:
    breakpoints = [
        (18, 29, "age_18_29"),
        (30, 39, "age_30_39"),
        (40, 49, "age_40_49"),
        (50, 59, "age_50_59"),
        (60, 69, "age_60_69"),
        (70, 79, "age_70_79"),
        (80, 99, "age_80_99"),
    ]
    for lo, hi, label in breakpoints:
        if lo <= age <= hi:
            return label
    return None


# AYUN tables that do not split by decade. The YAML stores decade blocks, so
# map the age to the block that holds AYUN's band for that age.
# Range of motion: AYUN uses 20–44 and 45+; the age_50_59 block holds the 45+ band.
_ROM_KEYS = {"shoulder_flexion", "hip_extension", "hip_flexion"}


def _ref_age_group(key: str | None, age) -> str | None:
    if age is None:
        return None
    a = float(age)
    if key in _ROM_KEYS and 45 <= a <= 49:
        return "age_50_59"
    return _age_group(a)


def _sex_group(sex: str) -> str | None:
    sx = str(sex).strip().lower()
    if sx in ("male", "m"):
        return "male"
    if sx in ("female", "f"):
        return "female"
    return None


# ── When a marker needs action ───────────────────────────────────────────────
#
# One rule for every card and protocol: excellent / good / average are fine;
# below average, poor, elevated and high get an action plan.

ACTION_RATINGS = {"below_average", "poor", "elevated", "high"}


def needs_action(parameter: str, value, member: dict, rules_data: dict | None = None) -> bool | None:
    """True/False when the parameter can be rated; None when it has no reference range."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    rating = rate_value(
        parameter, v, member.get("Demographic::Sex", ""), member.get("Demographic::Age"), rules_data
    ).rating
    if rating == "unknown":
        return None
    return rating in ACTION_RATINGS


# ── Condition evaluator ───────────────────────────────────────────────────────

def _eval_comparison(
    member_val: float | str | None,
    comparison: str,
    value,
) -> bool:
    """
    Evaluate a single YAML condition leaf.

    comparison types:
      "in"    + list → member_val in list  (case-insensitive strings)
      "in"    + {interval: [lo, hi]} → lo <= member_val <= hi
      "below" + {interval: [_, hi]} → member_val < hi
      "above" + {interval: [lo, _]} → member_val > lo
      "categorical" + list → same as "in" with list (for BMD text values)
    """
    if member_val is None:
        return False

    cmp = comparison.lower()

    if cmp == "in":
        if isinstance(value, list):
            return str(member_val).strip().lower() in [str(v).strip().lower() for v in value]
        if isinstance(value, dict) and "interval" in value:
            lo, hi = value["interval"]
            try:
                return lo <= float(member_val) <= hi
            except (TypeError, ValueError):
                return False

    if cmp == "below":
        if isinstance(value, dict) and "interval" in value:
            _, hi = value["interval"]
            try:
                return float(member_val) < hi
            except (TypeError, ValueError):
                return False

    if cmp == "above":
        if isinstance(value, dict) and "interval" in value:
            lo, _ = value["interval"]
            try:
                return float(member_val) > lo
            except (TypeError, ValueError):
                return False

    if cmp == "categorical":
        if isinstance(value, dict) and "categorical" in value:
            cats = value["categorical"]
        else:
            cats = value if isinstance(value, list) else []
        return str(member_val).strip().lower() in [str(c).strip().lower() for c in cats]

    return False


def _eval_condition_node(node: dict, member: dict) -> bool:
    """Evaluate a single condition dict (with parameter / value / comparison)."""
    param = node.get("parameter")
    comparison = node.get("comparison", "")
    value = node.get("value")
    return _eval_comparison(member.get(param), comparison, value)


def _branch_fires(node: dict, member: dict, rules_data: dict | None) -> bool:
    """A YAML threshold fires only when the marker's rating also needs action."""
    if not _eval_condition_node(node, member):
        return False
    param = node.get("parameter")
    if param in _PARAM_MAP or param in _BLOOD_REFS:
        # Rated markers must actually be rated below target; 0 / blank / no age or sex
        # gives no rating, so the marker counts as not measured.
        return needs_action(param, member.get(param), member, rules_data) is True
    value = member.get(param)
    if isinstance(value, (int, float)) and value <= 0:
        return False  # 0 means the field was left empty
    return True


def fired_parameters(rec: dict, member: dict, rules_data: dict | None = None) -> list[str]:
    """Parameters whose condition fired this YAML block (empty = block does not fire)."""
    branches = ([rec["condition"]] if "condition" in rec else []) + [
        b.get("condition", {}) for b in rec.get("any_of", [])
    ]
    return list(dict.fromkeys(
        b.get("parameter") for b in branches if b and _branch_fires(b, member, rules_data)
    ))


def _recommendation_fires(rec: dict, member: dict) -> bool:
    """
    Determine whether a recommendation block should fire for this member.

    A block fires when:
      - Its single `condition` passes (and the parameter was actually measured)
      - Any condition in `any_of` passes
      Unconditional blocks do not fire. Perfect-health / missing-data
      members get no invented recommendations.
    """
    has_condition = "condition" in rec
    has_any_of = "any_of" in rec

    if not has_condition and not has_any_of:
        return False

    if has_condition:
        if _eval_condition_node(rec["condition"], member):
            return True

    if has_any_of:
        for branch in rec["any_of"]:
            cond = branch.get("condition", {})
            if _eval_condition_node(cond, member):
                return True

    return False


# ── Main evaluation entry point ───────────────────────────────────────────────

def evaluate_member(
    member_data: dict,
    rules_data: dict | None = None,
) -> list[TriggeredRecommendation]:
    """
    Evaluate all relevant recommendation paths for this member.

    Returns triggered recommendations sorted by priority.
    """
    if rules_data is None:
        rules_data = load_rules()

    age = member_data.get("Demographic::Age")
    sex = member_data.get("Demographic::Sex", "")

    sex_grp = _sex_group(str(sex))
    age_grp = _age_group(float(age)) if age is not None else None

    if not sex_grp or not age_grp:
        return []

    paths = rules_data.get("recommendation_paths", {})
    age_block = paths.get(sex_grp, {}).get(age_grp, {})
    recs_list = age_block.get("recommendations", [])

    triggered: list[TriggeredRecommendation] = []

    for rec in recs_list:
        params = fired_parameters(rec, member_data, rules_data)
        if params:
            action_items = list(rec.get("recommendations", []))
            triggered.append(
                TriggeredRecommendation(
                    title=rec.get("title", ""),
                    category=rec.get("category", ""),
                    priority=rec.get("priority", "Medium"),
                    action_items=action_items,
                    sex_group=sex_grp,
                    age_group=age_grp,
                    parameters=params,
                )
            )

    triggered.sort(key=lambda r: PRIORITY_ORDER.get(r.priority, 99))
    return triggered


# ── Clinical rules (evidence-based, not age/sex stratified) ──────────────────
#
# These fire regardless of the YAML recommendation_paths and cover:
#   • Fatty liver (elevated ALAT / ASAT / GGT)
#   • High LDL (cardiovascular risk)
#   • High HbA1c (blood-sugar / prediabetes risk)
#   • Genetic bone health risk
#   • Upper body weakness (biceps / triceps below clinical threshold)

def evaluate_clinical_rules(member_data: dict) -> list[TriggeredRecommendation]:
    """
    Returns TriggeredRecommendation objects generated from clinical blood-,
    genetic-, and strength-based rules that apply to all age/sex groups.
    """
    # No default sex or age: rules that depend on them are skipped instead
    # (get_recommendations asks the member to add the missing field).
    sex_grp = _sex_group(str(member_data.get("Demographic::Sex", ""))) or ""
    age = member_data.get("Demographic::Age")
    age_grp = (_age_group(float(age)) if age not in (None, "") else None) or ""
    demographics_known = bool(sex_grp and age_grp)

    triggered: list[TriggeredRecommendation] = []

    # ── 1. Fatty Liver Detection (ALAT / ASAT / GGT) ─────────────────────────
    alat = member_data.get("Blood Biomarkers::ALAT")
    asat = member_data.get("Blood Biomarkers::ASAT")
    ggt  = member_data.get("Blood Biomarkers::GGT")

    alat_limit = 35.0 if sex_grp == "female" else 40.0
    ggt_limit  = 40.0 if sex_grp == "female" else 60.0

    fatty_liver_triggered = sex_grp != "" and (
        (alat is not None and alat > alat_limit) or
        (asat is not None and asat > 40.0) or
        (ggt  is not None and ggt  > ggt_limit)
    )
    if fatty_liver_triggered:
        abnormal = []
        if alat is not None and alat > alat_limit:
            abnormal.append(f"ALAT {alat} U/L (limit {alat_limit:.0f})")
        if asat is not None and asat > 40.0:
            abnormal.append(f"ASAT {asat} U/L (limit 40)")
        if ggt  is not None and ggt  > ggt_limit:
            abnormal.append(f"GGT {ggt} U/L (limit {ggt_limit:.0f})")

        triggered.append(TriggeredRecommendation(
            parameters=["Blood Biomarkers::ALAT", "Blood Biomarkers::ASAT", "Blood Biomarkers::GGT"],
            title="Elevated Liver Enzymes — Immediate Moderate Endurance Training",
            category="Metabolic / Liver Health",
            priority="Critical",
            action_items=[
                f"Elevated liver markers detected: {', '.join(abnormal)}",
                "Start moderate endurance training immediately: Zone 2 cardio "
                "(~60–70 % HR max), ≥150 min/week — this is the primary treatment",
                "Avoid alcohol entirely during the initial training phase",
                "Nutrition: Mediterranean diet, reduce refined carbohydrates and saturated fat",
                "Retest ALAT, ASAT and GGT after 12 weeks of consistent aerobic training",
                "Consider hepatology referral if enzymes remain elevated after 3 months",
            ],
            sex_group=sex_grp,
            age_group=age_grp,
        ))

    # ── 2. High LDL (Cardiovascular Risk) ────────────────────────────────────
    ldl = member_data.get("Blood Biomarkers::LDL")
    if ldl is not None:
        if ldl >= 4.1:
            triggered.append(TriggeredRecommendation(
                parameters=["Blood Biomarkers::LDL"],
                title=f"High LDL Cholesterol ({ldl} mmol/L) — Cardiovascular Risk",
                category="Cardiovascular Health",
                priority="Critical",
                action_items=[
                    f"LDL {ldl} mmol/L is above the high-risk threshold (4.1 mmol/L)",
                    "Zone 2 aerobic training ≥150 min/week — most effective lifestyle intervention for LDL",
                    "Dietary: reduce saturated fat, increase soluble fibre (oats, legumes, psyllium)",
                    "Increase omega-3 intake (fatty fish 2–3×/week or supplement)",
                    "Medical review recommended — discuss statin therapy if lifestyle changes insufficient",
                ],
                sex_group=sex_grp,
                age_group=age_grp,
            ))
        elif ldl >= 3.0:  # AYUN cut-off for high LDL (AYUN One-Year Outcomes Overview)
            triggered.append(TriggeredRecommendation(
                parameters=["Blood Biomarkers::LDL"],
                title=f"Borderline High LDL ({ldl} mmol/L) — Lipid Optimisation",
                category="Cardiovascular Health",
                priority="High",
                action_items=[
                    f"LDL {ldl} mmol/L is at or above the AYUN cut-off of 3.0 mmol/L",
                    "Regular Zone 2 cardio (≥120 min/week) to improve lipid profile",
                    "Dietary: limit red meat and processed foods, add plant sterols",
                    "Retest lipid panel in 3–6 months",
                ],
                sex_group=sex_grp,
                age_group=age_grp,
            ))

    # ── 3. High HbA1c (Blood Sugar / Prediabetes) ────────────────────────────
    hba1c = member_data.get("Blood Biomarkers::HbA1c")
    if hba1c is not None:
        if hba1c >= 6.5:
            triggered.append(TriggeredRecommendation(
                parameters=["Blood Biomarkers::HbA1c"],
                title=f"HbA1c in Diabetes Range ({hba1c}%) — Blood Sugar Management",
                category="Metabolic Health",
                priority="Critical",
                action_items=[
                    f"HbA1c {hba1c}% meets the diabetes diagnostic threshold (≥6.5%)",
                    "Immediate GP/endocrinology referral for diagnosis and treatment",
                    "Exercise prescription: 150 min/week aerobic + 2×/week resistance training",
                    "Post-meal walks (10–15 min) significantly reduce glucose spikes",
                    "Dietary: low-glycaemic index foods, reduce refined carbohydrates",
                    "Monitor blood glucose regularly",
                ],
                sex_group=sex_grp,
                age_group=age_grp,
            ))
        elif hba1c >= 5.7:
            triggered.append(TriggeredRecommendation(
                parameters=["Blood Biomarkers::HbA1c"],
                title=f"HbA1c in Prediabetes Range ({hba1c}%) — Prevention Protocol",
                category="Metabolic Health",
                priority="High",
                action_items=[
                    f"HbA1c {hba1c}% is in the prediabetes range (5.7–6.4%)",
                    "Aerobic training ≥150 min/week improves insulin sensitivity",
                    "Add 2× resistance/strength sessions per week",
                    "10–15 min walk after each meal to blunt postprandial glucose",
                    "Reduce refined carbohydrates; prefer whole grains, legumes, vegetables",
                    "Retest HbA1c in 3 months",
                ],
                sex_group=sex_grp,
                age_group=age_grp,
            ))

    # ── 4. Genetic Bone Health Risk ───────────────────────────────────────────
    bone_risk = str(member_data.get("Genetics::Bone Health Risk", "")).strip().lower()
    if bone_risk in ("high", "moderate", "low"):
        priority = "Critical" if bone_risk == "high" else ("High" if bone_risk == "moderate" else "Medium")
        triggered.append(TriggeredRecommendation(
            title=f"Genetic Bone Health Risk ({bone_risk.title()}) — Bone Loading Protocol",
            category="Bone Health",
            priority=priority,
            action_items=[
                f"Genetic testing indicates a {bone_risk} predisposition to bone mass loss",
                "Weight-bearing exercise is essential: walking, jogging, hiking, dance",
                "Impact/bone-loading: jumping exercises, plyometrics 2–3×/week",
                "Resistance training targeting hip and spine 2–3×/week",
                "Ensure adequate calcium (1000–1200 mg/day) and vitamin D (800–2000 IU/day)",
                "Consider DEXA scan to establish a bone density baseline",
                *(["High impact activities permitted if no current fracture risk"] if bone_risk != "high" else
                  ["Consult physician before high-impact activities; prioritise controlled loading"]),
            ],
            sex_group=sex_grp,
            age_group=age_grp,
        ))

    # ── 5. Upper Body Weakness (Biceps / Triceps) ─────────────────────────────
    biceps_r  = member_data.get("Physiological::Biceps Strength Rechts")
    biceps_l  = member_data.get("Physiological::Biceps Strength Links")
    triceps_r = member_data.get("Physiological::Triceps Strength Rechts")
    triceps_l = member_data.get("Physiological::Triceps Strength Links")

    # Sex-adjusted thresholds (kg) for "below average" upper body strength
    biceps_threshold  = 8.0  if sex_grp == "female" else 12.0
    triceps_threshold = 6.0  if sex_grp == "female" else 10.0

    def _low(param: str, v, threshold: float) -> bool:
        # 0 / blank means not measured. Rated markers follow the shared rating
        # rule; unrated ones use the clinical threshold.
        if not isinstance(v, (int, float)) or v <= 0:
            return False
        verdict = needs_action(param, v, member_data)
        return verdict if verdict is not None else (v is not None and v < threshold)

    biceps_params = [p for p, v in (("Physiological::Biceps Strength Rechts", biceps_r),
                                     ("Physiological::Biceps Strength Links", biceps_l)) if _low(p, v, biceps_threshold)]
    triceps_params = [p for p, v in (("Physiological::Triceps Strength Rechts", triceps_r),
                                      ("Physiological::Triceps Strength Links", triceps_l)) if _low(p, v, triceps_threshold)]
    biceps_low, triceps_low = bool(biceps_params), bool(triceps_params)

    if demographics_known and (biceps_low or triceps_low):
        weak_groups = []
        if biceps_low:  weak_groups.append("biceps")
        if triceps_low: weak_groups.append("triceps")
        triggered.append(TriggeredRecommendation(
            parameters=biceps_params + triceps_params,
            title=f"Below-Threshold Upper Body Strength ({' & '.join(weak_groups).title()})",
            category="Upper Body Strength",
            priority="High",
            action_items=[
                f"Weakness detected in: {', '.join(weak_groups)} — below age/sex reference threshold",
                "Upper body strength programme: 2–3×/week, 3–4 sets per muscle group",
                "Biceps focus: dumbbell curls, barbell curls, hammer curls",
                "Triceps focus: triceps extensions, close-grip press, dips",
                "Progressive overload: increase resistance every 2–3 weeks",
                "Compound movements first: rows and pull-ups engage biceps; bench press engages triceps",
            ],
            sex_group=sex_grp,
            age_group=age_grp,
        ))

    # ── 6. Range of Motion Limitations ───────────────────────────────────────
    shoulder_r = member_data.get("Physiological::Shoulder Flexion Right")
    shoulder_l = member_data.get("Physiological::Shoulder Flexion Left")
    hip_r      = member_data.get("Physiological::Hip Flexion Right")
    hip_l      = member_data.get("Physiological::Hip Flexion Left")

    shoulder_params = [p for p, v in (("Physiological::Shoulder Flexion Right", shoulder_r),
                                       ("Physiological::Shoulder Flexion Left", shoulder_l)) if _low(p, v, 163)]
    hip_params = [p for p, v in (("Physiological::Hip Flexion Right", hip_r),
                                  ("Physiological::Hip Flexion Left", hip_l)) if _low(p, v, 120)]
    shoulder_limited, hip_limited = bool(shoulder_params), bool(hip_params)

    if demographics_known and shoulder_limited:
        triggered.append(TriggeredRecommendation(
            parameters=shoulder_params,
            title="Limited Shoulder Range of Motion",
            category="Mobility & Flexibility",
            priority="Medium",
            action_items=[
                "Shoulder flexion below reference range (< 163°)",
                "Daily shoulder mobility routine: arm circles, cross-body stretch, doorway stretch",
                "Strengthening rotator cuff: external rotation exercises with band/dumbbell",
                "Avoid overhead press until mobility improves; substitute with incline press",
                "Consider physiotherapy assessment if mobility is significantly restricted",
            ],
            sex_group=sex_grp,
            age_group=age_grp,
        ))

    if demographics_known and hip_limited:
        triggered.append(TriggeredRecommendation(
            parameters=hip_params,
            title="Limited Hip Range of Motion",
            category="Mobility & Flexibility",
            priority="Medium",
            action_items=[
                "Hip flexion below reference range (< 120°)",
                "Daily hip mobility: 90/90 stretch, pigeon pose, hip flexor stretch",
                "Core and glute activation: bridges, clamshells, single-leg deadlifts",
                "Limited hip ROM affects squat form — use heel elevation temporarily",
                "Consider physiotherapy for structural assessment",
            ],
            sex_group=sex_grp,
            age_group=age_grp,
        ))

    triggered.sort(key=lambda r: PRIORITY_ORDER.get(r.priority, 99))
    return triggered


# ── Reference range rating ────────────────────────────────────────────────────

# Parameters rated from the YAML age/sex reference ranges
_PARAM_MAP = {
    # Aerobic
    "Physiological::Vo2Max":                              ("physiological", "vo2max"),
    # Grip / hand strength
    "Physiological::Gripstrength Rechts":                 ("physiological", "grip_strength"),
    "Physiological::Gripstrength Links":                  ("physiological", "grip_strength"),
    # Counter-movement jump
    "Physiological::Counter movement jump":               ("physiological", "counter_movement_jump"),
    # ROM — shoulder
    "Physiological::Shoulder Flexion Right":              ("physiological", "shoulder_flexion"),
    "Physiological::Shoulder Flexion Left":               ("physiological", "shoulder_flexion"),
    # ROM — hip
    "Physiological::Hip Extension Right":                 ("physiological", "hip_extension"),
    "Physiological::Hip Extension Left":                  ("physiological", "hip_extension"),
    "Physiological::Hip Flexion Right":                   ("physiological", "hip_flexion"),
    "Physiological::Hip Flexion Left":                    ("physiological", "hip_flexion"),
    # Strength — knee
    "Physiological::Knee Extension Rechts":               ("physiological", "knee_extension"),
    "Physiological::Knee Extension Links":                ("physiological", "knee_extension"),
    "Physiological::Knee Flexion Rechts":                 ("physiological", "knee_flexion"),
    "Physiological::Knee Flexion Links":                  ("physiological", "knee_flexion"),
    # Strength — elbow
    "Physiological::Triceps Strength Rechts":             ("physiological", "elbow_extension"),
    "Physiological::Triceps Strength Links":              ("physiological", "elbow_extension"),
    "Physiological::Biceps Strength Rechts":              ("physiological", "elbow_flexion"),
    "Physiological::Biceps Strength Links":               ("physiological", "elbow_flexion"),
    # Push-up & Y-Balance
    "Physiological::Push Up 30s":                         ("physiological", "push_up_30s"),
    "Physiological::Y-Balance Composite Score":           ("physiological", "y_balance_composite"),
    # Body composition
    "Body Composition::Muscle Mass Index (LMI)":          ("body_composition", "lmi"),
    "Body Composition::Fat percentage":                   ("body_composition", "fat_percentage"),
    "Body Composition::Visceral Fat Index (raw value from DEXA)": ("body_composition", "visceral_fat"),
}

# Body fat below the ACE athlete range (men < 6 %, women < 14 %) is rated "low".
BODY_FAT_LOW = {"male": 6.0, "female": 14.0}

_RATING_LABELS = ["excellent", "good", "average", "below_average", "poor"]

# Minimum physiologically plausible value per parameter. Values at or below
# this are still rated, but the member is asked to double-check them.
_PARAM_MIN_VALID: dict[str, float] = {
    "Physiological::Vo2Max":                                    5.0,
    "Physiological::Gripstrength Rechts":                       1.0,
    "Physiological::Gripstrength Links":                        1.0,
    "Physiological::Biceps Strength Rechts":                    1.0,
    "Physiological::Biceps Strength Links":                     1.0,
    "Physiological::Triceps Strength Rechts":                   1.0,
    "Physiological::Triceps Strength Links":                    1.0,
    "Physiological::Counter movement jump":                     1.0,
    "Physiological::Y-Balance Composite Score":                 30.0,
    "Physiological::HR max":                                    120.0,
    "Physiological::HR at VT1":                                 95.0,
    "Physiological::HR at VT2":                                 100.0,
    "Physiological::Shoulder Flexion Right":                    10.0,
    "Physiological::Shoulder Flexion Left":                     10.0,
    "Physiological::Hip Flexion Right":                         10.0,
    "Physiological::Hip Flexion Left":                          10.0,
    "Body Composition::Muscle Mass Index (LMI)":                5.0,
    "Body Composition::ALMI":                                   2.0,
    "Body Composition::Fat percentage":                         1.0,
    "Body Composition::Visceral Fat Index (raw value from DEXA)": 1.0,
    "Body Composition::Bone mineral density":                   -7.0,  # negative T/Z-scores are valid
    "Blood Biomarkers::LDL":                                    0.1,
    "Blood Biomarkers::HbA1c":                                  3.0,
    "Blood Biomarkers::ALAT":                                   1.0,
    "Blood Biomarkers::ASAT":                                   1.0,
    "Blood Biomarkers::GGT":                                    1.0,
}

# Fixed clinical reference ranges — includes blood biomarkers and bone density
_BLOOD_REFS: dict[str, dict] = {
    # BMD T-score or Z-score thresholds (WHO / age-matched scale)
    "Body Composition::Bone mineral density": {
        "unit": "SD",
        "excellent":     [1.0,  6.0],   # well above average
        "good":          [0.0,  1.0],   # normal-high / above average
        "average":       [-1.0, 0.0],   # normal range
        "below_average": [-2.5, -1.0],  # osteopenia territory
        "poor":          [-7.0, -2.5],  # osteoporosis territory
    },
    "Blood Biomarkers::LDL": {
        "unit": "mmol/L",
        "excellent":    [0.0, 2.6],
        "good":         [2.6, 3.0],
        "elevated":     [3.0, 4.1],  # AYUN: high LDL ≥ 3.0 mmol/L
        "high":         [4.1, 999],
    },
    "Blood Biomarkers::HbA1c": {
        "unit": "%",
        "excellent":    [0.0, 5.0],
        "good":         [5.0, 5.7],
        "elevated":     [5.7, 6.5],
        "high":         [6.5, 999],
    },
    "Blood Biomarkers::ALAT": {
        "unit": "U/L",
        "excellent":    [0.0, 20.0],
        "good":         [20.0, 35.0],
        "elevated":     [35.0, 80.0],
        "high":         [80.0, 999],
    },
    "Blood Biomarkers::ASAT": {
        "unit": "U/L",
        "excellent":    [0.0, 20.0],
        "good":         [20.0, 40.0],
        "elevated":     [40.0, 80.0],
        "high":         [80.0, 999],
    },
    # AYUN cut-offs (AYUN One-Year Outcomes Overview)
    "Blood Biomarkers::HOMA Index": {
        "unit": "",
        "good":         [0.0, 2.5],
        "elevated":     [2.5, 999],  # insulin resistance
    },
    "Blood Biomarkers::Triglycerides": {
        "unit": "mmol/L",
        "good":         [0.0, 1.7],
        "elevated":     [1.7, 999],
    },
    "Blood Biomarkers::hsCRP": {
        "unit": "mg/L",
        "good":         [0.0, 3.0],
        "elevated":     [3.0, 999],  # higher-risk inflammation range
    },
    "Blood Biomarkers::GGT": {
        "unit": "U/L",
        "excellent":    [0.0, 20.0],
        "good":         [20.0, 40.0],
        "elevated":     [40.0, 80.0],
        "high":         [80.0, 999],
    },
}


def rate_value(
    parameter: str,
    value: float | None,
    sex: str,
    age: int | float,
    rules_data: dict | None = None,
) -> RatingResult:
    """
    Look up the age+gender reference range (YAML) or fixed clinical range
    and return a RatingResult label (excellent/good/average/…).
    """
    if rules_data is None:
        rules_data = load_rules()

    if value is None:
        return RatingResult(parameter=parameter, value=None, rating="unknown", unit="")

    # 0 (or less) means the input was left empty. Low but positive values are
    # still rated — a typed LMI of 5 must show up as poor, not vanish.
    if value <= 0 and parameter != "Body Composition::Bone mineral density":
        return RatingResult(parameter=parameter, value=None, rating="unknown", unit="")

    # ── Blood biomarkers: fixed clinical thresholds ───────────────────────────
    if parameter in _BLOOD_REFS:
        ref  = _BLOOD_REFS[parameter]
        unit = ref.get("unit", "")
        for label in ["excellent", "good", "average", "below_average",
                      "poor", "elevated", "high"]:
            if label not in ref:
                continue
            lo, hi = ref[label]
            if lo <= value < hi:
                return RatingResult(parameter=parameter, value=value,
                                    rating=label, unit=unit)
        return RatingResult(parameter=parameter, value=value,
                            rating="unknown", unit=unit)

    # ── YAML age/sex stratified parameters ───────────────────────────────────
    section, key = _PARAM_MAP.get(parameter, (None, None))
    sex_grp = _sex_group(str(sex))
    age_grp = _ref_age_group(key, age)

    if not sex_grp or not age_grp:
        return RatingResult(parameter=parameter, value=value, rating="unknown", unit="")

    if section is None:
        return RatingResult(parameter=parameter, value=value, rating="unknown", unit="")

    ref = (
        rules_data
        .get("age_gender_reference_ranges", {})
        .get(sex_grp, {})
        .get(age_grp, {})
        .get(section, {})
        .get(key, {})
    )

    unit = ref.get("unit", "")

    _ORDERED_LABELS = ["excellent", "good", "average", "below_average",
                       "poor", "elevated", "high"]

    for label in _ORDERED_LABELS:
        if label not in ref:
            continue
        lo, hi = ref[label]
        if lo <= value <= hi:
            return RatingResult(parameter=parameter, value=value,
                                rating=label, unit=unit)

    # Fallback: value is outside all defined bounds.
    # Find the minimum lower bound and maximum upper bound in this ref block.
    bounds = [ref[l] for l in _ORDERED_LABELS if l in ref]
    if bounds:
        min_lo = min(lo for lo, _ in bounds)
        max_hi = max(hi for _, hi in bounds)
        # "Lower is better" params: below the minimum bound → excellent
        _LOWER_IS_BETTER = {
            "Body Composition::Fat percentage",
            "Body Composition::Visceral Fat Index (raw value from DEXA)",
        }
        if value < min_lo:
            # Body fat below the athlete range is too low, not better
            # (ACE: essential fat men 2–5 %, women 10–13 %; athletes from 6 / 14 %).
            if parameter == "Body Composition::Fat percentage" and \
                    value < BODY_FAT_LOW.get(_sex_group(str(sex)) or "", 0.0):
                return RatingResult(parameter=parameter, value=value,
                                    rating="low", unit=unit)
            best = "excellent" if parameter in _LOWER_IS_BETTER else "poor"
            return RatingResult(parameter=parameter, value=value,
                                rating=best, unit=unit)
        # Above maximum bound → worst rating for lower-is-better, excellent for higher-is-better
        if value > max_hi:
            worst = "high" if parameter in _LOWER_IS_BETTER else "excellent"
            return RatingResult(parameter=parameter, value=value,
                                rating=worst, unit=unit)

    return RatingResult(parameter=parameter, value=value, rating="unknown", unit=unit)


def rate_all_key_params(
    member_data: dict,
    rules_data: dict | None = None,
) -> list[RatingResult]:
    """Rate all trackable key parameters (YAML + blood biomarkers).

    Only rates parameters that were actually provided (non-None in member_data).
    Parameters with physiologically impossible values (e.g. 0.0) are skipped
    by the guard inside rate_value.
    """
    if rules_data is None:
        rules_data = load_rules()

    sex = member_data.get("Demographic::Sex", "")
    age = member_data.get("Demographic::Age")

    all_params = list(_PARAM_MAP.keys()) + list(_BLOOD_REFS.keys())
    results = []
    for param in all_params:
        val = member_data.get(param)
        # Skip params that were never submitted — no need to rate them at all
        if val is None:
            continue
        results.append(rate_value(param, val, sex, age, rules_data))
    return results


# ── Target-range gaps (anything below good / excellent gets a next step) ─────
#
# Every measured marker that is not rated good or excellent gets its own card
# saying where the member is, the target band for their age and sex, and what
# to do. The YAML paths above add the broader programme on top of this.

_ON_TARGET = {"excellent", "good", "average", "unknown"}
_LOWER_IS_BETTER_PARAMS = {
    "Body Composition::Fat percentage",
    "Body Composition::Visceral Fat Index (raw value from DEXA)",
    *_BLOOD_REFS.keys(),
}
_LOWER_IS_BETTER_PARAMS.discard("Body Composition::Bone mineral density")

_GAP_PRIORITY = {
    "poor": "High", "high": "High",
    "below_average": "Medium", "elevated": "Medium",
}
# Gentle, member-facing wording. AYUN targets are stricter than general
# population norms, so ratings are phrased relative to the AYUN target range.
_RATING_TEXT = {
    "low": "very low",
    "below_average": "a little below the AYUN target range",
    "poor": "below the AYUN target range",
    "elevated": "slightly above the AYUN target range",
    "high": "above the AYUN target range",
}
# Body fat classed as high (obese) by common standards, per sex
# (American Council on Exercise chart: men ≥ 25 %, women ≥ 32 %).
BODY_FAT_HIGH = {"male": 25.0, "female": 32.0}
_BODY_FAT_HIGH_DEFAULT = 30.0

LOW_BODY_FAT_ACTIONS = [
    "Please double-check the measurement with your clinic",
    "Do not aim for further fat loss; keep strength training and eat enough energy and protein",
    "Discuss your energy intake and recovery with an AYUN expert",
]

AYUN_STANDARD_NOTE = (
    "AYUN targets are set higher than general health norms, so this value "
    "can still be normal by common standards"
)

# (label, category, action items) per marker family; L/R share one card.
_GAP_ACTIONS: dict[str, tuple[str, str, list[str]]] = {
    # Wording follows the AYUN Longevity Report (longevity_plan_32_2.pdf) sections noted.
    # Basic endurance
    "vo2max": ("VO2max", "Aerobic Capacity", [
        "Regular endurance training: 2–5 sessions per week",
        "30–120 minutes per session, at a pace that allows you to talk but is still strenuous",
        "Choose an activity you enjoy that works your lungs more than individual muscles (hiking, rowing, cycling, swimming, jogging)",
        "Slowly increase training frequency or duration as soon as the training feels easier",
    ]),
    # Full body strength
    "grip_strength": ("Grip strength", "Strength and Muscle Mass", [
        "Multi-joint exercises for every muscle group in your body",
        "Choose weights or variations that allow a maximum of 3–6 repetitions with perfect form",
        "At least 1 strenuous set per muscle group per week, ideally 2–3 sessions per week with up to 4 sets per muscle group",
        "Plan rest days, get enough sleep and eat a protein-rich diet",
    ]),
    # Upper body strength
    "elbow_flexion": ("Biceps strength", "Strength and Muscle Mass", [
        "Multi-joint pulling and pushing exercises in the horizontal and vertical planes",
        "Choose weights or variations that allow a maximum of 3–6 repetitions with perfect form",
        "At least 1 strenuous set per muscle group per week, ideally 2–3 sessions per week with up to 4 sets per muscle group",
    ]),
    "elbow_extension": ("Triceps strength", "Strength and Muscle Mass", [
        "Multi-joint pulling and pushing exercises in the horizontal and vertical planes",
        "Choose weights or variations that allow a maximum of 3–6 repetitions with perfect form",
        "At least 1 strenuous set per muscle group per week, ideally 2–3 sessions per week with up to 4 sets per muscle group",
    ]),
    "push_up_30s": ("Push-ups (30 s)", "Strength and Muscle Mass", [
        "Multi-joint pulling and pushing exercises in the horizontal and vertical planes",
        "Choose weights or variations that allow a maximum of 3–6 repetitions with perfect form",
        "At least 1 strenuous set per muscle group per week, ideally 2–3 sessions per week with up to 4 sets per muscle group",
    ]),
    # Lower body strength
    "knee_extension": ("Knee extension strength", "Strength and Muscle Mass", [
        "Multi-joint exercises for both hip and knee extension",
        "Choose weights or variations that allow a maximum of 3–6 repetitions with perfect form",
        "At least 1 strenuous set per muscle group per week, ideally 2–3 sessions per week with up to 4 sets per muscle group",
    ]),
    "knee_flexion": ("Knee flexion strength", "Strength and Muscle Mass", [
        "Multi-joint exercises for both hip and knee extension",
        "Choose weights or variations that allow a maximum of 3–6 repetitions with perfect form",
        "At least 1 strenuous set per muscle group per week, ideally 2–3 sessions per week with up to 4 sets per muscle group",
    ]),
    # Leg Power
    "counter_movement_jump": ("Jump power", "Lower Body Power", [
        "Versatile jumps, ideally one per category: horizontal, lateral, single-leg and with additional weight",
        "Perfect technique first, then maximum effort with each repetition",
        "2–3 minutes rest between sets",
        "1–2 workouts per week with 80–200 jumps, slowly increase volume",
    ]),
    # Balance
    "y_balance_composite": ("Balance (Y-Balance)", "Balance and Stability", [
        "Balance training at least twice a week, ideally daily for 5–10 minutes",
        "Single-leg exercises, e.g. standing on one leg, step-downs or balance pad exercises",
        "Dynamic stability, e.g. side jumps, tandem walking or lunges with rotation",
    ]),
    # Shoulder mobility / Hip mobility
    "shoulder_flexion": ("Shoulder mobility", "Flexibility and Mobility", [
        "Regular stretching: 60 seconds per exercise, at least twice a week, ideally up to twice a day",
        "Use full range of motion in strength training",
        "Dynamic mobilization before training, e.g. arm circles or shoulder rolls",
    ]),
    "hip_flexion": ("Hip flexion mobility", "Flexibility and Mobility", [
        "Regular stretching: 60 seconds per exercise, at least twice a week, ideally up to twice a day",
        "Use full range of motion in strength training, e.g. a high box for step-ups or deep lunges",
        "Strengthen the hip muscles: abductors, adductors, hip flexors and glutes",
    ]),
    "hip_extension": ("Hip extension mobility", "Flexibility and Mobility", [
        "Regular stretching: 60 seconds per exercise, at least twice a week, ideally up to twice a day",
        "Use full range of motion in strength training, e.g. a high box for step-ups or deep lunges",
        "Strengthen the hip muscles: abductors, adductors, hip flexors and glutes",
    ]),
    # Full body hypertrophy
    "lmi": ("Muscle mass (LMI)", "Strength and Muscle Mass", [
        "Versatile exercises for every muscle group in your body",
        "Choose weights or variations that allow a maximum of 6–30 repetitions with perfect form",
        "At least 1 strenuous set per muscle group per week, ideally 2–3 sessions per week with up to 6 sets per muscle group",
        "Plan rest days, get enough sleep and eat a protein-rich diet",
    ]),
    # Sports for fatburn
    "fat_percentage": ("Body fat", "Body Composition", [
        "Regular strength training: versatile exercises for every muscle group, a maximum of 6–30 repetitions with perfect form",
        "At least 1 strenuous set per muscle group per week, ideally 2–4 sessions per week with up to 6 sets per muscle group",
        "Everyday exercise: walk at least 8,000 steps per day",
        "Follow the nutrition strategy in your AYUN plan and eat a protein-rich diet",
    ]),
    "visceral_fat": ("Visceral fat", "Visceral Fat and Metabolic Health", [
        "Regular strength training: versatile exercises for every muscle group, a maximum of 6–30 repetitions with perfect form",
        "At least 1 strenuous set per muscle group per week, ideally 2–4 sessions per week with up to 6 sets per muscle group",
        "Everyday exercise: walk at least 8,000 steps per day",
        "Follow the nutrition strategy in your AYUN plan and eat a protein-rich diet",
    ]),
    "Body Composition::Bone mineral density": ("Bone density", "Bone Health", [
        "Impact and heavy strength training 2–3×/week (jumps, squats, deadlifts)",
        "Check vitamin D and calcium intake with your clinician",
        "Recheck bone density in 12–24 months",
    ]),
    "Blood Biomarkers::LDL": ("LDL cholesterol", "Cardiovascular Health", [
        "Zone 2 cardio 150+ min/week",
        "Less saturated fat; more soluble fibre (oats, legumes) and oily fish",
        "Retest in 3 months",
    ]),
    "Blood Biomarkers::HbA1c": ("HbA1c", "Metabolic Health", [
        "Move for 10–15 min after meals; strength training 2×/week",
        "Fewer refined carbohydrates and sugary drinks",
        "Retest in 3 months",
    ]),
    "Blood Biomarkers::HOMA Index": ("HOMA index (insulin resistance)", "Metabolic Health", [
        "Discuss this result with your AYUN clinician", "Retest at your next AYUN check-up",
    ]),
    "Blood Biomarkers::Triglycerides": ("Triglycerides", "Cardiovascular Health", [
        "Discuss this result with your AYUN clinician", "Retest at your next AYUN check-up",
    ]),
    "Blood Biomarkers::hsCRP": ("hsCRP (inflammation)", "Metabolic Health", [
        "Discuss this result with your AYUN clinician", "Retest at your next AYUN check-up",
    ]),
    "Blood Biomarkers::ALAT": ("ALAT (liver)", "Metabolic / Liver Health", [
        "Zone 2 cardio 150+ min/week; limit alcohol", "Retest in 3 months",
    ]),
    "Blood Biomarkers::ASAT": ("ASAT (liver)", "Metabolic / Liver Health", [
        "Zone 2 cardio 150+ min/week; limit alcohol", "Retest in 3 months",
    ]),
    "Blood Biomarkers::GGT": ("GGT (liver)", "Metabolic / Liver Health", [
        "Zone 2 cardio 150+ min/week; limit alcohol", "Retest in 3 months",
    ]),
}


def _reference_block(parameter: str, sex: str, age, rules_data: dict) -> dict:
    if parameter in _BLOOD_REFS:
        return _BLOOD_REFS[parameter]
    section, key = _PARAM_MAP.get(parameter, (None, None))
    sex_grp = _sex_group(str(sex))
    age_grp = _ref_age_group(key, age)
    if not section or not sex_grp or not age_grp:
        return {}
    return (
        rules_data.get("age_gender_reference_ranges", {})
        .get(sex_grp, {}).get(age_grp, {}).get(section, {}).get(key, {})
    )


def _target_text(parameter: str, ref: dict) -> str:
    """Aim for the good band; markers with a 4-tier scale (no good band) aim for average."""
    unit = ref.get("unit", "")
    band, name = (ref["good"], "good range") if "good" in ref else (ref.get("average"), "healthy range")
    if not band:
        return ""
    if parameter in _LOWER_IS_BETTER_PARAMS:
        return f"AYUN target ({name}): at or below {band[1]:g} {unit}".strip()
    return f"AYUN target ({name}): at least {band[0]:g} {unit}".strip()


def evaluate_target_gaps(
    member_data: dict,
    ratings: list[RatingResult],
    rules_data: dict | None = None,
    already: list[TriggeredRecommendation] | None = None,
) -> list[TriggeredRecommendation]:
    """One card per marker family rated below average / elevated or worse.

    When another card already fired for that marker, its value and target are
    added to that card instead, so each marker appears on exactly one card.
    """
    owner: dict[str, TriggeredRecommendation] = {}
    for rec in already or []:
        for p in rec.parameters:
            owner.setdefault(p, rec)
    if rules_data is None:
        rules_data = load_rules()
    sex = member_data.get("Demographic::Sex", "")
    age = member_data.get("Demographic::Age")
    sex_grp = _sex_group(str(sex)) or ""
    age_grp = (_age_group(float(age)) if age is not None else "") or ""

    families: dict[str, list[RatingResult]] = {}
    for r in ratings:
        if r.value is None or r.rating in _ON_TARGET:
            continue
        family = _PARAM_MAP.get(r.parameter, (None, r.parameter))[1]
        if family in _GAP_ACTIONS:
            families.setdefault(family, []).append(r)

    order = list(_RATING_TEXT)
    out: list[TriggeredRecommendation] = []
    rated_priority: dict[int, str] = {}  # card id -> priority from its worst marker
    fat_high = BODY_FAT_HIGH.get(sex_grp, _BODY_FAT_HIGH_DEFAULT)
    sex_word = {"male": "men", "female": "women"}.get(sex_grp, "adults")
    for family, rows in families.items():
        worst = max(rows, key=lambda r: order.index(r.rating) if r.rating in order else -1)
        if family == "fat_percentage" and worst.rating == "low":
            ref = _reference_block(worst.parameter, sex, age, rules_data)
            items = [
                f"Your Body fat: {worst.value:g} % — very low",
                f"Below {BODY_FAT_LOW.get(sex_grp, 0):g} % is under the athlete range by common standards (ACE)",
                "Very low body fat can mean low energy availability"
                + (", which can affect your menstrual cycle and bone health" if sex_grp == "female" else ""),
                *LOW_BODY_FAT_ACTIONS,
            ]
            out.append(TriggeredRecommendation(
                title="Check your low body fat",
                category="Body Composition",
                priority="Medium",
                action_items=[i for i in items if i],
                sex_group=sex_grp,
                age_group=age_grp,
                parameters=[worst.parameter],
            ))
            continue
        label, category, actions = _GAP_ACTIONS[family]
        ref = _reference_block(worst.parameter, sex, age, rules_data)
        unit = ref.get("unit", worst.unit or "")
        values = ", ".join(f"{r.value:g}" for r in rows)
        status = _RATING_TEXT.get(worst.rating, worst.rating)
        scope = "" if worst.parameter in _BLOOD_REFS else " for your age and sex"
        items = [f"Your {label}: {values} {unit} — {status}{scope}".replace("  ", " ")]
        if worst.parameter not in _BLOOD_REFS:
            items.append(AYUN_STANDARD_NOTE)
        if family == "fat_percentage":
            # Keep the stricter AYUN target bands, but say where body fat is
            # classed as high by common standards for this sex (BODY_FAT_HIGH).
            top = max(r.value for r in rows)
            if top >= fat_high:
                items.remove(AYUN_STANDARD_NOTE)
            items.append(
                f"By common standards, body fat is classed as high from {fat_high:g}% for {sex_word}, so yours is not in that range"
                if top < fat_high else
                f"This is at or above {fat_high:g}%, which common standards class as high body fat for {sex_word}"
            )
        target = _target_text(worst.parameter, ref)
        if target:
            items.append(target)
        if any(r.value <= _PARAM_MIN_VALID.get(r.parameter, float("-inf")) for r in rows):
            items.append("This value is unusually low, so please double-check the measurement with your clinic")
        existing = next((owner[r.parameter] for r in rows if r.parameter in owner), None)
        if existing is not None:
            if not any(i.startswith(f"Your {label}:") for i in existing.action_items):
                existing.action_items[:0] = items
            # Programme cards carry a fixed YAML priority; match it to how far the
            # marker is off target instead (clinical blood rules keep their own).
            if worst.parameter not in _BLOOD_REFS and existing.category != "Injury":
                derived = (
                    "Medium" if family == "fat_percentage" and max(r.value for r in rows) < fat_high
                    else _GAP_PRIORITY.get(worst.rating, existing.priority)
                )
                prev = rated_priority.get(id(existing))
                if prev is None or PRIORITY_ORDER.get(derived, 99) < PRIORITY_ORDER.get(prev, 99):
                    rated_priority[id(existing)] = derived
                    existing.priority = derived
            continue
        items.extend(actions)
        out.append(TriggeredRecommendation(
            title=f"Work toward the AYUN target for {label}",
            category=category,
            priority=(
                "Medium" if family == "fat_percentage" and max(r.value for r in rows) < fat_high
                else _GAP_PRIORITY.get(worst.rating, "Medium")
            ),
            action_items=items,
            sex_group=sex_grp,
            age_group=age_grp,
            parameters=[r.parameter for r in rows],
        ))
    out.sort(key=lambda r: PRIORITY_ORDER.get(r.priority, 99))
    return out
