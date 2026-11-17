import { useMemo } from "react";
import { useStudio } from "../../state/StudioContext";
import { derivePlan } from "../../assistant/plan";

export function PlanPanel() {
  const { canvasState } = useStudio();
  const plan = useMemo(() => derivePlan(canvasState), [canvasState]);
  const hasProgress = plan.some((entry) => entry.records > 0);
  if (!hasProgress) {
    return null;
  }

  const visible = plan.slice(0, 6);
  const more = plan.length - visible.length;

  return (
    <section className="plan-panel" aria-label="Plan">
      {visible.map((entry) => (
        <div key={entry.stage.id} className="plan__row">
          <span className="plan__stage">{entry.stage.name}</span>
          <span
            className={`plan__dot plan__dot--${entry.status}`}
            aria-label={entry.status === "empty" ? "Not measured" : "Partial"}
            aria-hidden="true"
          />
          <span className="plan__label">
            {entry.status === "empty" ? "Not measured" : entry.records}
          </span>
        </div>
      ))}
      {more > 0 && <span className="plan__overflow">+{more} more</span>}
    </section>
  );
}
