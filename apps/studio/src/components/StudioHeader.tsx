import { useStudio } from "../state/StudioContext";

export function StudioHeader() {
  const { llmHealth, mcpReachable } = useStudio();

  return (
    <header className="studio-header fade-in">
      <div>
        <div className="studio-header__title">
          The Living Studio <span>| Outcome-Driven Innovation</span>
        </div>
        <div className="studio-header__subtitle">
          A canvas of human intent. Direct causality, zero noise.
        </div>
      </div>
      <div className="studio-header__pills">
        <span className="studio-pill pill-blue">ODI Framework v1.0</span>
        {llmHealth.healthy ? (
          <span className="studio-pill pill-green">🟢 LLM Active</span>
        ) : (
          <span className="studio-pill pill-amber">🟡 Local Studio Mode</span>
        )}
        {mcpReachable ? (
          <span className="studio-pill pill-green">🟢 FastMCP Connected</span>
        ) : (
          <span className="studio-pill pill-blue">⚡ Seed Prototype Ready</span>
        )}
      </div>
    </header>
  );
}
