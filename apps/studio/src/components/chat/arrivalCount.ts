/**
 * How many turns arrived while the reader was scrolled away from the bottom.
 *
 * Pure on purpose: assistant-ui owns the viewport (see `ChatStage`), so this
 * module carries only the arithmetic the viewport does not — the "3 new" in
 * "3 new · Jump to latest" — and can be tested without a DOM or a layout engine.
 */

/** Turns appended after `seen`, clamped at zero so a shrinking transcript never reads negative. */
export function arrivedSince(seen: number, messageCount: number): number {
  return Math.max(0, messageCount - seen);
}

/** The label for the control, naming the count only when there is one. */
export function arrivalLabel(arrived: number): string {
  return arrived > 0 ? `${arrived} new · Jump to latest` : "Jump to latest";
}

/** The polite announcement for a count, or an empty string when there is none. */
export function arrivalAnnouncement(arrived: number): string {
  if (arrived <= 0) {
    return "";
  }
  return `${arrived} new ${arrived === 1 ? "message" : "messages"}`;
}
