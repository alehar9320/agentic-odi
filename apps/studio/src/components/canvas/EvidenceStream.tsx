import { useStudio } from "../../state/StudioContext";
import { SignalIcon } from "../icons";

export function EvidenceStream() {
  const { openPanel } = useStudio();

  return (
    <section className="stack">
      <div className="evidence-empty">
        <span className="evidence-empty__icon" aria-hidden="true">
          <SignalIcon size={22} />
        </span>
        <p className="evidence-empty__title">No customer evidence yet.</p>
        <p className="evidence-empty__body">
          Nothing has been ingested in this build. Connect a source and the quotes, calls, and
          signals it brings will land here, linked to the job and outcome they support.
        </p>
        <button
          type="button"
          className="button button--ghost"
          onClick={() => openPanel("settings")}
        >
          Connect a source in Settings
        </button>
      </div>
    </section>
  );
}
