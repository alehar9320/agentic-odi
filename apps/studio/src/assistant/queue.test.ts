/**
 * The follow-up queue sequencing rules (issue #410).
 *
 * A queue is only trustworthy if its edges are exact: one turn in flight, order
 * preserved, a removed item never sent, a cancelled run never draining the
 * lane, and a failed dispatch putting the message back rather than eating it.
 * These drive the controller with a fake turn — no React, no network — because
 * the whole point is that this module owns the sequence, not the stream.
 */

import { describe, expect, it } from "vitest";

import { createTurnQueue, queuedUserMessage } from "./queue";
interface Run {
  text: string;
  steer: boolean;
  settle: () => void;
  fail: () => void;
}

function textOf(parts: readonly { type: string; text?: string }[]): string {
  return parts.flatMap((part) => (part.type === "text" ? [part.text ?? ""] : [])).join("");
}

function harness(options: { boomOnce?: boolean } = {}) {
  const runs: Run[] = [];
  const cancelled: string[] = [];
  let live: Run | null = null;
  let boomArmed = Boolean(options.boomOnce);

  const controller = createTurnQueue({
    run: (message, { steer }) => {
      const text = textOf(message.content);
      if (boomArmed && text === "boom") {
        boomArmed = false;
        throw new Error("dispatch refused");
      }
      let settle: () => void = () => undefined;
      let fail: () => void = () => undefined;
      const promise = new Promise<void>((resolve, reject) => {
        settle = resolve;
        fail = () => reject(new Error("turn failed"));
      });
      live = { text, steer, settle, fail };
      runs.push(live);
      return promise;
    },
    cancel: () => {
      if (live) cancelled.push(live.text);
    },
  });

  return { controller, runs, cancelled, laneTexts: () => controller.adapter.items.map((item) => textOf(item.parts)) };
}

/** Let queued microtasks (settle → notifyIdle → advance) run. */
async function tick() {
  await Promise.resolve();
  await Promise.resolve();
}

const message = queuedUserMessage;

describe("createTurnQueue", () => {
  it("dispatches an enqueue straight away while nothing runs", () => {
    const { controller, runs } = harness();

    controller.adapter.enqueue(message("first"));

    expect(runs.map((run) => run.text)).toEqual(["first"]);
    expect(controller.adapter.items).toHaveLength(0);
  });

  it("holds follow-ups while a turn is in flight and runs them in order", async () => {
    const { controller, runs } = harness();
    controller.adapter.enqueue(message("live"));
    // (an idle enqueue dispatches immediately; the wrapper marked busy)

    controller.adapter.enqueue(message("second"));
    controller.adapter.enqueue(message("third"));
    expect(runs.map((run) => run.text)).toEqual(["live"]);

    runs[0].settle();
    await tick();
    expect(runs.map((run) => run.text)).toEqual(["live", "second"]);

    runs[1].settle();
    await tick();
    expect(runs.map((run) => run.text)).toEqual(["live", "second", "third"]);
    expect(controller.adapter.items).toHaveLength(0);
  });

  it("removes exactly the item it names", () => {
    const { controller } = harness();
    controller.notifyBusy();
    controller.adapter.enqueue(message("keep"));
    controller.adapter.enqueue(message("drop"));

    controller.adapter.remove(controller.adapter.items[1].id);

    expect(controller.adapter.items.map((item) => textOf(item.parts))).toEqual(["keep"]);
  });

  it("steers by cancelling the live run exactly once and dispatching at once", () => {
    const { controller, runs, cancelled } = harness();
    controller.adapter.enqueue(message("live"));

    controller.adapter.steer(message("urgent"));

    expect(cancelled).toEqual(["live"]);
    expect(runs.map((run) => [run.text, run.steer])).toEqual([
      ["live", false],
      ["urgent", true],
    ]);
  });

  it("pauses — never drains — when the user cancels the live run", () => {
    const { controller, runs } = harness();
    controller.notifyBusy(); // a direct send, not a queued dispatch
    controller.adapter.enqueue(message("pending"));

    // The runtime notifies the queue before aborting, then the run settles.
    controller.adapter.__internal_notifyCancelled?.();
    controller.notifyIdle();

    expect(runs).toHaveLength(0);
    expect(controller.adapter.items).toHaveLength(1);

    // The next explicit send re-arms draining; the pending item goes first.
    controller.adapter.enqueue(message("fresh"));
    expect(runs.map((run) => run.text)).toEqual(["pending"]);
  });

  it("restores a failed dispatch to the head of its lane and pauses", () => {
    const { controller, runs } = harness({ boomOnce: true });
    controller.notifyBusy();
    controller.notifyIdle();

    expect(() => controller.adapter.enqueue(message("boom"))).toThrow("dispatch refused");
    expect(controller.adapter.items.map((item) => textOf(item.parts))).toEqual(["boom"]);

    controller.adapter.enqueue(message("after"));
    expect(runs.map((run) => run.text)).toEqual(["boom"]);
  });

  it("keeps the pending lane when a committed turn fails later", async () => {
    const { controller, runs } = harness();
    controller.adapter.enqueue(message("live"));
    controller.adapter.enqueue(message("pending"));

    runs[0].fail();
    await tick();

    expect(controller.adapter.items).toHaveLength(1);

    // The next send re-arms: the pending follow-up goes before the new one.
    controller.adapter.enqueue(message("later"));
    expect(runs.map((run) => run.text)).toEqual(["live", "pending"]);
  });

  it("splits follow-ups and steers into two lanes", () => {
    const { controller } = harness();
    controller.notifyBusy();

    controller.adapter.enqueue(message("queued"));
    controller.adapter.enqueue(message("priority"));
    // Anchored moves re-place an item without interrupting the live run.
    controller.adapter.move(controller.adapter.items[1].id, { lane: "steer", insertAfter: null });

    expect(controller.adapter.items.map((item) => textOf(item.parts))).toEqual(["queued"]);
    expect(controller.adapter.steerItems.map((item) => textOf(item.parts))).toEqual(["priority"]);
  });
});

describe("queuedUserMessage", () => {
  it("is a minimal user append", () => {
    expect(message("hello")).toMatchObject({
      role: "user",
      content: [{ type: "text", text: "hello" }],
    });
  });
});
