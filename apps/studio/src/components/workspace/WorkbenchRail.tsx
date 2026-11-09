import { useMemo, useState, type ReactNode } from "react";

import { canvasStatus } from "../../lib/canvasProvenance";
import { buildRecords } from "../../lib/records";
import { useStudio } from "../../state/StudioContext";
import type { WorkspacePanelId } from "../../types";
import {
  ClusterIcon,
  CompassIcon,
  RouteIcon,
  SignalIcon,
  SparkIcon,
  TableIcon,
} from "../icons";
import { findPanel } from "./panels";

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
  const { canvas, memory, segments, activePanel, openPanel, closePanel } = useStudio();
  // One tooltip at a time: the chip under the pointer or the keyboard (#696).
  const [openTip, setOpenTip] = useState<WorkspacePanelId | null>(null);

  const items = useMemo<RailItem[]>(() => {
    const outcomes = canvas?.outcomes ?? [];
    const steps = canvas?.steps ?? [];
    const evidence = outcomes.filter((outcome) => outcome.evidence?.trim()).length;
    const records = buildRecords(canvas);

    const rail: RailItem[] = [];
    if (records.length > 0) {
      rail.push({
        id: "records",
        label: "Records",
        count: records.length,
        noun: records.length === 1 ? "record" : "records",
        icon: <TableIcon size={14} />,
      });
    }
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
    if (segments.length > 0) {
      rail.push({
        id: "segments",
        label: "Segments",
        count: segments.length,
        noun: segments.length === 1 ? "segment" : "segments",
        icon: <ClusterIcon size={14} />,
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
  }, [canvas, memory, segments]);

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
          // The panel registry owns the sentence; a lens without one says what
          // its chip already says rather than opening an empty tooltip.
          const blurb = findPanel(item.id).blurb.trim() || item.label;
          const showing = openTip === item.id;
          return (
            <li key={item.id}>
              <button
                type="button"
                className={`rail__chip${open ? " is-open" : ""}`}
                aria-current={open ? "page" : undefined}
                aria-label={`${item.label}, ${item.count} ${item.noun}`}
                aria-describedby={showing ? `rail-tip-${item.id}` : undefined}
                onMouseEnter={() => setOpenTip(item.id)}
                onMouseLeave={() => setOpenTip((current) => (current === item.id ? null : current))}
                onFocus={() => setOpenTip(item.id)}
                onBlur={() => setOpenTip((current) => (current === item.id ? null : current))}
                onClick={() => (open ? closePanel() : openPanel(item.id))}
              >
                <span className="rail__icon" aria-hidden="true">
                  {item.icon}
                </span>
                {item.label}
                <span className="rail__count">{item.count}</span>
                {showing && (
                  <span id={`rail-tip-${item.id}`} className="rail__tip" role="tooltip">
                    {blurb}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
