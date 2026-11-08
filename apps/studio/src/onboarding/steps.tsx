import type { ReactElement } from "react";

import { sampleLoop, type SampleLoop } from "../lib/sampleLoop";
import { SCENES, type TourSceneId } from "./content";

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
/* Scene 1 — hear it                                                  */
/* ------------------------------------------------------------------ */

export function HearScene({ loop = sampleLoop() }: { loop?: SampleLoop }) {
  return (
    <>
      <SampleBadge />
      <SampleBriefCard loop={loop} />
      <p className="wizard-hint">
        The next slice turns this into the three paraphrases a person chooses from.
      </p>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Scene 2 — score it                                                 */
/* ------------------------------------------------------------------ */

export function ScoreScene({ loop = sampleLoop() }: { loop?: SampleLoop }) {
  return (
    <>
      <SampleBadge />
      <div className="tour-brief">
        <p className="tour-brief__job">{loop.outcome.statement}</p>
      </div>
      <p className="wizard-hint">
        The next slice adds the two sliders and scores this outcome live.
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
