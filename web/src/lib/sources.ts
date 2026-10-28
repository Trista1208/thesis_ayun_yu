import type { ProtocolRecommendation } from "./api";

export type SourceFamily = "protocol" | "member" | "web";

export type AnswerCitation = {
  index: string;
  marker?: string;
  title: string;
  family: SourceFamily;
  kind?: string;
  excerpt?: string;
  locator?: string;
  url?: string;
  origin?: string;
  used?: boolean | string;
  protocol?: ProtocolRecommendation | null;
};

export const SOURCE_META: Record<
  SourceFamily,
  { label: string; hint: string }
> = {
  protocol: {
    label: "AYUN protocol",
    hint: "Clinic templates, validated Q&A, and AYUN guidance",
  },
  member: {
    label: "From your data",
    hint: "Your own assessment, profile, and labs (not external evidence)",
  },
  web: {
    label: "From evidence · Evipedia",
    hint: "Forever Healthy evidence reviews on evipedia.ai",
  },
};

export function citationFamily(value: string, citations?: AnswerCitation[]): SourceFamily {
  const inner = value.replace(/^\[|\]$/g, "").trim();
  const lower = inner.toLowerCase();
  if (lower.startsWith("member") || lower.includes("your plan") || lower.includes("your data")) return "member";
  if (lower.startsWith("web") || /^e\d+$/i.test(inner)) return "web";
  if (lower.startsWith("protocol") || lower.includes("ayun")) return "protocol";
  const found = findCitation(inner, citations);
  if (found) return found.family;
  return "protocol";
}

export function findCitation(inner: string, citations?: AnswerCitation[]): AnswerCitation | undefined {
  if (!citations?.length) return undefined;
  const key = inner.replace(/^\[|\]$/g, "").trim().toLowerCase();
  return citations.find((cite) => {
    const index = String(cite.index || "").toLowerCase();
    const marker = String(cite.marker || "").replace(/^\[|\]$/g, "").toLowerCase();
    return index === key || marker === key;
  });
}

function shortChipTitle(title?: string): string {
  const clean = (title || "").trim();
  if (!clean) return "";
  const primary = clean.split(/\s+\/\s+/)[0].trim();
  return primary.length > 36 ? `${primary.slice(0, 34).trim()}…` : primary;
}

export function chipLabel(inner: string, cite?: AnswerCitation): string {
  const family = cite?.family || citationFamily(inner);
  const raw = inner.replace(/^\[|\]$/g, "").trim();
  if (family === "member") return "From your data";
  if (family === "web") {
    const title = shortChipTitle(cite?.title);
    if (title) return title;
    const n = raw.replace(/^web\s*|^e/i, "").trim();
    return n && /^\d+$/.test(n) ? `Evipedia ${n}` : "Evipedia";
  }
  if (cite?.kind === "validated-answer" || cite?.origin === "Validated Q&A") {
    return shortChipTitle(cite.title) || "Validated Q&A";
  }
  return shortChipTitle(cite?.title) || "AYUN protocol";
}

export function isCitationUsed(cite: AnswerCitation): boolean {
  return cite.used === true || cite.used === "1" || cite.used === "true";
}

export function normalizeCitations(raw?: Array<Partial<AnswerCitation> & { title: string }>): AnswerCitation[] {
  return (raw || []).map((cite, i) => {
    const kind = String(cite.kind || "");
    const family =
      cite.family ||
      (kind.includes("member") ? "member" : kind.includes("evipedia") || kind === "web" ? "web" : "protocol");
    return {
      index: String(cite.index || cite.marker || i + 1),
      marker: cite.marker || String(cite.index || ""),
      title: cite.title,
      family,
      kind,
      excerpt: cite.excerpt || "",
      locator: cite.locator || "",
      url: cite.url || "",
      origin: cite.origin || SOURCE_META[family].label,
      used: cite.used,
      protocol: cite.protocol || null,
    };
  });
}

export function scrubSourceBanners(content: string): string {
  return content
    .replace(/={8,}\s*/g, "")
    .replace(/\[?\s*MEMBER[\s_]+CONTEXT(?:\s*\([^)]*\))?\s*\]?:?/gi, "[Member]")
    .replace(/VALIDATED KNOWLEDGE CORPUS[^\n]*/gi, "")
    .replace(/--- This member's plan ---\s*/gi, "[Member] ")
    .replace(/--- End of member plan ---\s*/gi, "")
    .replace(/\$([^$]+)\$/g, (_, inner: string) =>
      inner.replace(/\\text\{([^}]+)\}/g, "$1").replace(/\\[,; ]/g, " ").replace(/\\/g, ""),
    )
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
