import type { CanvasData, StudioBrief } from "../../../types";

export function DataSection({
  brief,
  openSetup,
  canvas,
  refreshCanvas,
  startNewConversation,
  headingId = "settings-data-heading",
  sectionId,
}: {
  brief: StudioBrief | null;
  openSetup: () => void;
  canvas: CanvasData | null;
  refreshCanvas?: () => Promise<void>;
  startNewConversation?: () => void;
  headingId?: string;
  sectionId?: string;
}) {
  return (
    <section id={sectionId} className="settings__section" aria-labelledby={headingId} tabIndex={sectionId ? -1 : undefined}>
      <h3 className="settings__title" id={headingId}>Data</h3>
      <div className="settings__context">
        <div>
          <p className="settings__context-label">Your context</p>
          <p className="settings__context-value">
            {brief?.job_statement
              ? `${brief.product_name || "Your product"} — ${brief.job_statement}`
              : "Not set yet. The studio starts every reply from this."}
          </p>
          {brief?.v2mom?.vision ? (
            <p className="settings__context-value">
              <strong>Vision:</strong> {brief.v2mom.vision}
            </p>
          ) : null}
        </div>
        <button type="button" className="button button--ghost" onClick={openSetup}>
          {brief ? "Edit context" : "Set up context"}
        </button>
      </div>
      <dl className="customize__data-counts" aria-label="Canvas data counts">
        <div><dt>Jobs</dt><dd>{canvas?.jobs.length ?? 0}</dd></div>
        <div><dt>Steps</dt><dd>{canvas?.steps.length ?? 0}</dd></div>
        <div><dt>Outcomes</dt><dd>{canvas?.outcomes.length ?? 0}</dd></div>
        <div><dt>Evidence</dt><dd>{canvas?.evidence?.length ?? 0}</dd></div>
      </dl>
      {refreshCanvas ? (
        <button type="button" className="button button--ghost" onClick={() => void refreshCanvas()}>
          Sync canvas
        </button>
      ) : null}
      {startNewConversation ? (
        <button type="button" className="button" onClick={startNewConversation}>
          Start a new conversation
        </button>
      ) : null}
    </section>
  );
}
