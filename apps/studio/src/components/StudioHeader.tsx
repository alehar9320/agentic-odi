import { useStudio } from "../state/StudioContext";

export function StudioHeader() {
  const { llmHealth, mcpReachable, engagementLevel, setEngagementLevel } = useStudio();

  return (
    <header className="studio-header fade-in" role="banner">
      <div className="studio-header__brand">
        <div>
          <h1 className="studio-header__title" style={{ margin: 0 }}>
            The Living Studio <span>| ODI</span>
          </h1>
          <p className="studio-header__subtitle" style={{ margin: "2px 0 0" }}>
            A Canvas of Human Intent. Zero file trees.
          </p>
        </div>
      </div>

      <div className="studio-header__pills" role="region" aria-label="System status">
        <span className="studio-pill pill-blue">ODI v1.0</span>
        {llmHealth.healthy ? (
          <span className="studio-pill pill-green" title="LLM Backend is active and connected">
            🟢 LLM
          </span>
        ) : (
          <span className="studio-pill pill-amber" title="Running in standalone studio mode">
            🟡 Local Mode
          </span>
        )}
        {mcpReachable ? (
          <span className="studio-pill pill-green" title="FastMCP bridge reachable">
            🟢 FastMCP
          </span>
        ) : (
          <span className="studio-pill pill-blue" title="Using local seed prototype dataset">
            ⚡ Seed Mode
          </span>
        )}

        <div style={{ display: "inline-flex", gap: 2, background: "rgba(255,255,255,0.05)", padding: 2, borderRadius: 999 }}>
          {[0, 1, 2].map((level) => (
            <button
              key={level}
              type="button"
              onClick={() => setEngagementLevel(level)}
              aria-label={}
              style={{
                background: engagementLevel === level ? "var(--studio-indigo-strong, #6366f1)" : "transparent",
                color: engagementLevel === level ? "#fff" : "var(--studio-muted, #94a3b8)",
                border: "none",
                borderRadius: 999,
                padding: "3px 8px",
                fontSize: "0.72rem",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              L{level}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
