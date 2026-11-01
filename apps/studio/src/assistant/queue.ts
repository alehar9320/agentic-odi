/**
 * The follow-up queue (issue #410).
 *
 * One SSE turn at a time is the sidecar's contract, so a follow-up typed while
 * an answer streams must wait its turn rather than open a second stream. The
 * ordering, the steer lane, the pause-on-cancel, and the restore-on-failure all
 * come from assistant-ui's `createMessageQueue`; this module is the seam that
 * supplies the two edges the library cannot know about our turns: when a run
 * has truly begun, and when it has truly settled.
 *
 * No React, no network — the caller owns the turn, this owns the sequence.
 */

import {
  createMessageQueue,
  type AppendMessage,
  type ExternalThreadQueueAdapter,
  type MessageQueueController,
} from "@assistant-ui/react";

import type { ChatAttachment } from "../types";

export interface TurnDriver {
  /**
   * Start one turn and settle it. A synchronous throw means nothing was
   * committed: the queue puts the message back at the head of its lane and
   * pauses until the next send.
   */
  run(message: AppendMessage, options: { steer: boolean }): void | Promise<void>;
  /** Abort the live turn — steering and the user's stop button both land here. */
  cancel(): void;
}

export function createTurnQueue(driver: TurnDriver): MessageQueueController {
  // The library never invokes the driver before `createMessageQueue` returns,
  // so the callbacks can read the controller they belong to.
  const controller = createMessageQueue({
    run: (message, options) => {
      // Run first: everything a turn commits happens synchronously before
      // its first await, and a throw here must stay a pre-busy throw so the
      // library restores the item instead of dropping it.
      const settle = driver.run(message, options);
      controller.notifyBusy();
      return Promise.resolve(settle).then(
        () => controller.notifyIdle(),
        () => {
          // The turn failed after committing: keep the remaining queue
          // untouched. The wrapped adapter below re-arms on the next send.
          controller.hold();
          controller.notifyIdle();
        },
      );
    },
    cancel: () => {
      controller.notifyCancelled();
      driver.cancel();
    },
  });

  const base = controller.adapter;
  const adapter: ExternalThreadQueueAdapter = {
    ...base,
    // `items` and `steerItems` mutate on the source adapter with every lane
    // change, so the wrapper has to read them live rather than copy once.
    get items() {
      return base.items;
    },
    get steerItems() {
      return base.steerItems;
    },
    // A held queue — paused because a committed run failed — waits for a
    // person to speak again, not for a timer. Every explicit send re-arms it.
    enqueue: (message) => {
      controller.release();
      base.enqueue(message);
    },
    steer: (message) => {
      controller.release();
      base.steer(message);
    },
  };

  return { ...controller, adapter };
}

/**
 * The minimal user message a queue lane needs; mirrors what the composer sends.
 *
 * Prepared attachments ride in `metadata.custom`, not `attachments`: the
 * composer path's files are re-read by id from the attachment adapter's map,
 * but a direct studio send already holds the extraction and must carry it to
 * the turn it queues for.
 */
export function queuedUserMessage(
  text: string,
  parentId: string | null = null,
  attachments: ChatAttachment[] = [],
): AppendMessage {
  return {
    role: "user",
    content: [{ type: "text", text }],
    parentId,
    sourceId: null,
    runConfig: undefined,
    metadata: { custom: attachments.length ? { attachments } : {} },
    createdAt: new Date(),
  };
}
