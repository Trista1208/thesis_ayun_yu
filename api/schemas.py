from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PersonalProfile(BaseModel):
    name: str = ""
    goals: list[str] = Field(default_factory=list)
    activity_level: str = ""
    sport_prefs: list[str] = Field(default_factory=list)
    geographic_area: str = ""
    location_detail: str = ""
    health_status: str = ""
    existing_conditions: str = ""
    smoking_status: str = ""
    alcohol_use: str = ""
    sleep_hours: str = ""
    diet: str = ""
    stress: str = ""
    depression: str = ""
    optimism: str = ""
    injuries: str = ""
    notes: str = ""


class AssessmentRequest(BaseModel):
    member_data: dict[str, Any]
    personal_profile: PersonalProfile | None = None
    personal_context: str = ""
    pseudonym: str = ""


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context: str = ""
    spoken: bool = False
    language: str = "en"
    from_name: str = "Member"
    member_snapshot: dict[str, Any] | None = None


class AskRequest(BaseModel):
    question: str
    context: str = ""
    member_snapshot: dict[str, Any] | None = None
    from_name: str = "Member"
    from_role: str = "patient"
    auto_ticket: bool = True


class ExpertLoginRequest(BaseModel):
    name: str = ""
    password: str


class MemberRegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""


class MemberLoginRequest(BaseModel):
    email: str
    password: str


class GoogleStartRequest(BaseModel):
    origin: str = ""


class GoogleExchangeRequest(BaseModel):
    code: str
    state: str


class MemberProfileUpdate(BaseModel):
    display_name: str | None = None
    pseudonym: str | None = None
    member_data: dict[str, Any] | None = None
    personal_profile: PersonalProfile | None = None
    enabled_sections: dict[str, bool] | None = None


class TicketCreateRequest(BaseModel):
    question: str
    from_role: str = "patient"
    from_name: str = "Member"
    category: str = "General"
    assigned_expert_id: str = "general_pool"
    member_snapshot: dict[str, Any] | None = None
    chat_context: str = ""
    source: str = "patient_direct"


class TicketClaimRequest(BaseModel):
    ticket_ids: list[str] = Field(default_factory=list)


class GuestTicketLookupRequest(BaseModel):
    ticket_ids: list[str] = Field(default_factory=list)


class TicketUpdateRequest(BaseModel):
    draft_answer: str = ""
    action: str = "save_draft"  # save_draft | validate


class ExpertTicketChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)


class ExpertTicketPolishRequest(BaseModel):
    draft_answer: str = ""


class KnowledgeCaptureRequest(BaseModel):
    title: str
    category: str = "General"
    content: str
    captured_by: str = "Clinician"


class PlanReviewDraftRequest(BaseModel):
    recommendations: list[dict[str, Any]]


class PlanPublishRequest(BaseModel):
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    clinician_note: str = ""


class PlanPdfRequest(BaseModel):
    """Current review on screen. Omit a field to use the saved plan."""

    recommendations: list[dict[str, Any]] | None = None
    clinician_note: str | None = None


class ExpertMemberContextUpdate(BaseModel):
    member_name: str | None = None
    personal_profile: PersonalProfile | None = None
    member_data: dict[str, Any] | None = None


class ExpertAvailabilityRequest(BaseModel):
    status: str  # available | busy | away
