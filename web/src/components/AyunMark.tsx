type MarkProps = {
  size?: number;
  className?: string;
  title?: string;
};

export function AyunMark({ size = 24, className = "", title }: MarkProps) {
  return (
    <img
      src="/ayun-icon.png"
      alt={title || ""}
      width={size}
      height={size}
      className={`object-contain ${className}`.trim()}
      role={title ? "img" : "presentation"}
      aria-hidden={title ? undefined : true}
    />
  );
}

type ChatIconProps = {
  size?: number;
  className?: string;
  title?: string;
};

export function AyunChatIcon({ size = 28, className = "", title = "Joule for AYUN" }: ChatIconProps) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full bg-ayun-dark shadow-sm ${className}`.trim()}
      style={{ width: size, height: size }}
      title={title || undefined}
      role={title ? "img" : "presentation"}
      aria-label={title || undefined}
      aria-hidden={title ? undefined : true}
    >
      <img src="/ayun-icon.png" alt="" className="h-[58%] w-[58%] object-contain brightness-0 invert" />
    </span>
  );
}
