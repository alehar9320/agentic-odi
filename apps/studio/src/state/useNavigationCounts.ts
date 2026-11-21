import { useMemo } from "react";

import { buildRecords } from "../lib/records";
import type { WorkspacePanelId } from "../types";
import { useStudio } from "./StudioContext";

export type NavigationCounts = Partial<Record<WorkspacePanelId, number>>;

/**
 * How many records each destination holds.
 *
 * Every number here is the array the destination's own panel maps over, so a
 * count that disagrees with the list below it is a bug in one place and the fix
 * is in this file. Two exceptions are deliberate: Catch up counts what is
 * unread rather than what the feed renders, and Brief, Capture and Settings
 * have no list to count.
 */
export function useNavigationCounts(): NavigationCounts {
  const { canvas, memory, segments, unreadSignalCount } = useStudio();

  return useMemo<NavigationCounts>(() => {
    const jobs = canvas?.jobs ?? [];
    const steps = canvas?.steps ?? [];
    // The job map opens on the first job and shows only its steps; a count of
    // every step in the store would promise rows the panel never renders.
    const firstJobId = jobs[0]?.id;
    const mappedSteps = firstJobId
      ? steps.filter((step) => !step.job_id || step.job_id === firstJobId)
      : steps;

    return {
      records: buildRecords(canvas).length,
      catchup: unreadSignalCount,
      landscape: (canvas?.outcomes ?? []).length,
      jobmap: mappedSteps.length,
      segments: segments.length,
      evidence: (canvas?.evidence ?? []).length,
      memory: memory.filter((note) => note.status !== "dismissed").length,
      schedule: (canvas?.scheduled_work ?? []).length,
    };
  }, [canvas, memory, segments, unreadSignalCount]);
}
