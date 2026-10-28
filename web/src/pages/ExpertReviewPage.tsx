import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { FileDown, Loader2, X } from "lucide-react";
import { ExpertMemberContext } from "../components/ExpertMemberContext";
import { Layout } from "../components/Layout";
import { DEFAULT_PERSONAL_PROFILE } from "../lib/profileFields";
import { useApp } from "../lib/context";
import {
  archiveReviewAssessment,
  clearExpertSession,
  downloadProtocolPdf,
  fetchReviewAssessment,
  fetchReviewAssessments,
  getExpertToken,
  publishReviewPlan,
  saveReviewDraft,
  updateReviewAssessmentContext,
  type ReviewRecommendation,
  type SavedAssessmentDetail,
  type SavedAssessmentSummary,
} from "../lib/api";

const PRIORITIES = ["Critical", "High", "Medium", "Low"];

function itemsToText(items: string[] | string | undefined): string {
  if (Array.isArray(items)) return items.map((i) => `• ${i}`).join("\n");
  return items || "";
}

function textToItems(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.replace(/^[\s•-]+/, "").trim())
    .filter(Boolean);
}

export function ExpertReviewPage() {
  const { isExpert, setIsExpert, setActiveMode } = useApp();
  const [searchParams] = useSearchParams();
  const assessmentFromUrl = searchParams.get("assessment");
  const [inboxTab, setInboxTab] = useState<"pending" | "finished">("pending");
  const [list, setList] = useState<SavedAssessmentSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SavedAssessmentDetail | null>(null);
  const [recs, setRecs] = useState<ReviewRecommendation[]>([]);
  const [clinicianNote, setClinicianNote] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [needsLogin, setNeedsLogin] = useState(!getExpertToken());
  const [savingProfile, setSavingProfile] = useState(false);

  useEffect(() => {
    if (isExpert) setActiveMode("expert");
  }, [isExpert, setActiveMode]);

  const loadList = useCallback(async () => {
    if (!getExpertToken()) {
      setNeedsLogin(true);
      setLoadingList(false);
      return;
    }
    setLoadingList(true);
    setNeedsLogin(false);
    try {
      const data = await fetchReviewAssessments(inboxTab === "finished" ? "published" : "pending");
      setList(data.assessments);
      setSelectedId((prev) => {
        if (assessmentFromUrl) return assessmentFromUrl;
        if (prev && data.assessments.some((a) => a.id === prev)) return prev;
        return data.assessments[0]?.id || null;
      });
      setMessage("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not load assessments";
      if (msg.toLowerCase().includes("session") || msg.toLowerCase().includes("login")) {
        clearExpertSession();
        setIsExpert(false);
        setNeedsLogin(true);
        setMessage("");
      } else {
        setMessage(msg);
      }
    } finally {
      setLoadingList(false);
    }
  }, [setIsExpert, inboxTab, assessmentFromUrl]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    if (!assessmentFromUrl) return;
    setSelectedId(assessmentFromUrl);
    fetchReviewAssessment(assessmentFromUrl)
      .then((data) => setInboxTab(data.published ? "finished" : "pending"))
      .catch(() => {
        /* detail panel shows error */
      });
  }, [assessmentFromUrl]);

  useEffect(() => {
    if (assessmentFromUrl) return;
    setSelectedId(null);
  }, [inboxTab, assessmentFromUrl]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setRecs([]);
      return;
    }
    let cancelled = false;
    setLoadingDetail(true);
    setMessage("");
    fetchReviewAssessment(selectedId)
      .then((data) => {
        if (cancelled) return;
        setDetail(data);
        setRecs(data.draft_recommendations || []);
        setClinicianNote(data.published?.clinician_note || "");
      })
      .catch((err) => {
        if (!cancelled) setMessage(err instanceof Error ? err.message : "Could not load case");
      })
      .finally(() => {
        if (!cancelled) setLoadingDetail(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  function updateRec(index: number, patch: Partial<ReviewRecommendation>) {
    setRecs((prev) => prev.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  function addCustomRec() {
    setRecs((prev) => [
      ...prev,
      {
        id: `custom_${Date.now()}`,
        title: "",
        category: "Custom",
        reviewed_priority: "Medium",
        action_items: [],
        clinician_notes: "",
        source: "clinician_added",
        removed: false,
      },
    ]);
  }

  async function onSaveDraft() {
    if (!selectedId) return;
    setSaving(true);
    setMessage("");
    try {
      const data = await saveReviewDraft(selectedId, recs);
      setDetail(data);
      setMessage("Draft saved.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function onPublish() {
    if (!selectedId) return;
    setSaving(true);
    setMessage("");
    try {
      const data = await publishReviewPlan(selectedId, recs, clinicianNote);
      setDetail(data);
      setRecs(data.draft_recommendations || []);
      const activeCount = recs.filter((r) => !r.removed && r.title.trim()).length;
      setMessage(
        activeCount
          ? "Plan published. The member will see your updated recommendations on their Plan page."
          : "Plan published. All recommendations were removed; the member will no longer see them on their Plan page.",
      );
      loadList();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Publish failed");
    } finally {
      setSaving(false);
    }
  }

  async function onSaveProfile(payload: {
    member_name?: string;
    personal_profile: import("../lib/profileFields").PersonalProfile;
  }) {
    if (!selectedId) return;
    setSavingProfile(true);
    try {
      const data = await updateReviewAssessmentContext(selectedId, payload);
      setDetail(data);
    } finally {
      setSavingProfile(false);
    }
  }

  async function onRemoveFromInbox(id: string) {
    setRemovingId(id);
    setMessage("");
    try {
      await archiveReviewAssessment(id);
      setMessage("Assessment removed from your inbox. The member plan is unchanged.");
      if (selectedId === id) setSelectedId(null);
      loadList();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not remove assessment");
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <Layout>
      <p className="label-eyebrow mb-2">Expert tools</p>
      <h1 className="page-title mb-2">Review member plans</h1>
      <p className="mb-8 max-w-2xl text-sm text-ayun-muted">
        Members keep their preliminary plan immediately. Edit recommendations here, then click{" "}
        <strong className="text-ink">Publish to member</strong>: removed items disappear from their Plan
        page only after you publish.
      </p>

      {needsLogin || !isExpert ? (
        <div className="card-panel mb-6 text-center">
          <p className="text-sm text-ayun-muted">
            Expert sign-in is required to review member plans. Sessions survive API restarts after you
            log in once.
          </p>
          <Link to="/login?tab=expert&next=/expert/review" className="btn-primary mt-4 inline-flex">
            Sign in as expert
          </Link>
        </div>
      ) : null}

      {message ? (
        <p className="mb-4 rounded-lg bg-ayun-light px-4 py-3 text-sm text-ayun-dark">{message}</p>
      ) : null}

      {!needsLogin && isExpert ? (
      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <aside className="card-panel !p-0">
          <div className="border-b border-rule px-4 py-3">
            <div className="text-sm font-semibold text-ink">Recent assessments</div>
            <div className="mt-2 flex rounded-md border border-rule bg-ayun-light/40 p-0.5">
              <button
                type="button"
                className={`flex-1 rounded px-2 py-1 text-xs font-medium transition ${
                  inboxTab === "pending" ? "bg-white text-ayun-dark shadow-sm" : "text-ayun-muted hover:text-ink"
                }`}
                onClick={() => setInboxTab("pending")}
              >
                To review
              </button>
              <button
                type="button"
                className={`flex-1 rounded px-2 py-1 text-xs font-medium transition ${
                  inboxTab === "finished" ? "bg-white text-ayun-dark shadow-sm" : "text-ayun-muted hover:text-ink"
                }`}
                onClick={() => setInboxTab("finished")}
              >
                Finished
              </button>
            </div>
          </div>
          {loadingList ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-ayun-green" />
            </div>
          ) : list.length === 0 ? (
            <p className="px-4 py-6 text-sm text-ayun-muted">
              {inboxTab === "finished"
                ? "No published assessments. Finished reviews appear here."
                : "No assessments waiting for review."}
            </p>
          ) : (
            <ul className="max-h-[420px] overflow-y-auto">
              {list.map((item) => (
                <li key={item.id} className="border-b border-rule">
                  <div
                    className={`flex items-stretch ${
                      selectedId === item.id ? "bg-ayun-green/10" : "hover:bg-ayun-light/60"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => setSelectedId(item.id)}
                      className="min-w-0 flex-1 px-4 py-3 text-left text-sm transition"
                    >
                      <span className="font-medium text-ink">{item.member_name || "Guest member"}</span>
                      <span className="mt-1 block text-xs text-ayun-muted">
                        {new Date(item.created_at).toLocaleString()} · {item.triggered_count} recs
                      </span>
                      {item.has_published_plan ? (
                        <span className="mt-1 inline-block text-xs font-semibold text-ayun-green">Published</span>
                      ) : null}
                    </button>
                    {inboxTab === "finished" ? (
                      <button
                        type="button"
                        title="Remove from inbox"
                        aria-label="Remove from inbox"
                        disabled={removingId === item.id}
                        onClick={() => onRemoveFromInbox(item.id)}
                        className="flex shrink-0 items-center border-l border-rule px-3 text-ayun-muted transition hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                      >
                        {removingId === item.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <X className="h-4 w-4" />
                        )}
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <div>
          {loadingDetail ? (
            <div className="card-panel flex justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-ayun-green" />
            </div>
          ) : !detail ? (
            <div className="card-panel text-sm text-ayun-muted">Select an assessment to review.</div>
          ) : (
            <div className="space-y-4">
              <div className="card-panel">
                <ExpertMemberContext
                  memberName={detail.member_name || detail.personal_profile?.name || "Guest"}
                  pseudonym={detail.pseudonym}
                  personalProfile={{
                    ...DEFAULT_PERSONAL_PROFILE,
                    ...(detail.personal_profile || {}),
                  }}
                  memberData={detail.member_data || {}}
                  editable
                  saving={savingProfile}
                  onSave={onSaveProfile}
                />
                <p className="mt-4 text-xs text-ayun-muted">Assessment {detail.id}</p>
              </div>

              <p className="label-eyebrow">Recommendations</p>

              {recs
                .map((rec, index) => ({ rec, index }))
                .filter(({ rec }) => !rec.removed)
                .map(({ rec, index }) => (
                  <div key={rec.id || index} className="card-panel space-y-3">
                    <div className="flex flex-wrap gap-3">
                      <select
                        className="rounded-lg border border-rule px-3 py-2 text-sm"
                        value={rec.reviewed_priority}
                        onChange={(e) => updateRec(index, { reviewed_priority: e.target.value })}
                      >
                        {PRIORITIES.map((p) => (
                          <option key={p} value={p}>
                            {p}
                          </option>
                        ))}
                      </select>
                      <input
                        className="min-w-[200px] flex-1 rounded-lg border border-rule px-3 py-2 text-sm"
                        value={rec.title}
                        placeholder="Recommendation title"
                        onChange={(e) => updateRec(index, { title: e.target.value })}
                      />
                      <button
                        type="button"
                        className="btn-secondary !px-3 !py-2 text-xs"
                        onClick={() => updateRec(index, { removed: true })}
                      >
                        Remove
                      </button>
                    </div>
                    <textarea
                      className="w-full rounded-lg border border-rule px-3 py-2 text-sm"
                      rows={4}
                      placeholder="Action items (one per line)"
                      value={itemsToText(rec.action_items)}
                      onChange={(e) => updateRec(index, { action_items: textToItems(e.target.value) })}
                    />
                    <input
                      className="w-full rounded-lg border border-rule px-3 py-2 text-sm"
                      placeholder="Clinician notes (optional)"
                      value={rec.clinician_notes || ""}
                      onChange={(e) => updateRec(index, { clinician_notes: e.target.value })}
                    />
                  </div>
                ))}

              <button type="button" className="btn-secondary" onClick={addCustomRec}>
                Add recommendation
              </button>

              <div className="card-panel space-y-3">
                <label className="text-sm font-semibold text-ink">Message to member (optional)</label>
                <textarea
                  className="w-full rounded-lg border border-rule px-3 py-2 text-sm"
                  rows={2}
                  value={clinicianNote}
                  onChange={(e) => setClinicianNote(e.target.value)}
                  placeholder="Short note shown on the member Plan page when you publish"
                />
              </div>

              <div className="flex flex-wrap gap-3">
                <button type="button" className="btn-secondary" disabled={saving} onClick={onSaveDraft}>
                  Save draft
                </button>
                <button type="button" className="btn-primary" disabled={saving} onClick={onPublish}>
                  Publish to member
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={saving || downloading || !selectedId}
                  onClick={async () => {
                    if (!selectedId) return;
                    setDownloading(true);
                    setMessage("");
                    try {
                      await downloadProtocolPdf({
                        path: `/api/reviews/assessments/${selectedId}/pdf`,
                        auth: "expert",
                        body: { recommendations: recs, clinician_note: clinicianNote },
                        fallbackName: "AYUN-sports-performance.pdf",
                      });
                    } catch (err) {
                      setMessage(err instanceof Error ? err.message : "Could not download the protocol PDF");
                    } finally {
                      setDownloading(false);
                    }
                  }}
                >
                  <FileDown className="h-4 w-4" />
                  {downloading
                    ? "Preparing PDF…"
                    : detail?.published
                      ? "Download confirmed PDF"
                      : "Download protocol PDF"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
      ) : null}
    </Layout>
  );
}
