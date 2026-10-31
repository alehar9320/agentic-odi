import { useMemo, type ReactNode } from "react";

import { canvasStatus } from "../../lib/canvasProvenance";
import { useStudio } from "../../state/StudioContext";
import type { WorkspacePanelId } from "../../types";
import { CompassIcon, CoverageIcon, RouteIcon, SignalIcon, SparkIcon } from "../icons";

interface RailItem {
  id: WorkspacePanelId;
  label: string;
  count: number;
  noun: string;
  icon: ReactNode;
}

/**
 * The artifacts the conversation has produced, sitting above the conversation.
 *
 * This is deliberately not a tab bar: it has no fixed destinations, it derives
 * every chip from real state, and it renders nothing until the thread has made
 * something worth looking at. Clicking a chip is the "regular click" path for
 * people who prefer it; the conversation stays exactly where it was.
 */
export function WorkbenchRail() {
  const { canvas, memory, activePanel, openPanel, closePanel } = useStudio();

  const items = useMemo<RailItem[]>(() => {
    const outcomes = canvas?.outcomes ?? [];
    const steps = canvas?.steps ?? [];
    const evidence = outcomes.filter((outcome) => outcome.evidence?.trim()).length;

    // Coverage is a count of stages that hold at least one staged outcome, not
    // a count of steps: a job can have eight steps and cover one stage. The
    // chip is derived from the canvas, so it says roughly how much of the map
    // is filled; the Coverage lens reads the server's report for the exact
    // numbers and the gaps.
    const stagedSteps = new Set(
      steps.filter((step) => step.stage).map((step) => step.id).filter(Boolean),
    );
    const coveredStages = new Set(
      outcomes
        .map((outcome) => outcome.step_id)
        .filter((stepId): stepId is string => Boolean(stepId && stagedSteps.has(stepId)))
        .map((stepId) => steps.find((step) => step.id === stepId)?.stage),
    );

    const rail: RailItem[] = [];
    if (outcomes.length > 0) {
      rail.push({
        id: "landscape",
        label: "Landscape",
        count: outcomes.length,
        noun: outcomes.length === 1 ? "opportunity" : "opportunities",
        icon: <CompassIcon size={14} />,
      });
    }
    if (steps.length > 0) {
      rail.push({
        id: "jobmap",
        label: "Job map",
        count: steps.length,
        noun: steps.length === 1 ? "step" : "steps",
        icon: <RouteIcon size={14} />,
      });
    }
    if (coveredStages.size > 0) {
      rail.push({
        id: "coverage",
        label: "Coverage",
        count: coveredStages.size,
        noun: coveredStages.size === 1 ? "stage" : "stages",
        icon: <CoverageIcon size={14} />,
      });
    }
    if (evidence > 0) {
      rail.push({
        id: "evidence",
        label: "Evidence",
        count: evidence,
        noun: evidence === 1 ? "signal" : "signals",
        icon: <SignalIcon size={14} />,
      });
    }
    if (memory.length > 0) {
      rail.push({
        id: "memory",
        label: "What I know",
        count: memory.length,
        noun: memory.length === 1 ? "note" : "notes",
        icon: <SparkIcon size={14} />,
      });
    }
    return rail;
  }, [canvas, memory]);

  const status = canvasStatus(canvas);

  if (items.length === 0 && !status) {
    return null;
  }

  return (
    <nav className="rail" aria-label="Your work">
      <ul className="rail__list">
        {status ? (
          <li>
            <span className="rail__status" title={status.detail}>
              {status.label}
            </span>
          </li>
        ) : null}
        {items.map((item) => {
          const open = activePanel === item.id;
          return (
            <li key={item.id}>
              <button
                type="button"
                className={`rail__chip${open ? " is-open" : ""}`}
                aria-current={open ? "page" : undefined}
                aria-label={`${item.label}, ${item.count} ${item.noun}`}
                onClick={() => (open ? closePanel() : openPanel(item.id))}
              >
                <span className="rail__icon" aria-hidden="true">
                  {item.icon}
                </span>
                {item.label}
                <span className="rail__count">{item.count}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
