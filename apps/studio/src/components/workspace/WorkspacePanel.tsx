import { useStudio } from "../../state/StudioContext";
import { ArrowLeftIcon } from "../icons";
import { findPanel } from "./panels";

/**
 * A workspace surface takes the whole stage while it is open. The conversation
 * is one click away, and nothing is squeezed into a narrow side column.
 */
export function WorkspacePanel() {
  const { activePanel, closePanel } = useStudio();

  if (!activePanel) {
    return null;
  }

  const panel = findPanel(activePanel);

  return (
    <section className="panel" aria-label={panel.title} key={panel.id}>
      <header className="panel__head">
        <button type="button" className="back" onClick={closePanel}>
          <ArrowLeftIcon size={16} />
          Back to conversation
        </button>
        <div className="panel__heading">
          <span className="panel__icon">{panel.icon}</span>
          <div className="panel__heading-text">
            {/* The panel chrome owns the heading. Canvas content that repeats
                the same title renders it as a label, so no panel exposes two
                headings with the same accessible name. */}
            <h2 className="panel__title">{panel.title}</h2>
            <p className="panel__blurb">{panel.blurb}</p>
          </div>
        </div>
        <span className="panel__hint">
          <kbd>Esc</kbd> to return
        </span>
      </header>
      <div className="panel__body">
        <div className="panel__content">{panel.render()}</div>
      </div>
    </section>
  );
}
