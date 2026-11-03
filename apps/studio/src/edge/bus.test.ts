import { afterEach, describe, expect, it, vi } from "vitest";

import { createLadderBus } from "./bus";
import { installFakeBroadcastChannel } from "../test/fakeBroadcastChannel";

const original = globalThis.BroadcastChannel;
let uninstall: (() => void) | null = null;

afterEach(() => {
  uninstall?.();
  uninstall = null;
  // Every case here mutates a browser global; the next file must not inherit it.
  globalThis.BroadcastChannel = original;
});

describe("createLadderBus", () => {
  it("carries the news to the other tab and never back to the one that spoke", () => {
    uninstall = installFakeBroadcastChannel();
    const here = vi.fn();
    const there = vi.fn();
    const a = createLadderBus(here);
    const b = createLadderBus(there);

    a.publish();

    expect(there).toHaveBeenCalledTimes(1);
    expect(here).toHaveBeenCalledTimes(0);
    a.close();
    b.close();
  });

  it("stops hearing once the tab closes its bus", () => {
    // What `EdgeManager.reset()` relies on: a page-level owner that let go of
    // the ladder must not keep reacting to it.
    uninstall = installFakeBroadcastChannel();
    const speaker = vi.fn();
    const listener = vi.fn();
    const a = createLadderBus(speaker);
    const b = createLadderBus(listener);

    b.close();
    a.publish();

    expect(listener).toHaveBeenCalledTimes(0);
    a.close();
  });

  it("says nothing and throws nothing where the channel does not exist", () => {
    // Safari private browsing and a bare test environment both lack it. A
    // person's message must not be lost because a tab could not open a side
    // channel.
    delete (globalThis as unknown as { BroadcastChannel?: unknown }).BroadcastChannel;
    const onChange = vi.fn();
    const bus = createLadderBus(onChange);

    expect(() => bus.publish()).not.toThrow();
    expect(() => bus.close()).not.toThrow();
    expect(onChange).toHaveBeenCalledTimes(0);
  });

  it("says nothing and throws nothing when opening the channel is refused", () => {
    // Same reason: the ladder still works alone in one tab when the browser
    // won't let tabs talk at all.
    globalThis.BroadcastChannel = (function refused() {
      throw new Error("SecurityError");
    }) as unknown as typeof BroadcastChannel;
    const onChange = vi.fn();
    const bus = createLadderBus(onChange);

    expect(() => bus.publish()).not.toThrow();
    expect(() => bus.close()).not.toThrow();
    expect(onChange).toHaveBeenCalledTimes(0);
  });
});
