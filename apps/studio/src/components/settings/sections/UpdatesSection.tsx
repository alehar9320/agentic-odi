import { UpdateSettings } from "../../../updater";

interface UpdatesSectionProps {
  /** Whether the product tour is available to replay. */
  tourEnabled: boolean;
  /** Start the tour from its first step. */
  restartTour: () => void;
}

/**
 * Software update, the tour, and the essay about how the studio works.
 *
 * The updater owns its own provider-backed state, so a failure to check for an
 * update never reaches the sections beside it.
 */
export function UpdatesSection({ tourEnabled, restartTour }: UpdatesSectionProps) {
  return (
    <div className="settings__section">
      {tourEnabled ? (
        <div className="settings__tour">
          <h3 className="settings__title">Getting started</h3>
          <p className="muted">
            A four-step product tour, when you want one. It never opens by itself.
          </p>
          <button type="button" className="button button--ghost" onClick={restartTour}>
            Replay the tour
          </button>
        </div>
      ) : null}

      <UpdateSettings />

      <details className="disclosure">
        <summary>How the studio works</summary>
        <p>
          Backlogs and ticket accounting give way to a canvas of human intent. Point at an outcome,
          then talk about it: every bet traces back to evidence, and impact is simulated before code
          gets written.
        </p>
      </details>
    </div>
  );
}
