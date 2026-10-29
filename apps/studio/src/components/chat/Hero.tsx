import { useMemo } from "react";

import { greetingCandidates } from "../../lib/greeting";
import { isUnderserved } from "../../lib/odi";
import { useOnboarding } from "../../onboarding/context";
import { useStudio } from "../../state/StudioContext";

/**
 * The empty state.
 *
 * One still sentence, a quiet aside, and nothing else: the starter prompts
 * live in the composer, where they stay reachable once the thread starts.
 */
export function Hero() {
  const { displayName, canvas, llmHealth, brief, openSetup } = useStudio();
  const { enabled: tourEnabled, openTour } = useOnboarding();

  const jobs = canvas?.jobs.length ?? 0;
  const outcomes = canvas?.outcomes.length ?? 0;
  const underserved = (canvas?.outcomes ?? []).filter((outcome) =>
    isUnderserved(outcome.opportunity_score),
  ).length;

  const candidates = useMemo(
    () =>
      greetingCandidates({
        now: new Date(),
        displayName,
        jobCount: jobs,
        outcomeCount: outcomes,
        underservedCount: underserved,
        llmHealthy: llmHealth.healthy,
        productName: brief?.product_name,
        jobStatement: brief?.job_statement,
      }),
    [
      displayName,
      jobs,
      outcomes,
      underserved,
      llmHealth.healthy,
      brief?.product_name,
      brief?.job_statement,
    ],
  );

  // A first run gets one still sentence. Changing the headline while someone is
  // deciding what to say is the opposite of focus.
  const current = candidates[0];

  return (
    <div className="hero">
      {brief?.product_name ? <p className="hero__eyebrow">{brief.product_name}</p> : null}
      <h1 className="hero__line">{current?.text ?? "What do you want to win?"}</h1>
      <p className="hero__sub">
        {brief?.target_user
          ? `For ${brief.target_user}. Tell me where they get stuck.`
          : "One sentence is enough. I'll help you test whether it's worth chasing."}
      </p>
      <div className="hero__aside">
        <button
          type="button"
          className="hero__tour"
          onClick={openSetup}
          title="Tell me about your product, audience, and job"
        >
          {brief ? "Edit context" : "Tell me what you're building"}
        </button>
        {tourEnabled ? (
          <>
            <span className="hero__aside-divider" aria-hidden="true">
              ·
            </span>
            <button type="button" className="hero__tour" onClick={openTour}>
              Show me around
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}
