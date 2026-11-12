import { useMemo, useState } from "react";

import { canvasStatus } from "../../lib/canvasProvenance";
import { useStudio } from "../../state/StudioContext";
import type { WorkspacePanelId } from "../../types";
import { findPanel } from "./panels";
import { deriveViewItems, viewItemIcon } from "./viewItems";

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

  const items = useMemo(() => deriveViewItems(canvas, memory, segments), [canvas, memory, segments]);

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
                onClick={(event) => {
                  // The chip is what opened the lens, so it is where focus goes
                  // back to when the lens closes (#810). A browser focuses a
                  // button it was clicked with, but a programmatic activation
                  // does not; without this the lens falls back to whatever had
                  // focus — on an empty stage, the composer it auto-focused —
                  // and closing a lens would drop the caret into the reply box.
                  event.currentTarget.focus();
                  if (open) {
                    closePanel();
                  } else {
                    openPanel(item.id);
                  }
                }}
              >
                <span className="rail__icon" aria-hidden="true">
                  {viewItemIcon(item.id, 14)}
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
