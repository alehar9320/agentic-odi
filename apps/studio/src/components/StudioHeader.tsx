import { useState } from "react";

import { useStudio } from "../state/StudioContext";
import { ChangelogModal } from "./ChangelogModal";

export function StudioHeader() {
  const { llmHealth, mcpReachable } = useStudio();
  const [showChangelog, setShowChangelog] = useState(false);

  return (
    <>
      <header className="studio-header fade-in">
        <div>
          <div className="studio-header__title">
            The Living Studio <span>| Outcome-Driven Innovation</span>
          </div>
          <div className="studio-header__subtitle">
            A Canvas of Human Intent. Zero file trees. Real-time causality.
          </div>
        </div>
        <div className="studio-header__pills">
          <button
            type="button"
            className="studio-pill pill-changelog"
            onClick={() => setShowChangelog(true)}
            aria-label="Open What's New changelog"
          >
            ✨ What's New
          </button>
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

      <ChangelogModal
        isOpen={showChangelog}
        onClose={() => setShowChangelog(false)}
      />
    </>
  );
}
