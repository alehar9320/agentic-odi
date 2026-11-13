/**
 * The pending-call selector (issue #390).
 *
 * These tests pin the four states a tool part can be in — running, holding a
 * question, settled, and the kinds that are not calls at all — and the two
 * rules that keep the list from inventing anything: a settled call is never
 * kept alive, and a start time is passed through only when the store recorded
 * one.
 */

import { describe, expect, it } from "vitest";

import type { ChatPart } from "../types";
import { pendingCalls } from "./pending";

function call(overrides: Partial<Extract<ChatPart, { kind: "tool" }>> = {}): ChatPart {
  return { kind: "tool", id: "c-1", name: "list_jobs", status: "running", ...overrides };
}

describe("pendingCalls", () => {
  it("returns nothing for a turn with no calls", () => {
    expect(pendingCalls([])).toEqual([]);
    expect(pendingCalls([{ kind: "text", text: "The answer." }])).toEqual([]);
  });

  it("returns a running call with no clock when the store recorded no start", () => {
    expect(pendingCalls([call()])).toEqual([
      { id: "c-1", name: "list_jobs", awaitingApproval: false, prompt: null, startedAt: null },
    ]);
  });

  it("keeps a running call and an unanswered approval, in transcript order", () => {
    const pending = pendingCalls([
      call({ id: "c-1", name: "list_jobs" }),
      call({
        id: "c-2",
        name: "add_job",
        approval: { id: "a-1", prompt: "Add the retention job?" },
      }),
    ]);

    expect(pending.map((entry) => entry.id)).toEqual(["c-1", "c-2"]);
    expect(pending[1].awaitingApproval).toBe(true);
    expect(pending[1].prompt).toBe("Add the retention job?");
  });

  it("excludes a settled call, whatever preview it carries", () => {
    const pending = pendingCalls([
      call({ id: "c-1", status: "ok", preview: "3 jobs" }),
      call({ id: "c-2", status: "error" }),
      call({ id: "c-3", status: "declined" }),
    ]);

    expect(pending).toEqual([]);
  });

  it("passes the recorded start through, and never invents one", () => {
    const pending = pendingCalls([call({ startedAt: 1_700_000_000_000 })]);

    expect(pending[0].startedAt).toBe(1_700_000_000_000);
  });
});
