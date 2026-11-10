import { useEffect, useState } from "react";

import {
  UNDERSERVED_THRESHOLD,
  formatOpportunityScore,
  hasScore,
  isUnderserved,
  opportunityScore,
} from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import type { Outcome } from "../../types";

interface ScorePopoverProps {
  outcome: Outcome;
  isOpen: boolean;
  onClose: () => void;
}

const MISMATCH_THRESHOLD = 0.05;

export function ScorePopover({ outcome, isOpen, onClose }: ScorePopoverProps) {
  const { updateOutcome } = useStudio();

  const storedScore = outcome.opportunity_score;
  const initialImportance = outcome.importance ?? 5;
  const initialSatisfaction = outcome.satisfaction ?? 5;

  const [importance, setImportance] = useState(initialImportance);
  const [satisfaction, setSatisfaction] = useState(initialSatisfaction);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const computedScore = opportunityScore(importance, satisfaction);
  const gap = computedScore - UNDERSERVED_THRESHOLD;
  const isComputedUnderserved = isUnderserved(computedScore);
  const storedMinusComputed = hasScore(storedScore) ? storedScore! - computedScore : null;
  const hasMismatch = storedMinusComputed != null && Math.abs(storedMinusComputed) > MISMATCH_THRESHOLD;

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      onClose();
    }
  }

  useEffect(() => {
    if (!isOpen) return;
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, handleKeyDown]);

  function handleSave() {
    if (!outcome.id || saving) {
      return;
    }
    setSaving(true);
    setError(null);
    updateOutcome(outcome.id, { importance, satisfaction })
      .then(() => {
        onClose();
      })
      .catch((err: Error) => {
        setError(err.message || "Could not save scores");
      })
      .finally(() => {
        setSaving(false);
      });
  }

  function handleRecompute() {
    if (!outcome.id || saving) {
      return;
    }
    setSaving(true);
    setError(null);
    updateOutcome(outcome.id, { importance, satisfaction })
      .then(() => {
        onClose();
      })
      .catch((err: Error) => {
        setError(err.message || "Could not recompute score");
      })
      .finally(() => {
        setSaving(false);
      });
  }

  if (!isOpen) return null;

  return (
    <div className="score-popover-overlay fade-in">
      <button
        type="button"
        className="score-popover-scrim"
        aria-label="Close score editor (background)"
        tabIndex={-1}
        onClick={onClose}
      />
      <div
        className="score-popover"
        role="dialog"
        aria-modal="true"
        aria-labelledby="score-popover-title"
      >
        <header className="score-popover__header">
          <div>
            <div className="score-popover__badge">SCORE EDITOR</div>
            <h2 id="score-popover-title" className="score-popover__title">
              Adjust Assumptions
            </h2>
            <p className="score-popover__statement">{outcome.statement ?? "Untitled outcome"}</p>
          </div>
          <button
            type="button"
            className="score-popover__close"
            onClick={onClose}
            aria-label="Close score editor (button)"
          >
            ✕
          </button>
        </header>

        <div className="score-popover__body">
          <div className="score-popover__sliders">
            <label className="score-popover__slider" htmlFor={`importance-${outcome.id}`}>
              <span className="score-popover__slider-label">
                Importance · <b>{importance.toFixed(1)}</b>
              </span>
              <input
                id={`importance-${outcome.id}`}
                type="range"
                min={1}
                max={10}
                step={0.1}
                value={importance}
                onChange={(e) => setImportance(Number(e.target.value))}
                disabled={saving}
              />
              <input
                type="number"
                min={1}
                max={10}
                step={0.1}
                value={importance.toFixed(1)}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  if (!Number.isNaN(val) && val >= 1 && val <= 10) {
                    setImportance(val);
                  }
                }}
                disabled={saving}
                className="score-popover__number-input"
                aria-label="Importance value"
              />
            </label>

            <label className="score-popover__slider" htmlFor={`satisfaction-${outcome.id}`}>
              <span className="score-popover__slider-label">
                Satisfaction · <b>{satisfaction.toFixed(1)}</b>
              </span>
              <input
                id={`satisfaction-${outcome.id}`}
                type="range"
                min={1}
                max={10}
                step={0.1}
                value={satisfaction}
                onChange={(e) => setSatisfaction(Number(e.target.value))}
                disabled={saving}
              />
              <input
                type="number"
                min={1}
                max={10}
                step={0.1}
                value={satisfaction.toFixed(1)}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  if (!Number.isNaN(val) && val >= 1 && val <= 10) {
                    setSatisfaction(val);
                  }
                }}
                disabled={saving}
                className="score-popover__number-input"
                aria-label="Satisfaction value"
              />
            </label>
          </div>

          <div className="score-popover__arithmetic">
            <div className="score-popover__formula">
              <span className="score-popover__formula-label">Opportunity</span>
              <span className="score-popover__formula-value" data-testid="score-popover-formula-value">
                {importance.toFixed(1)} + max({importance.toFixed(1)} − {satisfaction.toFixed(1)}, 0)
                = <b>{formatOpportunityScore(computedScore)}</b>
              </span>
            </div>
            <div
              className={`score-popover__gap ${isComputedUnderserved ? "score-popover__gap--underserved" : ""}`}
            >
              <span className="score-popover__gap-label">
                Gap to underserved threshold (10.0)
              </span>
              <span className="score-popover__gap-value">
                {gap > 0 ? "+" : ""}{gap.toFixed(1)}
              </span>
            </div>
            <div className={`score-popover__verdict ${isComputedUnderserved ? "score-popover__verdict--underserved" : ""}`}>
              {isComputedUnderserved ? "🔥 Underserved" : "✓ Served"}
            </div>
          </div>

          {hasMismatch && (
            <div className="score-popover__mismatch" role="status">
              <span className="score-popover__mismatch-icon">⚠</span>
              <div className="score-popover__mismatch-content">
                <p className="score-popover__mismatch-message">
                  Stored score ({formatOpportunityScore(storedScore)}) differs from its inputs
                  ({formatOpportunityScore(computedScore)}).
                </p>
                <p className="score-popover__mismatch-hint">
                  The server returns its recomputed value on save. Press <b>Recompute</b> to send the
                  current inputs, or edit and press <b>Save</b>.
                </p>
              </div>
            </div>
          )}

          {error && (
            <div className="score-popover__error" role="alert">
              {error}
            </div>
          )}
        </div>

        <footer className="score-popover__footer">
          <button
            type="button"
            className="studio-button studio-button--ghost"
            onClick={onClose}
            disabled={saving}
          >
            Cancel
          </button>
          {hasMismatch ? (
            <button
              type="button"
              className="studio-button"
              onClick={handleRecompute}
              disabled={saving}
            >
              {saving ? "Recomputing…" : "Recompute"}
            </button>
          ) : (
            <button
              type="button"
              className="studio-button"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? "Saving…" : "Save"}
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}