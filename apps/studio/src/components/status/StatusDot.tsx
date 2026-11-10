export type StatusTone = "ok" | "warn" | "unknown" | "busy" | "ready";

// The base `.status-dot` rule is already green; only non-ok tones need a modifier.
const MODIFIER: Record<StatusTone, string> = {
  ok: "",
  warn: " is-warn",
  unknown: " is-unknown",
  busy: " is-busy",
  ready: " is-ready",
};

export function StatusDot({ tone, label }: { tone: StatusTone; label?: string }) {
  return (
    <span
      className={`status-dot${MODIFIER[tone]}`}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    />
  );
}
