import { afterEach, describe, expect, it, vi } from "vitest";

import { announce, subscribeToAnnouncements } from "./announce";

describe("announce", () => {
  afterEach(() => {
    // Release the slot so tests do not leak a listener into the next one.
    subscribeToAnnouncements(() => {});
  });

  it("drops a sentence when no region is listening", () => {
    expect(() => announce("nothing to hear")).not.toThrow();
  });

  it("hands a sentence to the subscribed region", () => {
    const heard = vi.fn();
    subscribeToAnnouncements(heard);
    announce("Copied");
    expect(heard).toHaveBeenCalledWith("Copied");
  });

  it("trims and ignores an empty sentence", () => {
    const heard = vi.fn();
    subscribeToAnnouncements(heard);
    announce("   ");
    announce("  Saved  ");
    expect(heard).toHaveBeenCalledTimes(1);
    expect(heard).toHaveBeenCalledWith("Saved");
  });

  it("stops delivering after the subscription is released", () => {
    const heard = vi.fn();
    const unsubscribe = subscribeToAnnouncements(heard);
    unsubscribe();
    announce("too late");
    expect(heard).not.toHaveBeenCalled();
  });

  it("does not let a stale cleanup disconnect the current region", () => {
    const first = vi.fn();
    const second = vi.fn();
    const unsubscribeFirst = subscribeToAnnouncements(first);
    subscribeToAnnouncements(second);
    // The first region unmounts after the second mounted: its cleanup must not
    // steal the slot from the live region.
    unsubscribeFirst();
    announce("still heard");
    expect(second).toHaveBeenCalledWith("still heard");
    expect(first).not.toHaveBeenCalled();
  });
});
