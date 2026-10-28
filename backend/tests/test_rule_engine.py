"""Boundary tests for the rule engine (female, 31 unless stated).

Expected values come from backend/rules/rule_engine.py and knowledge/sports_health_recommendations.yml
(YAML 2.2). Run with: python -m pytest backend/tests/test_rule_engine.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.rules.recommendation_api import get_recommendations  # noqa: E402
from backend.rules.rule_engine import rate_value  # noqa: E402

try:
    import pytest
    known_defect = pytest.mark.xfail(strict=True, reason="LMI 0 is rated unknown but still fires the YAML strength block")
except ImportError:  # allows the minimal runner without pytest
    def known_defect(f):
        f.known_defect = True
        return f

BASE = {"Demographic::Age": 31, "Demographic::Sex": "female"}
VO2 = "Physiological::Vo2Max"
GRIP = "Physiological::Gripstrength Rechts"
LDL = "Blood Biomarkers::LDL"
HBA1C = "Blood Biomarkers::HbA1c"
LMI = "Body Composition::Muscle Mass Index (LMI)"


def rating(param, value):
    return rate_value(param, value, "female", 31).rating


def priorities(extra):
    return [t.priority for t in get_recommendations({**BASE, **extra}).triggered]


# VO2max, female 30-39: average 34-39, good 39-51 (closed bands, better label wins at the edge)
def test_vo2max_just_below_good_is_average():
    assert rating(VO2, 38.9) == "average"

def test_vo2max_at_good_cut_point_is_good():
    assert rating(VO2, 39.0) == "good"

def test_vo2max_just_above_good_cut_point_is_good():
    assert rating(VO2, 39.1) == "good"

def test_vo2max_below_average_card_priority_follows_deviation():
    # the YAML block fires, but its priority now follows the rating:
    # below average / elevated -> Medium, poor / high -> High
    assert rating(VO2, 33.9) == "below_average"
    assert priorities({VO2: 33.9}) == ["Medium"]


# Grip strength (right), female 30-39: below_average 25-28, average 28-32
def test_grip_just_below_average_is_below_average():
    assert rating(GRIP, 27.9) == "below_average"

def test_grip_at_average_cut_point_is_average():
    assert rating(GRIP, 28.0) == "average"

def test_grip_average_gets_no_card():
    assert priorities({GRIP: 28.1}) == []


# LDL clinical rule: >= 3.0 High (AYUN One-Year Outcomes Overview), >= 4.1 Critical
def test_ldl_boundaries():
    assert priorities({LDL: 2.99}) == []
    assert priorities({LDL: 3.00}) == ["High"]
    assert priorities({LDL: 4.09}) == ["High"]
    assert priorities({LDL: 4.10}) == ["Critical"]


# HbA1c clinical rule: >= 5.7 High, >= 6.5 Critical
def test_hba1c_boundaries():
    assert priorities({HBA1C: 5.69}) == []
    assert priorities({HBA1C: 5.70}) == ["High"]
    assert priorities({HBA1C: 6.45}) == ["High"]
    assert priorities({HBA1C: 6.50}) == ["Critical"]


def test_empty_profile_gives_no_cards():
    assert priorities({}) == []


def test_lmi_zero_gives_no_card():
    assert rating(LMI, 0) == "unknown"
    assert priorities({LMI: 0}) == []


BMD = "Body Composition::Bone mineral density"


def test_bmd_zero_is_a_valid_score_not_missing():
    # a T/Z-score of 0 is an average result, unlike LMI 0 (rule_engine exempts BMD)
    r = rate_value(BMD, 0, "female", 31)
    assert r.value == 0 and r.rating == "good"
    assert priorities({BMD: 0}) == []


# ── Missing data: no guessed defaults ─────────────────────────────────────────
def titles(member):
    return [t.title for t in get_recommendations(member).triggered]


def test_lmi_blank_is_not_measured():
    assert rating(LMI, None) == "unknown"
    assert priorities({LMI: None}) == []


def test_missing_sex_asks_instead_of_male_default():
    member = {"Demographic::Age": 40, "Body Composition::Fat percentage": 35, "Blood Biomarkers::ALAT": 50}
    t = titles(member)
    assert "Add your sex to rate your results" in t
    assert not any("Liver Enzymes" in x for x in t)  # sex-specific liver limits are skipped
    assert rate_value("Body Composition::Fat percentage", 35, "", 40).rating == "unknown"


def test_missing_age_asks_instead_of_30_39_default():
    t = titles({"Demographic::Sex": "Male", VO2: 20})
    assert t == ["Add your age to rate your results"]


def test_no_measurements_and_no_demographics_gives_no_card():
    assert titles({}) == []


# ── AYUN age splits that are not decades (ROM: 20–44 vs 45+) ─────────────────
SHOULDER = "Physiological::Shoulder Flexion Right"


def test_rom_age_44_uses_20_44_band():
    # AYUN men 20–44: fair 162.6–167.8
    assert rate_value(SHOULDER, 165, "Male", 44).rating == "below_average"


def test_rom_age_45_uses_45_plus_band():
    # AYUN men 45+: good 164.1–169
    assert rate_value(SHOULDER, 165, "Male", 45).rating == "average"
    assert rate_value(SHOULDER, 165, "Male", 49).rating == "average"


# ── Combined profiles: several markers at once ────────────────────────────────
def test_combined_full_profile_fires_only_off_target_markers():
    member = {
        "Demographic::Age": 51, "Demographic::Sex": "Male",
        LMI: 18.1, "Body Composition::Fat percentage": 30.4,
        "Body Composition::Visceral Fat Index (raw value from DEXA)": 1722,
        VO2: 38.5, GRIP: 55.5, LDL: 2.3, HBA1C: 5.2,
    }
    r = get_recommendations(member)
    fired = {p for t in r.triggered for p in t.parameters}
    assert fired == {"Body Composition::Fat percentage", "Body Composition::Visceral Fat Index (raw value from DEXA)"}
    assert sorted(t.priority for t in r.triggered) == ["High", "Medium"]


def test_combined_profile_with_blank_and_zero_fields():
    member = {**BASE, LMI: 0, VO2: None, GRIP: 27.9, LDL: 3.0}
    r = get_recommendations(member)
    fired = {p for t in r.triggered for p in t.parameters}
    assert LMI not in fired and VO2 not in fired
    assert GRIP in fired and LDL in fired


def test_combined_profile_missing_sex_keeps_sex_free_blood_rules():
    member = {"Demographic::Age": 35, LDL: 4.2, GRIP: 20, HBA1C: 6.6}
    t = titles(member)
    assert "Add your sex to rate your results" in t
    assert any("High LDL" in x for x in t) and any("HbA1c" in x for x in t)
    assert not any("Grip" in x for x in t)  # grip bands depend on sex


def test_combined_rom_and_strength_at_47():
    member = {"Demographic::Age": 47, "Demographic::Sex": "Male", SHOULDER: 165, GRIP: 39.9}
    fired = {p for t in get_recommendations(member).triggered for p in t.parameters}
    assert SHOULDER not in fired      # 45+ band: good
    assert GRIP in fired              # men 40–49: below average ≤ 39.9


def test_zero_in_python_strength_and_rom_rules_is_not_measured():
    # found by the combined threshold suite: 0 used to fire the clinical biceps / hip rules
    member = {**BASE, "Physiological::Biceps Strength Rechts": 0, "Physiological::Triceps Strength Rechts": 0,
              "Physiological::Hip Flexion Right": 0, "Physiological::Shoulder Flexion Right": 0}
    assert priorities(member) == []


def test_excellent_targets_in_yaml_match_the_excellent_band():
    # "Target VO2max: Aim for ≥51 ml/min/kg (excellent …)" must equal the band it names
    import re
    from backend.rules.rule_engine import load_rules
    y = load_rules()
    ref, paths = y["age_gender_reference_ranges"], y["recommendation_paths"]
    keys = {"vo2max": ("physiological", "vo2max"), "lmi": ("body_composition", "lmi")}
    checked = 0
    for sex, ages in paths.items():
        if not isinstance(ages, dict):
            continue
        for age_grp, block in ages.items():
            for rec in (block or {}).get("recommendations", []) if isinstance(block, dict) else []:
                for item in rec.get("recommendations", []):
                    low = item.lower()
                    if "excellent" not in low or "target" not in low:
                        continue
                    for word, (section, key) in keys.items():
                        if word in low:
                            m = re.search(r"[>≥]\s*(\d+(?:\.\d+)?)", item)
                            band = ref[sex][age_grp][section][key]["excellent"][0]
                            assert m and float(m.group(1)) == band, (sex, age_grp, item, band)
                            checked += 1
    assert checked >= 20


# Body fat: below the ACE athlete range is "low" (not excellent); "high" by common
# standards uses sex-specific cut-offs (ACE: men >= 25 %, women >= 32 %).
FAT = "Body Composition::Fat percentage"


def fat_cards(sex, age, value):
    member = {"Demographic::Age": age, "Demographic::Sex": sex, FAT: value}
    return [t for t in get_recommendations(member).triggered if FAT in t.parameters]


def test_body_fat_at_excellent_lower_bound_is_excellent():
    assert rate_value(FAT, 19.0, "female", 31).rating == "excellent"


def test_body_fat_between_athlete_range_and_excellent_band_stays_excellent():
    assert rate_value(FAT, 15.7, "female", 31).rating == "excellent"
    assert rate_value(FAT, 6.0, "male", 31).rating == "excellent"


def test_body_fat_below_athlete_range_is_low():
    assert rate_value(FAT, 13.9, "female", 31).rating == "low"
    assert rate_value(FAT, 5.9, "male", 31).rating == "low"


def test_low_body_fat_gets_check_in_card_not_fat_loss():
    cards = fat_cards("female", 25, 12)
    assert len(cards) == 1 and cards[0].title == "Check your low body fat"
    assert cards[0].priority == "Medium"
    assert not any("deficit" in i or "fat loss is" in i for i in cards[0].action_items)


def test_male_body_fat_25_is_high_by_common_standards():
    (card,) = fat_cards("male", 25, 25)
    assert card.priority == "High"
    assert any("25%" in i and "high body fat for men" in i for i in card.action_items)


def test_male_body_fat_24_9_is_below_common_high_cut_off():
    (card,) = fat_cards("male", 25, 24.9)
    assert card.priority == "Medium"
    assert any("from 25% for men" in i for i in card.action_items)


def test_female_body_fat_31_is_not_called_high():
    (card,) = fat_cards("female", 25, 31)
    assert card.priority == "Medium"
    assert any("from 32% for women, so yours is not in that range" in i for i in card.action_items)


def test_female_body_fat_32_is_high_by_common_standards():
    (card,) = fat_cards("female", 25, 32)
    assert any("32%" in i and "high body fat for women" in i for i in card.action_items)
