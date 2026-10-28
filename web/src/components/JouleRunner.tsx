/** Official Joule runner, yellow tile removed. */

type MarkProps = {
  size?: number;
  className?: string;
  title?: string;
};

export function JouleMark({ size = 18, className = "", title }: MarkProps) {
  return (
    <img
      src="/joule-runner.png"
      alt={title || ""}
      width={size}
      height={size}
      className={`object-contain ${className}`.trim()}
      role={title ? "img" : "presentation"}
      aria-hidden={title ? undefined : true}
    />
  );
}

export function JouleLeap({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`joule-jog${compact ? " joule-jog-compact" : ""}`} aria-hidden="true">
      <img src="/joule-runner.png" alt="" />
    </span>
  );
}

export function JouleThinking({ label = "Joule is thinking…" }: { label?: string }) {
  return (
    <div className="joule-thinking" role="status" aria-live="polite">
      <JouleLeap />
      <span>{label}</span>
    </div>
  );
}
