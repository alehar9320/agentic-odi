import { useMemo } from "react";

import { greetingCandidates } from "../../lib/greeting";
import { isUnderserved } from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";

/**
 * The empty state.
 */
export function Hero() {
  const { displayName, canvas, llmHealth, brief, openSetup } = useStudio();

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

  const current = candidates[0];

  return (
    <div className="hero">
      {brief?.product_name ? <p className="hero__eyebrow">{brief.product_name}</p> : null}
      <h1 className="hero__line">
        {current?.text ?? "Good morning"}
      </h1>
      <p className="hero__sub">
        {brief?.target_user
          ? `For ${brief.target_user}. Tell me where they get stuck, and we'll turn it into something you can defend.`
          : "Name what you're trying to win. I'll help you test whether it's worth it — and what to do next."}
      </p>
      <div className="hero__actions">
        <button
          type="button"
          className="suggestion suggestion--quiet"
          onClick={openSetup}
          title="Tell me about your product, audience, and job"
        >
          {brief ? "Edit context" : "Tell me what you're building"}
        </button>
      </div>
    </div>
  );
}
