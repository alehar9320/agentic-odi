import { useUpdateService, useUpdateSnapshot } from "../../../updater";

/**
 * Updates in Settings: the current state and at most one action.
 * The banner handles urgent restart flows elsewhere; this row is the
 * configuration-facing summary.
 */
export function UpdatesSection() {
  const service = useUpdateService();
  const snapshot = useUpdateSnapshot();
  const supported = snapshot.phase !== "unsupported";
  const busy =
    snapshot.phase === "checking" ||
    snapshot.phase === "downloading" ||
    snapshot.phase === "installing";

  const action =
    !supported ? null : snapshot.phase === "ready" ? (
      <button type="button" className="button button--ghost" onClick={() => void service.installAndRestart()}>
        Restart to update
      </button>
    ) : snapshot.phase === "error" ? (
      <button type="button" className="button button--ghost" onClick={() => void service.retry()}>
        Try again
      </button>
    ) : (
      <button
        type="button"
        className="button button--ghost"
        disabled={busy}
        onClick={() => void service.check()}
      >
        {snapshot.phase === "checking" ? "Checking…" : "Check for updates"}
      </button>
    );

  return (
    <section className="settings__section settings__updates" aria-labelledby="settings-updates-heading">
      <h3 className="settings__title" id="settings-updates-heading">
        Updates
      </h3>
      <p className="settings__updates-row">
        <span>{service.statusLine()}</span>
        {action}
      </p>
    </section>
  );
}
