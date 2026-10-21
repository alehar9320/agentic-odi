import { useStudio } from "../../state/StudioContext";

/** A quiet, honest strip that turns a missing model into a way to work. */
export function OfflineNotice() {
  const { llmHealth, openPanel, openSetup } = useStudio();

  if (llmHealth.healthy !== false) {
    return null;
  }

  return (
    <div className="offline" role="status">
      <div className="offline__text">
        <strong>Working by hand.</strong> No model is reachable, so the assistant is paused.
        Every change below still writes to your ODI repository.
      </div>
      <div className="offline__actions">
        <button type="button" className="suggestion" onClick={() => openPanel("capture")}>
          Capture an outcome
        </button>
        <button type="button" className="suggestion" onClick={() => openPanel("jobmap")}>
          Map the job
        </button>
        <button type="button" className="suggestion" onClick={openSetup}>
          Set your context
        </button>
      </div>
    </div>
  );
}
