import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import { CloseIcon } from "../icons";
import { nowIso } from "../../bff/id";
import { openLocalStore } from "../../bff/store/openStore";
import type { LocalStore, StoredNotice } from "../../bff/store/types";
import {
  daySectionLabel,
  formatClockTime,
  formatExactTime,
  groupByDay,
} from "../../lib/relativeTime";

const NOTICE_CAP = 200;
const DEDUP_WINDOW_MS = 60_000;

const SEVERITY_TONE: Record<StoredNotice["severity"], string> = {
  info: "var(--muted)",
  success: "var(--green)",
  warning: "var(--amber)",
  critical: "var(--red)",
};

/** Raise a notice: capped at 200 entries, deduped within 60 seconds. */
export async function recordNotice(params: {
  severity: StoredNotice["severity"];
  title: string;
  detail: string;
  context?: string | null;
  at?: string;
}): Promise<void> {
  const store = await openLocalStore();
  const at = params.at ?? nowIso();

  const existing = await store.listNotices();
  const cutoff = Date.parse(at) - DEDUP_WINDOW_MS;
  const isDuplicate = existing.some(
    (n) =>
      n.severity === params.severity &&
      n.title === params.title &&
      n.detail === params.detail &&
      Date.parse(n.at) > cutoff,
  );
  if (isDuplicate) {
    return;
  }

  const notice: StoredNotice = {
    id: crypto.randomUUID(),
    severity: params.severity,
    title: params.title,
    detail: params.detail,
    context: params.context ?? null,
    at,
    read: false,
    dismissed: false,
  };

  await store.putNotice(notice);

  const all = await store.listNotices();
  if (all.length > NOTICE_CAP) {
    const toDelete = all.slice(NOTICE_CAP);
    for (const row of toDelete) {
      await store.deleteNotice(row.id);
    }
  }
}

export interface ActivityCentreProps {
  open: boolean;
  onClose: () => void;
}

export function ActivityCentre({ open, onClose }: ActivityCentreProps) {
  const [notices, setNotices] = useState<StoredNotice[]>([]);
  const storeRef = useRef<LocalStore | null>(null);
  const mountedRef = useRef(false);

  const load = useCallback(async () => {
    if (!open) {
      return;
    }
    const store = await openLocalStore();
    storeRef.current = store;
    mountedRef.current = true;
    const list = await store.listNotices();
    if (mountedRef.current) {
      setNotices(list);
    }
  }, [open]);

  useEffect(() => {
    load();
    return () => {
      mountedRef.current = false;
    };
  }, [load]);

  const dismiss = useCallback(
    async (id: string) => {
      const store = storeRef.current ?? (await openLocalStore());
      storeRef.current = store;
      await store.deleteNotice(id);
      setNotices((prev) => prev.filter((n) => n.id !== id));
    },
    [],
  );

  const markAllRead = useCallback(async () => {
    const store = storeRef.current ?? (await openLocalStore());
    storeRef.current = store;
    await store.markAllRead();
    setNotices((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const onKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Escape") {
        onClose();
      }
    },
    [onClose],
  );

  const groups = groupByDay(notices, (n) => n.at);
  const unreadCount = notices.filter((n) => !n.read).length;

  if (!open) {
    return null;
  }

  return (
    <div
      className="activity-centre"
      onKeyDown={onKeyDown}
      role="dialog"
      aria-modal="true"
      aria-label="Activity centre"
    >
      <button
        type="button"
        className="activity-centre__scrim"
        aria-label="Close activity centre"
        onClick={onClose}
      />
      <div className="activity-centre__panel">
        <header className="activity-centre__head">
          <h2 className="activity-centre__title">Activity centre</h2>
          <button
            type="button"
            className="activity-centre__close"
            aria-label="Close activity centre"
            onClick={onClose}
          >
            <CloseIcon size={18} />
          </button>
        </header>

        {notices.length === 0 ? (
          <p className="activity-centre__empty">
            Nothing has happened yet in this workspace.
          </p>
        ) : (
          <>
            {unreadCount > 0 && (
              <button
                type="button"
                className="activity-centre__mark-read"
                onClick={markAllRead}
              >
                Mark all read
              </button>
            )}
            <div className="activity-centre__list">
              {groups.map((group) => (
                <section
                  key={group.section}
                  className="activity-centre__group"
                >
                  <h3 className="activity-centre__day">{group.label}</h3>
                  {group.items.map((notice) => (
                    <article
                      key={notice.id}
                      className={`activity-centre__row${notice.read ? " activity-centre__row--read" : ""}`}
                    >
                      <span
                        className="activity-centre__severity"
                        style={{ color: SEVERITY_TONE[notice.severity] }}
                        aria-label={notice.severity}
                      >
                        {notice.severity}
                      </span>
                      <div className="activity-centre__body">
                        <h4 className="activity-centre__notice-title">
                          {notice.title}
                        </h4>
                        <time
                          className="activity-centre__notice-time"
                          dateTime={notice.at}
                          title={formatExactTime(notice.at)}
                        >
                          {formatClockTime(notice.at)}
                        </time>
                        {notice.detail && (
                          <p className="activity-centre__notice-detail">
                            {notice.detail}
                          </p>
                        )}
                      </div>
                      <button
                        type="button"
                        className="activity-centre__dismiss"
                        aria-label={`Dismiss ${notice.title}`}
                        onClick={() => dismiss(notice.id)}
                      >
                        ✕
                      </button>
                    </article>
                  ))}
                </section>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
