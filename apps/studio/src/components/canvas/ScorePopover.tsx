import { useState, useMemo, useEffect, useRef } from "react";

import { useStudio } from "../../state/StudioContext";
import type { Outcome } from "../../types";
import {
  opportunityScore,
  isUnderserved,
  formatOpportunityScore,
  UNDERSERVED_THRESHOLD,
} from "../../lib/odi";
import { useFocusTrap } from "../../lib/useFocusTrap";

interface ScorePopoverProps {
  outcome: Outcome;
  onClose: () => void;
}

export function ScorePopover({ outcome, onClose }: ScorePopoverProps) {
  const { updateOutcome, pushToast, canvasState } = useStudio();
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, true);

  const outcomeId = outcome.id ?? "";
  const initialImportance = outcome.importance ?? 5;
  const initialSatisfaction = outcome.satisfaction ?? 5;
  const storedScore = outcome.opportunity_score;

  const [importance, setImportance] = useState(initialImportance);
  const [satisfaction, setSatisfaction] = useState(initialSatisfaction);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [serverScore, setServerScore] = useState<number | null>(null);

  const computedScore = useMemo(
    () => opportunityScore(importance, satisfaction),
    [importance, satisfaction],
  );
  const computedUnderserved = useMemo(
    () => isUnderserved(computedScore),
    [computedScore],
  );

  const scoreMismatch = useMemo(() => {
    if (storedScore == null) {
      return false;
    }
    return Math.abs(storedScore - computedScore) > 0.05;
  }, [storedScore, computedScore]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const handleSave = async () => {
    if (!outcomeId || saving) {
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      await updateOutcome(outcomeId, { importance, satisfaction });
      const refreshed = canvasState.data?.outcomes.find((o) => o.id === outcomeId);
      if (refreshed?.opportunity_score != null) {
        setServerScore(refreshed.opportunity_score);
      }
      pushToast("success", "Scores saved");
    } catch (error) {
      setSaveError((error as Error).message || "Could not save scores");
      pushToast("error", "Could not save scores");
    } finally {
      setSaving(false);
    }
  };

  const handleRecompute = async () => {
    if (!outcomeId || saving) {
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      await updateOutcome(outcomeId, { importance, satisfaction });
      const refreshed = canvasState.data?.outcomes.find((o) => o.id === outcomeId);
      if (refreshed?.opportunity_score != null) {
        setServerScore(refreshed.opportunity_score);
      }
      pushToast("success", "Scores recomputed");
    } catch (error) {
      setSaveError((error as Error).message || "Could not recompute scores");
      pushToast("error", "Could not recompute scores");
    } finally {
      setSaving(false);
    }
  };

  const hasChanges =
    importance !== initialImportance || satisfaction !== initialSatisfaction;

  return (
    <div className="score-popover-overlay fade-in">
      <button
        type="button"
        className="score-popover-scrim"
        aria-label="Close score editor"
        tabIndex={-1}
        onClick={onClose}
        data-testid="score-popover-scrim"
      />
      <div
        ref={dialogRef}
        className="score-popover"
        role="dialog"
        aria-modal="true"
        aria-labelledby="score-popover-title"
      >
        <header className="score-popover__header">
          <div>
            <div className="score-popover__badge">EDIT SCORE</div>
            <h2 id="score-popover-title" className="score-popover__title">
              {outcome.statement ?? "Untitled outcome"}
            </h2>
            <span className="score-popover__id">{outcomeId}</span>
          </div>
          <button
            type="button"
            className="score-popover__close"
            onClick={onClose}
            aria-label="Close score editor"
            data-testid="score-popover-close"
          >
            ✕
          </button>
        </header>

        <div className="score-popover__body">
          <div className="score-popover__assumptions">
            <div className="score-popover__assumption">
              <label
                className="score-popover__slider-label"
                htmlFor={`importance-${outcomeId}`}
              >
                Importance · {importance.toFixed(1)}
              </label>
              <input
                id={`importance-${outcomeId}`}
                type="range"
                min={1}
                max={10}
                step={0.1}
                value={importance}
                onChange={(e) => setImportance(Number(e.target.value))}
                className="score-popover__slider"
              />
              <input
                type="number"
                min={1}
                max={10}
                step={0.1}
                value={importance}
                onChange={(e) => {
                  const value = Math.min(Math.max(Number(e.target.value), 1), 10);
                  setImportance(value);
                }}
                className="score-popover__number-input"
                aria-label="Importance"
              />
            </div>

            <div className="score-popover__assumption">
              <label
                className="score-popover__slider-label"
                htmlFor={`satisfaction-${outcomeId}`}
              >
                Satisfaction · {satisfaction.toFixed(1)}
              </label>
              <input
                id={`satisfaction-${outcomeId}`}
                type="range"
                min={1}
                max={10}
                step={0.1}
                value={satisfaction}
                onChange={(e) => setSatisfaction(Number(e.target.value))}
                className="score-popover__slider"
              />
              <input
                type="number"
                min={1}
                max={10}
                step={0.1}
                value={satisfaction}
                onChange={(e) => {
                  const value = Math.min(Math.max(Number(e.target.value), 1), 10);
                  setSatisfaction(value);
                }}
                className="score-popover__number-input"
                aria-label="Satisfaction"
              />
            </div>
          </div>

          <div className="score-popover__arithmetic">
            <div className="score-popover__formula" data-testid="score-formula">
              <span className="score-popover__importance">{importance.toFixed(1)}</span>
              <span className="score-popover__operator">+</span>
              <span className="score-popover__gap">
                max({importance.toFixed(1)} − {satisfaction.toFixed(1)}, 0) ={" "}
                {Math.max(importance - satisfaction, 0).toFixed(1)}
              </span>
              <span className="score-popover__equals">=</span>
              <span
                className={`score-popover__result ${
                  computedUnderserved ? "score-popover__result--hot" : ""
                }`}
              >
                {formatOpportunityScore(computedScore)}
              </span>
              <span className="score-popover__threshold">
                {"(underserved > " + UNDERSERVED_THRESHOLD + ")"}
              </span>
            </div>

            {scoreMismatch && (
              <div className="score-popover__mismatch" role="status">
                <span>⚠ Stored score differs from its inputs</span>
                <button
                  type="button"
                  className="score-popover__recompute"
                  onClick={handleRecompute}
                  disabled={saving}
                >
                  {saving ? "Recomputing…" : "Recompute"}
                </button>
              </div>
            )}

            {saveError && (
              <div className="score-popover__error" role="alert">
                {saveError}
              </div>
            )}

            {serverScore != null && serverScore !== computedScore && (
              <div className="score-popover__server-value" role="status">
                Server returned: <b>{formatOpportunityScore(serverScore)}</b>
              </div>
            )}
          </div>
        </div>

        <footer className="score-popover__footer">
          <button
            type="button"
            className="score-popover__cancel"
            onClick={onClose}
            disabled={saving}
          >
            Cancel
          </button>
          <button
            type="button"
            className="score-popover__save"
            onClick={handleSave}
            disabled={saving || !hasChanges}
          >
            {saving ? "Saving…" : "Save scores"}
          </button>
        </footer>
      </div>
    </div>
  );
}