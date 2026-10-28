import type { ProtocolRecommendation } from "../lib/api";
import { ProtocolSections } from "./ProtocolSections";

export function ProtocolCard({
  protocol,
  compact = false,
}: {
  protocol: ProtocolRecommendation;
  compact?: boolean;
}) {
  const heading = compact ? "font-serif text-lg text-ink" : "font-serif text-xl text-ink";
  const fromAyun = Boolean(protocol.source) && protocol.source.startsWith("AYUN");
  return (
    <article className={compact ? "text-left" : "card-panel border-l-4 border-l-ayun-dark"}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-ayun-light px-2.5 py-0.5 text-xs font-semibold text-ayun-dark">
          {!fromAyun
            ? "Evidence-based protocol"
            : protocol.category === "AYUN training template"
              ? "AYUN training template"
              : "AYUN scientist protocol"}
        </span>
      </div>
      <h3 className={heading}>{protocol.title}</h3>
      {protocol.description ? (
        <p className="mt-1 text-sm text-ayun-muted">{protocol.description}</p>
      ) : null}
      {protocol.action_items?.length || protocol.nutrition_focus?.length || protocol.recheck_interval ? (
        <ProtocolSections
          items={protocol.action_items ?? []}
          extraRows={[
            ...(protocol.nutrition_focus?.length
              ? [{ label: "Nutrition", text: protocol.nutrition_focus.map((n) => (/[.!?]$/.test(n) ? n : `${n}.`)).join(" ") }]
              : []),
            ...(protocol.recheck_interval ? [{ label: "Follow-up", text: `Recheck ${protocol.recheck_interval}.` }] : []),
          ]}
        />
      ) : null}
      {protocol.templates?.length ? (
        <div className="mt-4 rounded-xl bg-ayun-light/60 p-3">
          <p className="label-eyebrow mb-2">Matched workout templates</p>
          <div className="space-y-2">
            {protocol.templates.map((template) => (
              <div key={template.key}>
                <p className="text-sm font-semibold text-ink">{template.title}</p>
                {template.summary ? (
                  <p className="text-xs leading-relaxed text-ayun-muted">{template.summary}</p>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {protocol.source ? (
        <p className="mt-3 text-xs text-ayun-muted">
          <span className="font-semibold">Source: </span>
          {protocol.source}
        </p>
      ) : null}
    </article>
  );
}
