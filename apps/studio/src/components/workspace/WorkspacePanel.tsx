import { useStudio } from "../../state/StudioContext";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { CloseIcon } from "../icons";
import { PanelBoundary } from "./PanelBoundary";
import { findPanel, type PanelDefinition } from "./panels";

const MOBILE_QUERY = "(max-width: 1023px)";

/**
 * The lens body as its own component, so a lens that throws while rendering is
 * caught by the panel boundary instead of by the app.
 */
function PanelBody({ panel }: { panel: PanelDefinition }) {
  return <>{panel.render()}</>;
}

/**
 * A lens on the conversation, not a place you go.
 *
 * On a wide screen it docks to the right and the thread keeps the stage: the
 * composer is still there, still focused, still usable. On a narrow screen
 * there is no room for both, so it becomes a sheet over the thread with a scrim
 * and a close control.
 */
export function WorkspacePanel() {
  const { activePanel, closePanel, sendMessage } = useStudio();
  const isMobile = useMediaQuery(MOBILE_QUERY);

  if (!activePanel) {
    return null;
  }

  const panel = findPanel(activePanel);

  function talk() {
    if (!panel.talk) {
      return;
    }
    closePanel();
    void sendMessage(panel.talk.intent);
  }

  return (
    <>
      {isMobile && (
        <button
          type="button"
          className="scrim"
          aria-label="Close workspace view"
          onClick={closePanel}
        />
      )}
      <aside
        className="lens"
        role={isMobile ? "dialog" : "complementary"}
        aria-modal={isMobile || undefined}
        aria-label={panel.title}
        key={panel.id}
      >
        <header className="lens__head">
          <div className="lens__heading">
            <span className="lens__icon" aria-hidden="true">
              {panel.icon}
            </span>
            <div>
              <h2 className="lens__title">{panel.title}</h2>
              <p className="lens__blurb">{panel.blurb}</p>
            </div>
          </div>
          <button
            type="button"
            className="icon-button"
            aria-label="Close workspace view"
            title="Close"
            onClick={closePanel}
          >
            <CloseIcon size={16} />
          </button>
        </header>

        <div className="lens__body">
          <div className="lens__content">
            <PanelBoundary name={panel.id}>
              <PanelBody panel={panel} />
            </PanelBoundary>
          </div>
        </div>

        {panel.talk && (
          <footer className="lens__foot">
            <p className="lens__note">A lens on the conversation, not a separate place.</p>
            <button type="button" className="button button--block" onClick={talk}>
              {panel.talk.label}
            </button>
          </footer>
        )}
      </aside>
    </>
  );
}
