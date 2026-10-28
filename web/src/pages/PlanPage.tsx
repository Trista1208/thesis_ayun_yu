import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { FileDown } from "lucide-react";
import { Layout } from "../components/Layout";
import { ProtocolCard } from "../components/ProtocolCard";
import { ProtocolSections } from "../components/ProtocolSections";
import { useApp } from "../lib/context";
import { AYUN_RANGES_SOURCE, AYUN_STANDARD_NOTE, protocolIsIndicated, hasProblemRating, isConcerningRating, ratingLabel } from "../lib/protocols";
import { downloadProtocolPdf, fetchPublishedPlan, type PublishedPlan, type AssessmentResult } from "../lib/api";

type Triggered = AssessmentResult["triggered"][number];
type Rating = AssessmentResult["ratings"][number];
type ReviewRec = PublishedPlan["recommendations"][number];

function priorityClass(p: string) {
  const map: Record<string, string> = {
    Critical: "badge-critical",
    High: "badge-high",
    Medium: "badge-medium",
    Low: "badge-low",
  };
  return map[p] || "badge-medium";
}

function actionItems(items: string[] | string): string[] {
  if (Array.isArray(items)) return items;
  return items
    .split("\n")
    .map((line) => line.replace(/^[\s•-]+/, "").trim())
    .filter(Boolean);
}

function RecommendationCards({
  items,
  showNotes = false,
}: {
  items: Array<{ title: string; category?: string; priority: string; action_items: string[]; notes?: string }>;
  showNotes?: boolean;
}) {
  if (!items.length) {
    return <div className="card-panel">No recommendations in this section.</div>;
  }
  return (
    <div className="space-y-4">
      {items.map((rec) => (
        <article key={rec.title + rec.priority} className="card-panel border-l-4 border-l-ayun-green">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className={priorityClass(rec.priority)}>{rec.priority}</span>
            {rec.category ? <span className="text-xs text-ayun-muted">{rec.category}</span> : null}
          </div>
          <h2 className="font-serif text-xl text-ink">{rec.title}</h2>
          <ProtocolSections items={rec.action_items} />
          {showNotes && rec.notes ? (
            <p className="mt-3 rounded-lg bg-ayun-light/70 px-3 py-2 text-sm text-ayun-dark">
              <span className="font-semibold">Clinician note: </span>
              {rec.notes}
            </p>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function ProtocolCards({ items }: { items: NonNullable<AssessmentResult["protocol_recommendations"]> }) {
  if (!items.length) return null;
  return (
    <div className="space-y-4">
      {items.map((protocol) => (
        <ProtocolCard key={protocol.key} protocol={protocol} />
      ))}
    </div>
  );
}

export function PlanPage() {
  const { assessment, assessmentId, isMember, memberLoading, activeMode, isExpert } = useApp();
  const [published, setPublished] = useState<PublishedPlan | null>(null);
  const [loadingPublished, setLoadingPublished] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [pdfError, setPdfError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoadingPublished(true);
    fetchPublishedPlan({ assessmentId, asMember: isMember })
      .then((data) => {
        if (!cancelled) setPublished(data.published);
      })
      .catch(() => {
        if (!cancelled) setPublished(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingPublished(false);
      });
    return () => {
      cancelled = true;
    };
  }, [assessmentId, isMember]);

  if (activeMode === "expert" && isExpert) {
    return <Navigate to="/expert/members" replace />;
  }

  if (memberLoading) {
    return (
      <Layout>
        <p className="text-sm text-ayun-muted">Loading your plan…</p>
      </Layout>
    );
  }

  if (!assessment) {
    return (
      <Layout>
        <div className="card-panel text-center">
          <p className="text-ayun-muted">No plan yet.</p>
          <Link to="/assessment" className="btn-primary mt-4 inline-flex">
            Run assessment
          </Link>
        </div>
      </Layout>
    );
  }

  const removedTitles = new Set(published?.removed_titles || []);
  const inRange = !hasProblemRating(assessment.ratings);
  const averageNames = Array.from(
    new Set(
      assessment.ratings
        .filter((r: Rating) => r.value != null && r.rating === "average")
        .map((r: Rating) => r.parameter.split("::").pop() || r.parameter),
    ),
  );
  const preliminary = inRange
    ? []
    : assessment.triggered
        .filter((rec: Triggered) => !removedTitles.has(rec.title))
        .map((rec: Triggered) => ({
          title: rec.title,
          category: rec.category,
          priority: rec.priority,
          action_items: rec.action_items,
        }));

  const reviewed = inRange
    ? []
    : (published?.recommendations || [])
        .filter((rec: ReviewRec) => !rec.removed)
        .map((rec: ReviewRec) => ({
          title: rec.title,
          category: rec.category,
          priority: rec.reviewed_priority,
          action_items: actionItems(rec.action_items),
          notes: rec.clinician_notes,
        }));
  const protocols = (assessment.protocol_recommendations || []).filter((protocol) =>
    protocolIsIndicated(protocol.key, assessment.ratings),
  );

  async function onDownloadPdf() {
    setDownloading(true);
    setPdfError("");
    try {
      await downloadProtocolPdf({ path: "/api/plan/pdf", auth: "member" });
    } catch (err) {
      setPdfError(err instanceof Error ? err.message : "Could not download the protocol PDF");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <Layout>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label-eyebrow mb-2">Your plan</p>
          <h1 className="page-title mb-2">Recommendations</h1>
          <p className="text-sm text-ayun-muted">
            {assessment.sex_group.replace("_", " ")} · {assessment.age_group.replace("age_", "").replace("_", "–")}
          </p>
        </div>
        <button type="button" className="btn-secondary" disabled={downloading} onClick={onDownloadPdf}>
          <FileDown className="h-4 w-4" />
          {downloading ? "Preparing PDF…" : "Download protocol PDF"}
        </button>
      </div>
      {pdfError ? (
        <p className="mb-6 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{pdfError}</p>
      ) : null}

      {!loadingPublished && published ? (
        <div className="mb-8 rounded-xl border border-ayun-green/40 bg-ayun-green/10 px-4 py-3 text-sm text-ayun-dark">
          <p className="font-semibold">Updated by the AYUN clinician team</p>
          <p className="mt-1 text-ayun-muted">
            Reviewed by {published.published_by} ·{" "}
            {new Date(published.published_at).toLocaleString()}
          </p>
          {published.clinician_note ? (
            <p className="mt-2">{published.clinician_note}</p>
          ) : null}
        </div>
      ) : (
        <div className="mb-8 rounded-xl border border-rule bg-ayun-light/50 px-4 py-3 text-sm text-ayun-muted">
          Preliminary plan from your health profile. An AYUN clinician can review and update this for you.
        </div>
      )}

      {inRange ? (
        <section className="mb-10">
          <div className="card-panel border-l-4 border-l-ayun-green">
            <p className="label-eyebrow mb-2">Looking good</p>
            <h2 className="font-serif text-xl text-ink">You’re in a healthy range overall</h2>
            <p className="mt-2 text-sm leading-relaxed text-ayun-muted">
              Measured values are in a healthy range for your age and sex.
              Use Ask Joule if you want optional tips to move from good toward excellent.
            </p>
          </div>
        </section>
      ) : null}

      {averageNames.length > 0 ? (
        <p className="mb-10 text-sm leading-relaxed text-ayun-muted">
          {averageNames.join(", ")} {averageNames.length === 1 ? "is" : "are"} in the average range,
          which is fine. If you like, you can aim for the good range over time.
        </p>
      ) : null}

      {published && reviewed.length > 0 ? (
        <section className="mb-10">
          <h2 className="mb-4 font-serif text-2xl text-ink">Clinician-reviewed plan</h2>
          <RecommendationCards items={reviewed} showNotes />
        </section>
      ) : !inRange && published && removedTitles.size > 0 ? (
        <section className="mb-10">
          <h2 className="mb-4 font-serif text-2xl text-ink">Clinician-reviewed plan</h2>
          <div className="card-panel text-sm text-ayun-muted">
            Your clinician removed all recommendations from this plan.
          </div>
        </section>
      ) : null}

      {!inRange ? (
      <section>
        <h2 className="mb-4 font-serif text-2xl text-ink">
          {published ? "Original preliminary plan" : "Your preliminary plan"}
        </h2>
        <p className="mb-4 text-sm text-ayun-muted">{AYUN_STANDARD_NOTE}</p>
        {published && removedTitles.size > 0 ? (
          <p className="mb-4 text-sm text-ayun-muted">
            Items your clinician removed are hidden here after their review.
          </p>
        ) : null}
        <RecommendationCards items={preliminary} />
      </section>
      ) : null}

      {protocols.length > 0 ? (
        <section className="mt-10">
          <h2 className="mb-2 font-serif text-2xl text-ink">Matched AYUN protocols</h2>
          <p className="mb-4 text-sm text-ayun-muted">
            Clinic protocols automatically matched to your assessment results and goals.
          </p>
          <ProtocolCards items={protocols} />
        </section>
      ) : null}

      <section className="mt-10">
        <h2 className="mb-2 font-serif text-2xl">Parameter ratings</h2>
        <p className="text-sm text-ayun-muted">{AYUN_STANDARD_NOTE}</p>
        <p className="mb-4 mt-1 text-xs text-ayun-muted">{AYUN_RANGES_SOURCE}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {assessment.ratings
            .filter((r: Rating) => r.value != null)
            .map((r: Rating) => (
              <div key={r.parameter} className="card-panel !p-4">
                <p className="text-xs text-ayun-muted">{r.parameter.split("::").pop()}</p>
                <p className="font-semibold">
                  {r.value} {r.unit}{" "}
                  <span
                    className={`text-sm font-normal ${
                      isConcerningRating(r.parameter, r.rating) ? "text-amber-700" : "text-ayun-green"
                    }`}
                  >
                    · {ratingLabel(r.rating)}
                  </span>
                  {r.parameter === "Body Composition::Fat percentage" && r.value != null && r.value <= 30 &&
                  r.rating !== "excellent" && r.rating !== "good" ? (
                    <span className="block text-xs font-normal text-ayun-muted">
                      AYUN classes body fat as high only above 30%.
                    </span>
                  ) : null}
                </p>
              </div>
            ))}
        </div>
      </section>

      {assessment.training_zones && (
        <section className="mt-10">
          <h2 className="mb-4 font-serif text-2xl">Training zones</h2>
          <div className="card-panel text-sm">
            <p className="mb-3 text-xs text-ayun-muted">
              {assessment.training_zones.source} · HR max {assessment.training_zones.hr_max} bpm
              {assessment.training_zones.source.startsWith("CPET")
                ? ` · VT1 ${assessment.training_zones.vt1_bpm} bpm · VT2 ${assessment.training_zones.vt2_bpm} bpm`
                : ""}
            </p>
            <dl className="divide-y divide-rule/70">
              {Object.entries(assessment.training_zones.zones).map(([zone, range]) => (
                <div key={zone} className="grid grid-cols-[1fr_auto] gap-4 py-2">
                  <dt className="text-ayun-muted">{zone}</dt>
                  <dd className="font-medium text-ink">{range}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      )}
    </Layout>
  );
}
