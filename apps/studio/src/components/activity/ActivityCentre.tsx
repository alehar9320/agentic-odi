import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { CloseIcon } from "../icons";
import { formatExactTime, formatRelativeTime } from "../../lib/relativeTime";
import { useFocusTrap } from "../../lib/useFocusTrap";
import {
  useActivityOptional,
  type ActivityApi,
} from "../../notices/ActivityProvider";
import { groupNoticesByDay } from "../../notices/recorder";
import type { Notice, NoticeSeverity } from "../../notices/types";

const SEVERITY_LABEL: Record<NoticeSeverity, string> = {
  critical: "Critical",
  warning: "Warning",
  info: "Info",
  success: "Done",
};

/**
 * The activity centre (#406): a durable history of what the studio announced.
 *
 * Every notice is a banner that has since faded. This dialog is where they are
 * still readable — what happened, when, and how bad — with a dismissal that
 * sticks across a reload. It is a dialog, not a page: Escape closes it without
 * touching a row, and only an explicit Dismiss removes one.
 *
 * Accepts an explicit `api` so a test can drive it without a provider.
 */
export function ActivityCentre({
  open,
  onClose,
  api,
}: {
  open: boolean;
  onClose: () => void;
  api?: ActivityApi;
}) {
  // Hooks run in the same order on every render: the context is read
  // unconditionally, and a closed dialog is a no-op that needs no data. This
  // lets the bar render it unconditionally without every test tree supplying
  // an activity provider.
  const fromContext = useActivityOptional();
  if (!open) {
    return null;
  }
  const resolved = api ?? fromContext;
  if (!resolved) {
    throw new Error("ActivityCentre needs an activity api, from props or a provider.");
  }
  return <ActivityCentreInner onClose={onClose} api={resolved} />;
}

function ActivityCentreInner({
  onClose,
  api,
}: {
  onClose: () => void;
  api: ActivityApi;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [announced, setAnnounced] = useState("");
  useFocusTrap(dialogRef, true, true);

  const groups = useMemo(() => groupNoticesByDay(api.notices), [api.notices]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  function toggle(id: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function dismiss(notice: Notice) {
    api.dismiss(notice.id);
    setAnnounced(`${notice.title || notice.detail} dismissed.`);
  }

  function markAllRead() {
    const count = api.unread;
    api.markAllRead();
    setAnnounced(count === 1 ? "1 notice marked read" : `${count} notices marked read`);
  }

  // Rendered at the document root, outside the shell, so the shell behind it
  // can be made inert without inerting the dialog too.
  return createPortal(
    <div className="activity-overlay">
      <button
        type="button"
        className="activity-scrim"
        aria-label="Close activity centre"
        tabIndex={-1}
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        className="activity-centre"
        role="dialog"
        aria-modal="true"
        aria-labelledby="activity-centre-title"
      >
        <header className="activity-centre__header">
          <div>
            <h2 id="activity-centre-title" className="activity-centre__title">
              Activity
            </h2>
            <p className="activity-centre__subtitle">
              {api.unread > 0
                ? `${api.unread} unread ${api.unread === 1 ? "notice" : "notices"}`
                : "What the studio has announced."}
            </p>
          </div>
          <div className="activity-centre__controls">
            <button
              type="button"
              className="activity-centre__mark-read"
              onClick={markAllRead}
              disabled={api.unread === 0}
            >
              Mark all read
            </button>
            <button
              type="button"
              className="activity-centre__close"
              onClick={onClose}
              aria-label="Close activity centre"
            >
              <CloseIcon size={16} />
            </button>
          </div>
        </header>

        <div className="activity-centre__body">
          {api.notices.length === 0 ? (
            <p className="activity-centre__empty">
              Nothing has happened yet in this workspace.
            </p>
          ) : (
            groups.map((group) => (
              <section key={group.day} className="activity-group" aria-label={group.label}>
                <h3 className="activity-group__day">{group.label}</h3>
                <ul className="activity-list">
                  {group.items.map((notice) => {
                    const isOpen = expanded.has(notice.id);
                    const iso = new Date(notice.at).toISOString();
                    return (
                      <li key={notice.id} className="activity-row">
                        <div className="activity-row__head">
                          <span
                            className={`activity-row__severity activity-row__severity--${notice.severity}`}
                          >
                            {SEVERITY_LABEL[notice.severity]}
                          </span>
                          <span className="activity-row__title">
                            {notice.title || notice.detail}
                          </span>
                          <time className="activity-row__time" dateTime={iso}>
                            {formatRelativeTime(iso)}
                          </time>
                        </div>
                        <div className="activity-row__foot">
                          <button
                            type="button"
                            className="activity-row__details"
                            aria-expanded={isOpen}
                            onClick={() => toggle(notice.id)}
                          >
                            {isOpen ? "Hide details" : "Details"}
                          </button>
                          <button
                            type="button"
                            className="activity-row__dismiss"
                            onClick={() => dismiss(notice)}
                          >
                            Dismiss
                          </button>
                        </div>
                        {isOpen && (
                          <dl className="activity-row__detail">
                            <dt>When</dt>
                            <dd>{formatExactTime(iso)}</dd>
                            <dt>Source</dt>
                            <dd>{notice.context}</dd>
                            {notice.detail && (
                              <>
                                <dt>Detail</dt>
                                <dd>{notice.detail}</dd>
                              </>
                            )}
                          </dl>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))
          )}
        </div>

        <p className="sr-only" role="status" aria-live="polite">
          {announced}
        </p>
      </div>
    </div>,
    document.body,
  );
}
