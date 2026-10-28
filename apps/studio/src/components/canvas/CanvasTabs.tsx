import { useStudio } from "../../state/StudioContext";
import { DirectCapture } from "./DirectCapture";
import { EvidenceStream } from "./EvidenceStream";
import { ImpactSim } from "./ImpactSim";
import { JobMap } from "./JobMap";
import { OpportunityLandscape } from "./OpportunityLandscape";

interface TabDef {
  id: string;
  label: string;
  shortLabel: string;
}

const TABS: TabDef[] = [
  { id: "landscape", label: "🌟 Opportunity Landscape", shortLabel: "🌟 Landscape" },
  { id: "jobmap", label: "🗺️ Universal Job Map", shortLabel: "🗺️ Job Map" },
  { id: "impact", label: "⚡ WYSIWYG Impact", shortLabel: "⚡ Impact" },
  { id: "evidence", label: "📡 Customer Evidence", shortLabel: "📡 Evidence" },
  { id: "capture", label: "➕ Direct Capture", shortLabel: "➕ Capture" },
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

  function handleKeyDown(event: React.KeyboardEvent, index: number) {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      const nextIndex = (index + 1) % TABS.length;
      setActiveTab(TABS[nextIndex].id);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      const prevIndex = (index - 1 + TABS.length) % TABS.length;
      setActiveTab(TABS[prevIndex].id);
    }
  }

  return (
    <div>
      {showTabs && (
        <div className="studio-card" role="status" aria-live="polite" style={{ padding: "12px 16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
            <span style={{ fontSize: "0.85rem", fontWeight: 500 }}>
              {canvasLoading ? (
                "⚡ Syncing with Living Studio Canvas & FastMCP..."
              ) : canvas?.source === "seed" ? (
                "🟢 Local Studio Prototype Loaded"
              ) : (
                "✨ Living Studio Canvas Ready"
              )}
            </span>
            {canvas && (
              <span className="source-badge">
                Source: <b>{canvas.source}</b>
                {canvasCached && <span className="cached-badge"> · cached</span>}
              </span>
            )}
          </div>
        </div>
      )}

      {showTabs && (
        <div
          className="studio-tabs__list"
          role="tablist"
          aria-label="Living Studio Canvas Views"
        >
          {TABS.map((tab, idx) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={}
              className="studio-tab"
              aria-selected={activeTab === tab.id}
              aria-controls={}
              tabIndex={activeTab === tab.id ? 0 : -1}
              onClick={() => setActiveTab(tab.id)}
              onKeyDown={(e) => handleKeyDown(e, idx)}
            >
              <span className="desktop-only">{tab.label}</span>
              <span className="mobile-only">{tab.shortLabel}</span>
            </button>
          ))}
        </div>
      )}

      {showTabs && (
        <div role="tabpanel" id={} aria-labelledby={}>
          {renderPanel(activeTab)}
        </div>
      )}
    </div>
  );
}
