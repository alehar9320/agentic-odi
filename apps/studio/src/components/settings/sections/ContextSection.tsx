import type { StudioBrief } from "../../../types";

interface ContextSectionProps {
  brief: StudioBrief | null;
  openSetup: () => void;
  displayName: string;
  setDisplayName: (name: string) => void;
  closeSetup: () => void;
  clearChat: () => void;
  refreshCanvas: () => Promise<void>;
}

/**
 * The person's own context and the two actions that start fresh: the job the
 * studio answers from, the name it greets them with, and the canvas sync.
 *
 * Every value here is local, so the section has nothing to load and nothing to
 * fail on its own.
 */
export function ContextSection({
  brief,
  openSetup,
  displayName,
  setDisplayName,
  closeSetup,
  clearChat,
  refreshCanvas,
}: ContextSectionProps) {
  return (
    <div className="settings__section">
      <div className="settings__context">
        <div>
          <p className="settings__context-label">Your context</p>
          <p className="settings__context-value">
            {brief?.job_statement
              ? `${brief.product_name || "Your product"} — ${brief.job_statement}`
              : "Not set yet. The studio starts every reply from this."}
          </p>
          {brief?.v2mom?.vision && (
            <p className="settings__context-value">
              <strong>Vision:</strong> {brief.v2mom.vision}
            </p>
          )}
        </div>
        <button type="button" className="button button--ghost" onClick={openSetup}>
          {brief ? "Edit context" : "Set up context"}
        </button>
      </div>

      <div className="field">
        <label htmlFor="display-name">
          Your name <span className="field__hint">optional — used in the greeting</span>
        </label>
        <input
          id="display-name"
          className="input"
          value={displayName}
          placeholder="Ada"
          autoComplete="given-name"
          onChange={(event) => setDisplayName(event.target.value)}
        />
      </div>

      <div className="settings__actions">
        <button
          type="button"
          className="button"
          onClick={() => {
            closeSetup();
            clearChat();
          }}
        >
          Start a new conversation
        </button>
        <button type="button" className="button button--ghost" onClick={() => void refreshCanvas()}>
          Sync canvas
        </button>
      </div>
    </div>
  );
}
