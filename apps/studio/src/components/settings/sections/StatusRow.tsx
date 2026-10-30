export type StatusValue = "reachable" | "unavailable" | "unknown" | "connected" | "offline" | "available";

export function StatusRow({
  label,
  status,
  reason,
}: {
  label: string;
  status: StatusValue;
  reason?: string | null;
}) {
  const stateClass =
    status === "unavailable" || status === "offline"
      ? "is-warn"
      : status === "unknown"
        ? "is-unknown"
        : "";
  return (
    <div className="settings__status-entry">
      <dt>{label}</dt>
      <dd>
        <span className={`status-dot ${stateClass}`} aria-hidden="true" />
        {status}{reason ? ` — ${reason}` : ""}
      </dd>
    </div>
  );
}
