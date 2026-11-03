import { useState } from "react";

import {
  SAMPLE_LOOP,
  readSampleLoopDismissed,
  sampleSegmentLabel,
  writeSampleLoopDismissed,
} from "../../lib/sampleLoop";

/**
 * The empty stage's worked example: one finished ODI loop, labelled a sample.
 *
 * A person who has never seen the method run gets the whole pass at once — the
 * customer's words, the outcome they imply, the score two numbers produce, and
 * the evidence still missing — without starting anything. Nothing here is
 * fetched, written, or counted: the strip renders from `SAMPLE_LOOP` and its
 * only side effect is the dismissal key the person sets with **Hide**.
 */
export function SampleLoopStrip({
  onStartOwn,
}: {
  /** Focus the composer and offer a starting placeholder. Sends nothing. */
  onStartOwn: () => void;
}) {
  const [hidden, setHidden] = useState(() => readSampleLoopDismissed());

  if (hidden) {
    return null;
  }

  function hide() {
    writeSampleLoopDismissed();
    setHidden(true);
  }

  return (
    <section className="sample-loop" aria-label="Sample loop, not your data">
      <p className="sample-loop__head">
        <span className="sample-loop__label">Sample, not your data.</span>
        <span className="sample-loop__chip">SAMPLE</span>
      </p>

      <div className="sample-loop__band">
        <div className="sample-loop__beat">
          <p className="sample-loop__quote">“{SAMPLE_LOOP.quote}”</p>
          <p className="sample-loop__source">{SAMPLE_LOOP.sourceLabel}</p>
        </div>

        <div className="sample-loop__beat">
          <p className="sample-loop__outcome">{SAMPLE_LOOP.outcome}</p>
          <p className="sample-loop__values">
            Importance <b>{SAMPLE_LOOP.importance}</b>
            <span aria-hidden="true"> · </span>
            Satisfaction <b>{SAMPLE_LOOP.satisfaction}</b>
            <span aria-hidden="true"> · </span>
            Opportunity <b className="sample-loop__score">{SAMPLE_LOOP.score}</b>
          </p>
          <p className="sample-loop__segment">{sampleSegmentLabel()}</p>
        </div>

        <div className="sample-loop__beat">
          <p className="sample-loop__gap-title">What's missing</p>
          <ul className="sample-loop__gap">
            {SAMPLE_LOOP.missing.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="sample-loop__actions">
        <button type="button" className="sample-loop__start" onClick={onStartOwn}>
          Start with my own
        </button>
        <button type="button" className="sample-loop__hide" onClick={hide}>
          Hide
        </button>
      </div>
    </section>
  );
}
