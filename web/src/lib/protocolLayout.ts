/**
 * Turns a card's flat action items into a protocol layout:
 * a short finding, a target, and labelled rows (Training, Cardio, …).
 */

export type ProtocolRow = { label: string; text: string };
export type ProtocolLayout = {
  findings: string[];
  target: string;
  notes: string[];
  footnote: string;
  rows: ProtocolRow[];
};

const ROW_RULES: Array<{ label: string; test: RegExp }> = [
  { label: "Follow-up", test: /\b(retest|recheck|re-?assess|monitor|consult|referral|physician|physiotherap|medical review|clinician|DEXA scan|screening|check-?up|doctor)/i },
  { label: "Nutrition", test: /\b(protein|diet|calori|eat|meal|fibre|fiber|carbohydrat|sugar|omega|vitamin|calcium|saturated fat|g\/kg|kcal)/i },
  { label: "Cardio", test: /\b(zone 2|cardio|endurance|aerobic|interval|hiit|vt2|vt1|walk|jog|running|cycling|swim)/i },
  { label: "Mobility", test: /\b(mobility|stretch|flexib|range of motion|yoga|pilates|balance|single-leg balance)/i },
  { label: "Training", test: /\b(strength|resistance|training|lift|overload|squat|deadlift|press|row|pull|push|curl|plyometric|jump|carries|sessions?|reps|sets)/i },
  { label: "Lifestyle", test: /\b(sleep|alcohol|stress|smok|recovery|hrv|rest)/i },
];

const FINDING = /^(your |weakness detected|elevated liver markers|genetic testing indicates|shoulder flexion below|hip flexion below)|\b(is|are) (borderline|above|below|in the|at or above)\b/i;
const TARGET = /^AYUN target/i;
/** Protocol lines that already carry their own label, e.g. "Frequency: 2–3 sessions". */
const OWN_LABEL = /^(Frequency|Intensity|Duration|Volume|Rest):\s*/i;
const FOOTNOTE = /^AYUN targets are set higher/i;
const NOTE = /double-check the measurement|framed as development|classes body fat as high/i;
const GOAL = /^target [^:]*:\s*/i;
/** "Dietary: …" under a Nutrition row just repeats the label. */
const REDUNDANT_PREFIX = /^(dietary|diet|nutrition|cardio|training):\s*/i;

function sentence(text: string): string {
  const t = text.trim().replace(/\s+/g, " ");
  if (!t) return t;
  const cap = t[0].toUpperCase() + t.slice(1);
  return /[.!?)]$/.test(cap) ? cap : `${cap}.`;
}

export function layoutProtocol(items: string[]): ProtocolLayout {
  const out: ProtocolLayout = { findings: [], target: "", notes: [], footnote: "", rows: [] };
  const rows = new Map<string, string[]>();

  for (const raw of items) {
    const item = raw.replace(/^[\s•-]+/, "").trim();
    if (!item) continue;
    if (FOOTNOTE.test(item)) out.footnote = sentence(item);
    else if (TARGET.test(item)) out.target = item.replace(/^AYUN target[^:]*:\s*/i, "");
    else if (NOTE.test(item)) {
      if (!/framed as development/i.test(item)) out.notes.push(sentence(item));
    } else if (FINDING.test(item)) out.findings.push(sentence(item.replace(/ — /g, ", ")));
    else if (OWN_LABEL.test(item)) {
      const label = item.match(OWN_LABEL)![1];
      const nice = label[0].toUpperCase() + label.slice(1).toLowerCase();
      rows.set(nice, [...(rows.get(nice) ?? []), sentence(item.replace(OWN_LABEL, ""))]);
    } else if (GOAL.test(item)) {
      rows.set("Long-term goal", [...(rows.get("Long-term goal") ?? []), sentence(item.replace(GOAL, ""))]);
    } else {
      const label = ROW_RULES.find((r) => r.test.test(item))?.label ?? "Guidance";
      rows.set(label, [...(rows.get(label) ?? []), sentence(item.replace(REDUNDANT_PREFIX, ""))]);
    }
  }

  // A personal "Your …" finding already says it; drop generic restatements.
  const personal = out.findings.filter((f) => /^your /i.test(f));
  if (personal.length) out.findings = personal;

  const order = [
    "Frequency", "Intensity", "Duration", "Volume", "Rest",
    "Training", "Cardio", "Mobility", "Nutrition", "Lifestyle", "Guidance", "Long-term goal", "Follow-up",
  ];
  out.rows = order.filter((l) => rows.has(l)).map((label) => ({ label, text: rows.get(label)!.join(" ") }));
  return out;
}
