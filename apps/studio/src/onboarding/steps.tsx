import { useEffect, useId, useState, type ReactElement } from "react";

import {
  formatOpportunityScore,
  isUnderserved,
  opportunityArithmetic,
  opportunityPill,
} from "../lib/odi";
import {
  sampleLoop,
  scoreSampleOutcome,
  type SampleLoop,
  type SampleOutcome,
} from "../lib/sampleLoop";
import { SCENES, type TourSceneId } from "./content";
import { BoltIcon, CompassIcon, SignalIcon, SparkIcon } from "../components/icons";
import { GOALS, type GoalIconName, type GoalId } from "./content";

/* ------------------------------------------------------------------ */
/* Shared                                                             */
/* ------------------------------------------------------------------ */

/**
 * The one label every scene carries. The sample is named as a sample wherever
 * it appears, so nothing on screen can be mistaken for the person's own work.
 */
export function SampleBadge({ detail }: { detail?: string }) {
  return (
    <p className="tour-sample" role="note">
      <span className="tour-sample__badge">Sample</span>
      <span className="tour-sample__detail">
        {detail ?? "A worked example. Nothing here is stored."}
      </span>
    </p>
  );
}

/** The brief itself, shown the same way in every scene. */
export function SampleBriefCard({ loop }: { loop: SampleLoop }) {
  return (
    <div className="tour-brief">
      <p className="tour-brief__job">{loop.job.name}</p>
      <blockquote className="tour-brief__quote">“{loop.quote.content}”</blockquote>
      <p className="tour-brief__source">{loop.quote.source_name}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Scene 1 — hear it: a quote becomes an outcome                      */
/* ------------------------------------------------------------------ */

/**
 * Scene one asks the only question that matters about a quote — what is this
 * person trying to get done? — and the three answers are a job, a workaround,
 * and a solution in disguise. A wrong pick is named for what it is and the
 * person tries again; the right one reveals the job and the outcome it implies.
 * The evidence record is the quote, and the outcome links back to it.
 */
export function HearScene({ loop = sampleLoop() }: { loop?: SampleLoop }) {
  const [chosenId, setChosenId] = useState<string | null>(null);
  const questionId = useId();
  const chosen = loop.interpretations.find((option) => option.id === chosenId) ?? null;
  const correct = chosen?.kind === "job";

  // 1 / 2 / 3 choose an answer, so the scene is completable from the keyboard.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      const index = Number(event.key) - 1;
      if (Number.isInteger(index) && index >= 0 && index < loop.interpretations.length) {
        event.preventDefault();
        setChosenId(loop.interpretations[index].id);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [loop.interpretations]);

  return (
    <>
      <SampleBadge />
      <SampleBriefCard loop={loop} />

      <p className="tour-question" id={questionId}>
        What is this person trying to get done?
      </p>
      <div className="tour-answers" role="group" aria-labelledby={questionId}>
        {loop.interpretations.map((option, index) => {
          const selected = option.id === chosenId;
          const state = selected ? (option.kind === "job" ? " is-correct" : " is-wrong") : "";
          return (
            <button
              key={option.id}
              type="button"
              className={`tour-answer${selected ? " is-chosen" : ""}${state}`}
              aria-pressed={selected}
              onClick={() => setChosenId(option.id)}
            >
              <span className="tour-answer__key" aria-hidden="true">
                {index + 1}
              </span>
              <span className="tour-answer__text">{option.text}</span>
            </button>
          );
        })}
      </div>

      {chosen ? (
        <p
          className={`tour-verdict${correct ? " is-correct" : " is-wrong"}`}
          role="status"
        >
          {chosen.verdict}
        </p>
      ) : (
        <p className="wizard-hint">Choose one. A wrong pick costs nothing — try again.</p>
      )}

      {correct ? (
        <div className="tour-records">
          <div className="tour-record">
            <p className="tour-record__kind">Evidence record</p>
            <p className="tour-record__value">“{loop.quote.content}”</p>
            <p className="tour-record__meta">Source: {loop.quote.source_name}</p>
          </div>
          <div className="tour-record">
            <p className="tour-record__kind">Outcome record — linked to the evidence</p>
            <p className="tour-record__value">{loop.outcome.statement}</p>
            <p className="tour-record__meta">
              Evidence {loop.quote.id} → outcome {loop.outcome.id}
            </p>
          </div>
        </div>
      ) : null}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Scene 2 — score it: two numbers become a scored outcome            */
/* ------------------------------------------------------------------ */

/**
 * Scene two scores the outcome with the real formula, shown as arithmetic before
 * it is shown as a number. The two sliders are the only inputs, and the label
 * flips at the threshold the rest of the studio uses.
 */
export function ScoreScene({ loop = sampleLoop() }: { loop?: SampleLoop }) {
  const [importance, setImportance] = useState(9);
  const [satisfaction, setSatisfaction] = useState(3);
  const prefix = useId();

  const scored: SampleOutcome = scoreSampleOutcome(importance, satisfaction);
  const score = scored.opportunity_score ?? 0;
  const underserved = isUnderserved(score);
  const pill = opportunityPill(score);

  return (
    <>
      <SampleBadge />
      <p className="tour-brief__job">{loop.outcome.statement}</p>

      <div className="tour-sliders">
        <label className="tour-slider" htmlFor={`${prefix}-importance`}>
          <span className="tour-slider__name">Importance</span>
          <span className="tour-slider__value">{importance}</span>
          <input
            id={`${prefix}-importance`}
            type="range"
            min={1}
            max={10}
            step={1}
            value={importance}
            onChange={(event) => setImportance(Number(event.target.value))}
          />
        </label>
        <label className="tour-slider" htmlFor={`${prefix}-satisfaction`}>
          <span className="tour-slider__name">Satisfaction</span>
          <span className="tour-slider__value">{satisfaction}</span>
          <input
            id={`${prefix}-satisfaction`}
            type="range"
            min={1}
            max={10}
            step={1}
            value={satisfaction}
            onChange={(event) => setSatisfaction(Number(event.target.value))}
          />
        </label>
      </div>

      <p className="tour-score__arithmetic" aria-live="polite">
        {opportunityArithmetic(importance, satisfaction)}
      </p>
      <p className="tour-score__number">
        <span className="tour-score__label">Opportunity</span>{" "}
        <b>{formatOpportunityScore(score)}</b>{" "}
        <span
          className={`tour-score__band${underserved ? " is-underserved" : " is-served"}`}
        >
          {pill.label}
        </span>
      </p>
      <p className="wizard-hint">
        The score is a sorting device, not a verdict. Drag satisfaction up and the label
        changes where the score crosses the threshold of 10.
      </p>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Scene 3 — place it                                                 */
/* ------------------------------------------------------------------ */

export function PlaceScene({ loop = sampleLoop() }: { loop?: SampleLoop }) {
  return (
    <>
      <SampleBadge />
      <div className="tour-brief">
        <p className="tour-brief__job">{loop.outcome.statement}</p>
      </div>
      <ul className="tour-missing">
        {loop.missingEvidence.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Router                                                             */
/* ------------------------------------------------------------------ */

const SCENE_COMPONENTS: Record<TourSceneId, () => ReactElement> = {
  hear: () => <HearScene />,
  score: () => <ScoreScene />,
  place: () => <PlaceScene />,
};

export function TourSceneBody({ scene }: { scene: number }) {
  const index = Math.min(Math.max(scene, 0), SCENES.length - 1);
  const Component = SCENE_COMPONENTS[SCENES[index].id];
  return <Component />;
}
