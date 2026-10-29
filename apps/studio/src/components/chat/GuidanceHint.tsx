import { useState } from "react";

import {
  GUIDANCE_CAPTURE_PROMPT,
  currentGuidance,
  readDismissedGuidance,
  writeDismissedGuidance,
  type GuidanceId,
} from "../../lib/guidance";
import { useStudio } from "../../state/StudioContext";

/**
 * One quiet sentence that teaches the next thing, after the first exchange.
 *
 * It is deliberately not a walkthrough: nothing is highlighted, nothing is
 * covered, and it disappears the moment it is dismissed. The studio should
 * explain itself in place, not in front of itself.
 */
export function GuidanceHint() {
  const { brief, messages, canvas, llmHealth, openSetup, openPanel, sendMessage } =
    useStudio();
  const [dismissed, setDismissed] = useState<GuidanceId[]>(readDismissedGuidance);

  const outcomes = canvas?.outcomes ?? [];
  const guidance = currentGuidance({
    brief,
    messageCount: messages.length,
    outcomeCount: outcomes.length,
    evidenceCount: outcomes.filter((outcome) => outcome.evidence?.trim()).length,
    dismissed,
  });

  if (!guidance) {
    return null;
  }

  function dismiss(id: GuidanceId) {
    const next = [...dismissed, id];
    setDismissed(next);
    writeDismissedGuidance(next);
  }

  function act() {
    if (!guidance) {
      return;
    }
    if (guidance.action === "context") {
      openSetup();
      return;
    }
    // Without a model, capture is the offline form; with one, it is a sentence.
    if (llmHealth.healthy === false) {
      openPanel("capture");
      return;
    }
    void sendMessage(GUIDANCE_CAPTURE_PROMPT);
  }

  return (
    <aside className="guidance" aria-label="Next step">
      <p className="guidance__line">{guidance.line}</p>
      <button type="button" className="guidance__action" onClick={act}>
        {guidance.actionLabel}
      </button>
      <button
        type="button"
        className="guidance__dismiss"
        aria-label="Dismiss this hint"
        title="Don't show this again"
        onClick={() => dismiss(guidance.id)}
      >
        ✕
      </button>
    </aside>
  );
}
