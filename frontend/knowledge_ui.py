"""Streamlit UI — knowledge library, expert availability, tickets."""

from __future__ import annotations

from typing import Any

import streamlit as st

from backend.workflow.experts import (
    expert_options_for_select,
    get_expert,
    load_experts,
    set_expert_availability,
)
from backend.ai.knowledge_pipeline import capture_manual_knowledge
from backend.storage.knowledge_store import delete_node, list_nodes, list_tickets, save_draft_answer, store_stats, validate_ticket
from backend.workflow.ticket_service import create_expert_ticket, list_tickets_for_expert, list_tickets_for_member


_CATEGORIES = [
    "General",
    "Cardiovascular",
    "Metabolic",
    "Strength",
    "Mobility",
    "Bone Health",
    "Training Zones",
]


def render_knowledge_stats(green: str) -> None:
    stats = store_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Knowledge nodes", stats["nodes"])
    c2.metric("Open questions", stats["tickets_open"])
    c3.metric("Awaiting validation", stats["tickets_answered"])
    c4.metric("Validated Q&A", stats["tickets_validated"])
    backend = stats.get("backend", "json_files")
    if backend == "supabase":
        st.caption("Storage: Supabase Postgres")
    else:
        st.caption("Storage: local JSON files (see database/README.md to enable Supabase)")


def _render_expert_roster(green: str, compact: bool = False) -> None:
    experts = load_experts(include_pool=False)
    if compact:
        cols = st.columns(min(len(experts), 3))
        for i, e in enumerate(experts):
            with cols[i % len(cols)]:
                st.markdown(
                    f"**{e.status_emoji} {e.name}**  \n"
                    f"<span style='color:#666;font-size:0.85rem;'>{e.role}</span>  \n"
                    f"<span style='color:{green};font-size:0.8rem;'>{e.status_label}</span>  \n"
                    f"<span style='font-size:0.75rem;color:#888;'>{e.default_hours}</span>",
                    unsafe_allow_html=True,
                )
        return

    for e in experts:
        spec = ", ".join(e.specialties[:3])
        st.markdown(
            f"**{e.status_emoji} {e.name}** · _{e.status_label}_  \n"
            f"{e.role} · {spec}  \n"
            f"Hours: {e.default_hours}"
        )


def render_expert_qa_tab(
    green: str,
    user_role: str,
    viewer_name: str,
    member_snapshot: dict[str, Any] | None = None,
    chat_context: str = "",
) -> None:
    _is_expert = user_role == "doctor"
    st.subheader("🎫 Expert Inbox & Q&A" if _is_expert else "🎫 Ask an AYUN Expert")
    st.caption(
        "Manage assigned questions, set your availability, and validate answers."
        if _is_expert
        else "See who is available, ask a question directly, or track your tickets."
    )

    render_knowledge_stats(green)
    st.markdown("### AYUN expert availability")
    _render_expert_roster(green, compact=True)

    st.divider()

    # ── Patient / member: ask directly ───────────────────────────────────────
    if not _is_expert:
        st.markdown("### Ask a question")
        _cat = st.selectbox("Topic", _CATEGORIES, key="pt_ticket_cat")
        _expert_opts = expert_options_for_select(include_any=True)
        _expert_labels = [o[0] for o in _expert_opts]
        _expert_ids = [o[1] for o in _expert_opts]
        _ex_idx = st.selectbox(
            "Send to",
            range(len(_expert_labels)),
            format_func=lambda i: _expert_labels[i],
            key="pt_ticket_expert",
        )
        _expert_id = _expert_ids[_ex_idx]
        _q = st.text_area("Your question", key="pt_ticket_q", height=100)
        if st.button("Submit question", type="primary", key="pt_submit_ticket"):
            if _q.strip():
                create_expert_ticket(
                    question=_q.strip(),
                    from_role="patient",
                    from_name=viewer_name or "Member",
                    member_snapshot=member_snapshot,
                    chat_context=chat_context,
                    category=_cat,
                    assigned_expert_id=_expert_id,
                    source="patient_direct",
                )
                st.success("Question submitted — an expert will respond.")
                st.rerun()
            else:
                st.warning("Please enter a question.")

        st.divider()
        st.markdown("### Your tickets")
        _my = list_tickets_for_member(viewer_name or "Member")
        if not _my:
            st.info("No tickets yet.")
        for t in _my:
            st.markdown(f"**[{t.id}]** {t.status.upper()} — {t.question[:120]}")
            if t.draft_answer and t.status in ("answered", "validated"):
                st.markdown(f"**Answer:** {t.draft_answer}")
        return

    # ── Expert: availability + inbox ───────────────────────────────────────────
    _experts = load_experts(include_pool=False)
    _expert_names = [e.name for e in _experts]
    _expert_ids_list = [e.id for e in _experts]
    if "active_expert_id" not in st.session_state:
        st.session_state.active_expert_id = _expert_ids_list[0] if _expert_ids_list else "general_pool"

    _c1, _c2, _c3 = st.columns([2, 1, 1])
    with _c1:
        _sel = st.selectbox(
            "Acting as",
            range(len(_expert_names)),
            format_func=lambda i: _expert_names[i],
            key="doc_active_expert",
        )
        st.session_state.active_expert_id = _expert_ids_list[_sel]
    _active = get_expert(st.session_state.active_expert_id)
    with _c2:
        _new_status = st.selectbox(
            "My availability",
            ["available", "busy", "away"],
            index=["available", "busy", "away"].index(_active.status) if _active else 0,
            format_func=lambda s: {"available": "🟢 Available", "busy": "🟡 Busy", "away": "🔴 Away"}[s],
            key="doc_avail_status",
        )
    with _c3:
        if st.button("Update status", key="doc_set_avail", use_container_width=True):
            set_expert_availability(st.session_state.active_expert_id, _new_status)
            st.success("Availability updated.")
            st.rerun()

    with st.expander("➕ Ask a colleague / log a question", expanded=False):
        _dq = st.text_area("Question", key="doc_ticket_q", height=80)
        _dcat = st.selectbox("Topic", _CATEGORIES, key="doc_ticket_cat")
        if st.button("Create ticket", key="doc_create_ticket"):
            if _dq.strip():
                create_expert_ticket(
                    question=_dq.strip(),
                    from_role="doctor",
                    from_name=viewer_name or (_active.name if _active else "Clinician"),
                    category=_dcat,
                    assigned_expert_id=st.session_state.active_expert_id,
                    source="doctor_direct",
                )
                st.success("Ticket created.")
                st.rerun()

    st.divider()
    _expert_id = st.session_state.active_expert_id
    tab_in, tab_ans, tab_val, tab_all = st.tabs(["📥 My inbox", "✏️ Answer", "✅ Validate", "📁 All"])

    open_list = list_tickets_for_expert(_expert_id, status="open")
    answered_list = list_tickets_for_expert(_expert_id, status="answered")

    with tab_in:
        if not open_list:
            st.success("No open tickets in your inbox.")
        for t in open_list:
            ex = get_expert(t.assigned_expert_id)
            st.markdown(f"**[{t.id}]** {t.question}")
            st.caption(
                f"From: {t.from_name} ({t.from_role}) · {t.category} · "
                f"Assigned: {ex.name if ex else 'Team'}"
            )
            draft_val = st.text_area("Draft answer", key=f"draft_{t.id}", height=100)
            if st.button("Submit draft", key=f"submit_{t.id}"):
                if draft_val.strip():
                    save_draft_answer(t.id, draft_val.strip())
                    st.rerun()

    with tab_ans:
        pool = open_list + answered_list
        if not pool:
            st.info("No tickets to answer.")
        for t in pool:
            st.markdown(f"**[{t.id}]** {t.question}")
            draft = st.text_area("Answer", value=t.draft_answer or "", key=f"ans_{t.id}", height=120)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Save draft", key=f"save_d_{t.id}"):
                    if draft.strip():
                        save_draft_answer(t.id, draft.strip())
                        st.rerun()
            with c2:
                if st.button("Validate & publish", key=f"val_{t.id}", type="primary"):
                    if draft.strip():
                        validate_ticket(t.id, viewer_name or (_active.name if _active else "Clinician"), draft.strip())
                        st.success("Validated — added to knowledge corpus.")
                        st.rerun()

    with tab_val:
        if not answered_list:
            st.info("No drafts awaiting validation.")
        for t in answered_list:
            st.markdown(f"**[{t.id}]** {t.question}")
            st.markdown(t.draft_answer)
            if st.button("✅ Validate answer", key=f"validate_{t.id}"):
                validate_ticket(t.id, viewer_name or (_active.name if _active else "Clinician"))
                st.rerun()

    with tab_all:
        all_t = list_tickets(limit=100)
        for t in all_t:
            ex = get_expert(t.assigned_expert_id)
            badge = {"open": "🔴", "answered": "🟡", "validated": "🟢"}.get(t.status, "⚪")
            st.markdown(
                f"{badge} **`{t.id}`** · {t.status} · {ex.name if ex else 'Team'} · "
                f"{t.question[:70]}…"
            )


def render_knowledge_library_tab(green: str, green_dark: str, user_role: str, viewer_name: str) -> None:
    st.subheader("📚 Clinical Knowledge Library")
    st.caption(
        "Validated recommendations and expert answers accumulate here. "
        "The AI assistant uses this corpus to improve over time."
    )
    render_knowledge_stats(green)

    if user_role == "doctor":
        with st.expander("➕ Capture new knowledge (expert only)", expanded=False):
            k_title = st.text_input("Title", key="kn_title", placeholder="e.g. Zone 2 progression for fatty liver")
            k_cat = st.selectbox(
                "Category",
                _CATEGORIES,
                key="kn_cat",
            )
            k_body = st.text_area("Content", key="kn_body", height=140)
            if st.button("Save to knowledge base", key="kn_save", type="primary"):
                if not k_title.strip() or not k_body.strip():
                    st.warning("Title and content are required.")
                else:
                    capture_manual_knowledge(
                        title=k_title,
                        category=k_cat,
                        content=k_body,
                        captured_by=viewer_name or "Clinician",
                    )
                    st.success(f"Saved **{k_title}** to the knowledge base.")
                    st.rerun()

    st.divider()
    nodes = list_nodes(limit=100)
    if not nodes:
        st.info("No knowledge captured yet.")
        return
    for n in nodes:
        with st.expander(f"{n.title} · {n.category}", expanded=False):
            st.markdown(n.summary)
            st.caption(f"Captured by {n.captured_by} · {n.source} · {n.created_at}")
            if user_role == "doctor" and st.button("Delete", key=f"del_node_{n.id}"):
                delete_node(n.id)
                st.rerun()
