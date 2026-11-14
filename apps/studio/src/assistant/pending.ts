/**
 * The calls a turn is actually waiting on.
 *
 * A long tool call makes a running turn look like a freeze. The transcript is
 * the record of what happened; this selector answers the narrower question of
 * what has not happened yet, and it answers it only from what the client can
 * see: a tool part the store still holds as `running`, or one holding an
 * unanswered approval. A speculative "up next" list would be fiction, so it is
 * deliberately not derivable from this module.
 *
 * It reads the Studio's own part model, not assistant-ui's: the runtime's
 * external-store path normalizes every part to `complete` (the store, not the
 * library, owns liveness here), so the store is the only honest source.
 *
 * `startedAt` is stamped by the store at the moment it received the call, so it
 * is an observed start rather than an invented one. When a part carries none —
 * a turn restored from history — the field is null and the row shows no clock.
 */

import type { ChatPart } from "../types";

export interface PendingCall {
  /** The tool call id, which is also the React key. */
  id: string;
  /** The tool name, rendered through the transcript's own label table. */
  name: string;
  /** True when the call is holding a question the person has not answered. */
  awaitingApproval: boolean;
  /** The question being asked, when there is one. */
  prompt: string | null;
  /** Epoch milliseconds the store recorded when the call arrived, or null. */
  startedAt: number | null;
}

/** The tool parts of one message, narrowed for the loop below. */
type ToolPart = Extract<ChatPart, { kind: "tool" }>;

function isAwaitingApproval(part: ToolPart): boolean {
  return part.status === "running" && part.approval !== undefined;
}

/**
 * Every call in flight, in transcript order.
 *
 * A settled call is excluded: once a result landed, the transcript owns it and
 * this list must not say it twice.
 */
export function pendingCalls(parts: readonly ChatPart[]): PendingCall[] {
  const pending: PendingCall[] = [];

  for (const part of parts) {
    if (part.kind !== "tool" || part.status !== "running") {
      continue;
    }
    pending.push({
      id: part.id,
      name: part.name,
      awaitingApproval: isAwaitingApproval(part),
      prompt: part.approval?.prompt ?? null,
      startedAt: part.startedAt ?? null,
    });
  }

  return pending;
}
