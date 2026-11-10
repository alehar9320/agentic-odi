import { describe, expect, it } from "vitest";
import { toThreadData } from "./threadList";
import type { ConversationSummary } from "../types";

const conversation = (overrides: Partial<ConversationSummary> = {}): ConversationSummary => ({
  id: "c-1",
  title: "A conversation",
  created_at: "2026-10-21T09:00:00Z",
  updated_at: "2026-10-21T09:00:00Z",
  head_id: null,
  turn_count: 0,
  ...overrides,
});

describe("toThreadData", () => {
  it("returns an empty list for no conversations", () => {
    expect(toThreadData([])).toEqual([]);
  });

  it("returns an empty list when the store has not loaded a list yet", () => {
    expect(toThreadData(undefined)).toEqual([]);
  });

  it("maps one conversation with title, status, and custom updatedAt", () => {
    const [row] = toThreadData([conversation({ id: "c-1" })]);
    expect(row).toEqual({
      id: "c-1",
      title: "A conversation",
      status: "regular",
      custom: { updatedAt: "2026-10-21T09:00:00Z" },
    });
  });

  it("orders newest first regardless of input order", () => {
    const rows = toThreadData(
      [
        conversation({ id: "c-1", updated_at: "2026-10-20T09:00:00Z" }),
        conversation({ id: "c-2", updated_at: "2026-10-22T09:00:00Z" }),
        conversation({ id: "c-3", updated_at: "2026-10-21T09:00:00Z" }),
      ],
    );
    expect(rows.map((row) => row.id)).toEqual(["c-2", "c-3", "c-1"]);
  });

  it("reports a blank title as New conversation", () => {
    const [row] = toThreadData([conversation({ title: "" })]);
    expect(row.title).toBe("New conversation");
  });

  it("trims whitespace-only titles to New conversation", () => {
    const [row] = toThreadData([conversation({ title: "   " })]);
    expect(row.title).toBe("New conversation");
  });
});
