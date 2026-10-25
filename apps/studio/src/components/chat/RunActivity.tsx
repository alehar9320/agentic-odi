/**
 * The run, as it happens.
 *
 * A streaming reply with no visible work is indistinguishable from a stalled
 * one, so while a turn is live the studio names the step it is on. When the turn
 * settles the timeline collapses to a single line — the detail stays available,
 * but it stops competing with the answer.
 */

import { activityLabel, formatDuration, runSummary, stepLabel, type RunStep } from "../../lib/run";
import { AlertIcon, CheckIcon, StopIcon } from "../icons";

function StepStatus({ status }: { status: RunStep["status"] }) {
  if (status === "running") {
    return <span className="run__pulse" aria-hidden="true" />;
  }
  if (status === "error") {
    return <AlertIcon size={12} />;
  }
  if (status === "stopped") {
    return <StopIcon size={12} />;
  }
  return <CheckIcon size={12} />;
}

function stepStatusText(step: RunStep): string {
  if (step.status === "running") {
    return "in progress";
  }
  if (step.status === "error") {
    return "failed";
  }
  if (step.status === "stopped") {
    return "stopped";
  }
  return "done";
}

function StepList({ steps }: { steps: RunStep[] }) {
  return (
    <ul className="run__steps">
      {steps.map((step) => (
        <li className={`run__step run__step--${step.status}`} key={step.id}>
          <span className="run__mark" aria-hidden="true">
            <StepStatus status={step.status} />
          </span>
          <span className="run__label">
            {stepLabel(step.name)}
            <span className="sr-only">, {stepStatusText(step)}</span>
          </span>
          {step.endedAt !== undefined ? (
            <span className="run__time" aria-hidden="true">
              {formatDuration(step.endedAt - step.startedAt)}
            </span>
          ) : null}
          {step.preview ? (
            <span className="run__preview" title={step.preview}>
              {step.preview}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function RunActivity({
  steps,
  live,
  phase,
}: {
  steps: RunStep[];
  /** True while this turn is still streaming. */
  live: boolean;
  /** The sidecar's stage, used before the first tool call arrives. */
  phase: string | null;
}) {
  if (!steps.length) {
    return null;
  }

  if (live) {
    return (
      <div className="run run--live">
        <p className="run__now" role="status">
          <span className="run__pulse" aria-hidden="true" />
          <span>{activityLabel(phase, steps)}…</span>
        </p>
        <StepList steps={steps} />
      </div>
    );
  }

  const settledAt = Math.max(...steps.map((step) => step.endedAt ?? step.startedAt));

  return (
    <details className="run run--settled">
      <summary className="run__summary">
        <span className="run__summary-text">{runSummary(steps, settledAt)}</span>
      </summary>
      <StepList steps={steps} />
    </details>
  );
}
