import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  GREETING_ROTATION_MS,
  greetingCandidates,
  nextGreeting,
} from "../../lib/greeting";
import { isUnderserved } from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import { BoltIcon, CaptureIcon, CompassIcon, SparkIcon } from "../icons";

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

const OPPORTUNITY_PROMPT =
  "I have an opportunity in mind. Ask me what it is, then help me sharpen it into something I can defend.";
const FIND_PROMPT =
  "I need to find the next opportunity worth chasing. Help me look across what I know about my customers and find the gap that matters most.";
const PRESSURE_TEST_PROMPT =
  "I have a bet I'm about to make. Pressure-test it with me: ask what it is, then tell me what would have to be true and what evidence I'm missing.";
const CAPTURE_PROMPT =
  "I heard something from a customer that I want to make sense of. Ask me what they said, then help me turn it into something we can act on.";

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
      id: "sharpen",
      label: "Sharpen an opportunity",
      icon: <SparkIcon size={15} />,
      run: () => onSubmit(OPPORTUNITY_PROMPT),
      conversational: true,
    },
    outcomes > 0
      ? {
          id: "pressure-test",
          label: "Pressure-test a bet",
          icon: <BoltIcon size={15} />,
          run: () => onSubmit(PRESSURE_TEST_PROMPT),
          conversational: true,
        }
      : {
          id: "find",
          label: "Find the next opportunity",
          icon: <CompassIcon size={15} />,
          run: () => onSubmit(FIND_PROMPT),
          conversational: true,
        },
    jobs > 0
      ? {
          id: "capture",
          label: "Capture what you heard",
          icon: <CaptureIcon size={15} />,
          run: () =>
            llmHealth.healthy === false
              ? openPanel("capture")
              : onSubmit(CAPTURE_PROMPT),
          conversational: true,
        }
      : {
          id: "landscape",
          label: "Opportunity landscape",
          icon: <CompassIcon size={15} />,
          run: () => openPanel("landscape"),
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
          ? `For ${brief.target_user}. Tell me where they get stuck, and we'll turn it into something you can defend.`
          : "Name what you're trying to win. I'll help you test whether it's worth it — and what to do next."}
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
