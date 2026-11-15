/* eslint-disable react-refresh/only-export-components -- context module intentionally exports the hook alongside the provider */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { getStudioBff } from "../bff";
import {
  EMPTY_NOTICES,
  dismissNotice,
  markAllRead,
  recordNotice,
  unreadCount,
} from "./recorder";
import type { Notice, NoticeInput } from "./types";

export interface ActivityApi {
  /** The recorded notices, newest first. */
  notices: Notice[];
  unread: number;
  /** Record a statement. The same statement raised twice in a minute is one. */
  record: (input: Omit<NoticeInput, "at"> & { at?: number }) => void;
  /** Remove one row, permanently. */
  dismiss: (id: string) => void;
  /** Clear the unread count without removing rows. */
  markAllRead: () => void;
}

const ActivityContext = createContext<ActivityApi | null>(null);

/**
 * The recorder behind the activity centre (#406).
 *
 * It holds the notice list, writes every change to the browser store so the
 * history outlives a reload, and never lets a persistence failure block the
 * studio: if the store is unreachable the list still works in memory.
 */
export function ActivityProvider({ children }: { children: ReactNode }) {
  const [notices, setNotices] = useState<Notice[]>(EMPTY_NOTICES);
  const loaded = useRef(false);

  // Read the history once, on mount. A store that fails to open leaves the
  // list empty rather than blocking the shell.
  useEffect(() => {
    let mounted = true;
    getStudioBff()
      .then((bff) => bff.store.listNotices())
      .then((stored) => {
        if (mounted && stored.length > 0) {
          loaded.current = true;
          setNotices(stored);
        }
      })
      .catch(() => undefined);
    return () => {
      mounted = false;
    };
  }, []);

  // Persist after every change, once the initial read has settled so an empty
  // mount does not overwrite what is on disk before it is read back.
  useEffect(() => {
    if (!loaded.current && notices.length === 0) {
      return;
    }
    loaded.current = true;
    void getStudioBff()
      .then((bff) => bff.store.putNotices(notices))
      .catch(() => undefined);
  }, [notices]);

  const record = useCallback((input: Omit<NoticeInput, "at"> & { at?: number }) => {
    setNotices((current) =>
      recordNotice(current, { ...input, at: input.at ?? Date.now() }),
    );
  }, []);

  const dismiss = useCallback((id: string) => {
    setNotices((current) => dismissNotice(current, id));
  }, []);

  const readAll = useCallback(() => {
    setNotices((current) => markAllRead(current));
  }, []);

  const value = useMemo<ActivityApi>(
    () => ({ notices, unread: unreadCount(notices), record, dismiss, markAllRead: readAll }),
    [notices, record, dismiss, readAll],
  );

  return <ActivityContext.Provider value={value}>{children}</ActivityContext.Provider>;
}

export function useActivity(): ActivityApi {
  const context = useContext(ActivityContext);
  if (!context) {
    throw new Error("useActivity must be used within an ActivityProvider");
  }
  return context;
}

/** For presentational components that accept an explicit api as a prop. */
export function useActivityOptional(): ActivityApi | null {
  return useContext(ActivityContext);
}
