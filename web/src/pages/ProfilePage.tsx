import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Layout } from "../components/Layout";
import { MemorySettingsPanel } from "../components/MemorySettingsPanel";
import { memberLogout, updateMemberProfile } from "../lib/api";
import { useApp } from "../lib/context";
import { DEMOGRAPHIC_FIELDS } from "../lib/assessmentFields";
import {
  ACTIVITY_LEVELS,
  ALCOHOL_USE_OPTIONS,
  GEOGRAPHIC_AREAS,
  GOAL_OPTIONS,
  HEALTH_STATUS_OPTIONS,
  SLEEP_HOURS_OPTIONS,
  SMOKING_STATUS_OPTIONS,
  SPORT_OPTIONS,
  WELLBEING_LEVELS,
  type PersonalProfile,
} from "../lib/profileFields";

const AGE_KEY = "Demographic::Age";
const SEX_KEY = "Demographic::Sex";
const HEIGHT_KEY = "Demographic::Height (cm)";
const WEIGHT_KEY = "Demographic::Weight (kg)";

function TagPicker({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  function toggle(option: string) {
    onChange(selected.includes(option) ? selected.filter((o) => o !== option) : [...selected, option]);
  }

  return (
    <div>
      <label className="text-sm font-medium">{label}</label>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((option) => {
          const on = selected.includes(option);
          return (
            <button
              key={option}
              type="button"
              onClick={() => toggle(option)}
              className={`rounded-full border px-3 py-1 text-xs transition ${
                on
                  ? "border-ayun-green bg-ayun-green/10 text-ayun-dark"
                  : "border-rule text-ayun-muted hover:border-ayun-green/40"
              }`}
            >
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function ProfilePage() {
  const navigate = useNavigate();
  const {
    isMember,
    memberUser,
    personalProfile,
    setPersonalProfile,
    memberName,
    setMemberName,
    pseudonym,
    setPseudonym,
    memberData,
    setMemberData,
    clearMember,
  } = useApp();

  const ageField = DEMOGRAPHIC_FIELDS.find((f) => f.key === AGE_KEY)!;
  const sexField = DEMOGRAPHIC_FIELDS.find((f) => f.key === SEX_KEY)!;
  const heightField = DEMOGRAPHIC_FIELDS.find((f) => f.key === HEIGHT_KEY)!;
  const weightField = DEMOGRAPHIC_FIELDS.find((f) => f.key === WEIGHT_KEY)!;
  const ageValue = memberData[AGE_KEY];
  const genderValue = String(memberData[SEX_KEY] ?? sexField.options?.[0] ?? "Male");
  const heightValue = memberData[HEIGHT_KEY];
  const weightValue = memberData[WEIGHT_KEY];
  const heightNum = Number(heightValue);
  const weightNum = Number(weightValue);
  const bmi =
    Number.isFinite(heightNum) && heightNum > 0 && Number.isFinite(weightNum) && weightNum > 0
      ? weightNum / (heightNum / 100) ** 2
      : null;
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  function updateProfile(patch: Partial<PersonalProfile>) {
    setPersonalProfile({ ...personalProfile, ...patch });
    setSaved(false);
  }

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    if (!isMember) return;
    setSaving(true);
    setError("");
    try {
      const profile = { ...personalProfile, name: memberName.trim() || personalProfile.name };
      const memberPayload = {
        ...memberData,
        [AGE_KEY]: memberData[AGE_KEY],
        [SEX_KEY]: memberData[SEX_KEY],
        [HEIGHT_KEY]: memberData[HEIGHT_KEY],
        [WEIGHT_KEY]: memberData[WEIGHT_KEY],
      };
      const user = await updateMemberProfile({
        display_name: memberName.trim() || memberUser?.display_name,
        pseudonym,
        personal_profile: profile,
        member_data: memberPayload,
      });
      setMemberData(user.member_data || memberPayload);
      setPersonalProfile({ ...profile, ...user.personal_profile });
      setMemberName(user.personal_profile?.name?.trim() || user.display_name || memberName);
      setPseudonym(user.pseudonym);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function onSignOut() {
    try {
      await memberLogout();
    } catch {
      /* clear local session anyway */
    }
    clearMember();
    navigate("/login");
  }

  if (!isMember) {
    return (
      <Layout>
        <div className="card-panel mx-auto max-w-md text-center">
          <h1 className="page-title mb-3">Personal profile</h1>
          <p className="mb-6 text-sm text-ayun-muted">
            Sign in to save your goals, preferences, and wellbeing notes across sessions.
          </p>
          <Link to="/login" className="btn-primary">
            Sign in or register
          </Link>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <p className="label-eyebrow mb-2">Saved to your account</p>
      <h1 className="page-title mb-4">Personal profile</h1>
      <p className="mb-8 max-w-2xl text-sm text-ayun-muted">
        Optional fields sent to Ask Joule and included in your sport plan context. Assessment lab values
        are saved when you run an assessment.
      </p>

      <form onSubmit={onSave} className="card-panel max-w-3xl space-y-8">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="text-sm font-medium">Member name</label>
            <input
              className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
              value={memberName}
              onChange={(e) => {
                setMemberName(e.target.value);
                setSaved(false);
              }}
              placeholder="e.g. Manuel Burger"
            />
          </div>
          <div>
            <label className="text-sm font-medium">Research pseudonym</label>
            <input
              className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
              value={pseudonym}
              onChange={(e) => {
                setPseudonym(e.target.value);
                setSaved(false);
              }}
            />
          </div>
        </div>

        <div className="border-t border-rule pt-6">
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-ayun-muted">Demographics</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium">Age</label>
              <input
                type="number"
                min={ageField.min}
                max={ageField.max}
                step={ageField.step ?? 1}
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={ageValue != null && ageValue !== "" ? String(ageValue) : ""}
                onChange={(e) => {
                  setMemberData({
                    ...memberData,
                    [AGE_KEY]: e.target.value === "" ? null : Number(e.target.value),
                  });
                  setSaved(false);
                }}
              />
            </div>
            <div>
              <label className="text-sm font-medium">Gender</label>
              <select
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={genderValue}
                onChange={(e) => {
                  setMemberData({ ...memberData, [SEX_KEY]: e.target.value });
                  setSaved(false);
                }}
              >
                {sexField.options!.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Height (cm)</label>
              <input
                type="number"
                min={heightField.min}
                max={heightField.max}
                step={heightField.step ?? 1}
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={heightValue != null && heightValue !== "" ? String(heightValue) : ""}
                onChange={(e) => {
                  setMemberData({
                    ...memberData,
                    [HEIGHT_KEY]: e.target.value === "" ? null : Number(e.target.value),
                  });
                  setSaved(false);
                }}
                placeholder="e.g. 175"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Weight (kg)</label>
              <input
                type="number"
                min={weightField.min}
                max={weightField.max}
                step={weightField.step ?? 0.1}
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={weightValue != null && weightValue !== "" ? String(weightValue) : ""}
                onChange={(e) => {
                  setMemberData({
                    ...memberData,
                    [WEIGHT_KEY]: e.target.value === "" ? null : Number(e.target.value),
                  });
                  setSaved(false);
                }}
                placeholder="e.g. 72"
              />
            </div>
          </div>
          {bmi != null && (
            <p className="mt-2 text-xs text-ayun-muted">Estimated BMI: {bmi.toFixed(1)} kg/m²</p>
          )}
          <p className="mt-2 text-xs text-ayun-muted">
            Used for age-, sex-, and body-composition–aware recommendations. Synced with Assessment.
          </p>
        </div>

        <div className="border-t border-rule pt-6">
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-ayun-muted">
            Lifestyle
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium">Smoking status</label>
              <select
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={personalProfile.smoking_status || "Not specified"}
                onChange={(e) => updateProfile({ smoking_status: e.target.value })}
              >
                {SMOKING_STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Alcohol use</label>
              <select
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={personalProfile.alcohol_use || "Not specified"}
                onChange={(e) => updateProfile({ alcohol_use: e.target.value })}
              >
                {ALCOHOL_USE_OPTIONS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Typical sleep</label>
              <select
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={personalProfile.sleep_hours || "Not specified"}
                onChange={(e) => updateProfile({ sleep_hours: e.target.value })}
              >
                {SLEEP_HOURS_OPTIONS.map((hours) => (
                  <option key={hours} value={hours}>
                    {hours}
                  </option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className="text-sm font-medium">Diet / dietary notes</label>
              <textarea
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                rows={3}
                value={personalProfile.diet || ""}
                onChange={(e) => updateProfile({ diet: e.target.value })}
                placeholder="e.g. Vegetarian, gluten-free, low carb, no dairy — or leave blank if none"
              />
            </div>
          </div>
          <p className="mt-2 text-xs text-ayun-muted">
            Used for recovery, cardiovascular risk, and nutrition-aware recommendations.
          </p>
        </div>

        <div className="border-t border-rule pt-6">
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-ayun-muted">
            Location & health background
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium">Geographic area</label>
              <select
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={personalProfile.geographic_area}
                onChange={(e) => updateProfile({ geographic_area: e.target.value })}
              >
                {GEOGRAPHIC_AREAS.map((area) => (
                  <option key={area} value={area}>
                    {area}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">City / region (optional)</label>
              <input
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={personalProfile.location_detail}
                onChange={(e) => updateProfile({ location_detail: e.target.value })}
                placeholder="e.g. Zurich, Bernese Oberland"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="text-sm font-medium">General health status</label>
              <select
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={personalProfile.health_status}
                onChange={(e) => updateProfile({ health_status: e.target.value })}
              >
                {HEALTH_STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className="text-sm font-medium">Existing conditions / diagnoses</label>
              <textarea
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                rows={3}
                value={personalProfile.existing_conditions}
                onChange={(e) => updateProfile({ existing_conditions: e.target.value })}
                placeholder="e.g. Type 2 diabetes, hypertension, asthma — or leave blank if none"
              />
            </div>
          </div>
          <p className="mt-2 text-xs text-ayun-muted">
            Helps tailor exercise intensity, altitude exposure, and medical precautions.
          </p>
        </div>

        <TagPicker
          label="Health goals"
          options={GOAL_OPTIONS}
          selected={personalProfile.goals}
          onChange={(goals) => updateProfile({ goals })}
        />

        <div>
          <label className="text-sm font-medium">Activity level</label>
          <select
            className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
            value={personalProfile.activity_level}
            onChange={(e) => updateProfile({ activity_level: e.target.value })}
          >
            {ACTIVITY_LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </div>

        <TagPicker
          label="Sport preferences"
          options={SPORT_OPTIONS}
          selected={personalProfile.sport_prefs}
          onChange={(sport_prefs) => updateProfile({ sport_prefs })}
        />

        <div className="grid gap-4 sm:grid-cols-3">
          {(["stress", "depression", "optimism"] as const).map((field) => (
            <div key={field}>
              <label className="text-sm font-medium capitalize">{field}</label>
              <select
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={personalProfile[field]}
                onChange={(e) => updateProfile({ [field]: e.target.value })}
              >
                {WELLBEING_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>

        <div>
          <label className="text-sm font-medium">Injuries / limitations</label>
          <textarea
            className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
            rows={3}
            value={personalProfile.injuries}
            onChange={(e) => updateProfile({ injuries: e.target.value })}
          />
        </div>

        <div>
          <label className="text-sm font-medium">Additional notes</label>
          <textarea
            className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
            rows={3}
            value={personalProfile.notes}
            onChange={(e) => updateProfile({ notes: e.target.value })}
          />
        </div>

        {memberUser && (
          <p className="text-xs text-ayun-muted">
            Signed in as {memberUser.email}
            {memberUser.updated_at ? ` · Last saved ${new Date(memberUser.updated_at).toLocaleString()}` : ""}
          </p>
        )}

        {/* AI Memory — three-tier consent panel */}
        <div className="border-t border-rule pt-6">
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-ayun-muted">AI Memory & Privacy</p>
          <MemorySettingsPanel />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {saved && <p className="text-sm text-ayun-green">Profile saved.</p>}

        <div className="flex flex-wrap gap-3">
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Save profile
          </button>
          <button type="button" className="btn-secondary" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      </form>
    </Layout>
  );
}
