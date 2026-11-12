import type { ReactNode } from "react";

import { buildRecords } from "../../lib/records";
import type { CanvasData, Observation, Segment, WorkspacePanelId } from "../../types";
import {
  ClusterIcon,
  CompassIcon,
  RouteIcon,
  SignalIcon,
  SparkIcon,
  TableIcon,
} from "../icons";

/** One lens the conversation has something to show for, with its real count. */
export interface ViewItem {
  id: WorkspacePanelId;
  label: string;
  count: number;
  noun: string;
}

/**
 * The artifacts a thread has produced, derived once so the rail and the lens
 * header cannot disagree about what exists or how much of it. A lens with
 * nothing behind it is simply absent: no count is ever invented.
 */
export function deriveViewItems(
  canvas: CanvasData | null | undefined,
  memory: Observation[] | null | undefined,
  segments: Segment[] | null | undefined,
): ViewItem[] {
  const outcomes = canvas?.outcomes ?? [];
  const steps = canvas?.steps ?? [];
  const notes = memory ?? [];
  const segmentRows = segments ?? [];
  const evidence = outcomes.filter((outcome) => outcome.evidence?.trim()).length;
  const records = buildRecords(canvas);

  const items: ViewItem[] = [];
  if (records.length > 0) {
    items.push({
      id: "records",
      label: "Records",
      count: records.length,
      noun: records.length === 1 ? "record" : "records",
    });
  }
  if (outcomes.length > 0) {
    items.push({
      id: "landscape",
      label: "Landscape",
      count: outcomes.length,
      noun: outcomes.length === 1 ? "opportunity" : "opportunities",
    });
  }
  if (steps.length > 0) {
    items.push({
      id: "jobmap",
      label: "Job map",
      count: steps.length,
      noun: steps.length === 1 ? "step" : "steps",
    });
  }
  if (segmentRows.length > 0) {
    items.push({
      id: "segments",
      label: "Segments",
      count: segmentRows.length,
      noun: segmentRows.length === 1 ? "segment" : "segments",
    });
  }
  if (evidence > 0) {
    items.push({
      id: "evidence",
      label: "Evidence",
      count: evidence,
      noun: evidence === 1 ? "signal" : "signals",
    });
  }
  if (notes.length > 0) {
    items.push({
      id: "memory",
      label: "What I know",
      count: notes.length,
      noun: notes.length === 1 ? "note" : "notes",
    });
  }
  return items;
}

/** The rail's icon for a lens, so the chip and the switcher draw the same set. */
export function viewItemIcon(id: WorkspacePanelId, size: number): ReactNode {
  switch (id) {
    case "records":
      return <TableIcon size={size} />;
    case "landscape":
      return <CompassIcon size={size} />;
    case "jobmap":
      return <RouteIcon size={size} />;
    case "segments":
      return <ClusterIcon size={size} />;
    case "evidence":
      return <SignalIcon size={size} />;
    case "memory":
      return <SparkIcon size={size} />;
    default:
      return null;
  }
}
