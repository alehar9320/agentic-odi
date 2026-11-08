import { sampleLoop } from "../lib/sampleLoop";

/* ------------------------------------------------------------------ */
/* Shared                                                             */
/* ------------------------------------------------------------------ */

/**
 * The one word that keeps a rehearsal from reading as the person's own work.
 * Every scene shows it, because the sample must be labelled everywhere.
 */
export function SampleBadge() {
  return <span className="tour-sample">Sample</span>;
}

/* ------------------------------------------------------------------ */
/* Scene 1 — hear it                                                  */
/* ------------------------------------------------------------------ */

/**
 * The quote as a transcript would show it: the words, then where they came
 * from. The question that follows ("what is this person trying to get done?")
 * is the interactive work of #594; this slice shows the sample it runs on.
 */
export function HearScene() {
  const sample = sampleLoop();
  return (
    <figure className="tour-quote">
      <SampleBadge />
      <blockquote className="tour-quote__text">{sample.quote.text}</blockquote>
      <figcaption className="tour-quote__source">
        {sample.quote.source}
        <span className="tour-quote__job"> · {sample.job.statement}</span>
      </figcaption>
    </figure>
  );
}

/* ------------------------------------------------------------------ */
/* Scene 2 — score it                                                 */
/* ------------------------------------------------------------------ */

/**
 * The outcome the quote implies, unscored. The two sliders that compute a
 * score and show the arithmetic are #594; this slice shows what they will act
 * on, and says plainly that the number is not here yet.
 */
export function ScoreScene() {
  const sample = sampleLoop();
  return (
    <div className="tour-outcome">
      <SampleBadge />
      <p className="tour-outcome__statement">{sample.outcome.statement}</p>
      <p className="tour-outcome__next">
        The next slice adds the two sliders that score this outcome and show the
        arithmetic behind the number.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Scene 3 — place it                                                 */
/* ------------------------------------------------------------------ */

/**
 * Where the outcome lands, and what evidence is still missing. The landscape
 * and the keep/clear choice are #595; the missing-evidence list is the one
 * honest thing this slice can already show.
 */
export function PlaceScene() {
  const sample = sampleLoop();
  return (
    <div className="tour-outcome">
      <SampleBadge />
      <p className="tour-outcome__statement">{sample.outcome.statement}</p>
      <p className="tour-outcome__label">What is still missing</p>
      <ul className="tour-missing">
        {sample.missing_evidence.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <p className="tour-outcome__next">
        The next slice draws the landscape this outcome sits on, and the one
        choice that keeps or clears the sample.
      </p>
    </div>
  );
}
