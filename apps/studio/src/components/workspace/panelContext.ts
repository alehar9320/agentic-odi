import { JOB_STAGES } from "../../domain/jobStages";
import type { Detail } from "../../state/regions";
import type { CanvasData } from "../../types";

/**
 * The "Step 2 of 4 • Setup & team invites" line a detail's header carries.
 *
 * The line is only ever built from a real `Step.order`/`Step.name`, or — when
 * the canvas has no step for that position — from the generated `JOB_STAGES`
 * catalog. It returns `null` when nothing real backs it, so the header omits
 * the line instead of inventing one (#740).
 */
export function stepContextLine(detail: Detail | null, canvas: CanvasData | null): string | null {
  const subject = detail?.subject;
  if (!subject || subject.kind !== "step") {
    return null;
  }
  const steps = canvas?.steps ?? [];
  const step = steps.find((candidate) => candidate.id === subject.id);
  if (!step || step.order == null) {
    return null;
  }
  const total = steps.length > 0 ? steps.length : JOB_STAGES.length;
  const name = step.name?.trim() || JOB_STAGES[step.order - 1]?.name;
  if (!name) {
    return null;
  }
  return `Step ${step.order} of ${total} • ${name}`;
}
