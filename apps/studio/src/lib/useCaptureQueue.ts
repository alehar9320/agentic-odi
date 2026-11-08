import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getStudioBff } from "../bff/index";
import { asStudioError, isTransportFailure, sendQueuedCapture } from "../api/studioApi";
import type { Outcome } from "../types";
import { useOnlineStatus } from "./onlineStatus";

export interface CaptureQueue {
  /** The captures still waiting to sync, oldest first. */
  queued: Outcome[];
  /** How many captures are waiting to sync, which is what the badge shows. */
  waiting: number;
  /** The captures the sidecar refused, kept so they are surfaced, not dropped. */
  failed: Outcome[];
  /** Replay the queue now; returns how many were sent. */
  replay: () => Promise<number>;
  /** Re-read the queue from the store. */
  refresh: () => Promise<void>;
  /** Drop one queued capture by its id. */
  discard: (id: string) => Promise<void>;
}

/**
 * The offline capture queue, as the UI sees it: the waiting captures and a
 * replay.
 *
 * Replay runs when the browser comes back online, and the drain guard inside
 * the BFF makes it send each record at most once even if two tabs both call
 * it. Nothing here blocks the UI: the count updates after the replay settles,
 * and a capture that fails stays queued.
 */
export function useCaptureQueue(mcpUrl: string): CaptureQueue {
  const online = useOnlineStatus();
  const [queued, setQueued] = useState<Outcome[]>([]);
  const [failed, setFailed] = useState<Outcome[]>([]);
  const replayingRef = useRef(false);

  const refresh = useCallback(async () => {
    const bff = await getStudioBff();
    const [nextQueued, nextFailed] = await Promise.all([
      bff.listQueuedCaptures(),
      bff.listFailedCaptures(),
    ]);
    setQueued(nextQueued);
    setFailed(nextFailed);
  }, []);

  const replay = useCallback(async () => {
    if (replayingRef.current) {
      return 0;
    }
    replayingRef.current = true;
    try {
      const bff = await getStudioBff();
      const sent = await bff.replayCaptures(async (record) => {
        try {
          await sendQueuedCapture(record, mcpUrl);
        } catch (error) {
          // A transport failure keeps the record pending for the next attempt.
          if (isTransportFailure(error)) {
            throw error;
          }
          // A real refusal is not retried forever, but it is not dropped
          // either: mark it failed so the record is surfaced, and let the drain
          // skip past it to the captures behind it.
          await bff.failQueuedCapture(record.id, asStudioError(error).message);
        }
      });
      await refresh();
      return sent;
    } finally {
      replayingRef.current = false;
    }
  }, [mcpUrl, refresh]);

  const discard = useCallback(
    async (id: string) => {
      const bff = await getStudioBff();
      await bff.discardQueuedCapture(id);
      await refresh();
    },
    [refresh],
  );

  useEffect(() => {
    // Wrapped so the first read is asynchronous: the store opens a database,
    // and a synchronous setState in the effect body would cascade renders.
    const load = async () => {
      await Promise.resolve();
      await refresh();
    };
    void load();
  }, [refresh]);

  // Replay once each time the browser comes back online. Watching the count
  // too would re-enter whenever a failed record kept it up, so the trigger is
  // the transition, not the number.
  const wasOnline = useRef(online);
  useEffect(() => {
    const cameBack = online && !wasOnline.current;
    wasOnline.current = online;
    if (cameBack) {
      void replay();
    }
  }, [online, replay]);

  return useMemo(
    () => ({ queued, waiting: queued.length, failed, replay, refresh, discard }),
    [queued, failed, replay, refresh, discard],
  );
}
