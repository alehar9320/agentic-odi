import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  GREETING_ROTATION_MS,
  greetingCandidates,
  nextGreeting,
} from "../../lib/greeting";
import { isUnderserved } from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import { BoltIcon, CaptureIcon, CompassIcon, RouteIcon, SparkIcon } from "../icons";

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

const DEFINE_JOB_PROMPT =
  "Help me define a job-to-be-done my customers are trying to get done.";
const GUIDELINES_PROMPT = "Walk me through the ODI stage-by-stage guidelines.";

interface HeroPill {
  id: string;
  label: string;
  icon: ReactNode;
  run: () => void;
  conversational?: boolean;
}

export function Hero({ onSubmit }: { onSubmit: (text: string) => void }) {
  const { displayName, canvas, llmHealth, openPanel, streaming, brief, openSetup } =
    useStudio();
  const [now, setNow] = useState(() => new Date());
  const [currentId, setCurrentId] = useState<string | null>(null);

  const jobs = canvas?.jobs.length ?? 0;
  const outcomes = canvas?.outcomes.length ?? 0;
  const underserved = (canvas?.outcomes ?? []).filter((outcome) =>
    isUnderserved(outcome.opportunity_score),
  ).length;

  const candidates = useMemo(
    () =>
      greetingCandidates({
        now,
        displayName,
        jobCount: jobs,
        outcomeCount: outcomes,
        underservedCount: underserved,
        llmHealthy: llmHealth.healthy,
        productName: brief?.product_name,
        jobStatement: brief?.job_statement,
      }),
    [
      now,
      displayName,
      jobs,
      outcomes,
      underserved,
      llmHealth.healthy,
      brief?.product_name,
      brief?.job_statement,
    ],
  );

  const current = candidates.find((candidate) => candidate.id === currentId) ?? candidates[0];

  useEffect(() => {
    if (prefersReducedMotion()) {
      return;
    }
    const timer = window.setInterval(() => {
      if (typeof document !== "undefined" && document.hidden) {
        return;
      }
      setNow(new Date());
      setCurrentId((id) => nextGreeting(candidates, id ?? current?.id)?.id ?? null);
    }, GREETING_ROTATION_MS);
    return () => window.clearInterval(timer);
  }, [candidates, current?.id]);

  const pills: HeroPill[] = [
    {
      id: "define-job",
      label: "Define a job",
      icon: <SparkIcon size={15} />,
      run: () => onSubmit(DEFINE_JOB_PROMPT),
      conversational: true,
    },
    {
      id: "landscape",
      label: "Opportunity landscape",
      icon: <CompassIcon size={15} />,
      run: () => openPanel("landscape"),
    },
    outcomes > 0
      ? {
          id: "impact",
          label: "Simulate a bet",
          icon: <BoltIcon size={15} />,
          run: () =>
            onSubmit(
              "Simulate the impact of a bet on my most underserved opportunity. " +
                "Ask me what the bet is, then show me what changes before and after.",
            ),
          conversational: true,
        }
      : {
          id: "guidelines",
          label: "ODI guidelines",
          icon: <BoltIcon size={15} />,
          run: () => onSubmit(GUIDELINES_PROMPT),
          conversational: true,
        },
    jobs > 0
      ? {
          id: "capture",
          label: "Capture an outcome",
          icon: <CaptureIcon size={15} />,
          run: () =>
            llmHealth.healthy === false
              ? openPanel("capture")
              : onSubmit(
                  "I want to capture an outcome I heard from a customer. " +
                    "Ask me what they said, then help me sharpen it.",
                ),
          conversational: true,
        }
      : {
          id: "jobmap",
          label: "Job map",
          icon: <RouteIcon size={15} />,
          run: () => openPanel("jobmap"),
        },
  ];

  return (
    <div className="hero">
      <p className="hero__eyebrow">
        {brief?.product_name ? `Living Studio · ${brief.product_name}` : "Living Studio"}
      </p>
      <h1 className="hero__line" key={current?.id ?? "greeting"}>
        {current?.text ?? "Good morning"}
      </h1>
      <p className="hero__sub">
        {brief?.target_user
          ? `For ${brief.target_user}. Tell me where they get stuck, and we will turn it into a measurable outcome.`
          : "Think in outcomes, not tickets. Tell me what you're building and I'll keep it in mind — or just start anywhere."}
      </p>
      <div className="hero__pills" aria-label="Suggested next steps">
        {pills.map((pill) => (
          <button
            key={pill.id}
            type="button"
            className="suggestion"
            disabled={Boolean(pill.conversational && streaming)}
            onClick={pill.run}
          >
            {pill.icon}
            {pill.label}
          </button>
        ))}
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
