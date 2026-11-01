import { describe, expect, it, vi } from "vitest";

import type { Conversation } from "../types";
import { UNTITLED_CONVERSATION, threadListAdapter, toThreadListItem } from "./threadList";

const CONVERSATIONS: Conversation[] = [
  {
    id: "c-2",
    title: "The churn spike",
    created_at: "2026-10-22T10:00:00+00:00",
    updated_at: "2026-10-22T11:00:00+00:00",
    turn_count: 6,
  },
  {
    id: "c-1",
    title: "   ",
    created_at: "2026-10-21T09:00:00+00:00",
    updated_at: "2026-10-21T09:30:00+00:00",
  },
];

describe("thread list adapter", () => {
  it("keeps the store's order and carries the timestamp the row type lacks", () => {
    const rows = CONVERSATIONS.map(toThreadListItem);

    expect(rows.map((row) => row.id)).toEqual(["c-2", "c-1"]);
    expect(rows[0].custom).toEqual({
      updatedAt: "2026-10-22T11:00:00+00:00",
      turnCount: 6,
    });
    expect(rows[1].custom).toEqual({
      updatedAt: "2026-10-21T09:30:00+00:00",
      turnCount: 0,
    });
  });

  it("names a thread that has no title yet", () => {
    expect(toThreadListItem(CONVERSATIONS[1]).title).toBe(UNTITLED_CONVERSATION);
  });

  it("switches to exactly the thread that was clicked", async () => {
    const onSwitchToThread = vi.fn();
    const onSwitchToNewThread = vi.fn();
    const adapter = threadListAdapter({
      conversations: CONVERSATIONS,
      conversationId: "c-1",
      loading: true,
      onSwitchToThread,
      onSwitchToNewThread,
    });

    expect(adapter.threadId).toBe("c-1");
    expect(adapter.isLoading).toBe(true);
    expect(adapter.threads).toHaveLength(2);

    await adapter.onSwitchToThread?.("c-2");
    await adapter.onSwitchToNewThread?.();

    expect(onSwitchToThread).toHaveBeenCalledExactlyOnceWith("c-2");
    expect(onSwitchToNewThread).toHaveBeenCalledOnce();
  });
});
