import { useState } from "react";
import { Loader2 } from "lucide-react";
import { labelForFieldKey } from "../lib/assessmentFields";
import { extractText } from "../lib/api";
import type { PersonalProfile } from "../lib/profileFields";

const PROFILE_LABELS: Partial<Record<keyof PersonalProfile, string>> = {
  goals: "Goals",
  sport_prefs: "Preferred sports",
  activity_level: "Activity level",
  geographic_area: "Region",
  location_detail: "Location",
  health_status: "Health status",
  existing_conditions: "Existing conditions",
  smoking_status: "Smoking",
  alcohol_use: "Alcohol",
  sleep_hours: "Sleep",
  diet: "Diet",
  stress: "Stress",
  injuries: "Injuries",
};

type Proposal = {
  id: string;
  target: "member" | "profile";
  key: string;
  label: string;
  current: unknown;
  value: unknown;
  checked: boolean;
};

function show(v: unknown): string {
  if (v == null || v === "" || (Array.isArray(v) && v.length === 0)) return "—";
  return Array.isArray(v) ? v.join(", ") : String(v);
}

export function PasteTextPanel({
  memberData,
  personalProfile,
  onApply,
}: {
  memberData: Record<string, unknown>;
  personalProfile: PersonalProfile;
  onApply: (member: Record<string, unknown>, profile: Partial<PersonalProfile>) => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [proposals, setProposals] = useState<Proposal[] | null>(null);
  const [applied, setApplied] = useState(0);

  async function onRead() {
    setBusy(true);
    setError("");
    setApplied(0);
    setProposals(null);
    try {
      const res = await extractText(text);
      const rows: Proposal[] = [
        ...Object.entries(res.member_data).map(([key, value]) => ({
          id: `m:${key}`,
          target: "member" as const,
          key,
          label: labelForFieldKey(key),
          current: memberData[key],
          value,
          checked: true,
        })),
        ...Object.entries(res.personal_profile).map(([key, value]) => ({
          id: `p:${key}`,
          target: "profile" as const,
          key,
          label: PROFILE_LABELS[key as keyof PersonalProfile] ?? key,
          current: personalProfile[key as keyof PersonalProfile],
          value,
          checked: true,
        })),
      ];
      setWarnings(res.warnings || []);
      if (rows.length === 0) setError("No values found in this text. Try adding numbers with units, e.g. “body fat 21%”.");
      else setProposals(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read the text");
    } finally {
      setBusy(false);
    }
  }

  function toggle(id: string) {
    setProposals((rows) => rows && rows.map((r) => (r.id === id ? { ...r, checked: !r.checked } : r)));
  }

  function apply() {
    if (!proposals) return;
    const picked = proposals.filter((r) => r.checked);
    const member: Record<string, unknown> = {};
    const profile: Partial<PersonalProfile> = {};
    for (const r of picked) {
      if (r.target === "member") member[r.key] = r.value;
      else (profile as Record<string, unknown>)[r.key] = r.value;
    }
    onApply(member, profile);
    setApplied(picked.length);
    setProposals(null);
  }

  return (
    <div className="card-panel h-fit">
      <p className="label-eyebrow mb-3">Paste as text</p>
      <p className="mb-3 text-sm text-ayun-muted">
        Type or paste anything about yourself: age, height, goals, diet, injuries, DEXA or lab values.
        You review every value before it fills the form.
      </p>
      <textarea
        className="w-full rounded-lg border border-rule px-3 py-2 text-sm"
        rows={6}
        maxLength={20000}
        placeholder="e.g. 42, male, 181 cm, 79 kg. Body fat 21%, ALMI 8.1. Mostly vegetarian. Want to lose weight and run a half marathon. Left knee pain."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button
        type="button"
        className="btn-primary mt-3 w-full"
        disabled={busy || !text.trim()}
        onClick={onRead}
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        {busy ? "Reading…" : "Read text"}
      </button>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      {warnings.length > 0 && <p className="mt-3 text-xs text-amber-800">{warnings.join(" ")}</p>}

      {proposals && (
        <div className="mt-4 rounded-lg border border-ayun-green/30 bg-ayun-green/5 px-3 py-3 text-sm">
          <p className="mb-2 font-medium text-ayun-dark">Review what we found</p>
          <ul className="space-y-2">
            {proposals.map((r) => (
              <li key={r.id}>
                <label className="flex cursor-pointer items-start gap-2">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 accent-ayun-green"
                    checked={r.checked}
                    onChange={() => toggle(r.id)}
                  />
                  <span>
                    <span className="font-medium text-ink">{r.label}</span>
                    <span className="block text-xs text-ayun-muted">
                      {show(r.current)} → <span className="text-ink">{show(r.value)}</span>
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex gap-2">
            <button type="button" className="btn-primary flex-1" onClick={apply}>
              Apply selected
            </button>
            <button type="button" className="flex-1 rounded-lg border border-rule px-3 py-2 text-sm" onClick={() => setProposals(null)}>
              Discard
            </button>
          </div>
        </div>
      )}

      {applied > 0 && (
        <p className="mt-3 text-xs text-ayun-muted">
          {applied} value{applied === 1 ? "" : "s"} added to the form. Check them, then press “Generate recommendations” to save.
        </p>
      )}
    </div>
  );
}
