import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useAuiState } from "@assistant-ui/react";

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

const PILL_ICONS: ReactNode[] = [
  <SparkIcon size={15} key="spark" />,
  <BoltIcon size={15} key="bolt" />,
  <CaptureIcon size={15} key="capture" />,
];

interface HeroPill {
  id: string;
  label: string;
  icon: ReactNode;
  run: () => void;
  conversational?: boolean;
}

/**
 * The empty state.
 *
 * The starter prompts are the runtime's: `suggestions` on the external store is
 * the one place they are decided, so what the hero offers and what the thread
 * knows cannot drift apart.
 */
export function Hero() {
  const { displayName, canvas, llmHealth, openPanel, streaming, brief, openSetup, sendMessage } =
    useStudio();
  const suggestions = useAuiState((state) => state.thread.suggestions);
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

  const pills: HeroPill[] = suggestions.map((suggestion, index) => ({
    id: `suggestion-${index}`,
    label: suggestion.title ?? suggestion.prompt,
    icon: PILL_ICONS[index % PILL_ICONS.length],
    run: () => void sendMessage(suggestion.prompt),
    conversational: true,
  }));

  pills.push(
    jobs > 0 && llmHealth.healthy === false
      ? {
          id: "capture",
          label: "Capture what you heard",
          icon: <CaptureIcon size={15} />,
          run: () => openPanel("capture"),
        }
      : {
          id: "landscape",
          label: "Opportunity landscape",
          icon: <CompassIcon size={15} />,
          run: () => openPanel("landscape"),
        },
  );

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
