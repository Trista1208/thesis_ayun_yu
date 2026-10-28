import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useNavigate } from "react-router-dom";
import { Loader2, Upload } from "lucide-react";
import { Layout } from "../components/Layout";
import { RequireMember } from "../components/RequireMember";
import { PasteTextPanel } from "../components/PasteTextPanel";
import { useApp } from "../lib/context";
import {
  ASSESSMENT_SECTIONS,
  buildMemberPayload,
  DEMOGRAPHIC_FIELDS,
  labelForFieldKey,
  sectionsFromMemberData,
  type FieldDef,
} from "../lib/assessmentFields";
import { createAssessment, extractFile, fetchExtractStatus, updateMemberProfile } from "../lib/api";

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: FieldDef;
  value: unknown;
  onChange: (v: string | number | null) => void;
}) {
  const inputClass = "mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm";

  if (field.type === "select") {
    return (
      <select
        className={inputClass}
        value={String(value ?? field.options?.[0] ?? "")}
        onChange={(e) => onChange(e.target.value)}
      >
        {field.options!.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    );
  }

  return (
    <input
      type="number"
      step={field.step ?? "any"}
      min={field.min}
      max={field.max}
      className={inputClass}
      value={value != null && value !== "" ? String(value) : ""}
      onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
    />
  );
}

export function AssessmentPage() {
  const navigate = useNavigate();
  const {
    memberData,
    setMemberData,
    setAssessment,
    pseudonym,
    setPseudonym,
    setMemberName,
    memberName,
    personalProfile,
    setPersonalProfile,
    enabledSections,
    setEnabledSections,
    isMember,
    activeMode,
    isExpert,
  } = useApp();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [extractReady, setExtractReady] = useState<boolean | null>(null);
  const [extractModel, setExtractModel] = useState("gpt-4o");
  const [uploadMeta, setUploadMeta] = useState<{
    name: string;
    fields: string[];
    warnings: string[];
  } | null>(null);

  useEffect(() => {
    fetchExtractStatus()
      .then((s) => {
        setExtractReady(s.configured);
        setExtractModel(s.model);
      })
      .catch(() => setExtractReady(null));
  }, []);

  function updateField(key: string, value: string | number | null) {
    setMemberData({ ...memberData, [key]: value });
  }

  function toggleSection(id: string, on: boolean) {
    setEnabledSections((prev) => ({ ...prev, [id]: on }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const payload = buildMemberPayload(memberData, enabledSections);
      const profile = { ...personalProfile, name: memberName.trim() || personalProfile.name };
      const result = await createAssessment(payload, pseudonym, profile);
      setMemberData(payload);
      setAssessment(result);
      if (isMember) {
        await updateMemberProfile({
          display_name: memberName.trim() || undefined,
          pseudonym,
          member_data: payload,
          personal_profile: profile,
          enabled_sections: enabledSections,
        });
      }
      navigate("/plan");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assessment failed");
    } finally {
      setLoading(false);
    }
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    setUploadMeta(null);
    try {
      const data = await extractFile(file);
      if (data.ok && data.member_data && Object.keys(data.member_data).length > 0) {
        const merged = { ...memberData, ...data.member_data };
        setMemberData(merged);
        setEnabledSections((prev) => sectionsFromMemberData(data.member_data!, prev));
        const fields = Object.keys(data.member_data).map(labelForFieldKey);
        setUploadMeta({
          name: data.filename || file.name,
          fields,
          warnings: data.warnings || [],
        });
      } else {
        setError(data.warnings?.join(" ") || "Could not extract values from this file");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "File upload failed. Is the API running?");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  if (activeMode === "expert" && isExpert) {
    return <Navigate to="/expert/members" replace />;
  }

  return (
    <RequireMember
      title="Assessment"
      message="Sign in to run an assessment and save it to your profile."
    >
    <Layout>
      <p className="label-eyebrow mb-2">Member data</p>
      <h1 className="page-title mb-4">Assessment</h1>
      <p className="mb-8 max-w-2xl text-sm text-ayun-muted">
        Toggle each data section you have available. Upload reports or paste text to pre-fill sections
        automatically. Results are saved to your account.
      </p>

      <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <form onSubmit={onSubmit} className="card-panel space-y-6">
          <div className="space-y-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-ayun-muted">Demographics</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="text-sm font-medium">Display name (optional)</label>
                <input
                  className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                  value={memberName}
                  onChange={(e) => setMemberName(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium">Research pseudonym (optional)</label>
                <input
                  className="mt-1 w-full rounded-lg border border-rule px-3 py-2 text-sm"
                  value={pseudonym}
                  onChange={(e) => setPseudonym(e.target.value)}
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {DEMOGRAPHIC_FIELDS.map((field) => (
                <div key={field.key}>
                  <label className="text-sm font-medium">{field.label}</label>
                  <FieldInput
                    field={field}
                    value={memberData[field.key]}
                    onChange={(v) => updateField(field.key, v)}
                  />
                </div>
              ))}
            </div>
          </div>

          {ASSESSMENT_SECTIONS.map((section) => {
            const on = enabledSections[section.id] ?? false;
            return (
              <div key={section.id} className="border-t border-rule pt-5">
                <label className="flex cursor-pointer items-center justify-between gap-4">
                  <span className="text-sm font-semibold text-ink">{section.title}</span>
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-ayun-green"
                    checked={on}
                    onChange={(e) => toggleSection(section.id, e.target.checked)}
                  />
                </label>
                {on && (
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    {section.fields.map((field) => (
                      <div key={field.key} className={section.fields.length === 1 ? "sm:col-span-2" : ""}>
                        <label className="text-sm font-medium">{field.label}</label>
                        <FieldInput
                          field={field}
                          value={
                            field.type === "select" && memberData[field.key] == null
                              ? field.nullIf ?? field.options?.[0]
                              : memberData[field.key]
                          }
                          onChange={(v) => updateField(field.key, v)}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}

          {error && <p className="text-sm text-red-600">{error}</p>}
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Generate recommendations
          </button>
        </form>

        <div className="space-y-6 lg:sticky lg:top-20 lg:self-start">
        <div className="card-panel h-fit">
          <p className="label-eyebrow mb-3">Import report</p>
          <p className="mb-4 text-sm text-ayun-muted">
            {extractReady
              ? `Upload PDF, Word, or JSON. AI (${extractModel}) reads your report and pre-fills assessment values.`
              : extractReady === false
                ? "Report import needs a free model. Start Ollama on this computer, or add a Gemini key on a remote host."
                : "Upload PDF, Word, or JSON to pre-fill values from your clinic report."}
          </p>
          <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-rule bg-ayun-light/50 px-6 py-12 text-center transition hover:border-ayun-green/40">
            <Upload className="mb-2 h-8 w-8 text-ayun-green" />
            <span className="text-sm font-medium">{uploading ? "Extracting…" : "Choose file"}</span>
            <span className="mt-1 text-xs text-ayun-muted">PDF, Word, TXT, or JSON</span>
            <input type="file" className="hidden" accept=".pdf,.docx,.txt,.json" onChange={onFile} />
          </label>

          {uploadMeta && (
            <div className="mt-4 rounded-lg border border-ayun-green/30 bg-ayun-green/5 px-4 py-3 text-sm">
              <p className="font-medium text-ayun-dark">
                Uploaded: <span className="font-normal">{uploadMeta.name}</span>
              </p>
              <p className="mt-2 text-ayun-muted">
                {uploadMeta.fields.length} value{uploadMeta.fields.length === 1 ? "" : "s"} extracted
                {uploadMeta.fields.length > 0 ? ":" : "."}
              </p>
              {uploadMeta.fields.length > 0 && (
                <ul className="mt-2 list-inside list-disc text-xs text-ink">
                  {uploadMeta.fields.map((label) => (
                    <li key={label}>{label}</li>
                  ))}
                </ul>
              )}
              {uploadMeta.warnings.length > 0 && (
                <p className="mt-2 text-xs text-amber-800">{uploadMeta.warnings.join(" ")}</p>
              )}
              <p className="mt-2 text-xs text-ayun-muted">
                Missing fields? Enable the section and enter them manually, or try re-uploading.
              </p>
            </div>
          )}
        </div>

        <PasteTextPanel
          memberData={memberData}
          personalProfile={personalProfile}
          onApply={(member, profile) => {
            setMemberData({ ...memberData, ...member });
            setEnabledSections((prev) => sectionsFromMemberData(member, prev));
            setPersonalProfile({ ...personalProfile, ...profile });
          }}
        />
        </div>
      </div>
    </Layout>
    </RequireMember>
  );
}
