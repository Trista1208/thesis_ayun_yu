/**
 * One rule for plan cards and protocols (matches backend rule_engine.ACTION_RATINGS):
 * excellent / good / average are fine; these ratings get an action plan.
 */
const ACTION_RATINGS = new Set(["below_average", "poor", "elevated", "high"]);

const PROTOCOL_PARAMS: Record<string, string[]> = {
  low_vo2max: ["Physiological::Vo2Max"],
  high_body_fat: [
    "Body Composition::Fat percentage",
    "Body Composition::Visceral Fat Index (raw value from DEXA)",
  ],
  low_bone_density: ["Body Composition::Bone mineral density"],
  low_strength_muscle: [
    "Physiological::Gripstrength Rechts",
    "Physiological::Gripstrength Links",
    "Body Composition::Muscle Mass Index (LMI)",
    "Body Composition::ALMI",
  ],
  elevated_hba1c: ["Blood Biomarkers::HbA1c"],
  possible_fatty_liver: [
    "Blood Biomarkers::ALAT",
    "Blood Biomarkers::ASAT",
    "Blood Biomarkers::GGT",
  ],
};

/** True when a measured marker is below average / elevated or worse. */
export function isConcerningRating(_parameter: string, rating: string): boolean {
  return ACTION_RATINGS.has(rating.toLowerCase());
}

export function hasProblemRating(
  ratings: Array<{ parameter: string; value: number | null; rating: string }>,
): boolean {
  return ratings.some(
    (row) => row.value != null && isConcerningRating(row.parameter, row.rating),
  );
}

export function protocolIsIndicated(
  key: string,
  ratings: Array<{ parameter: string; value: number | null; rating: string }>,
): boolean {
  const params = PROTOCOL_PARAMS[key];
  if (!params) return true;
  const relevant = ratings.filter((row) => params.includes(row.parameter) && row.value != null);
  if (!relevant.length) return false;

  return relevant.some((row) => ACTION_RATINGS.has(row.rating.toLowerCase()));
}

/** Gentle member-facing wording for a rating, relative to the AYUN standard. */
const RATING_LABELS: Record<string, string> = {
  excellent: "excellent",
  good: "good",
  average: "average",
  below_average: "a little below AYUN target",
  poor: "below AYUN target",
  elevated: "slightly above AYUN target",
  high: "above AYUN target",
  low: "very low",
};

export function ratingLabel(rating: string): string {
  return RATING_LABELS[rating.toLowerCase()] ?? rating.replace("_", " ");
}

export const AYUN_STANDARD_NOTE =
  "Ratings use the AYUN standard, which is set higher than general health norms. " +
  "A value outside the AYUN target range can still be normal by common standards.";

/** Where the rating bands come from, shown under the ratings on the plan page. */
export const AYUN_RANGES_SOURCE =
  "Sources: AYUN Physiological Testing reference table (fitness tests), " +
  "AYUN visceral fat reference (visceral fat) and AYUN One-Year Outcomes Overview (blood cut-offs).";
