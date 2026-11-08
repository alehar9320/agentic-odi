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
 * The honest, complete picture: the running version, what the updater is doing,
 * the release notes, and the two preferences that matter.
 */
export function UpdateSettings() {
  const service = useUpdateService();
  const snapshot = useUpdateSnapshot();

  const supported = snapshot.phase !== "unsupported";
  const busy =
    snapshot.phase === "checking" ||
    snapshot.phase === "downloading" ||
    snapshot.phase === "installing";
  const version = snapshot.currentVersion;
  const notes = snapshot.available?.notes;
  // A check that never reached the server has no update to talk about; the
  // status line owns that sentence, so the bare check time would contradict it.
  const checkFailed = snapshot.phase === "error" && snapshot.available === null;
  const recentActions = snapshot.actions.slice(0, ACTION_LOG_LIMIT);
  const canSkip =
    snapshot.available !== null &&
    !snapshot.installed &&
    (snapshot.phase === "error" || snapshot.phase === "ready");

  return (
    <section className="update-settings" aria-labelledby="software-update-heading">
      <div className="update-settings__head">
        <h3 className="settings__title" id="software-update-heading">
          Software update
        </h3>
        {version && <span className="update-settings__version">v{version}</span>}
      </div>

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
      </p>

      {supported && snapshot.lastCheckedAt !== null && !checkFailed && (
        <p className="muted">{service.checkedAtLabel()}</p>
      )}

      {supported && recentActions.length > 0 && (
        <details className="disclosure update-settings__activity">
          <summary>Recent update activity</summary>
          <ul className="update-settings__log">
            {recentActions.map((action, index) => (
              <li
                key={`${action.kind}-${action.at}-${index}`}
                className="update-settings__log-row"
              >
                <span>{ACTION_LABELS[action.kind]}</span>
                <span className="muted">{formatActionTime(action.at)}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {snapshot.available && notes && (
        <details className="disclosure update-settings__notes">
          <summary>What's new in {snapshot.available.version}</summary>
          <p className="update-settings__notes-body">{notes}</p>
        </details>
      )}

      {supported && (
        <div className="update-settings__actions">
          {snapshot.phase === "ready" ? (
            <button
              type="button"
              className="button"
              onClick={() => void service.installAndRestart()}
            >
              {snapshot.pendingInstall ? "Update & restart" : "Restart now"}
            </button>
          ) : snapshot.phase === "error" ? (
            <button type="button" className="button" onClick={() => void service.retry()}>
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
          )}

          {canSkip && snapshot.available && (
            <button
              type="button"
              className="button button--ghost"
              onClick={() => service.skipCurrent()}
            >
              Skip this version
            </button>
          )}
        </div>
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
