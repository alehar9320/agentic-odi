/**
 * The quiet lane for follow-ups (issue #410).
 *
 * A message typed mid-answer belongs to the conversation, not to the moment:
 * it waits here, in order, until the running turn settles. "Run now"
 * interrupts the live answer exactly once; ✕ takes the follow-up back.
 * `ComposerPrimitive.Queue` renders only while the runtime reports queued
 * items, so an empty lane leaves no furniture behind, and the row text comes
 * from the item's parts — the deprecated `prompt` field must not be read.
 */

import { AuiIf, ComposerPrimitive, QueueItemPrimitive } from "@assistant-ui/react";

export function QueueLane() {
  return (
    <AuiIf condition={(state) => state.composer.queue.length > 0}>
      {/* role=log announces an addition or removal once, never per token. */}
      <div className="queue-lane" role="log" aria-label="Queued follow-ups">
        <ComposerPrimitive.Queue>
          {({ queueItem }) => (
            <div className="queue-lane__item" key={queueItem.id}>
              <QueueItemPrimitive.Text className="queue-lane__text" />
              <QueueItemPrimitive.Steer className="queue-lane__steer" aria-label="Run now">
                Run now
              </QueueItemPrimitive.Steer>
              <QueueItemPrimitive.Remove className="queue-lane__remove" aria-label="Remove queued message">
                ✕
              </QueueItemPrimitive.Remove>
            </div>
          )}
        </ComposerPrimitive.Queue>
      </div>
    </AuiIf>
  );
}
