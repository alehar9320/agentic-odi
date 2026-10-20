import { useStudio } from "../../state/StudioContext";
import { CloseIcon } from "../icons";
import { findPanel } from "./panels";

/**
 * The secondary surface: classic UI (landscape, job map, impact, evidence,
 * capture, settings) opening beside the conversation, never replacing it.
 */
export function WorkspacePanel() {
  const { activePanel, closePanel } = useStudio();

  if (!activePanel) {
    return null;
  }

  const panel = findPanel(activePanel);

  return (
    <aside className="panel" aria-label={panel.title} key={panel.id}>
      <header className="panel__head">
        <div className="panel__heading">
          <span className="panel__icon">{panel.icon}</span>
          <div className="panel__heading-text">
            <h2 className="panel__title">{panel.title}</h2>
            <p className="panel__blurb">{panel.blurb}</p>
          </div>
        </div>
        <button type="button" className="icon-button" aria-label="Close panel" onClick={closePanel}>
          <CloseIcon />
        </button>
      </header>
      <div className="panel__body">{panel.render()}</div>
    </aside>
  );
}
