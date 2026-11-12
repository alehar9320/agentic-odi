/**
 * One queue for the sentences a screen reader should hear.
 *
 * Outcome confirmations — a copy, an export, a save, a connection, a
 * mark-read — used to be said from wherever they happened: a toast here, an
 * inline live region there. A burst of three actions then produced three
 * overlapping live regions, which a reader hears as a jumble.
 *
 * `announce` pushes a sentence onto a single queue. `Announcer` renders that
 * queue into one `aria-live="polite"` region, one sentence at a time, so a
 * burst is three sentences in order rather than three voices at once.
 */

type Listener = (message: string) => void;

let listener: Listener | null = null;

/**
 * Say one sentence. Called from anywhere — a component, a state module — and
 * heard through whichever `Announcer` is mounted. When none is mounted the
 * sentence is dropped rather than queued forever.
 */
export function announce(message: string): void {
  const sentence = message.trim();
  if (!sentence || !listener) {
    return;
  }
  listener(sentence);
}

/**
 * Make `next` the region that hears announcements. Returns the cleanup that
 * gives the slot back — and only if this listener still holds it, so an
 * unmounting region cannot disconnect the one that replaced it.
 */
export function subscribeToAnnouncements(next: Listener): () => void {
  listener = next;
  return () => {
    if (listener === next) {
      listener = null;
    }
  };
}
