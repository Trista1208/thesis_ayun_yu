"""Ask Joule (Cited Q&A) source tests: matched AYUN protocols are retrieved and cited first.

No model call is made. Run with: python -m pytest backend/tests/test_ask_sources.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.ai.ask_engine import _build_citations, _format_sources_for_llm, _grounded_corpus  # noqa: E402
from backend.rules.protocol_library import enrich_member_context, ratings_from_context  # noqa: E402
from backend.rules.recommendation_api import get_recommendations  # noqa: E402

HIGH_FAT = {
    "Demographic::Age": 45,
    "Demographic::Sex": "Female",
    "Body Composition::Fat percentage": 36,
    "Physiological::Vo2Max": 30,
}
# What the web app sends before the member's own data has loaded.
APP_DEFAULT = {"Demographic::Age": 35, "Demographic::Sex": "Male"}
QUESTION = "How should I train with the Norwegian 4x4?"
FAT_PROTOCOL = "High Body Fat / Elevated Visceral Fat"


def _assessment_context():
    return get_recommendations(HIGH_FAT).context_for_llm


def _corpus(snapshot):
    ctx = enrich_member_context(_assessment_context(), question=QUESTION, member_data=snapshot)
    return ctx, _grounded_corpus(ctx, QUESTION)


def test_first_rating_line_is_parsed():
    params = {r.parameter for r in ratings_from_context(_assessment_context())}
    assert "Physiological::Vo2Max" in params
    assert "Body Composition::Fat percentage" in params


def test_protocol_matched_with_full_snapshot():
    _, corpus = _corpus(HIGH_FAT)
    assert FAT_PROTOCOL in [c.title for c in corpus if c.kind == "ayun-protocol"]


def test_protocol_matched_when_snapshot_is_app_default():
    _, corpus = _corpus(APP_DEFAULT)
    assert FAT_PROTOCOL in [c.title for c in corpus if c.kind == "ayun-protocol"]


def test_protocol_matched_without_snapshot():
    _, corpus = _corpus(None)
    assert FAT_PROTOCOL in [c.title for c in corpus if c.kind == "ayun-protocol"]


def test_norwegian_4x4_attaches_interval_template():
    _, corpus = _corpus(APP_DEFAULT)
    assert "Polarized Training / HIIT" in [c.title for c in corpus if c.kind == "ayun-template"]


def test_protocol_listed_and_cited_before_member_data():
    ctx, corpus = _corpus(APP_DEFAULT)
    sources = _format_sources_for_llm(corpus, [], ctx)
    assert sources.index(FAT_PROTOCOL) < sources.index("[Member]")
    citations = _build_citations(["Member"], corpus, [], ctx)
    assert citations[0]["title"] == FAT_PROTOCOL
    assert citations[0]["used"] == "1" and citations[0]["protocol"]
    assert [c["index"] for c in citations].index("Member") > 0


def test_good_ratings_attach_no_condition_protocol():
    fit = {"Demographic::Age": 31, "Demographic::Sex": "female", "Body Composition::Fat percentage": 19}
    ctx = enrich_member_context(get_recommendations(fit).context_for_llm, question=QUESTION, member_data=fit)
    assert not [c for c in _grounded_corpus(ctx, QUESTION) if c.kind == "ayun-protocol"]


def test_cited_template_opens_in_protocol_panel():
    fit = {"Demographic::Age": 31, "Demographic::Sex": "female", "Body Composition::Fat percentage": 19}
    ctx = enrich_member_context(get_recommendations(fit).context_for_llm, question=QUESTION, member_data=fit)
    corpus = _grounded_corpus(ctx, QUESTION)
    n = next(i for i, c in enumerate(corpus, start=1) if c.title == "Polarized Training / HIIT")
    cites = {c["title"]: c for c in _build_citations([n], corpus, [], ctx)}
    assert cites["Polarized Training / HIIT"]["protocol"]["title"] == "Polarized Training / HIIT"


def test_untopical_question_without_protocol_still_gets_ayun_templates():
    fit = {"Demographic::Age": 31, "Demographic::Sex": "female", "Body Composition::Fat percentage": 19}
    question = "I sleep 6 hours and feel stressed, what should I change?"
    ctx = enrich_member_context(get_recommendations(fit).context_for_llm, question=question, member_data=fit)
    corpus = _grounded_corpus(ctx, question)
    titles = [c.title for c in corpus if c.kind == "ayun-template"]
    assert "Zone 2 Base Endurance" in titles and "Full Body Strength (3–6 reps)" in titles
    sources = _format_sources_for_llm(corpus, [], ctx)
    assert sources.index("Zone 2 Base Endurance") < sources.index("[Member]")
