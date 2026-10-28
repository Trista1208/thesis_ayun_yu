import { useEffect, useState } from "react";
import { Loader2, Send, Sparkles, Wand2, ExternalLink } from "lucide-react";
import { ExpertMemberContext } from "../components/ExpertMemberContext";
import { MarkdownContent } from "../components/MarkdownContent";
import { SourcePanel } from "../components/SourcePanel";
import { normalizeCitations, type AnswerCitation } from "../lib/sources";
import { JouleMark, JouleThinking } from "../components/JouleRunner";
import { Layout } from "../components/Layout";
import { RequireMember } from "../components/RequireMember";
import { DEFAULT_PERSONAL_PROFILE } from "../lib/profileFields";
import { useApp } from "../lib/context";
import {
  claimMemberTickets,
  createTicket,
  deleteTicket,
  expertTicketAssistChat,
  expertTicketPolishAnswer,
  expertTicketSuggestDraft,
  fetchChatStatus,
  fetchExperts,
  fetchMyTickets,
  fetchTicketDetail,
  fetchTickets,
  getGuestTicketIds,
  clearGuestTicketIds,
  updateTicket,
  type Expert,
  type Ticket,
  type TicketDetail,
} from "../lib/api";

const CATEGORIES = ["General", "Cardiovascular", "Metabolic", "Strength", "Mobility", "Bone Health"];

const STATUS_LABEL: Record<string, string> = {
  open: "Waiting for expert",
  answered: "Draft answer saved",
  validated: "Answer published",
};

function statusBadgeClass(status: string) {
  if (status === "validated") return "bg-ayun-green/10 text-ayun-dark";
  if (status === "answered") return "bg-amber-50 text-amber-900";
  return "bg-ayun-light text-ayun-muted";
}

export function TicketsPage() {
  const { isExpert, activeMode, memberName, isMember } = useApp();
  const expertView = isExpert && activeMode === "expert";
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [myTickets, setMyTickets] = useState<Ticket[]>([]);
  const [experts, setExperts] = useState<Expert[]>([]);
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [draft, setDraft] = useState("");
  const [question, setQuestion] = useState("");
  const [category, setCategory] = useState("General");
  const [expertId, setExpertId] = useState("general_pool");
  const [loading, setLoading] = useState(true);
  const [myLoading, setMyLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [expertMessage, setExpertMessage] = useState("");
  const [expertError, setExpertError] = useState("");
  const [ticketDetail, setTicketDetail] = useState<TicketDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [aiConfigured, setAiConfigured] = useState<boolean | null>(null);
  const [aiModel, setAiModel] = useState("");
  const [aiProvider, setAiProvider] = useState("");
  const [aiHint, setAiHint] = useState("");
  const [assistChat, setAssistChat] = useState<
    Array<{ role: string; content: string; citations?: AnswerCitation[] }>
  >([]);
  const [assistInput, setAssistInput] = useState("");
  const [assistLoading, setAssistLoading] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);

  async function loadInbox() {
    setLoading(true);
    try {
      const t = await fetchTickets();
      setTickets(t.tickets);
      if (selected) {
        const updated = t.tickets.find((x) => x.id === selected.id);
        if (updated) setSelected(updated);
      }
    } catch {
      setTickets([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadMyTickets() {
    if (!isMember) {
      setMyTickets([]);
      return;
    }
    setMyLoading(true);
    try {
      const guestIds = getGuestTicketIds();
      if (guestIds.length) {
        try {
          await claimMemberTickets(guestIds);
          clearGuestTicketIds();
        } catch {
          /* claim is best-effort */
        }
      }
      const resp = await fetchMyTickets();
      setMyTickets(resp.tickets);
    } catch {
      setMyTickets([]);
    } finally {
      setMyLoading(false);
    }
  }

  useEffect(() => {
    fetchExperts()
      .then((e) => setExperts(e.experts.filter((x) => x.id !== "general_pool")))
      .catch(() => setExperts([]));
    fetchChatStatus()
      .then((s) => {
        setAiConfigured(s.configured);
        setAiModel(s.model || "");
        setAiProvider(s.provider || "");
        setAiHint(s.hint || "");
      })
      .catch(() => setAiConfigured(null));
  }, []);

  useEffect(() => {
    if (expertView) {
      loadInbox();
    } else {
      setLoading(false);
      setTickets([]);
      setSelected(null);
    }
  }, [expertView]);

  useEffect(() => {
    if (!expertView) {
      loadMyTickets();
    }
  }, [expertView, isMember, memberName]);

  useEffect(() => {
    if (selected) {
      setDraft(selected.draft_answer || "");
    } else {
      setTicketDetail(null);
      setAssistChat([]);
      setAssistInput("");
    }
  }, [selected]);

  useEffect(() => {
    if (!expertView || !selected) {
      setTicketDetail(null);
      return;
    }
    let cancelled = false;
    setLoadingDetail(true);
    fetchTicketDetail(selected.id)
      .then((data) => {
        if (!cancelled) setTicketDetail(data);
      })
      .catch(() => {
        if (!cancelled) setTicketDetail(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingDetail(false);
      });
    return () => {
      cancelled = true;
    };
  }, [expertView, selected?.id]);

  async function submitQuestion(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setSubmitting(true);
    setSubmitted(false);
    try {
      await createTicket({
        question,
        from_name: memberName || "Member",
        category,
        assigned_expert_id: expertId,
      });
      setQuestion("");
      setSubmitted(true);
      loadMyTickets();
    } finally {
      setSubmitting(false);
    }
  }

  async function dismissTicket() {
    if (!selected) return;
    setExpertError("");
    try {
      await deleteTicket(selected.id);
      setSelected(null);
      setExpertMessage("Ticket dismissed.");
      loadInbox();
    } catch (err) {
      setExpertError(err instanceof Error ? err.message : "Could not dismiss ticket");
    }
  }

  async function saveDraft(action: "save_draft" | "validate") {
    if (!selected) return;
    setExpertMessage("");
    setExpertError("");
    try {
      const updated = await updateTicket(selected.id, draft, action);
      setSelected(updated);
      if (action === "validate") {
        setExpertMessage(
          "Answer published to the knowledge library and visible on the member's Ask Expert page.",
        );
      } else {
        setExpertMessage("Draft saved.");
      }
      loadInbox();
    } catch (err) {
      setExpertError(err instanceof Error ? err.message : "Could not update ticket");
    }
  }

  async function onPolishDraft() {
    if (!selected || !draft.trim()) return;
    setAiBusy(true);
    setExpertError("");
    try {
      const { polished } = await expertTicketPolishAnswer(selected.id, draft);
      setDraft(polished);
      setExpertMessage("Spelling and grammar polished. Review before publishing.");
    } catch (err) {
      setExpertError(err instanceof Error ? err.message : "Polish failed");
    } finally {
      setAiBusy(false);
    }
  }

  async function onSuggestDraft() {
    if (!selected) return;
    setAiBusy(true);
    setExpertError("");
    try {
      const { suggestion } = await expertTicketSuggestDraft(selected.id);
      setDraft(suggestion);
      setExpertMessage("AI draft inserted. Edit and validate when ready.");
    } catch (err) {
      setExpertError(err instanceof Error ? err.message : "Could not suggest draft");
    } finally {
      setAiBusy(false);
    }
  }

  async function onAssistSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selected || !assistInput.trim()) return;
    const userMsg = { role: "user", content: assistInput.trim() };
    const next = [...assistChat, userMsg];
    setAssistChat(next);
    setAssistInput("");
    setAssistLoading(true);
    setExpertError("");
    try {
      const { reply, citations } = await expertTicketAssistChat(selected.id, next);
      const text = (reply || "").trim();
      if (!text) {
        throw new Error("Joule returned an empty answer. Try again.");
      }
      setAssistChat([
        ...next,
        { role: "assistant", content: text, citations: normalizeCitations(citations) },
      ]);
    } catch (err) {
      setExpertError(err instanceof Error ? err.message : "Assistant failed");
    } finally {
      setAssistLoading(false);
    }
  }

  if (!expertView) {
    return (
      <RequireMember
        title="Ask an expert"
        message="Sign in to send a question to the AYUN team and see your tickets."
      >
      <Layout>
        <p className="label-eyebrow mb-2">Expert support</p>
        <h1 className="page-title mb-4">Ask an expert</h1>
        <p className="mb-8 max-w-xl text-sm text-ayun-muted">
          Submit a question to the AYUN sports science team. Your questions are private; you only
          see your own.
        </p>

        <form onSubmit={submitQuestion} className="card-panel max-w-xl space-y-3">
          <textarea
            className="w-full rounded-lg border border-rule px-3 py-2 text-sm"
            rows={4}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Your question…"
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              className="rounded-lg border border-rule px-3 py-2 text-sm"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <select
              className="rounded-lg border border-rule px-3 py-2 text-sm"
              value={expertId}
              onChange={(e) => setExpertId(e.target.value)}
            >
              <option value="general_pool">Any available expert</option>
              {experts.map((ex) => (
                <option key={ex.id} value={ex.id}>
                  {ex.name} ({ex.status_label})
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Submit question
          </button>
          {submitted && (
            <p className="rounded-lg bg-ayun-light px-4 py-3 text-sm text-ayun-dark">
              Question submitted. An assigned expert will respond when they review your ticket.
            </p>
          )}
        </form>

        <div className="mt-10 max-w-xl">
          <h2 className="mb-4 font-serif text-xl text-ayun-dark">Your questions</h2>
          {myLoading ? (
            <Loader2 className="h-6 w-6 animate-spin text-ayun-green" />
          ) : myTickets.length === 0 ? (
            <p className="text-sm text-ayun-muted">No questions yet.</p>
          ) : (
            <div className="space-y-4">
              {myTickets.map((t) => (
                <div key={t.id} className="card-panel">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-mono text-ayun-muted">{t.id}</span>
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusBadgeClass(t.status)}`}>
                      {STATUS_LABEL[t.status] || t.status}
                    </span>
                  </div>
                  <p className="mt-3 text-sm font-medium text-ink">{t.question}</p>
                  {t.draft_answer && t.status !== "open" ? (
                    <div className="mt-4 rounded-lg bg-ayun-light/70 px-4 py-3">
                      <p className="text-xs font-semibold uppercase tracking-wider text-ayun-muted">Expert answer</p>
                      <p className="mt-2 text-sm text-ink">{t.draft_answer}</p>
                      {t.status === "validated" && t.validated_by && (
                        <p className="mt-2 text-xs text-ayun-muted">Validated by {t.validated_by}</p>
                      )}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-ayun-muted">Waiting for an expert response…</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </Layout>
      </RequireMember>
    );
  }

  return (
    <Layout>
      <p className="label-eyebrow mb-2">Expert pipeline</p>
      <h1 className="page-title mb-2">All member questions</h1>
      <p className="mb-8 max-w-2xl text-sm text-ayun-muted">
        Every question submitted by members appears here. Validate answers to publish them to the
        knowledge library for future AI responses. Members never see each other&apos;s questions.
      </p>

      {expertMessage && (
        <p className="mb-4 rounded-lg bg-ayun-green/10 px-4 py-3 text-sm text-ayun-dark">{expertMessage}</p>
      )}
      {expertError && (
        <p className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{expertError}</p>
      )}

      {loading ? (
        <Loader2 className="mx-auto h-8 w-8 animate-spin text-ayun-green" />
      ) : (
        <div className="grid gap-6 lg:grid-cols-5">
          <div className="lg:col-span-2 space-y-2">
            {tickets.length === 0 && (
              <p className="text-sm text-ayun-muted">No member questions yet.</p>
            )}
            {tickets.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  setSelected(t);
                  setExpertMessage("");
                  setExpertError("");
                  setAssistChat([]);
                  setAssistInput("");
                }}
                className={`w-full rounded-xl border p-4 text-left transition ${
                  selected?.id === t.id
                    ? "border-ayun-green bg-white shadow-sm"
                    : "border-rule bg-white/80 hover:border-ayun-green/40"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-mono text-ayun-muted">{t.id}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase ${statusBadgeClass(t.status)}`}>
                    {t.status}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium line-clamp-2">{t.question}</p>
                <p className="mt-1 text-xs text-ayun-muted">{t.from_name} · {t.category}</p>
              </button>
            ))}
          </div>

          <div className="lg:col-span-3 space-y-4">
            {selected ? (
              <>
                <div className="card-panel">
                  <h2 className="font-serif text-xl">{selected.question}</h2>
                  <p className="mt-2 text-sm text-ayun-muted">
                    From {selected.from_name} · {selected.category} · {selected.status}
                    {selected.status === "validated" && selected.validated_by
                      ? ` · validated by ${selected.validated_by}`
                      : ""}
                  </p>

                  {ticketDetail?.evipedia_matches && ticketDetail.evipedia_matches.length > 0 ? (
                    <div className="mt-4 rounded-xl border border-ayun-green/20 bg-ayun-light/40 p-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-ayun-dark">
                        evipedia quick check
                        {ticketDetail.evipedia_match_mode === "semantic" ? (
                          <span className="ml-2 rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-medium normal-case text-ayun-dark">
                            Semantic match
                          </span>
                        ) : ticketDetail.evipedia_match_mode === "keyword" ? (
                          <span className="ml-2 rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-medium normal-case text-ayun-dark">
                            Keyword match
                          </span>
                        ) : null}
                      </p>
                      <p className="mt-1 text-xs text-ayun-muted">
                        Matched evidence reviews from{" "}
                        <a href="https://evipedia.ai" target="_blank" rel="noreferrer" className="underline">
                          evipedia.ai
                        </a>{" "}
                        (clinician reference only)
                      </p>
                      <ul className="mt-3 space-y-2">
                        {ticketDetail.evipedia_matches.map((ref) => (
                          <li key={ref.id} className="text-sm">
                            <a
                              href={ref.url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 font-medium text-ayun-green underline"
                            >
                              {ref.title}
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                            <span className="ml-2 text-xs text-ayun-muted">{ref.category}</span>
                            {ref.summary ? (
                              <p className="mt-0.5 text-xs text-ayun-muted line-clamp-2">{ref.summary}</p>
                            ) : null}
                            {typeof ref.score === "number" ? (
                              <p className="mt-0.5 text-[11px] text-ayun-muted">
                                {Math.round(ref.score * 100)}% relevance
                              </p>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  <label className="mt-4 block text-sm font-semibold text-ink">Your answer to the member</label>
                  <textarea
                    className="mt-2 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                    rows={6}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    disabled={selected.status === "validated"}
                    placeholder="Write your answer here…"
                  />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => saveDraft("save_draft")}
                      disabled={selected.status === "validated"}
                    >
                      Save draft
                    </button>
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => saveDraft("validate")}
                      disabled={selected.status === "validated" || !draft.trim()}
                    >
                      Validate & publish
                    </button>
                    <button
                      type="button"
                      className="btn-secondary !text-red-700 !border-red-200 hover:!bg-red-50"
                      onClick={() => dismissTicket()}
                    >
                      Dismiss ticket
                    </button>
                  </div>
                  {selected.status !== "validated" && aiConfigured !== false ? (
                    <div className="mt-3 flex flex-wrap gap-2 border-t border-rule pt-3">
                      <button
                        type="button"
                        className="btn-secondary !text-xs"
                        disabled={aiBusy || aiConfigured === null}
                        onClick={() => onSuggestDraft()}
                      >
                        {aiBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                        Suggest draft
                      </button>
                      <button
                        type="button"
                        className="btn-secondary !text-xs"
                        disabled={aiBusy || !draft.trim() || aiConfigured === null}
                        onClick={() => onPolishDraft()}
                      >
                        {aiBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Wand2 className="h-3 w-3" />}
                        Fix spelling & grammar
                      </button>
                    </div>
                  ) : aiConfigured === false ? (
                    <p className="mt-3 text-xs text-amber-800">
                      AI assistant is not configured on the server. Contact your admin.
                    </p>
                  ) : null}
                  {selected.status === "validated" && (
                    <p className="mt-4 text-sm text-ayun-green">
                      Published. The member can read this answer on Ask Expert (Member mode).
                    </p>
                  )}
                </div>

                <div className="card-panel">
                    <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <JouleMark size={18} />
                        <p className="label-eyebrow">Expert assistant</p>
                      </div>
                      <p
                        className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                          aiConfigured
                            ? "bg-ayun-green/10 text-ayun-dark"
                            : "bg-amber-50 text-amber-900"
                        }`}
                      >
                        {aiConfigured
                          ? `Same as Ask · ${aiProvider === "gemini" ? "Gemini" : aiProvider || "AI"} · ${aiModel}`
                          : "Waiting for the Ask Joule model"}
                      </p>
                    </div>
                    <h3 className="font-serif text-lg text-ink">Ask Joule about this member</h3>
                    <p className="mt-1 text-xs text-ayun-muted">
                      Same Gemini model as member Ask Joule, plus this member&apos;s profile and checkup.
                      For your eyes only, not sent to the member.
                    </p>
                    {loadingDetail ? (
                      <div className="mt-4 flex justify-center py-6">
                        <Loader2 className="h-6 w-6 animate-spin text-ayun-green" />
                      </div>
                    ) : (
                      <div className="mt-4 rounded-xl border border-rule bg-ayun-light/30 p-4">
                        <ExpertMemberContext
                          compact
                          memberName={
                            ticketDetail?.member_name || selected.from_name || "Member"
                          }
                          email={ticketDetail?.email}
                          pseudonym={ticketDetail?.pseudonym}
                          personalProfile={{
                            ...DEFAULT_PERSONAL_PROFILE,
                            ...(ticketDetail?.personal_profile || {}),
                          }}
                          memberData={ticketDetail?.member_data || {}}
                        />
                      </div>
                    )}
                    {aiConfigured === false ? (
                      <p className="mt-3 text-xs text-amber-800">
                        {aiHint ||
                          "Ask Joule is not configured on this host, so the expert assistant uses the same gap. No extra key is required."}
                      </p>
                    ) : null}
                    {selected.status !== "validated" ? (
                      <>
                        <div className="mt-3 max-h-[28rem] space-y-3 overflow-y-auto rounded-lg bg-ayun-light/50 p-3">
                          {assistChat.length === 0 ? (
                            <p className="text-xs text-ayun-muted">
                              e.g. &quot;Given her stress level, what recovery advice fits?&quot;
                            </p>
                          ) : (
                            assistChat.map((m, i) => (
                              <div
                                key={i}
                                className={`rounded-lg px-3 py-2 text-sm ${
                                  m.role === "user" ? "ml-8 bg-white" : "mr-2 bg-white text-ink shadow-sm"
                                }`}
                              >
                                {m.role === "assistant" ? (
                                  <>
                                    <MarkdownContent content={m.content} citations={m.citations} />
                                    {m.citations?.length ? <SourcePanel citations={m.citations} /> : null}
                                  </>
                                ) : (
                                  m.content
                                )}
                              </div>
                            ))
                          )}
                          {assistLoading && <JouleThinking />}
                        </div>
                        <form onSubmit={onAssistSubmit} className="mt-3 flex gap-2">
                          <input
                            className="flex-1 rounded-lg border border-rule px-3 py-2 text-sm"
                            value={assistInput}
                            onChange={(e) => setAssistInput(e.target.value)}
                            placeholder="Ask the clinical assistant…"
                            disabled={assistLoading || !aiConfigured}
                          />
                          <button
                            type="submit"
                            className="btn-primary !px-3"
                            disabled={assistLoading || !assistInput.trim() || !aiConfigured}
                          >
                            <Send className="h-4 w-4" />
                          </button>
                        </form>
                      </>
                    ) : null}
                  </div>
              </>
            ) : (
              <div className="card-panel text-center text-sm text-ayun-muted">
                Select a ticket to review and respond
              </div>
            )}
          </div>
        </div>
      )}
    </Layout>
  );
}
