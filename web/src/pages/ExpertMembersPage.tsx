import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { ExpertMemberContext } from "../components/ExpertMemberContext";
import { Layout } from "../components/Layout";
import { DEFAULT_PERSONAL_PROFILE } from "../lib/profileFields";
import { useApp } from "../lib/context";
import {
  fetchMemberDirectory,
  getExpertToken,
  updateMemberDirectoryContext,
  type MemberDirectoryEntry,
} from "../lib/api";

export function ExpertMembersPage() {
  const { isExpert, setActiveMode } = useApp();
  const [members, setMembers] = useState<MemberDirectoryEntry[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [needsLogin, setNeedsLogin] = useState(!getExpertToken());

  useEffect(() => {
    if (isExpert) setActiveMode("expert");
  }, [isExpert, setActiveMode]);

  const load = useCallback(async () => {
    if (!getExpertToken()) {
      setNeedsLogin(true);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    setNeedsLogin(false);
    try {
      const data = await fetchMemberDirectory();
      setMembers(data.members);
      setSelectedKey((prev) => {
        if (prev && data.members.some((m) => m.member_key === prev)) return prev;
        return data.members[0]?.member_key || null;
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not load members";
      if (msg.toLowerCase().includes("session") || msg.toLowerCase().includes("login")) {
        setNeedsLogin(true);
      } else {
        setError(msg);
      }
      setMembers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isExpert) load();
  }, [isExpert, load]);

  const selected = members.find((m) => m.member_key === selectedKey) || null;

  async function onSaveProfile(payload: {
    member_name?: string;
    personal_profile: import("../lib/profileFields").PersonalProfile;
  }) {
    if (!selected) return;
    setSaving(true);
    try {
      const updated = await updateMemberDirectoryContext(selected.member_key, payload);
      setMembers((prev) => prev.map((m) => (m.member_key === updated.member_key ? updated : m)));
    } finally {
      setSaving(false);
    }
  }

  if (needsLogin || !isExpert) {
    return (
      <Layout>
        <div className="card-panel text-center text-sm text-ayun-muted">
          <p>Member profiles are for AYUN clinicians only.</p>
          <Link to="/login?tab=expert&next=/expert/members" className="btn-primary mt-4 inline-flex">
            Sign in as expert
          </Link>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <p className="label-eyebrow mb-2">Expert tools</p>
      <h1 className="page-title mb-2">Member profiles</h1>
      <p className="mb-8 max-w-2xl text-sm text-ayun-muted">
        Personal context and checkup results from saved assessments. Edit profile notes here, then open
        Plan review to adjust recommendations.
      </p>

      {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

      {loading ? (
        <Loader2 className="mx-auto h-8 w-8 animate-spin text-ayun-green" />
      ) : members.length === 0 ? (
        <div className="card-panel text-sm text-ayun-muted">
          No member assessments saved yet. Members appear here after they run an assessment while signed
          in, or as guests with a name on their profile.
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
          <aside className="card-panel !p-0">
            <div className="border-b border-rule px-4 py-3 text-sm font-semibold text-ink">Members</div>
            <ul className="max-h-[520px] overflow-y-auto">
              {members.map((m) => (
                <li key={m.member_key}>
                  <button
                    type="button"
                    onClick={() => setSelectedKey(m.member_key)}
                    className={`w-full border-b border-rule px-4 py-3 text-left text-sm transition hover:bg-ayun-light/60 ${
                      selectedKey === m.member_key ? "bg-ayun-green/10" : ""
                    }`}
                  >
                    <span className="font-medium text-ink">{m.member_name}</span>
                    {m.email ? (
                      <span className="mt-0.5 block text-xs text-ayun-muted">{m.email}</span>
                    ) : null}
                    <span className="mt-1 block text-xs text-ayun-muted">
                      {m.assessment_count} assessment{m.assessment_count === 1 ? "" : "s"} ·{" "}
                      {new Date(m.latest_created_at).toLocaleDateString()}
                    </span>
                    {m.has_published_plan ? (
                      <span className="mt-1 inline-block text-xs font-semibold text-ayun-green">
                        Published plan
                      </span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          {selected ? (
            <div className="space-y-6">
              <div className="card-panel">
                <h2 className="font-serif text-2xl text-ink">{selected.member_name}</h2>
                <p className="mt-2 text-sm text-ayun-muted">
                  Latest assessment {new Date(selected.latest_created_at).toLocaleString()}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Link
                    to={`/expert/review?assessment=${selected.latest_assessment_id}`}
                    className="btn-primary !text-sm"
                  >
                    Open in Plan review
                  </Link>
                </div>
              </div>

              <div className="card-panel">
                <ExpertMemberContext
                  memberName={selected.member_name}
                  email={selected.email}
                  pseudonym={selected.pseudonym}
                  personalProfile={{ ...DEFAULT_PERSONAL_PROFILE, ...selected.personal_profile }}
                  memberData={selected.member_data}
                  editable
                  saving={saving}
                  onSave={onSaveProfile}
                />
              </div>

              <section className="card-panel">
                <h3 className="mb-4 font-serif text-xl text-ink">Assessment history</h3>
                <div className="space-y-2">
                  {selected.assessments.map((a) => (
                    <div
                      key={a.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-rule px-3 py-2 text-sm"
                    >
                      <div>
                        <span className="font-mono text-xs text-ayun-muted">{a.id}</span>
                        <span className="ml-2 text-ayun-muted">
                          {new Date(a.created_at).toLocaleString()} · {a.triggered_count} recs
                        </span>
                        {a.has_published_plan ? (
                          <span className="ml-2 text-xs font-semibold text-ayun-green">Published</span>
                        ) : null}
                      </div>
                      <Link
                        to={`/expert/review?assessment=${a.id}`}
                        className="text-sm font-medium text-ayun-green hover:underline"
                      >
                        Review
                      </Link>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          ) : (
            <div className="card-panel text-sm text-ayun-muted">Select a member.</div>
          )}
        </div>
      )}
    </Layout>
  );
}
