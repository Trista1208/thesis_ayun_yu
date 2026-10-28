import { layoutProtocol, type ProtocolRow } from "../lib/protocolLayout";

/** Finding + target, then labelled protocol rows, then a quiet footnote. */
export function ProtocolSections({
  items,
  extraRows = [],
}: {
  items: string[];
  extraRows?: ProtocolRow[];
}) {
  const layout = layoutProtocol(items);
  const rows = [...layout.rows];
  for (const extra of extraRows) {
    const existing = rows.find((r) => r.label === extra.label);
    if (existing) existing.text = `${existing.text} ${extra.text}`;
    else rows.push(extra);
  }
  // Keep Follow-up last even when it comes from an extra row (stable sort keeps the rest).
  rows.sort((a, b) => Number(a.label === "Follow-up") - Number(b.label === "Follow-up"));

  return (
    <div className="mt-3 text-sm">
      {layout.findings.length || layout.target ? (
        <div className="rounded-lg bg-ayun-light/60 px-4 py-3">
          {layout.findings.map((f) => (
            <p key={f} className="text-ink">
              <span className="mr-2 text-[11px] font-semibold uppercase tracking-wider text-ayun-muted">Finding</span>
              {f}
            </p>
          ))}
          {layout.target ? (
            <p className="mt-1 text-ink">
              <span className="mr-2 text-[11px] font-semibold uppercase tracking-wider text-ayun-muted">AYUN target</span>
              {layout.target}
            </p>
          ) : null}
          {layout.notes.map((n) => (
            <p key={n} className={`mt-1 text-xs ${/double-check/i.test(n) ? "text-amber-800" : "text-ayun-muted"}`}>
              {n}
            </p>
          ))}
        </div>
      ) : null}

      {rows.length ? (
        <dl className="mt-3 divide-y divide-rule/70 border-y border-rule/70">
          {rows.map((row) => (
            <div key={row.label} className="grid gap-1 py-2.5 sm:grid-cols-[110px_1fr] sm:gap-4">
              <dt className="text-[11px] font-semibold uppercase tracking-wider text-ayun-dark sm:pt-0.5">
                {row.label}
              </dt>
              <dd className="leading-relaxed text-ayun-muted">{row.text}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {layout.footnote ? <p className="mt-2 text-xs italic text-ayun-muted">{layout.footnote}</p> : null}
    </div>
  );
}
