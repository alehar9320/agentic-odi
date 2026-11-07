import { StatusDot } from "../components/status/StatusDot";
import { useUpdateService, useUpdateSnapshot } from "./UpdateProvider";

/**
 * Updates: one line that says where things stand, and at most one action.
 *
 * The running version and the build facts live in About; the bar's version
 * pill and the banner carry the urgent restart. This row is the quiet,
 * configuration-facing summary, so the detail (release notes, when the last
 * check ran, the running version) is deliberately absent here.
 */
export function UpdateSettings() {
  const service = useUpdateService();
  const snapshot = useUpdateSnapshot();

  const supported = snapshot.phase !== "unsupported";
  const busy =
    snapshot.phase === "checking" ||
    snapshot.phase === "downloading" ||
    snapshot.phase === "installing";

  const action = !supported ? null : snapshot.phase === "ready" ? (
    <button
      type="button"
      className="button button--ghost"
      onClick={() => void service.installAndRestart()}
    >
      {snapshot.pendingInstall ? "Update & restart" : "Restart now"}
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
      {snapshot.phase === "checking" ? "Checking…" : "Check now"}
    </button>
  );

  return (
    <section className="update-settings" aria-labelledby="settings-updates-heading">
      <h3 className="settings__title" id="settings-updates-heading">
        Updates
      </h3>
      <p className="update-settings__status">
        <StatusDot
          tone={
            snapshot.phase === "error"
              ? "warn"
              : snapshot.phase === "ready"
                ? "ready"
                : busy
                  ? "busy"
                  : "ok"
          }
        />
        <span>{service.statusLine()}</span>
        {action}
      </p>

      {supported && (
        <label className="update-settings__toggle">
          <input
            type="checkbox"
            checked={snapshot.autoCheck}
            onChange={(event) => service.setAutoCheck(event.target.checked)}
          />
          <span>Check for updates automatically</span>
        </label>
      )}
    </section>
  );
}
