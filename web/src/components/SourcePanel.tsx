import { BookOpen, ChevronDown, MapPin } from "lucide-react";
import { ProtocolCard } from "./ProtocolCard";
import { SOURCE_META, type AnswerCitation, type SourceFamily } from "../lib/sources";

export function SourceChip({
  family,
  label,
}: {
  family: SourceFamily;
  label: string;
}) {
  return <span className={`source-chip is-${family}`}>{label}</span>;
}

export function SourcePanel({ citations }: { citations: AnswerCitation[] }) {
  const protocols = citations.filter((cite) => cite.family === "protocol" && cite.protocol);
  const web = citations.filter((cite) => cite.family === "web" && cite.url);
  if (!protocols.length && !web.length) return null;

  return (
    <div className="source-panel">
      <p className="label-eyebrow">Open the protocol</p>
      {protocols.length ? (
        <ul className="source-list">
          {protocols.map((cite) => (
            <li key={`${cite.family}-${cite.index}-${cite.title}`}>
              <details className={`source-card is-${cite.family} source-card-openable`}>
                <summary>
                  <span className="source-summary-row">
                    <span className={`source-card-type is-${cite.family}`}>
                      <BookOpen className="h-3.5 w-3.5" />
                      {SOURCE_META.protocol.label}
                    </span>
                    <strong>{cite.title}</strong>
                    <span className="source-open-hint">
                      Read protocol
                      <ChevronDown className="h-3.5 w-3.5" />
                    </span>
                  </span>
                </summary>
                <div className="source-protocol">
                  <ProtocolCard protocol={cite.protocol!} compact />
                </div>
              </details>
            </li>
          ))}
        </ul>
      ) : null}
      {web.length ? (
        <ul className="source-list mt-3">
          {web.map((cite) => (
            <li key={`${cite.family}-${cite.index}-${cite.title}`}>
              <a className="source-card is-web" href={cite.url} target="_blank" rel="noreferrer">
                <span className="source-card-type is-web">
                  <MapPin className="h-3.5 w-3.5" />
                  {SOURCE_META.web.label}
                </span>
                <strong>{cite.title}</strong>
                {cite.locator ? (
                  <span className="source-locator">
                    <MapPin className="h-3 w-3" />
                    {cite.locator}
                  </span>
                ) : null}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
