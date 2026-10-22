import { useMemo, useState } from "react";

import { useStudio } from "../../state/StudioContext";
import type { Observation, ObservationKind, ObservationStatus } from "../../types";

const KIND_LABELS: Record<ObservationKind, string> = {
  career: "Your role",
  opportunity: "The opportunity",
  business: "The business",
  stakeholder: "A stakeholder",
  constraint: "A constraint",
  evidence: "Evidence",
  preference: "How you work",
};

function byStatus(a: Observation, b: Observation): number {
  if (a.status !== b.status) {
    return a.status === "suggested" ? -1 : 1;
  }
  return a.created_at.localeCompare(b.created_at);
}

/**
 * What the agent believes about the person and the work, in plain sentences.
 *
 * Every line is either confirmed or explicitly a guess, so trust is earned by
 * correction rather than by a settings screen.
 */
export function MemoryPanel() {
  const { memory, memoryLoading, updateObservation, deleteObservation, clearMemory } = useStudio();
  const [confirmingClear, setConfirmingClear] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const items = useMemo(() => [...memory].sort(byStatus), [memory]);
  const suggested = items.filter((item) => item.status === "suggested");
  const confirmed = items.filter((item) => item.status === "confirmed");

  async function decide(observation: Observation, status: ObservationStatus) {
    setBusyId(observation.id);
    await updateObservation(observation.id, { status });
    setBusyId(null);
  }

  async function forget(observation: Observation) {
    setBusyId(observation.id);
    await deleteObservation(observation.id);
    setBusyId(null);
  }

  return (
    <div className="stack memory-panel">
      {memoryLoading && items.length === 0 && (
        <p className="memory-empty">Reading back what I've learned…</p>
      )}

      {!memoryLoading && items.length === 0 && (
        <div className="memory-empty">
          <p className="memory-empty__title">Nothing yet.</p>
          <p>
            As we talk, I'll note what matters about you, the work, and what you've learned. You
            can correct any of it here.
          </p>
        </div>
      )}

      {suggested.length > 0 && (
        <section className="memory-group" aria-label="Not confirmed yet">
          <h3 className="memory-group__title">Did I get this right?</h3>
          <ul className="memory-list">
            {suggested.map((observation) => (
              <li key={observation.id} className="memory-item memory-item--suggested">
                <p className="memory-item__kind">{KIND_LABELS[observation.kind]}</p>
                <p className="memory-item__text">{observation.text}</p>
                <div className="memory-item__actions">
                  <button
                    type="button"
                    className="button button--ghost memory-item__button"
                    disabled={busyId === observation.id}
                    onClick={() => void decide(observation, "confirmed")}
                  >
                    Yes, that's right
                  </button>
                  <button
                    type="button"
                    className="quiet-action quiet-action--danger"
                    disabled={busyId === observation.id}
                    onClick={() => void decide(observation, "dismissed")}
                  >
                    That's not it
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {confirmed.length > 0 && (
        <section className="memory-group" aria-label="Confirmed">
          <h3 className="memory-group__title">What I'm working from</h3>
          <ul className="memory-list">
            {confirmed.map((observation) => (
              <li key={observation.id} className="memory-item">
                <div className="memory-item__head">
                  <p className="memory-item__kind">{KIND_LABELS[observation.kind]}</p>
                  <button
                    type="button"
                    className="quiet-action"
                    aria-label={`Forget ${observation.text}`}
                    disabled={busyId === observation.id}
                    onClick={() => void forget(observation)}
                  >
                    Forget
                  </button>
                </div>
                <p className="memory-item__text">{observation.text}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer className="memory-foot">
        <p className="memory-foot__note">
          Wrong or missing something? Say so in the conversation and I'll fix it.
        </p>
        {items.length > 0 &&
          (confirmingClear ? (
            <div className="memory-foot__confirm">
              <p>Forget everything, including this thread?</p>
              <div className="memory-foot__actions">
                <button
                  type="button"
                  className="button button--danger"
                  onClick={() => {
                    setConfirmingClear(false);
                    void clearMemory();
                  }}
                >
                  Forget everything
                </button>
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={() => setConfirmingClear(false)}
                >
                  Keep it
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="quiet-action quiet-action--danger"
              onClick={() => setConfirmingClear(true)}
            >
              Forget everything
            </button>
          ))}
      </footer>
    </div>
  );
}
