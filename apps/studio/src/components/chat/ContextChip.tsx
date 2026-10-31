/**
 * The composer's copy of what the agent is pointed at.
 *
 * Focus lives on the workspace lenses; the chip repeats it where a message gets
 * written, so the person can see the record an answer will be about and jump
 * back to it. The name is always read off the board — when the board does not
 * hold the record, the chip says so with the id rather than inventing a title.
 */

import { useStudio } from "../../state/StudioContext";
import type { CanvasData, SignalSubjectKind } from "../../types";

const KIND_LABEL: Record<SignalSubjectKind, string> = {
  job: "Job",
  step: "Step",
  outcome: "Outcome",
  evidence: "Evidence",
  connector: "Connector",
  agent_work: "Agent work",
  segment: "Segment",
  strategy: "Strategy",
};

const CHIP_HELP = "Opens the record the agent is pointed at.";

function subjectName(subject: { kind: SignalSubjectKind; id: string }, canvas: CanvasData | null) {
  if (!canvas) {
    return subject.id;
  }
  if (subject.kind === "job") {
    return canvas.jobs.find((job) => job.id === subject.id)?.name ?? subject.id;
  }
  if (subject.kind === "step") {
    return canvas.steps.find((step) => step.id === subject.id)?.name ?? subject.id;
  }
  if (subject.kind === "outcome") {
    return canvas.outcomes.find((outcome) => outcome.id === subject.id)?.statement ?? subject.id;
  }
  if (subject.kind === "evidence") {
    const item = (canvas.evidence ?? []).find((record) => record.id === subject.id);
    return item?.name ?? item?.source_name ?? subject.id;
  }
  return subject.id;
}

export function ContextChip() {
  const { focusedSubject, canvas, revealSubject } = useStudio();

  if (!focusedSubject) {
    return null;
  }

  const kindLabel = KIND_LABEL[focusedSubject.kind] ?? focusedSubject.kind;
  const name = subjectName(focusedSubject, canvas);

  return (
    <button
      type="button"
      className="context-chip"
      aria-label={`Agent context: ${kindLabel} ${name}. Open it.`}
      title={CHIP_HELP}
      onClick={() => revealSubject(focusedSubject.kind, focusedSubject.id)}
    >
      <span className="context-chip__kind">{kindLabel}</span>
      <span className="context-chip__name">{name}</span>
    </button>
  );
}
