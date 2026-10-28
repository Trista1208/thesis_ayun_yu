export type PersonalProfile = {
  name: string;
  goals: string[];
  activity_level: string;
  sport_prefs: string[];
  geographic_area: string;
  location_detail: string;
  health_status: string;
  existing_conditions: string;
  smoking_status: string;
  alcohol_use: string;
  sleep_hours: string;
  diet: string;
  stress: string;
  depression: string;
  optimism: string;
  injuries: string;
  notes: string;
};

export const DEFAULT_PERSONAL_PROFILE: PersonalProfile = {
  name: "",
  goals: [],
  activity_level: "Moderately Active (2–4h/week)",
  sport_prefs: [],
  geographic_area: "Not specified",
  location_detail: "",
  health_status: "Not specified",
  existing_conditions: "",
  smoking_status: "Not specified",
  alcohol_use: "Not specified",
  sleep_hours: "Not specified",
  diet: "",
  stress: "Not assessed",
  depression: "Not assessed",
  optimism: "Not assessed",
  injuries: "",
  notes: "",
};

export const GEOGRAPHIC_AREAS = [
  "Not specified",
  "Switzerland — urban",
  "Switzerland — rural / alpine",
  "Central Europe",
  "Northern Europe",
  "Southern Europe",
  "United Kingdom & Ireland",
  "North America",
  "Asia-Pacific",
  "Other",
];

export const HEALTH_STATUS_OPTIONS = [
  "Not specified",
  "Good health — no known conditions",
  "Generally healthy — minor issues only",
  "Managing chronic condition(s)",
  "Recovering from illness or injury",
];

export const SMOKING_STATUS_OPTIONS = [
  "Not specified",
  "Non-smoker",
  "Former smoker",
  "Occasional smoker",
  "Daily smoker",
];

export const ALCOHOL_USE_OPTIONS = [
  "Not specified",
  "None",
  "Occasional (social)",
  "1–3 drinks / week",
  "4–7 drinks / week",
  "More than 7 drinks / week",
];

export const SLEEP_HOURS_OPTIONS = [
  "Not specified",
  "Less than 5 hours",
  "5–6 hours",
  "6–7 hours",
  "7–8 hours",
  "8–9 hours",
  "More than 9 hours",
];

export const GOAL_OPTIONS = [
  "Weight management",
  "Build muscle / hypertrophy",
  "Improve endurance & VO2max",
  "Reduce cardiovascular risk",
  "Improve bone health",
  "Reduce stress & mental wellbeing",
  "Improve sleep quality",
  "Longevity & disease prevention",
  "Improve mobility & flexibility",
  "Rehabilitation / recovery",
  "General wellbeing",
  "Athletic performance",
];

export const ACTIVITY_LEVELS = [
  "Not specified",
  "Sedentary (< 1h/week)",
  "Lightly Active (1–2h/week)",
  "Moderately Active (2–4h/week)",
  "Very Active (4–7h/week)",
  "Athlete (daily training)",
];

export const SPORT_OPTIONS = [
  "Running / jogging",
  "Cycling",
  "Swimming",
  "Hiking",
  "Gym / weight training",
  "CrossFit / HIIT",
  "Yoga / Pilates",
  "Team sports (football, basketball…)",
  "Tennis / racket sports",
  "Dancing",
  "Martial arts",
  "Rowing",
  "Climbing",
  "Golf",
];

export const WELLBEING_LEVELS = ["Not assessed", "Low", "Moderate", "High", "Very High"];

export function buildPersonalContext(
  profile: PersonalProfile,
  demographics?: {
    age?: unknown;
    gender?: unknown;
    height_cm?: unknown;
    weight_kg?: unknown;
  },
): string {
  const parts: string[] = [];
  if (profile.name.trim()) parts.push(`Member name: ${profile.name.trim()}`);
  if (demographics?.age != null && demographics.age !== "") {
    parts.push(`Age: ${demographics.age}`);
  }
  if (demographics?.gender) parts.push(`Gender: ${demographics.gender}`);
  if (demographics?.height_cm != null && demographics.height_cm !== "") {
    parts.push(`Height: ${demographics.height_cm} cm`);
  }
  if (demographics?.weight_kg != null && demographics.weight_kg !== "") {
    parts.push(`Weight: ${demographics.weight_kg} kg`);
  }
  const height = Number(demographics?.height_cm);
  const weight = Number(demographics?.weight_kg);
  if (Number.isFinite(height) && height > 0 && Number.isFinite(weight) && weight > 0) {
    const bmi = weight / (height / 100) ** 2;
    parts.push(`BMI: ${bmi.toFixed(1)} kg/m²`);
  }
  if (profile.geographic_area && profile.geographic_area !== "Not specified") {
    const location = profile.location_detail.trim()
      ? `${profile.geographic_area} (${profile.location_detail.trim()})`
      : profile.geographic_area;
    parts.push(`Geographic area: ${location}`);
  } else if (profile.location_detail.trim()) {
    parts.push(`Geographic area: ${profile.location_detail.trim()}`);
  }
  if (profile.health_status && profile.health_status !== "Not specified") {
    parts.push(`General health status: ${profile.health_status}`);
  }
  if (profile.existing_conditions.trim()) {
    parts.push(`Existing conditions / diagnoses: ${profile.existing_conditions.trim()}`);
  }
  if (profile.smoking_status && profile.smoking_status !== "Not specified") {
    parts.push(`Smoking status: ${profile.smoking_status}`);
  }
  if (profile.alcohol_use && profile.alcohol_use !== "Not specified") {
    parts.push(`Alcohol use: ${profile.alcohol_use}`);
  }
  if (profile.sleep_hours && profile.sleep_hours !== "Not specified") {
    parts.push(`Typical sleep: ${profile.sleep_hours}`);
  }
  if (profile.diet.trim()) {
    parts.push(`Diet / dietary notes: ${profile.diet.trim()}`);
  }
  if (profile.goals.length) parts.push(`Health goals: ${profile.goals.join(", ")}`);
  if (profile.activity_level && profile.activity_level !== "Not specified") {
    parts.push(`Current activity level: ${profile.activity_level}`);
  }
  if (profile.sport_prefs.length) parts.push(`Preferred activities: ${profile.sport_prefs.join(", ")}`);
  if (profile.stress && profile.stress !== "Not assessed") parts.push(`Stress level: ${profile.stress}`);
  if (profile.depression && profile.depression !== "Not assessed") {
    parts.push(`Depression level: ${profile.depression}`);
  }
  if (profile.optimism && profile.optimism !== "Not assessed") {
    parts.push(`Optimism level: ${profile.optimism}`);
  }
  if (profile.injuries.trim()) parts.push(`Injuries / limitations: ${profile.injuries.trim()}`);
  if (profile.notes.trim()) parts.push(`Additional notes: ${profile.notes.trim()}`);
  return parts.join("\n");
}

export type PrivacySettings = {
  memory_enabled: boolean;
  memory_retention_days: number;
  consented_at?: string;
};

export type AppUser = {
  id: string;
  email: string;
  display_name: string;
  pseudonym: string;
  member_data: Record<string, unknown>;
  personal_profile: PersonalProfile;
  enabled_sections: Record<string, boolean>;
  privacy_settings?: PrivacySettings;
  created_at: string;
  updated_at: string;
};
