import { useMemo, useState } from "react";

import { OpportunityPlot } from "../components/canvas/OpportunityLandscape";
import {
  SAMPLE_MISSING_EVIDENCE,
  SAMPLE_OUTCOME_ID,
  sampleCanvas,
} from "../lib/sampleLoop";
import type { Outcome } from "../types";

/**
 * Scene three: where it lands.
 *
 * The scored sample outcome is plotted on the landscape the person would use
 * for their own work, highlighted against two comparisons. It is labelled as a
 * sample everywhere, and the note names what the sample does not prove, so the
 * tour ends on the artifact rather than a summary.
 */
export function LandScene() {
  const canvas = useMemo(() => sampleCanvas(), []);
  const [selectedOutcomeId, setSelectedOutcomeId] = useState<string | null>(
    SAMPLE_OUTCOME_ID,
  );
  const [hoveredOutcome, setHoveredOutcome] = useState<Outcome | null>(null);

  return (
    <div className="wizard-land">
      <p className="wizard-land__note">
        <span className="badge badge--amber">Sample</span> The outcome you just scored,
        plotted on the landscape you would use for your own work. Nothing here is yours
        yet.
      </p>

      <div className="wizard-land__plot">
        <OpportunityPlot
          outcomes={canvas.outcomes}
          selectedOutcomeId={selectedOutcomeId}
          highlightedOutcomeId={SAMPLE_OUTCOME_ID}
          onSelectOutcome={(id) =>
            setSelectedOutcomeId((prev) => (prev === id ? null : id))
          }
          onHoverOutcome={setHoveredOutcome}
          activeOutcome={hoveredOutcome}
          compact
        />
      </div>

      <div className="wizard-land__missing">
        <p className="wizard-land__missing-label">What the sample does not prove</p>
        <ul className="wizard-land__missing-list">
          {SAMPLE_MISSING_EVIDENCE.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
