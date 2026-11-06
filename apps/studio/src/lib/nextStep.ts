/**
 * The one thing kept about the next step: whether this visit put the question away.
 *
 * The step itself lives in the store, so the studio must not remember on its own
 * that the person did not want to talk about it. A dismissal that outlives the
 * session would silence the question the product exists to ask the next time
 * they come back; the visit it belongs to is the session.
 */

export const NEXT_STEP_DISMISS_KEY = "studio.nextStepDismissed";

export interface NextStepStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function browserSession(): NextStepStorage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function readNextStepDismissed(
  session: NextStepStorage | null = browserSession(),
): boolean {
  if (!session) {
    return false;
  }
  try {
    return session.getItem(NEXT_STEP_DISMISS_KEY) === "1";
  } catch {
    return false;
  }
}

export function writeNextStepDismissed(
  dismissed: boolean,
  session: NextStepStorage | null = browserSession(),
): void {
  if (!session) {
    return;
  }
  try {
    if (dismissed) {
      session.setItem(NEXT_STEP_DISMISS_KEY, "1");
    }
  } catch {
    // Storage denied: the question comes back on the next render, which is the
    // honest failure — a promise kept is worth asking about once more.
  }
}
