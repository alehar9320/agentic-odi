import { useUpdateService, useUpdateSnapshot } from "./UpdateProvider";

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
  const canSkip =
    snapshot.available !== null &&
    !snapshot.installed &&
    (snapshot.phase === "error" || snapshot.phase === "ready");
  const dotClass =
    snapshot.phase === "error"
      ? " is-warn"
      : snapshot.phase === "ready"
        ? " is-ready"
        : busy
          ? " is-busy"
          : "";

  return (
    <section className="update-settings" aria-labelledby="software-update-heading">
      <div className="update-settings__head">
        <h3 className="settings__title" id="software-update-heading">
          Software update
        </h3>
        {version && <span className="update-settings__version">v{version}</span>}
      </div>

      <p className="update-settings__status">
        <span className={`status-dot${dotClass}`} aria-hidden="true" />
        <span>{service.statusLine()}</span>
      </p>

      {supported && snapshot.lastCheckedAt !== null && (
        <p className="muted">{service.checkedAtLabel()}</p>
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
