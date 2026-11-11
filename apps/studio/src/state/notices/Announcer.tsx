/**
 * The one live region the whole room speaks through (#701 D47).
 *
 * A region that stays mounted can never be missed by a reader that arrives
 * late, and a region that holds the newest sentence can never overlap itself:
 * a burst of three actions is three sentences in order, not three competing
 * regions. The component is deliberately trivial — it is the *route* that
 * matters, and every call site is edited to use it.
 */
export function Announcer({ announcement }: { announcement: string }) {
  return (
    <p className="sr-only" role="status" aria-live="polite">
      {announcement}
    </p>
  );
}