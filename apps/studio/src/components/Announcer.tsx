import { useEffect, useRef, useState } from "react";

import { subscribeToAnnouncements } from "../lib/announce";

/**
 * How long one sentence holds the region before the next takes it.
 *
 * Long enough that a screen reader finishes a short confirmation, short enough
 * that a burst of three actions does not feel stuck.
 */
const ANNOUNCE_GAP_MS = 1200;

/**
 * The one polite live region for outcome confirmations.
 *
 * It owns a queue, not a single string: a burst of three actions becomes three
 * sentences read in order, where three separate live regions would talk over
 * one another. Mounted once, near the root.
 */
export function Announcer() {
  const [current, setCurrent] = useState("");
  const queue = useRef<string[]>([]);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    function advance() {
      const next = queue.current.shift();
      if (next === undefined) {
        timer.current = null;
        setCurrent("");
        return;
      }
      setCurrent(next);
      timer.current = window.setTimeout(advance, ANNOUNCE_GAP_MS);
    }

    const unsubscribe = subscribeToAnnouncements((message) => {
      queue.current.push(message);
      if (timer.current === null) {
        advance();
      }
    });

    return () => {
      unsubscribe();
      if (timer.current !== null) {
        window.clearTimeout(timer.current);
        timer.current = null;
      }
    };
  }, []);

  return (
    <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">
      {current}
    </p>
  );
}
