export type FieldDef = {
  key: string;
  label: string;
  type: "number" | "select";
  min?: number;
  max?: number;
  step?: number | "any";
  options?: readonly string[];
  /** When select value equals this, store null (e.g. genetic "None"). */
  nullIf?: string;
};

export type SectionDef = {
  id: string;
  title: string;
  description?: string;
  fields: FieldDef[];
};

export const DEMOGRAPHIC_FIELDS: FieldDef[] = [
  { key: "Demographic::Age", label: "Age", type: "number", min: 18, max: 99, step: 1 },
  {
    key: "Demographic::Sex",
    label: "Sex",
    type: "select",
    options: ["Male", "Female"],
  },
  {
    key: "Demographic::Height (cm)",
    label: "Height (cm)",
    type: "number",
    min: 100,
    max: 250,
    step: 1,
  },
  {
    key: "Demographic::Weight (kg)",
    label: "Weight (kg)",
    type: "number",
    min: 30,
    max: 300,
    step: 0.1,
  },
];

export const ASSESSMENT_SECTIONS: SectionDef[] = [
  {
    id: "dexa",
    title: "Body Composition (DEXA)",
    fields: [
      {
        key: "Body Composition::Muscle Mass Index (LMI)",
        label: "Muscle Mass Index – LMI (kg/m²)",
        type: "number",
        min: 0,
        max: 40,
        step: 0.1,
      },
      {
        key: "Body Composition::ALMI",
        label: "ALMI (kg/m²)",
        type: "number",
        min: 0,
        max: 15,
        step: 0.1,
      },
      {
        key: "Body Composition::Fat percentage",
        label: "Body Fat (%)",
        type: "number",
        min: 0,
        max: 60,
        step: 0.1,
      },
      {
        key: "Body Composition::Visceral Fat Index (raw value from DEXA)",
        label: "Visceral Fat Volume (cm³)",
        type: "number",
        min: 0,
        max: 20000,
        step: "any",
      },
      {
        key: "Body Composition::Bone mineral density",
        label: "Bone Density T/Z-score",
        type: "number",
        min: -4,
        max: 4,
        step: 0.1,
      },
    ],
  },
  {
    id: "strength",
    title: "Upper Body Strength",
    fields: [
      {
        key: "Physiological::Biceps Strength Rechts",
        label: "Biceps Strength Right (kg)",
        type: "number",
        min: 0,
        max: 60,
        step: 0.1,
      },
      {
        key: "Physiological::Biceps Strength Links",
        label: "Biceps Strength Left (kg)",
        type: "number",
        min: 0,
        max: 60,
        step: 0.1,
      },
      {
        key: "Physiological::Triceps Strength Rechts",
        label: "Triceps Strength Right (kg)",
        type: "number",
        min: 0,
        max: 60,
        step: 0.1,
      },
      {
        key: "Physiological::Triceps Strength Links",
        label: "Triceps Strength Left (kg)",
        type: "number",
        min: 0,
        max: 60,
        step: 0.1,
      },
      {
        key: "Physiological::Gripstrength Rechts",
        label: "Handgrip Right (kg)",
        type: "number",
        min: 0,
        max: 100,
        step: 0.1,
      },
      {
        key: "Physiological::Gripstrength Links",
        label: "Handgrip Left (kg)",
        type: "number",
        min: 0,
        max: 100,
        step: 0.1,
      },
    ],
  },
  {
    id: "lower",
    title: "Lower Body & Stability",
    fields: [
      {
        key: "Physiological::Counter movement jump",
        label: "Counter Movement Jump (cm)",
        type: "number",
        min: 0,
        max: 80,
        step: 0.1,
      },
      {
        key: "Physiological::Y-Balance Composite Score",
        label: "Y-Balance Composite Score (%)",
        type: "number",
        min: 0,
        max: 130,
        step: 0.1,
      },
    ],
  },
  {
    id: "cpet",
    title: "VO2max & CPET",
    fields: [
      {
        key: "Physiological::Vo2Max",
        label: "VO2max (ml/min/kg)",
        type: "number",
        min: 0,
        max: 90,
        step: 0.1,
      },
      {
        key: "Physiological::HR max",
        label: "HR max (bpm)",
        type: "number",
        min: 0,
        max: 220,
        step: 1,
      },
      {
        key: "Physiological::HR at VT1",
        label: "HR at VT1 (bpm)",
        type: "number",
        min: 0,
        max: 220,
        step: 1,
      },
      {
        key: "Physiological::HR at VT2",
        label: "HR at VT2 (bpm)",
        type: "number",
        min: 0,
        max: 220,
        step: 1,
      },
    ],
  },
  {
    id: "rom",
    title: "Range of Motion",
    fields: [
      {
        key: "Physiological::Shoulder Flexion Right",
        label: "Shoulder Flexion Right (°)",
        type: "number",
        min: 0,
        max: 200,
        step: 1,
      },
      {
        key: "Physiological::Shoulder Flexion Left",
        label: "Shoulder Flexion Left (°)",
        type: "number",
        min: 0,
        max: 200,
        step: 1,
      },
      {
        key: "Physiological::Hip Flexion Right",
        label: "Hip Flexion Right (°)",
        type: "number",
        min: 0,
        max: 160,
        step: 1,
      },
      {
        key: "Physiological::Hip Flexion Left",
        label: "Hip Flexion Left (°)",
        type: "number",
        min: 0,
        max: 160,
        step: 1,
      },
    ],
  },
  {
    id: "blood",
    title: "Blood Biomarkers",
    fields: [
      {
        key: "Blood Biomarkers::LDL",
        label: "LDL Cholesterol (mmol/L)",
        type: "number",
        min: 0,
        max: 15,
        step: 0.1,
      },
      {
        key: "Blood Biomarkers::HbA1c",
        label: "HbA1c (%)",
        type: "number",
        min: 0,
        max: 15,
        step: 0.1,
      },
      {
        key: "Blood Biomarkers::ALAT",
        label: "ALAT / ALT (U/L)",
        type: "number",
        min: 0,
        max: 500,
        step: 1,
      },
      {
        key: "Blood Biomarkers::ASAT",
        label: "ASAT / AST (U/L)",
        type: "number",
        min: 0,
        max: 500,
        step: 1,
      },
      {
        key: "Blood Biomarkers::GGT",
        label: "GGT (U/L)",
        type: "number",
        min: 0,
        max: 500,
        step: 1,
      },
    ],
  },
  {
    id: "genetics",
    title: "Genetic Testing",
    fields: [
      {
        key: "Genetics::Bone Health Risk",
        label: "Bone Health Genetic Risk",
        type: "select",
        options: ["None", "Low", "Moderate", "High"],
        nullIf: "None",
      },
    ],
  },
];

/** Human-readable label for a member_data / rule-engine key. */
export function labelForFieldKey(key: string): string {
  const demo = DEMOGRAPHIC_FIELDS.find((f) => f.key === key);
  if (demo) return demo.label;
  for (const section of ASSESSMENT_SECTIONS) {
    const field = section.fields.find((f) => f.key === key);
    if (field) return field.label;
  }
  const part = key.split("::").pop();
  return part || key;
}

export function sectionFieldKeys(section: SectionDef): string[] {
  return section.fields.map((f) => f.key);
}

export function allSectionKeys(): string[] {
  return ASSESSMENT_SECTIONS.flatMap((s) => sectionFieldKeys(s));
}

/** Build payload matching Streamlit: disabled sections → null. */
export function buildMemberPayload(
  memberData: Record<string, unknown>,
  enabledSections: Record<string, boolean>,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    "Demographic::Age": memberData["Demographic::Age"],
    "Demographic::Sex": memberData["Demographic::Sex"],
    "Demographic::Height (cm)": memberData["Demographic::Height (cm)"],
    "Demographic::Weight (kg)": memberData["Demographic::Weight (kg)"],
  };

  for (const section of ASSESSMENT_SECTIONS) {
    const on = enabledSections[section.id] ?? false;
    for (const field of section.fields) {
      if (!on) {
        payload[field.key] = null;
        continue;
      }
      const raw = memberData[field.key];
      if (field.type === "select" && field.nullIf && raw === field.nullIf) {
        payload[field.key] = null;
      } else {
        payload[field.key] = raw ?? null;
      }
    }
  }

  return payload;
}

/** Auto-enable sections when imported data contains values. */
export function sectionsFromMemberData(
  data: Record<string, unknown>,
  current: Record<string, boolean>,
): Record<string, boolean> {
  const next = { ...current };
  for (const section of ASSESSMENT_SECTIONS) {
    if (section.fields.some((f) => data[f.key] != null && data[f.key] !== "")) {
      next[section.id] = true;
    }
  }
  return next;
}

export const DEFAULT_ENABLED_SECTIONS: Record<string, boolean> = Object.fromEntries(
  ASSESSMENT_SECTIONS.map((s) => [s.id, false]),
);
