import { CheckIcon } from "../components/icons";
import { updateTitle, versionLabel } from "../lib/brand";
import { useUpdateService, useUpdateSnapshot } from "./UpdateProvider";
import { bannerView } from "./machine";

/**
 * One quiet line about the update, above the conversation.
 *
 * It never blocks, never takes focus, and never says anything a person cannot
 * act on. Dismissing it is always safe: a staged update still applies on the
 * next launch.
 */
export function UpdateBanner() {
  const service = useUpdateService();
  const snapshot = useUpdateSnapshot();
  const view = bannerView(snapshot);

  if (!view) {
    return null;
  }

  const percent = view.percent;
  const percentLabel = percent === null ? null : `${Math.round(percent * 100)}%`;

  const { title, detail } = (() => {
    switch (view.kind) {
      case "downloading":
        return {
          title: updateTitle(view.version, "downloading"),
          detail: "Downloading in the background — you can keep working.",
        };
      case "installing":
        return {
          title: updateTitle(view.version, "installing"),
          detail: "One moment.",
        };
      case "ready":
        return {
          title: `${versionLabel(view.version)} is ready`,
          detail: view.pendingInstall
            ? "Updating closes and reopens the app."
            : "Restart now, or it will apply the next time you open the studio.",
        };
      default:
        return {
          title: "The update didn't finish",
          detail: snapshot.error ?? "Try again in a moment.",
        };
    }
  })();

  const primary =
    view.kind === "ready" ? (
      <button
        type="button"
        className="button update-banner__action"
        onClick={() => void service.installAndRestart()}
      >
        {view.pendingInstall ? "Update & restart" : "Restart now"}
      </button>
    ) : view.kind === "error" ? (
      <button
        type="button"
        className="button update-banner__action"
        onClick={() => void service.retry()}
      >
        Try again
      </button>
    ) : null;

  return (
    <section
      className={`update-banner update-banner--${view.kind}`}
      role="status"
      aria-live="polite"
      aria-label="Software update"
    >
      <span className="update-banner__mark" aria-hidden="true">
        {view.kind === "ready" ? <CheckIcon size={15} /> : "◍"}
      </span>

      <div className="update-banner__copy">
        <p className="update-banner__title">{title}</p>
        <p className="update-banner__detail">{detail}</p>
      </div>

      {view.kind === "downloading" && (
        <span
          className="update-banner__progress"
          role="progressbar"
          aria-label="Update download progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent === null ? undefined : Math.round(percent * 100)}
        >
          <span
            className="update-banner__progress-fill"
            style={{ width: percent === null ? "12%" : `${Math.max(2, percent * 100)}%` }}
          />
        </span>
      )}

      {percentLabel && <span className="update-banner__percent">{percentLabel}</span>}

      <div className="update-banner__actions">
        {primary}
        {view.kind !== "installing" && (
          <button
            type="button"
            className="update-banner__dismiss"
            aria-label="Dismiss update notice"
            title="Not now"
            onClick={() => service.dismiss()}
          >
            ×
          </button>
        )}
      </div>
    </section>
  );
}
