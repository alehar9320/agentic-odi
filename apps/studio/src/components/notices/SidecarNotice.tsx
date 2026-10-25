import { useStudio } from "../../state/StudioContext";

/**
 * A subtle, persistent strip that names the real problem when the Living Studio
 * sidecar isn't answering: the assistant pauses, live data waits, and the user
 * gets a one-click path back instead of a generic "something went wrong".
 *
 * It only shows once reachability has been confirmed false (not while the
 * first probe is still in flight), and it can be dismissed per session.
 */
export function SidecarNotice() {
  const {
    sidecarReachable,
    dismissedSidecarNotice,
    dismissSidecarNotice,
    recheckConnections,
    openSetup,
  } = useStudio();

  if (sidecarReachable !== false || dismissedSidecarNotice) {
    return null;
  }

  return (
    <div className="sidecar-notice" role="status">
      <div className="sidecar-notice__text">
        <strong>The studio sidecar isn't running.</strong> The assistant is paused and live
        data is frozen until it comes back.
      </div>
      <div className="sidecar-notice__actions">
        <button type="button" className="suggestion" onClick={recheckConnections}>
          Recheck
        </button>
        <button type="button" className="suggestion" onClick={openSetup}>
          Start the sidecar
        </button>
        <button
          type="button"
          className="quiet-action"
          aria-label="Dismiss"
          onClick={() => dismissSidecarNotice()}
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
