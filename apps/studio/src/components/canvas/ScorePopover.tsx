import { useMemo, useState } from "react";

import {
  formatOpportunityScore,
  opportunityScore,
  scoreMismatch,
  UNDERSERVED_THRESHOLD,
} from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import type { Outcome } from "../../types";
import { Dialog } from "@/components/ui/dialog";

const MIN_SCORE = 1;
const MAX_SCORE = 10;

function clampScore(value: number): number {
  return Math.min(Math.max(value, MIN_SCORE), MAX_SCORE);
}

/** The stored score and the two inputs it was made from — what the record says,
 * kept apart from the live draft so the mismatch notice describes the record and
 * not the person's in-flight edit. */
interface StoredScore {
  importance: number;
  satisfaction: number;
  score: number | null;
}

/**
 * The panel that shows a score, and changes the two facts it is made of.
 *
 * Editing happens where the arithmetic is visible: drag a slider and watch
 * `importance + gap = opportunity` move and cross the underserved line, then
 * save through the same `updateOutcome` the card uses and read back the value
 * the server returned. A stored score that no longer matches its own inputs is
 * reported, never silently repaired.
 */
export function ScorePopover({ outcome, onClose }: { outcome: Outcome; onClose: () => void }) {
  const { updateOutcome } = useStudio();

  const [stored, setStored] = useState<StoredScore>({
    importance: outcome.importance ?? 5,
    satisfaction: outcome.satisfaction ?? 5,
    score: outcome.opportunity_score ?? null,
  });
  const [importance, setImportance] = useState(stored.importance);
  const [satisfaction, setSatisfaction] = useState(stored.satisfaction);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const computed = useMemo(
    () => opportunityScore(importance, satisfaction),
    [importance, satisfaction],
  );
  const gap = useMemo(() => Math.max(importance - satisfaction, 0), [importance, satisfaction]);
  const underserved = computed > UNDERSERVED_THRESHOLD;
  // The record's own consistency, evaluated from the record's inputs — so the
  // notice is stable while the person drags, and clears only when a save lands.
  const mismatch = scoreMismatch(stored.score, stored.importance, stored.satisfaction);

  const outcomeId = outcome.id ?? "";
  const changed = importance !== stored.importance || satisfaction !== stored.satisfaction;
  const canSave = Boolean(outcomeId) && changed && !saving;

  async function save() {
    if (!outcomeId || saving) {
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const result = await updateOutcome(outcomeId, { importance, satisfaction });
      if (result === null) {
        // The panel stays open with what was typed; the message is the reason.
        setSaveError("Could not save scores");
        return;
      }
      setStored({
        importance,
        satisfaction,
        score: result.opportunity_score ?? null,
      });
    } catch (error) {
      setSaveError((error as Error).message || "Could not save scores");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) {
          onClose();
        }
      }}
      title={outcome.statement ?? "Untitled outcome"}
      footer={
        <>
          <button type="button" className="quiet-action" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="button" className="button button--ghost" onClick={save} disabled={!canSave}>
            {saving ? "Saving…" : "Save scores"}
          </button>
        </>
      }
    >
      <div className="score-popover">
        <p className="score-popover__id">{outcomeId}</p>

        <div className="score-popover__assumptions">
          <div className="score-popover__assumption">
            <span className="score-popover__assumption-label">
              Importance · {importance.toFixed(1)}
            </span>
            <input
              type="range"
              aria-label="Importance slider"
              min={MIN_SCORE}
              max={MAX_SCORE}
              step={0.1}
              value={importance}
              onChange={(event) => setImportance(clampScore(Number(event.target.value)))}
            />
            <input
              type="number"
              aria-label="Importance"
              min={MIN_SCORE}
              max={MAX_SCORE}
              step={0.1}
              value={importance}
              onChange={(event) => setImportance(clampScore(Number(event.target.value)))}
            />
          </div>

          <div className="score-popover__assumption">
            <span className="score-popover__assumption-label">
              Satisfaction · {satisfaction.toFixed(1)}
            </span>
            <input
              type="range"
              aria-label="Satisfaction slider"
              min={MIN_SCORE}
              max={MAX_SCORE}
              step={0.1}
              value={satisfaction}
              onChange={(event) => setSatisfaction(clampScore(Number(event.target.value)))}
            />
            <input
              type="number"
              aria-label="Satisfaction"
              min={MIN_SCORE}
              max={MAX_SCORE}
              step={0.1}
              value={satisfaction}
              onChange={(event) => setSatisfaction(clampScore(Number(event.target.value)))}
            />
          </div>
        </div>

        <p className="score-popover__formula" data-testid="score-formula">
          {importance.toFixed(1)} + {gap.toFixed(1)} = <b>{formatOpportunityScore(computed)}</b>
        </p>
        <p className="score-popover__verdict">
          {underserved
            ? `Underserved — above ${UNDERSERVED_THRESHOLD}`
            : `Served — ${UNDERSERVED_THRESHOLD} or below`}
        </p>

        <p className="score-popover__stored">
          Stored score <b>{formatOpportunityScore(stored.score)}</b>
        </p>

        {mismatch && (
          <div className="score-popover__mismatch" role="status">
            <p>Stored score differs from its inputs</p>
            <button type="button" className="quiet-action" onClick={save} disabled={saving}>
              Recompute
            </button>
          </div>
        )}

        {saveError && (
          <p className="score-popover__error" role="alert">
            {saveError}
          </p>
        )}
      </div>
    </Dialog>
  );
}
