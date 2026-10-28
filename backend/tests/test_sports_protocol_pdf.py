"""Sports performance protocol PDF: cover wording, watermark text, and confirmed copy."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pypdf import PdfReader  # noqa: E402
from io import BytesIO  # noqa: E402

from backend.documents.sports_protocol_pdf import (  # noqa: E402
    build_clinician_report,
    build_member_report,
    sports_performance_pdf,
)
from backend.storage.plan_review_store import SavedAssessment  # noqa: E402


def _record(**overrides) -> SavedAssessment:
    assessment = {
        "triggered": [
            {
                "title": "Zone 2 base",
                "category": "Cardio",
                "priority": "High",
                "action_items": ["Frequency: 3 sessions a week", "Zone 2 cycling for 40 minutes."],
            }
        ],
        "protocol_recommendations": [
            {
                "key": "high_body_fat",
                "title": "High body fat protocol",
                "description": "Reduce visceral fat with strength and zone 2.",
                "action_items": ["Strength train 2 times a week."],
                "templates": [{"title": "Full Body Strength", "summary": "Pull-ups, press, deadlifts."}],
            },
            {
                "key": "low_vo2max",
                "title": "Should stay hidden",
                "action_items": ["This marker is not indicated."],
            },
        ],
        "ratings": [
            {"parameter": "Body Composition::Fat percentage", "value": 32, "unit": "%", "rating": "high"},
            {"parameter": "Physiological::Vo2Max", "value": 48, "unit": "ml/kg/min", "rating": "good"},
        ],
        "training_zones": {"source": "Estimated", "hr_max": 185, "zones": {"Zone 2": "111-130 bpm"}},
    }
    base = dict(
        id="abc",
        member_user_id="user-1",
        member_name="Jonas Weber",
        pseudonym="",
        member_data={"Demographic::Age": 32, "Demographic::Sex": "Male"},
        personal_profile={"goals": ["Improve endurance and strength for sport."]},
        assessment=assessment,
        created_at="2026-01-15T09:00:00+00:00",
    )
    base.update(overrides)
    return SavedAssessment(**base)


def _text(pdf: bytes) -> str:
    reader = PdfReader(BytesIO(pdf))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_member_preliminary_pdf_uses_sports_performance_wording():
    pdf = sports_performance_pdf(build_member_report(_record()))
    assert pdf.startswith(b"%PDF")
    text = _text(pdf)
    assert "Sports Performance Report" in text
    assert "Your sports" in text
    assert "performance" in text
    assert "SPORTS PERFORMANCE" in text
    assert "Zone 2 base" in text
    assert "High body fat protocol" in text
    assert "Should stay hidden" not in text
    assert "Longevity" not in text
    assert "Jonas Weber, 32 years" in text


def test_confirmed_copy_names_the_clinician():
    record = _record(
        published={
            "recommendations": [
                {
                    "title": "Confirmed strength block",
                    "reviewed_priority": "High",
                    "category": "Training",
                    "action_items": ["Two full-body sessions each week."],
                    "clinician_notes": "Keep the loads conservative.",
                }
            ],
            "published_by": "Dr Meier",
            "published_at": "2026-01-15T15:00:00+00:00",
            "clinician_note": "Start next Monday.",
        }
    )
    member = _text(sports_performance_pdf(build_member_report(record)))
    assert "Confirmed by the AYUN clinician team (Dr Meier)" in member
    assert "Confirmed strength block" in member
    assert "Zone 2 base" not in member
    assert "Start next Monday." in member

    clinician = _text(sports_performance_pdf(build_clinician_report(record)))
    assert "Clinician copy" in clinician
    assert "Dr Meier" in clinician
    assert "Confirmed strength block" in clinician
