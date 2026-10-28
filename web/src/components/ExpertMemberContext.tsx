import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { labelForFieldKey } from "../lib/assessmentFields";
import {
  ACTIVITY_LEVELS,
  ALCOHOL_USE_OPTIONS,
  GEOGRAPHIC_AREAS,
  GOAL_OPTIONS,
  HEALTH_STATUS_OPTIONS,
  SLEEP_HOURS_OPTIONS,
  SMOKING_STATUS_OPTIONS,
  type PersonalProfile,
} from "../lib/profileFields";

type Props = {
  memberName: string;
  email?: string;
  pseudonym?: string;
  personalProfile: PersonalProfile;
  memberData: Record<string, unknown>;
  editable?: boolean;
  compact?: boolean;
  saving?: boolean;
  onSave?: (payload: {
    member_name?: string;
    personal_profile: PersonalProfile;
  }) => Promise<void>;
};

function CheckupResults({ memberData }: { memberData: Record<string, unknown> }) {
  const filled = Object.entries(memberData).filter(([, v]) => v != null && v !== "");
  if (!filled.length) {
    return <p className="text-sm text-ayun-muted">No checkup values recorded.</p>;
  }
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {filled.map(([key, value]) => (
        <div key={key} className="rounded-lg border border-rule px-3 py-2 text-sm">
          <p className="text-xs text-ayun-muted">{labelForFieldKey(key)}</p>
          <p className="font-medium text-ink">{String(value)}</p>
        </div>
      ))}
    </div>
  );
}

export function ExpertMemberContext({
  memberName,
  email,
  pseudonym,
  personalProfile,
  memberData,
  editable = false,
  compact = false,
  saving = false,
  onSave,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState(memberName);
  const [draftProfile, setDraftProfile] = useState<PersonalProfile>(personalProfile);
  const [message, setMessage] = useState("");

  useEffect(() => {
    setDraftName(memberName);
    setDraftProfile(personalProfile);
  }, [memberName, personalProfile]);

  async function handleSave() {
    if (!onSave) return;
    setMessage("");
    try {
      await onSave({
        member_name: draftName.trim() || undefined,
        personal_profile: draftProfile,
      });
      setEditing(false);
      setMessage("Profile saved.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not save profile");
    }
  }

  return (
    <div className={compact ? "space-y-4" : "space-y-6"}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className={`font-serif text-ink ${compact ? "text-base" : "text-xl"}`}>
            {compact ? memberName || personalProfile.name || "Member profile" : "Member context"}
          </h3>
          <p className="mt-1 text-sm text-ayun-muted">
            {email ? `${email} · ` : ""}
            {pseudonym ? `Pseudonym ${pseudonym}` : "No pseudonym"}
          </p>
        </div>
        {editable && onSave ? (
          <div className="flex gap-2">
            {editing ? (
              <>
                <button
                  type="button"
                  className="btn-secondary !px-3 !py-1.5 !text-xs"
                  disabled={saving}
                  onClick={() => {
                    setEditing(false);
                    setDraftName(memberName);
                    setDraftProfile(personalProfile);
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn-primary !px-3 !py-1.5 !text-xs"
                  disabled={saving}
                  onClick={handleSave}
                >
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save profile"}
                </button>
              </>
            ) : (
              <button
                type="button"
                className="btn-secondary !px-3 !py-1.5 !text-xs"
                onClick={() => setEditing(true)}
              >
                Edit profile
              </button>
            )}
          </div>
        ) : null}
      </div>

      {message ? (
        <p className="rounded-lg bg-ayun-light px-3 py-2 text-sm text-ayun-dark">{message}</p>
      ) : null}

      <section>
        <p className="label-eyebrow mb-3">Personal profile</p>
        {editing ? (
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Display name</label>
              <input
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={draftName}
                onChange={(e) => setDraftName(e.target.value)}
              />
            </div>
            <div>
              <label className="text-sm font-medium">Activity level</label>
              <select
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={draftProfile.activity_level}
                onChange={(e) =>
                  setDraftProfile({ ...draftProfile, activity_level: e.target.value })
                }
              >
                {ACTIVITY_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="text-sm font-medium">Geographic area</label>
                <select
                  className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                  value={draftProfile.geographic_area}
                  onChange={(e) =>
                    setDraftProfile({ ...draftProfile, geographic_area: e.target.value })
                  }
                >
                  {GEOGRAPHIC_AREAS.map((area) => (
                    <option key={area} value={area}>
                      {area}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">City / region</label>
                <input
                  className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                  value={draftProfile.location_detail}
                  onChange={(e) =>
                    setDraftProfile({ ...draftProfile, location_detail: e.target.value })
                  }
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">General health status</label>
              <select
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                value={draftProfile.health_status}
                onChange={(e) =>
                  setDraftProfile({ ...draftProfile, health_status: e.target.value })
                }
              >
                {HEALTH_STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Existing conditions / diagnoses</label>
              <textarea
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                rows={3}
                value={draftProfile.existing_conditions}
                onChange={(e) =>
                  setDraftProfile({ ...draftProfile, existing_conditions: e.target.value })
                }
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="text-sm font-medium">Smoking status</label>
                <select
                  className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                  value={draftProfile.smoking_status || "Not specified"}
                  onChange={(e) =>
                    setDraftProfile({ ...draftProfile, smoking_status: e.target.value })
                  }
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
                  value={draftProfile.alcohol_use || "Not specified"}
                  onChange={(e) =>
                    setDraftProfile({ ...draftProfile, alcohol_use: e.target.value })
                  }
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
                  value={draftProfile.sleep_hours || "Not specified"}
                  onChange={(e) =>
                    setDraftProfile({ ...draftProfile, sleep_hours: e.target.value })
                  }
                >
                  {SLEEP_HOURS_OPTIONS.map((hours) => (
                    <option key={hours} value={hours}>
                      {hours}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Diet / dietary notes</label>
              <textarea
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                rows={3}
                value={draftProfile.diet || ""}
                onChange={(e) => setDraftProfile({ ...draftProfile, diet: e.target.value })}
                placeholder="e.g. Vegetarian, gluten-free, low carb"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Goals</label>
              <div className="mt-2 flex flex-wrap gap-2">
                {GOAL_OPTIONS.map((goal) => {
                  const selected = draftProfile.goals.includes(goal);
                  return (
                    <button
                      key={goal}
                      type="button"
                      className={`rounded-full border px-3 py-1 text-xs transition ${
                        selected
                          ? "border-ayun-green bg-ayun-green/10 text-ayun-dark"
                          : "border-rule text-ayun-muted hover:border-ayun-green/40"
                      }`}
                      onClick={() =>
                        setDraftProfile({
                          ...draftProfile,
                          goals: selected
                            ? draftProfile.goals.filter((g) => g !== goal)
                            : [...draftProfile.goals, goal],
                        })
                      }
                    >
                      {goal}
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Injuries / limitations</label>
              <textarea
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                rows={3}
                value={draftProfile.injuries}
                onChange={(e) => setDraftProfile({ ...draftProfile, injuries: e.target.value })}
              />
            </div>
            <div>
              <label className="text-sm font-medium">Clinician notes (member profile)</label>
              <textarea
                className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                rows={3}
                value={draftProfile.notes}
                onChange={(e) => setDraftProfile({ ...draftProfile, notes: e.target.value })}
              />
            </div>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ["Name", memberName || personalProfile.name || "—"],
              ["Age", memberData["Demographic::Age"] != null ? String(memberData["Demographic::Age"]) : "—"],
              ["Gender", memberData["Demographic::Sex"] ? String(memberData["Demographic::Sex"]) : "—"],
              [
                "Height",
                memberData["Demographic::Height (cm)"] != null
                  ? `${memberData["Demographic::Height (cm)"]} cm`
                  : "—",
              ],
              [
                "Weight",
                memberData["Demographic::Weight (kg)"] != null
                  ? `${memberData["Demographic::Weight (kg)"]} kg`
                  : "—",
              ],
              [
                "Geographic area",
                personalProfile.geographic_area && personalProfile.geographic_area !== "Not specified"
                  ? personalProfile.location_detail?.trim()
                    ? `${personalProfile.geographic_area} (${personalProfile.location_detail.trim()})`
                    : personalProfile.geographic_area
                  : personalProfile.location_detail?.trim() || "—",
              ],
              [
                "Health status",
                personalProfile.health_status && personalProfile.health_status !== "Not specified"
                  ? personalProfile.health_status
                  : "—",
              ],
              ["Existing conditions", personalProfile.existing_conditions?.trim() || "—"],
              [
                "Smoking",
                personalProfile.smoking_status && personalProfile.smoking_status !== "Not specified"
                  ? personalProfile.smoking_status
                  : "—",
              ],
              [
                "Alcohol",
                personalProfile.alcohol_use && personalProfile.alcohol_use !== "Not specified"
                  ? personalProfile.alcohol_use
                  : "—",
              ],
              [
                "Typical sleep",
                personalProfile.sleep_hours && personalProfile.sleep_hours !== "Not specified"
                  ? personalProfile.sleep_hours
                  : "—",
              ],
              ["Diet", personalProfile.diet?.trim() || "—"],
              ["Goals", personalProfile.goals?.length ? personalProfile.goals.join(", ") : "—"],
              ["Activity level", personalProfile.activity_level || "—"],
              ["Sports", personalProfile.sport_prefs?.length ? personalProfile.sport_prefs.join(", ") : "—"],
              ["Stress", personalProfile.stress || "—"],
              ["Injuries / limitations", personalProfile.injuries?.trim() || "—"],
              ["Notes", personalProfile.notes?.trim() || "—"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg bg-ayun-light/50 px-3 py-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-ayun-muted">{label}</p>
                <p className="mt-1 text-sm text-ink">{value}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <p className="label-eyebrow mb-3">Checkup results</p>
        <CheckupResults memberData={memberData} />
      </section>
    </div>
  );
}
