import { useStudio } from "../../state/StudioContext";
import { DirectCapture } from "./DirectCapture";
import { EvidenceStream } from "./EvidenceStream";
import { ImpactSim } from "./ImpactSim";
import { JobMap } from "./JobMap";
import { OpportunityLandscape } from "./OpportunityLandscape";

interface TabDef {
  id: string;
  label: string;
}

const TABS: TabDef[] = [
  { id: "landscape", label: "🌟 Opportunity Landscape" },
  { id: "jobmap", label: "🗺️ Universal Job Map" },
  { id: "impact", label: "⚡ WYSIWYG Impact" },
  { id: "evidence", label: "📡 Customer Evidence" },
  { id: "capture", label: "➕ Direct Capture" },
];

function renderPanel(tab: string) {
  switch (tab) {
    case "jobmap":
      return <JobMap />;
    case "impact":
      return <ImpactSim />;
    case "evidence":
      return <EvidenceStream />;
    case "capture":
      return <DirectCapture />;
    case "landscape":
    default:
      return <OpportunityLandscape />;
  }
}

export function CanvasTabs() {
  const { canvas, canvasLoading, canvasCached, activeTab, setActiveTab, engagementLevel } = useStudio();

  const showTabs = engagementLevel >= 1;

  return (
    <div>
      {showTabs && (
        <div className="studio-card" role="status" aria-live="polite">
          {canvasLoading ? (
            <span>⚡ Syncing with Living Studio Canvas &amp; FastMCP...</span>
          ) : canvas?.source === "seed" ? (
            <span>🟢 Local Studio Prototype Loaded</span>
          ) : (
            <span>✨ Living Studio Canvas ready</span>
          )}
          {canvas && (
            <span className="source-badge">
              source: <b>{canvas.source}</b>
              {canvasCached && <span className="cached-badge"> · cached · updating…</span>}
            </span>
          )}
        </div>
      )}

      {showTabs && (
        <div className="studio-tabs__list" role="tablist" aria-label="Living Studio canvas views">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`tab-${tab.id}`}
              className="studio-tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`panel-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {showTabs && (
        <div role="tabpanel" id={`panel-${activeTab}`} aria-labelledby={`tab-${activeTab}`}>
          {renderPanel(activeTab)}
        </div>
      )}
    </div>
  );
}
