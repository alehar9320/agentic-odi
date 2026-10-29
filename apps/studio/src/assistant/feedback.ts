/**
 * What the reader thought of a reply.
 *
 * assistant-ui's feedback adapter is the seam; the Studio keeps the answer
 * locally because there is no server-side quality store, and inventing one
 * would claim a telemetry pipeline that does not exist. A message keeps its
 * latest verdict, so clicking the other thumb replaces the first.
 */

export interface StoredFeedback {
  type: "positive" | "negative";
  comment?: string;
  created_at: string;
}

const FEEDBACK_KEY = "studio.feedback";

function readAll(): Record<string, StoredFeedback> {
  try {
    const raw = localStorage.getItem(FEEDBACK_KEY);
    if (raw) {
      return JSON.parse(raw) as Record<string, StoredFeedback>;
    }
  } catch {
    /* storage unavailable */
  }
  return {};
}

export function recordFeedback(
  messageId: string,
  type: StoredFeedback["type"],
  comment?: string,
): void {
  const all = readAll();
  all[messageId] = {
    type,
    ...(comment ? { comment } : {}),
    created_at: new Date().toISOString(),
  };
  try {
    localStorage.setItem(FEEDBACK_KEY, JSON.stringify(all));
  } catch {
    /* storage unavailable: the verdict still shows for this session */
  }
}

/** The verdict recorded for a message, if any. */
export function feedbackFor(messageId: string): StoredFeedback | undefined {
  return readAll()[messageId];
}
