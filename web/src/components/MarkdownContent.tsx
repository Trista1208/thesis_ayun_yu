import type { ReactNode } from "react";
import { SourceChip } from "./SourcePanel";
import {
  chipLabel,
  citationFamily,
  findCitation,
  scrubSourceBanners,
  type AnswerCitation,
} from "../lib/sources";

type Props = {
  content: string;
  className?: string;
  citations?: AnswerCitation[];
};

function citationChip(inner: string, citations: AnswerCitation[] | undefined, key: number) {
  const cite = findCitation(inner, citations);
  const family = citationFamily(inner, citations);
  return <SourceChip key={key} family={family} label={chipLabel(inner, cite)} />;
}

function renderInline(text: string, citations?: AnswerCitation[]): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[(?:\d+(?:\s*,\s*\d+)+|\d+|Member(?:\s+Context)?|MEMBER(?:\s+CONTEXT)?|Protocol(?:\s+\d+)?|Web\s*\d+|E\d+|AYUN(?:\s+(?:clinic|protocol))?|Your plan)\])/gi;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    const token = match[0];
    if (token.startsWith("**")) {
      nodes.push(
        <strong key={key++} className="font-semibold text-ink">
          {token.slice(2, -2)}
        </strong>,
      );
    } else if (token.startsWith("*")) {
      nodes.push(
        <em key={key++} className="italic">
          {token.slice(1, -1)}
        </em>,
      );
    } else if (token.startsWith("`")) {
      nodes.push(
        <code key={key++} className="rounded bg-white/70 px-1 py-0.5 text-[0.85em]">
          {token.slice(1, -1)}
        </code>,
      );
    } else {
      const inner = token.slice(1, -1);
      if (/^\d+(?:\s*,\s*\d+)+$/.test(inner)) {
        inner.split(/\s*,\s*/).forEach((part) => {
          nodes.push(citationChip(part, citations, key++));
        });
      } else {
        nodes.push(citationChip(inner, citations, key++));
      }
    }
    last = match.index + token.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function inlineMarkdown(text: string, citations?: AnswerCitation[]): ReactNode[] {
  return renderInline(text, citations);
}

function renderBlock(
  lines: string[],
  start: number,
  citations?: AnswerCitation[],
): { node: ReactNode; next: number } {
  const line = lines[start] ?? "";

  if (/^---+$/.test(line.trim())) {
    return { node: <hr key={start} className="my-3 border-rule" />, next: start + 1 };
  }

  const heading = /^(#{1,3})\s+(.+)$/.exec(line);
  if (heading) {
    const level = heading[1].length;
    const text = heading[2].replace(/\*\*/g, "").trim();
    const cls =
      level === 1
        ? "mt-3 mb-1.5 font-serif text-base font-semibold text-ink first:mt-0"
        : level === 2
          ? "mt-3 mb-1.5 font-serif text-[0.95rem] font-semibold text-ink first:mt-0"
          : "mt-2.5 mb-1 text-sm font-semibold text-ink first:mt-0";
    return {
      node: (
        <p key={start} className={cls}>
          {inlineMarkdown(text, citations)}
        </p>
      ),
      next: start + 1,
    };
  }

  if (/^\s*[-*]\s+/.test(line)) {
    const items: string[] = [];
    let i = start;
    while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
      items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
      i += 1;
    }
    return {
      node: (
        <ul key={start} className="my-2 list-disc space-y-1.5 pl-5">
          {items.map((item, idx) => (
            <li key={idx} className="leading-relaxed">
              {inlineMarkdown(item, citations)}
            </li>
          ))}
        </ul>
      ),
      next: i,
    };
  }

  if (/^\s*\d+\.\s+/.test(line)) {
    const items: string[] = [];
    let i = start;
    while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
      items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
      i += 1;
    }
    return {
      node: (
        <ol key={start} className="my-2 list-decimal space-y-1.5 pl-5">
          {items.map((item, idx) => (
            <li key={idx} className="leading-relaxed">
              {inlineMarkdown(item, citations)}
            </li>
          ))}
        </ol>
      ),
      next: i,
    };
  }

  if (!line.trim()) {
    return { node: null, next: start + 1 };
  }

  const para: string[] = [line];
  let i = start + 1;
  while (i < lines.length && lines[i].trim() && !/^(#{1,3}\s|[-*]\s|\d+\.\s|---+$)/.test(lines[i])) {
    para.push(lines[i]);
    i += 1;
  }
  return {
    node: (
      <p key={start} className="my-1.5 leading-relaxed first:mt-0">
        {inlineMarkdown(para.join(" "), citations)}
      </p>
    ),
    next: i,
  };
}

export function MarkdownContent({ content, className = "", citations }: Props) {
  const cleaned = scrubSourceBanners(content);
  if (!cleaned) return null;
  const lines = cleaned.replace(/\r\n/g, "\n").split("\n");
  const nodes: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const { node, next } = renderBlock(lines, i, citations);
    if (node) nodes.push(node);
    i = next;
  }
  return <div className={`text-sm text-ink ${className}`}>{nodes}</div>;
}
