import { useEffect, useRef, useState } from "react";

import { useStudio } from "../../state/StudioContext";
import { formatRelativeTime } from "../../lib/relativeTime";
import { groupNoticesByDay, severityLabel } from "../../banners/activityStore";
import type { StoredNotice } from "../../bff/store/types";
import { CloseIcon } from "../icons";

interface ActivityCentreProps {
  isOpen: boolean;
  onClose: () => void;
}

const EMPTY_STATE_MESSAGE = "Nothing has happened yet in this workspace.";

export function ActivityCentre({ isOpen, onClose }: ActivityCentreProps) {
  if (!isOpen) return null;

  const { loadNotices, saveNotices } = useStudio();
  const [notices, setNotices] = useState<StoredNotice[]>([]);
  const [groups, setGroups] = useState<{ label: string; items: StoredNotice[] }[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const dialogRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Load notices when store is available
  useEffect(() => {
    loadNotices().then((loaded) => {
      setNotices(loaded);
      setGroups(groupNoticesByDay(loaded));
      setUnreadCount(loaded.filter((n) => !n.dismissed).length);
    });
  }, [loadNotices]);

  // Focus management
  useEffect(() => {
    if (!isOpen) return;

    const dialog = dialogRef.current;
    const focusableElements = dialog?.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    const firstElement = focusableElements?.[0];
    const lastElement = focusableElements?.[focusableElements.length - 1];

    firstElement?.focus();

    function handleTab(event: KeyboardEvent) {
      if (event.key !== "Tab") return;

      if (event.shiftKey) {
        if (document.activeElement === firstElement) {
          event.preventDefault();
          lastElement?.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          event.preventDefault();
          firstElement?.focus();
        }
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    }

    dialog?.addEventListener("keydown", handleTab);
    dialog?.addEventListener("keydown", handleEscape);
    return () => {
      dialog?.removeEventListener("keydown", handleTab);
      dialog?.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen, onClose]);

  // Return focus to trigger on close
  useEffect(() => {
    if (!isOpen && triggerRef.current) {
      triggerRef.current.focus();
    }
  }, [isOpen]);

  async function handleDismiss(id: string) {
    const updated = notices.map((n) => (n.id === id ? { ...n, dismissed: true } : n));
    setNotices(updated);
    setGroups(groupNoticesByDay(updated));
    setUnreadCount(updated.filter((n) => !n.dismissed).length);
    await saveNotices(updated);
  }

  async function handleMarkAllRead() {
    const updated = notices.map((n) => ({ ...n, dismissed: true }));
    setNotices(updated);
    setGroups(groupNoticesByDay(updated));
    setUnreadCount(0);
    await saveNotices(updated);
  }

  function formatTime(iso: string): string {
    return formatRelativeTime(iso);
  }

  function getTimeElement(iso: string): React.ReactElement {
    return (
      <time dateTime={iso} className="activity__time">
        {formatTime(iso)}
      </time>
    );
  }

  if (!isOpen) return null;

  return (
    <div
      className="activity"
      ref={dialogRef}
      role="dialog"
      aria-label="Activity centre"
      aria-modal="true"
    >
      <div className="activity__header">
        <h2 className="activity__title">Activity centre</h2>
        <div className="activity__header-actions">
          {unreadCount > 0 && (
            <button
              type="button"
              className="activity__mark-read"
              onClick={handleMarkAllRead}
            >
              Mark all read
            </button>
          )}
          <button
            type="button"
            className="activity__close"
            onClick={onClose}
            aria-label="Close activity centre"
          >
            <CloseIcon size={18} />
          </button>
        </div>
      </div>

      {notices.length === 0 ? (
        <div className="activity__empty">
          <p>{EMPTY_STATE_MESSAGE}</p>
        </div>
      ) : (
        <div className="activity__list" role="list" aria-label="Activity history">
          {groups.map((group) => (
            <div key={group.label} className="activity__day-group">
              <p className="activity__day-label">{group.label}</p>
              {group.items.map((notice) => (
                <article
                  key={notice.id}
                  className={`activity__item activity__item--${notice.severity} ${notice.dismissed ? "activity__item--dismissed" : ""}`}
                  role="listitem"
                >
                  <div className="activity__item-main">
                    <div className="activity__item-header">
                      <span className={`activity__severity activity__severity--${notice.severity}`}>
                        {severityLabel(notice.severity)}
                      </span>
                      <h3 className="activity__item-title">{notice.title}</h3>
                      {getTimeElement(notice.at)}
                    </div>
                    <p className="activity__item-detail">{notice.detail}</p>
                    {notice.context && (
                      <p className="activity__item-context">{notice.context}</p>
                    )}
                  </div>
                  <div className="activity__item-actions">
                    {!notice.dismissed && (
                      <button
                        type="button"
                        className="activity__dismiss"
                        onClick={() => handleDismiss(notice.id)}
                        aria-label={`Dismiss "${notice.title}"`}
                      >
                        <CloseIcon size={14} />
                        <span className="sr-only">Dismiss</span>
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}