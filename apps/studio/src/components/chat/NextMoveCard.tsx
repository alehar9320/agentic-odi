import { useMemo, useState } from "react";

import {
  lastAssistantTurn,
  nextMoveKindLabel,
  recommendNextMove,
  type NextMove,
} from "../../lib/nextMove";
import { useStudio } from "../../state/StudioContext";

/**
 * The one thing worth doing next, after the turn that just ended.
 *
 * It replaces the old hint row: no permanent dismissal, no second voice on an
 * empty stage, and every line computed from the store rather than the model.
 */
export function NextMoveCard() {
  const { brief, messages, canvas, signals, theses, llmHealth, openSetup, openPanel, sendMessage } =
    useStudio();
  const [dismissedId, setDismissedId] = useState<string | null>(null);

  const lastTurn = useMemo(() => lastAssistantTurn(messages), [messages]);
  const move = recommendNextMove({
    brief,
    lastTurn,
    canvas: canvas
      ? {
          jobs: canvas.jobs ?? [],
          steps: canvas.steps ?? [],
          outcomes: canvas.outcomes ?? [],
          evidence: canvas.evidence ?? [],
          provenance: canvas.provenance,
        }
      : null,
    signals,
    theses,
    dismissedId,
    modelAvailable: llmHealth.healthy !== false,
  });

  if (!move || move.id === dismissedId) {
    return null;
  }

  function act(next: NextMove) {
    if (next.action.kind === "setup") {
      openSetup();
      return;
    }
    if (next.action.kind === "panel") {
      openPanel(next.action.panel);
      return;
    }
    void sendMessage(next.action.prompt);
  }

  return (
    <aside className="next-move" aria-label="Recommended next move">
      <p className="next-move__kind">{nextMoveKindLabel(move.kind)}</p>
      <p className="next-move__move">{move.move}</p>
      <p className="next-move__why">{move.rationale}</p>
      <p className="next-move__expected">
        <span>What would change it: </span>
        {move.expectedEvidence}
      </p>
      <div className="next-move__actions">
        <button type="button" className="next-move__action" onClick={() => act(move)}>
          {move.action.label}
        </button>
        <button
          type="button"
          className="next-move__dismiss"
          aria-label="Dismiss this recommendation"
          title="Hide this for now"
          onClick={() => setDismissedId(move.id)}
        >
          ✕
        </button>
      </div>
    </aside>
  );
}
