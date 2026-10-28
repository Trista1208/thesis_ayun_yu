"""
Member signals Joule must address, read deterministically from the member's
profile context and measured data (no LLM).

The rule engine only reads measured parameters. Lifestyle inputs (sleep,
stress, diet, goals, free-text symptoms) therefore never reached a rule and
Joule could mention them without acting on them. This module turns them into
explicit flags for the prompt, and reports which data domains are missing so
the stated confidence can be capped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Adults need at least 7 hours (Watson et al., 2015, AASM/SRS consensus).
_SHORT_SLEEP = {"Less than 5 hours", "5–6 hours", "6–7 hours"}
_RAISED_STRESS = {"Moderate", "High", "Very High"}
_JUNK_FOOD = re.compile(
    r"\b(chips|crisps|chocolate|cakes?|cookies|sweets|candy|soda|soft drinks?|fast food|pastr(?:y|ies)|sugar|fries)\b",
    re.I,
)
_KCAL = re.compile(r"(\d[\d',.]*)\s*\+?\s*kcal", re.I)
_NONE_TEXT = re.compile(r"^(none|no|n/?a|-|nothing|keine)\.?$", re.I)

# Data domains and the member_data keys (by prefix) that count as measured.
_DOMAINS: dict[str, tuple[str, ...]] = {
    "body composition (DEXA)": ("Body Composition::",),
    "fitness (VO2max / CPET)": ("Physiological::Vo2Max", "Physiological::HR "),
    "strength tests": (
        "Physiological::Gripstrength", "Physiological::Biceps", "Physiological::Triceps",
        "Physiological::Push Up", "Physiological::Counter movement jump", "Physiological::Knee",
    ),
    "blood panel": ("Blood Biomarkers::",),
}
_CORE_DOMAINS = ("fitness (VO2max / CPET)", "strength tests", "blood panel")


@dataclass
class MemberSignals:
    flags: list[str] = field(default_factory=list)
    missing_domains: list[str] = field(default_factory=list)
    measured_domains: list[str] = field(default_factory=list)
    context: str = ""

    @property
    def confidence_cap(self) -> str | None:
        """Highest confidence Joule may state. Never "low": that auto-files a ticket."""
        missing_core = [d for d in self.missing_domains if d in _CORE_DOMAINS]
        if len(missing_core) >= 2 or (self.flags and missing_core):
            return "medium"
        if any(f.startswith("INJURY") for f in self.flags):
            return "medium"  # an injury needs an expert check before any plan
        return None

    def cap_reason(self) -> str:
        parts = []
        if self.missing_domains:
            parts.append("not measured: " + ", ".join(self.missing_domains))
        if self.flags:
            parts.append(f"{len(self.flags)} lifestyle point{'s' if len(self.flags) != 1 else ''} still open")
        return "; ".join(parts)


def _field(context: str, label: str) -> str:
    m = re.search(rf"^{re.escape(label)}:\s*(.+)$", context or "", re.M)
    return m.group(1).strip() if m else ""


def _number(text: str) -> float | None:
    try:
        return float(text.replace("'", "").replace(",", "").split()[0])
    except (ValueError, IndexError):
        return None


def _measured(member_data: dict | None, context: str) -> tuple[list[str], list[str]]:
    keys = [k for k, v in (member_data or {}).items() if v not in (None, "")]
    measured, missing = [], []
    for domain, prefixes in _DOMAINS.items():
        hit = any(k.startswith(prefixes) for k in keys)
        if not member_data:  # fall back to the context text
            hit = any(p.split("::")[-1].strip().lower() in (context or "").lower() for p in prefixes)
        (measured if hit else missing).append(domain)
    return measured, missing


_ACUTE_INJURY = re.compile(
    r"(last week|yesterday|days? ago|recent|today|can'?t move|cannot move|unable to|swollen|swelling|sharp pain)", re.I
)


def injury(context: str) -> tuple[str, bool] | None:
    """(injury text, is_acute) from the profile, or None when no injury is reported."""
    text = _field(context, "Injuries / limitations")
    if not text or _NONE_TEXT.match(text) or re.match(r"^no (recent |current )?injur", text, re.I):
        return None
    return text, bool(_ACUTE_INJURY.search(text))


def read_signals(context: str, member_data: dict | None = None) -> MemberSignals:
    sig = MemberSignals()
    sig.context = context
    sig.measured_domains, sig.missing_domains = _measured(member_data, context)

    sleep = _field(context, "Typical sleep")
    stress = _field(context, "Stress level")
    diet = _field(context, "Diet / dietary notes")
    goals = _field(context, "Health goals")
    conditions = _field(context, "Existing conditions / diagnoses")
    depression = _field(context, "Depression level")
    bmi = _number(_field(context, "BMI"))

    # 1. Sleep (+ stress) as a recovery risk.
    if sleep in _SHORT_SLEEP:
        with_stress = f" combined with {stress.lower()} stress" if stress in _RAISED_STRESS else ""
        sig.flags.append(
            f"RECOVERY RISK: typical sleep is {sleep}{with_stress}. Adults need at least 7 hours "
            "(Watson et al., 2015). Say this plainly as a flag; do not present the short sleep as normal "
            "or use it only to justify a rest day. If the plan has 3 or more hard days (HIIT, heavy strength), "
            "apply a recovery check in the weekly plan itself: at most 2 hard days per week until sleep reaches "
            "7 hours, and mark the other sessions as moderate effort."
        )

    # 2. Diet signal.
    if diet:
        junk = sorted({m.group(1).lower() for m in _JUNK_FOOD.finditer(diet)})
        kcal = _number(_KCAL.search(diet).group(1)) if _KCAL.search(diet) else None
        if junk or (kcal and kcal >= 3500):
            detail = f'"{diet}"'
            plausibility = ""
            if kcal and kcal >= 3500 and bmi and bmi < 25:
                plausibility = (
                    f" Also note that {int(kcal)}+ kcal/day is hard to reconcile with BMI {bmi:.1f} "
                    "unless energy expenditure is very high, so the intake estimate is worth checking."
                )
            sig.flags.append(
                f"DIET: the member reports {detail}. Name this diet pattern explicitly (do not reduce it to "
                "'keep an eye on nutrition'), link it to the longevity goal, and suggest one question for an "
                "AYUN expert, e.g. 'Could an AYUN nutrition expert review my diet and intake?'." + plausibility
            )

    # 3. Weight-management goal that the data does not support.
    if "weight management" in goals.lower():
        fat = (member_data or {}).get("Body Composition::Fat percentage")
        fat_ok = False
        if fat not in (None, ""):
            try:
                from backend.rules.rule_engine import rate_value

                fat_ok = rate_value(
                    "Body Composition::Fat percentage", float(fat),
                    (member_data or {}).get("Demographic::Sex", ""), (member_data or {}).get("Demographic::Age"),
                ).rating in {"excellent", "good", "average"}
            except Exception:
                fat_ok = False
        if bmi and 18.5 <= bmi < 25 and (fat_ok or fat in (None, "")):
            fat_txt = f" and body fat {fat}%" if fat not in (None, "") else ""
            sig.flags.append(
                f"GOAL CHECK: 'Weight management' is selected, but BMI {bmi:.1f}{fat_txt} are already in a healthy "
                "range. Do not accept the goal at face value: ask whether they mean weight maintenance or "
                "body recomposition (more muscle, same weight)."
            )

    # 4. Free-text symptom / condition.
    if conditions and not _NONE_TEXT.match(conditions):
        sig.flags.append(
            f'SYMPTOM: the member wrote "{conditions}". Do not interpret it medically. Suggest sending it to an '
            "AYUN expert as a question."
        )

    # 5. Injury. A fresh injury that limits movement comes before any training plan.
    hurt = injury(context)
    if hurt:
        injuries, acute = hurt
        sig.flags.append(
            f'INJURY: the member wrote "{injuries}". '
            + ("This sounds recent and limits movement: put this first, advise getting it checked by a doctor or "
               "physiotherapist before training the affected area, and suggest sending it to an AYUN expert. "
               "Only offer training that does not load the injured area. "
               if acute else
               "Avoid loading the affected area and suggest checking with an AYUN expert. ")
        )

    # 6. Wellbeing. Not Joule's remit to treat, but it must not be ignored.
    if depression in {"High", "Very High"}:
        sig.flags.append(
            f"WELLBEING: depression level is reported as {depression}. Acknowledge it kindly in one sentence, "
            "do not give mental-health advice, and suggest talking to their doctor or an AYUN clinician."
        )
    return sig


def signals_block(sig: MemberSignals) -> str:
    """Prompt block: flags Joule must address, plus data coverage."""
    lines = ["── MEMBER SIGNALS TO ADDRESS (from the member's own data) ──"]
    if sig.flags:
        lines.append("Address every point below in a short 'Watch-outs' section:")
        lines += [f"- {f}" for f in sig.flags]
    exact = [
        f"{label}: {_field(sig.context, label)}"
        for label in ("Typical sleep", "Stress level", "Depression level", "Optimism level")
        if _field(sig.context, label)
    ]
    if exact:
        lines.append(
            "Self-reported values (quote them exactly; never change, swap or merge them, e.g. do not call stress "
            "high when it is low): " + " · ".join(exact)
        )
    lines.append("Measured: " + (", ".join(sig.measured_domains) or "nothing yet"))
    if sig.missing_domains:
        lines.append(
            "Not measured: " + ", ".join(sig.missing_domains)
            + ". Say once that advice for these areas is general, because they were not tested."
        )
    return "\n".join(lines)
