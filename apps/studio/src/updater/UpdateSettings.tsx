import { StatusDot } from "../components/status/StatusDot";
import { formatActionTime } from "./machine";
import { useUpdateService, useUpdateSnapshot } from "./UpdateProvider";
import type { UpdateActionKind } from "./types";

const ACTION_LABELS: Record<UpdateActionKind, string> = {
  "check-started": "Checked for updates",
  "check-succeeded": "Reached the update server",
  "check-failed": "Couldn't reach the update server",
  "download-started": "Started downloading",
  "download-finished": "Finished downloading",
  "download-failed": "The download didn't finish",
  "install-started": "Started installing",
  installed: "Update installed",
  "install-failed": "The install didn't finish",
  skipped: "Skipped this version",
  dismissed: "Dismissed the update",
  "restart-failed": "Couldn't restart the app",
};

const ACTION_LOG_LIMIT = 6;

/**
 * Updates: one line that says where things stand, and at most one action.
 *
 * The running version and the build facts live in About; the bar's version
 * pill and the banner carry the urgent restart. This row is the quiet,
 * configuration-facing summary, so the release notes, the last-check time, and
 * the skip control are deliberately absent here.
 */
export function UpdateSettings() {
  const service = useUpdateService();
  const snapshot = useUpdateSnapshot();

  const supported = snapshot.phase !== "unsupported";
  const busy =
    snapshot.phase === "checking" ||
    snapshot.phase === "downloading" ||
    snapshot.phase === "installing";
  const recentActions = snapshot.actions.slice(0, ACTION_LOG_LIMIT);

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

      {supported && recentActions.length > 0 && (
        <details className="disclosure update-settings__activity">
          <summary>Recent update activity</summary>
          <ul className="update-settings__log">
            {recentActions.map((entry, index) => (
              <li
                key={`${entry.kind}-${entry.at}-${index}`}
                className="update-settings__log-row"
              >
                <span>{ACTION_LABELS[entry.kind]}</span>
                <span className="muted">{formatActionTime(entry.at)}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

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
