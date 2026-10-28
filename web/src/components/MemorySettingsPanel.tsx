/**
 * MemorySettingsPanel — shows episodic memory records + consent / retention controls.
 * Mounted on the ProfilePage for signed-in members.
 *
 * Tiers visible to the user:
 *   Tier 1 (Working)  — ephemeral, in-session, nothing stored
 *   Tier 2 (Episodic) — past session summaries with TTL; managed here
 *   Tier 3 (Semantic) — shared knowledge library; no personal data
 */

import { useEffect, useRef, useState } from "react";
import { Brain, ChevronDown, Clock, Shield, Trash2 } from "lucide-react";
import {
  deleteMyMemory,
  fetchMyMemory,
  fetchRetentionOptions,
  updatePrivacySettings,
  type MemoryRecord,
  type RetentionOption,
} from "../lib/api";
import { useApp } from "../lib/context";

export function MemorySettingsPanel() {
  const { memberUser, applyMemberUser } = useApp();

  const [records, setRecords] = useState<MemoryRecord[]>([]);
  const [options, setOptions] = useState<RetentionOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const privacySettings = memberUser?.privacy_settings;
  const [memEnabled, setMemEnabled] = useState(privacySettings?.memory_enabled ?? true);
  const [retentionDays, setRetentionDays] = useState(privacySettings?.memory_retention_days ?? 30);
  const [open, setOpen] = useState(false);

  const initDone = useRef(false);

  useEffect(() => {
    if (!memberUser) return;
    // Sync local state when memberUser updates
    setMemEnabled(memberUser.privacy_settings?.memory_enabled ?? true);
    setRetentionDays(memberUser.privacy_settings?.memory_retention_days ?? 30);
  }, [memberUser]);

  useEffect(() => {
    if (!memberUser || initDone.current) return;
    initDone.current = true;

    Promise.all([fetchMyMemory(), fetchRetentionOptions()])
      .then(([memRes, optRes]) => {
        setRecords(memRes.records);
        setOptions(optRes.options);
      })
      .catch(() => setError("Could not load memory data"))
      .finally(() => setLoading(false));
  }, [memberUser]);

  async function savePrivacy() {
    setSaving(true);
    setError("");
    try {
      const result = await updatePrivacySettings({ memory_enabled: memEnabled, memory_retention_days: retentionDays });
      if (memberUser) {
        applyMemberUser({ ...memberUser, privacy_settings: result.privacy_settings });
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function eraseMemory() {
    try {
      await deleteMyMemory();
      setRecords([]);
      setConfirmDelete(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  const confidenceColor = (c: string) =>
    c === "high" ? "text-ayun-green" : c === "medium" ? "text-amber-600" : "text-ayun-muted";

  return (
    <div className="border border-rule rounded-2xl overflow-hidden">
      {/* Header / toggle */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-6 py-4 text-left hover:bg-surface-hover transition"
      >
        <div className="flex items-center gap-3">
          <Brain className="h-5 w-5 text-ayun-green flex-shrink-0" />
          <div>
            <p className="text-sm font-semibold">AI Memory</p>
            <p className="text-xs text-ayun-muted">
              {memEnabled
                ? `Remembers past sessions · ${options.find((o) => o.days === retentionDays)?.label ?? `${retentionDays}d`}`
                : "Memory off. Every session starts fresh."}
            </p>
          </div>
        </div>
        <ChevronDown
          className={`h-4 w-4 text-ayun-muted transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="border-t border-rule px-6 py-5 space-y-6">
          {/* Memory architecture explainer */}
          <div className="grid gap-3 sm:grid-cols-3 text-xs">
            {[
              {
                tier: "Tier 1",
                name: "Working",
                desc: "Last 6 turns of the current chat. Ephemeral, never stored.",
                icon: <Clock className="h-3.5 w-3.5" />,
                color: "text-blue-600",
              },
              {
                tier: "Tier 2",
                name: "Episodic",
                desc: "Compact summary of past sessions, stored under your chosen retention period.",
                icon: <Brain className="h-3.5 w-3.5" />,
                color: "text-ayun-green",
              },
              {
                tier: "Tier 3",
                name: "Knowledge",
                desc: "Shared validated health evidence. No personal data, never expires.",
                icon: <Shield className="h-3.5 w-3.5" />,
                color: "text-ayun-muted",
              },
            ].map((t) => (
              <div key={t.tier} className="rounded-xl border border-rule p-3 space-y-1">
                <div className={`flex items-center gap-1.5 font-semibold ${t.color}`}>
                  {t.icon}
                  <span>{t.tier}: {t.name}</span>
                </div>
                <p className="text-ayun-muted leading-snug">{t.desc}</p>
              </div>
            ))}
          </div>

          {/* Consent switch */}
          <div className="flex items-center justify-between rounded-xl border border-rule px-4 py-3">
            <div>
              <p className="text-sm font-medium">Enable episodic memory</p>
              <p className="text-xs text-ayun-muted">
                AI will recall past sessions to personalise answers.
              </p>
            </div>
            <button
              type="button"
              onClick={() => { setMemEnabled((v) => !v); setSaved(false); }}
              className={`relative h-6 w-11 rounded-full transition-colors ${
                memEnabled ? "bg-ayun-green" : "bg-rule"
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  memEnabled ? "translate-x-5" : ""
                }`}
              />
            </button>
          </div>

          {/* Retention picker */}
          {memEnabled && (
            <div>
              <label className="text-sm font-medium">Retention period (GDPR Art. 5)</label>
              <div className="mt-2 flex flex-col gap-2">
                {options.map((opt) => (
                  <label
                    key={opt.days}
                    className="flex items-center gap-3 cursor-pointer rounded-lg border border-rule px-3 py-2 text-sm hover:border-ayun-green/40 transition"
                  >
                    <input
                      type="radio"
                      name="retention"
                      value={opt.days}
                      checked={retentionDays === opt.days}
                      onChange={() => { setRetentionDays(opt.days); setSaved(false); }}
                      className="accent-ayun-green"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>
          )}

          {error && <p className="text-xs text-red-600">{error}</p>}
          {saved && <p className="text-xs text-ayun-green">Preferences saved.</p>}

          <button
            type="button"
            onClick={savePrivacy}
            disabled={saving}
            className="btn-primary text-sm"
          >
            {saving ? "Saving…" : "Save preferences"}
          </button>

          {/* Past session records */}
          {loading ? (
            <p className="text-xs text-ayun-muted">Loading memory…</p>
          ) : records.length > 0 ? (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-ayun-muted mb-3">
                Past session summaries ({records.length})
              </p>
              <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                {records.map((rec) => (
                  <div key={rec.id} className="rounded-xl border border-rule p-3 text-xs space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex flex-wrap gap-1">
                        {rec.topics.map((t) => (
                          <span key={t} className="rounded-full bg-ayun-green/10 px-2 py-0.5 text-ayun-dark font-medium">
                            {t}
                          </span>
                        ))}
                      </div>
                      <span className="text-ayun-muted whitespace-nowrap">{rec.created_at.slice(0, 10)}</span>
                    </div>
                    <p className="text-ayun-muted leading-relaxed">{rec.summary}</p>
                    <div className="flex items-center gap-3 text-ayun-muted">
                      <span className={confidenceColor(rec.confidence_avg)}>
                        {rec.confidence_avg} confidence
                      </span>
                      <span>·</span>
                      <span>{rec.turn_count} exchange{rec.turn_count !== 1 ? "s" : ""}</span>
                      {rec.expires_at && (
                        <>
                          <span>·</span>
                          <span>Expires {rec.expires_at.slice(0, 10)}</span>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-xs text-ayun-muted">
              No session summaries stored yet. They appear here after a chat ends.
            </p>
          )}

          {/* Right to erasure */}
          <div className="border-t border-rule pt-4">
            {!confirmDelete ? (
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                className="flex items-center gap-2 text-xs text-red-600 hover:text-red-700 transition"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Erase all my memory (GDPR Art. 17, Right to Erasure)
              </button>
            ) : (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 space-y-2">
                <p className="text-xs font-medium text-red-700">
                  This permanently deletes all stored session summaries. This action cannot be undone.
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={eraseMemory}
                    className="rounded-lg bg-red-600 px-3 py-1 text-xs text-white hover:bg-red-700 transition"
                  >
                    Yes, erase everything
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(false)}
                    className="rounded-lg border border-rule px-3 py-1 text-xs hover:bg-surface-hover transition"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
