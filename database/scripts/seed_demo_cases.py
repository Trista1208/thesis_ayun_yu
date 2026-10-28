#!/usr/bin/env python3
"""
Load four fictional clinic cases into local JSON and Supabase (if configured).

Fills Expert → Members, Plan review, Tickets, and Knowledge so a manual
or demo is not empty.

Usage (from the repo root):
  python database/scripts/seed_demo_cases.py

Member login for each case: password from DEFAULT_MEMBER_PASSWORD (ayun123456).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.deps import load_env  # noqa: E402

load_env()

from api.serializers import recommendation_to_dict  # noqa: E402
from backend.storage import ayun_db  # noqa: E402
from backend.storage.knowledge_store import KnowledgeTicket, add_ticket, validate_ticket  # noqa: E402
from backend.storage.plan_review_store import (  # noqa: E402
    SavedAssessment,
    get_assessment,
    publish_review,
    recommendations_from_assessment,
    upsert_assessment,
)
from backend.rules.recommendation_api import get_recommendations  # noqa: E402
from backend.storage.user_store import AppUser, _hash_password, _now_iso, upsert_user  # noqa: E402


PASSWORD = os.environ.get("DEFAULT_MEMBER_PASSWORD", "ayun123456")
REVIEWER = "Dr. Meier"


def _profile_context(profile: dict) -> str:
    parts = [
        f"Member name: {profile.get('name') or ''}",
        f"Geographic area: {profile.get('geographic_area') or 'Not specified'}",
        f"General health status: {profile.get('health_status') or 'Not specified'}",
        f"Health goals: {', '.join(profile.get('goals') or [])}",
        f"Current activity level: {profile.get('activity_level') or ''}",
        f"Preferred activities: {', '.join(profile.get('sport_prefs') or [])}",
    ]
    if profile.get("existing_conditions"):
        parts.append(f"Existing conditions / diagnoses: {profile['existing_conditions']}")
    if profile.get("injuries"):
        parts.append(f"Injuries / limitations: {profile['injuries']}")
    if profile.get("notes"):
        parts.append(f"Additional notes: {profile['notes']}")
    return "\n".join(parts)


def _base_profile(**overrides: object) -> dict:
    profile = {
        "name": "",
        "goals": [],
        "activity_level": "Moderately Active (2–4h/week)",
        "sport_prefs": [],
        "geographic_area": "Switzerland — urban",
        "location_detail": "Zürich",
        "health_status": "Generally healthy — minor issues only",
        "existing_conditions": "",
        "smoking_status": "Non-smoker",
        "alcohol_use": "Occasional (social)",
        "sleep_hours": "7–8 hours",
        "diet": "",
        "stress": "Not assessed",
        "depression": "Not assessed",
        "optimism": "Not assessed",
        "injuries": "",
        "notes": "",
    }
    profile.update(overrides)
    return profile


CASES = [
    {
        "user_id": "demo-lena-hofmann",
        "email": "lena.demo@ayun.local",
        "name": "Lena Hofmann",
        "pseudonym": "LH-42F",
        "member_data": {
            "Demographic::Age": 42,
            "Demographic::Sex": "Female",
            "Physiological::Vo2Max": 28,
            "Physiological::HR max": 178,
            "Physiological::HR at VT1": 128,
            "Physiological::HR at VT2": 155,
            "Physiological::Gripstrength Rechts": 26,
            "Physiological::Gripstrength Links": 24,
            "Physiological::Counter movement jump": 22,
            "Body Composition::Fat percentage": 34,
            "Body Composition::Muscle Mass Index (LMI)": 14.2,
            "Body Composition::ALMI": 5.8,
            "Body Composition::Visceral Fat Index (raw value from DEXA)": 9,
            "Blood Biomarkers::LDL": 4.2,
            "Blood Biomarkers::HbA1c": 5.8,
        },
        "profile": _base_profile(
            name="Lena Hofmann",
            goals=["Improve aerobic fitness", "Lower cholesterol"],
            activity_level="Lightly Active (under 2h/week)",
            sport_prefs=["Walking", "Yoga"],
            health_status="Generally healthy — minor issues only",
            existing_conditions="Family history of cardiovascular disease",
            notes="Wants a plan she can keep with two small children.",
        ),
        "publish": False,
        "tickets": [
            {
                "id": "demo-t-lena-z2",
                "question": "My VO2max is low. Is zone-2 walking enough, or do I need intervals?",
                "status": "open",
                "category": "Aerobic fitness",
                "source": "patient_direct",
                "chat_context": "Member asked during Talk whether easy walking covers the low VO2max finding.",
            }
        ],
    },
    {
        "user_id": "demo-marco-keller",
        "email": "marco.demo@ayun.local",
        "name": "Marco Keller",
        "pseudonym": "MK-58M",
        "member_data": {
            "Demographic::Age": 58,
            "Demographic::Sex": "Male",
            "Physiological::Vo2Max": 32,
            "Physiological::HR max": 168,
            "Physiological::HR at VT1": 118,
            "Physiological::HR at VT2": 145,
            "Physiological::Gripstrength Rechts": 38,
            "Physiological::Gripstrength Links": 36,
            "Physiological::Biceps Strength Rechts": 28,
            "Physiological::Biceps Strength Links": 26,
            "Body Composition::Fat percentage": 27,
            "Body Composition::Muscle Mass Index (LMI)": 17.4,
            "Body Composition::ALMI": 7.1,
            "Blood Biomarkers::LDL": 3.9,
            "Blood Biomarkers::HbA1c": 5.6,
        },
        "profile": _base_profile(
            name="Marco Keller",
            goals=["Stay active for work travel", "Protect the left knee"],
            activity_level="Moderately Active (2–4h/week)",
            sport_prefs=["Running", "Cycling"],
            health_status="Recovering from illness or injury",
            existing_conditions="Mild left-knee osteoarthritis",
            injuries="Left knee pain after interval sessions",
            notes="Published plan already reviewed by the clinic.",
        ),
        "publish": True,
        "tickets": [
            {
                "id": "demo-t-marco-knee",
                "question": "Left knee hurts after intervals. Can I keep running?",
                "status": "validated",
                "category": "Injury / joints",
                "source": "patient_direct",
                "draft_answer": (
                    "Keep easy running on flat ground 2×/week. Replace interval days with "
                    "cycling or an elliptical so the knee is not loaded at speed. Add "
                    "quad and hip-stability work twice a week. Stop and book a clinician "
                    "visit if swelling or night pain appears."
                ),
                "chat_context": "Talk thread about keeping running after the new plan.",
            }
        ],
    },
    {
        "user_id": "demo-sofia-rossi",
        "email": "sofia.demo@ayun.local",
        "name": "Sofia Rossi",
        "pseudonym": "SR-29F",
        "member_data": {
            "Demographic::Age": 29,
            "Demographic::Sex": "Female",
            "Physiological::Vo2Max": 48,
            "Physiological::HR max": 191,
            "Physiological::HR at VT1": 148,
            "Physiological::HR at VT2": 172,
            "Physiological::Gripstrength Rechts": 32,
            "Physiological::Gripstrength Links": 31,
            "Physiological::Counter movement jump": 34,
            "Body Composition::Fat percentage": 22,
            "Body Composition::Muscle Mass Index (LMI)": 16.1,
            "Body Composition::ALMI": 6.6,
            "Blood Biomarkers::LDL": 2.4,
            "Blood Biomarkers::HbA1c": 5.1,
        },
        "profile": _base_profile(
            name="Sofia Rossi",
            goals=["Race a half marathon", "Raise top-end speed"],
            activity_level="Very Active (6h+/week)",
            sport_prefs=["Running", "Strength training"],
            health_status="Good health — no known conditions",
            diet="High-carb around long runs",
            notes="Already trains often; wants quality, not more volume.",
        ),
        "publish": False,
        "tickets": [
            {
                "id": "demo-t-sofia-hiit",
                "question": "I already run four days. How many HIIT sessions is safe?",
                "status": "answered",
                "category": "Training load",
                "source": "patient_direct",
                "draft_answer": (
                    "One hard interval session plus one tempo is enough with four run days. "
                    "Keep two easy days and one rest day. A second HIIT day usually costs "
                    "recovery more than it adds speed."
                ),
                "chat_context": "Asked whether more intensity would help race pace.",
            }
        ],
    },
    {
        "user_id": "demo-jonas-weber",
        "email": "jonas.demo@ayun.local",
        "name": "Jonas Weber",
        "pseudonym": "JW-67M",
        "member_data": {
            "Demographic::Age": 67,
            "Demographic::Sex": "Male",
            "Physiological::Vo2Max": 22,
            "Physiological::HR max": 153,
            "Physiological::HR at VT1": 102,
            "Physiological::HR at VT2": 124,
            "Physiological::Gripstrength Rechts": 24,
            "Physiological::Gripstrength Links": 22,
            "Physiological::Y-Balance Composite Score": 78,
            "Body Composition::Fat percentage": 31,
            "Body Composition::Muscle Mass Index (LMI)": 15.1,
            "Body Composition::ALMI": 6.4,
            "Body Composition::Bone mineral density": -1.4,
            "Blood Biomarkers::LDL": 3.6,
            "Genetics::Bone Health Risk": "Moderate",
        },
        "profile": _base_profile(
            name="Jonas Weber",
            goals=["Stay independent", "Reduce fall risk"],
            activity_level="Lightly Active (under 2h/week)",
            sport_prefs=["Walking", "Swimming"],
            geographic_area="Switzerland — rural / alpine",
            location_detail="Bernese Oberland",
            health_status="Managing chronic condition(s)",
            existing_conditions="Osteopenia; history of a near-fall last winter",
            injuries="Unsteady on uneven ground",
            notes="Prefers supervised strength work before any jumping.",
        ),
        "publish": False,
        "tickets": [
            {
                "id": "demo-t-jonas-falls",
                "question": "I am afraid of falling. What strength work is safe to start with?",
                "status": "open",
                "category": "Strength / fall risk",
                "source": "patient_direct",
                "chat_context": "Talk after seeing low grip strength and bone-risk notes.",
            }
        ],
    },
]


def _seed_user(case: dict) -> AppUser:
    now = _now_iso()
    user = AppUser(
        id=case["user_id"],
        email=case["email"],
        password_hash=_hash_password(PASSWORD),
        display_name=case["name"],
        pseudonym=case["pseudonym"],
        member_data=case["member_data"],
        personal_profile=case["profile"],
        created_at=now,
        updated_at=now,
    )
    return upsert_user(user)


def _seed_plan(case: dict, user: AppUser) -> SavedAssessment:
    ctx = _profile_context(case["profile"])
    result = get_recommendations(case["member_data"], personal_context=ctx)
    payload = recommendation_to_dict(result)
    record = SavedAssessment(
        id=f"demo-{user.id.split('-', 1)[-1][:8]}-plan",
        member_user_id=user.id,
        member_name=case["name"],
        pseudonym=case["pseudonym"],
        member_data=case["member_data"],
        personal_profile=case["profile"],
        assessment=payload,
        draft_recommendations=recommendations_from_assessment(payload),
        created_at=_now_iso(),
    )
    upsert_assessment(record)
    ayun_db.persist_assessment(
        case["member_data"],
        result,
        personal_profile=case["profile"],
        pseudonym=case["pseudonym"],
        source="demo_seed",
    )
    if case.get("publish"):
        published = publish_review(
            record.id,
            record.draft_recommendations,
            REVIEWER,
            clinician_note="Demo published plan for the clinic manual.",
        )
        if published:
            return published
    return get_assessment(record.id) or record


def _seed_tickets(case: dict, user: AppUser) -> None:
    for item in case.get("tickets") or []:
        ticket = KnowledgeTicket(
            id=item["id"],
            question=item["question"],
            from_role="patient",
            from_name=case["name"],
            status="open",
            draft_answer=item.get("draft_answer") or "",
            validated_by="",
            member_snapshot=case["member_data"],
            chat_context=item.get("chat_context") or "",
            created_at=_now_iso(),
            updated_at=_now_iso(),
            assigned_expert_id="general_pool",
            category=item.get("category") or "General",
            source=item.get("source") or "patient_direct",
            member_user_id=user.id,
        )
        add_ticket(ticket)
        if item.get("status") == "answered":
            from backend.storage.knowledge_store import save_draft_answer

            save_draft_answer(ticket.id, item["draft_answer"])
        elif item.get("status") == "validated":
            validate_ticket(ticket.id, REVIEWER, item["draft_answer"])


def main() -> int:
    print(f"Supabase configured: {ayun_db.is_configured()} ({ayun_db.backend_label()})")
    if not ayun_db.is_configured():
        print(ayun_db.config_hint())
        print(
            "Cases still go into local JSON. After the Secret key is in .env, "
            "run 004_plan_reviews.sql, then run this script again."
        )
    else:
        probe = ayun_db.list_plan_reviews(limit=1)
        if probe is None:
            print(
                "Connected, but plan_reviews is missing. "
                "Run database/migrations/004_plan_reviews.sql in the SQL Editor, then re-run this script."
            )

    for case in CASES:
        user = _seed_user(case)
        record = _seed_plan(case, user)
        _seed_tickets(case, user)
        state = "published" if case.get("publish") else "pending review"
        print(f"  {user.display_name:16}  {user.email:24}  plan {record.id} ({state})")

    print()
    print("Expert inbox: Members, Plan review, Tickets, Knowledge.")
    print(f"Member login password for all four: {PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
