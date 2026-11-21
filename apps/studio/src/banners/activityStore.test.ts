import { describe, it, expect } from "vitest";
import {
  recordNotice,
  dismissNotice,
  deleteNotice,
  groupNoticesByDay,
  severityWeight,
  severityLabel,
  EMPTY_ACTIVITY_STATE,
} from "./activityStore";
import type { StoredNotice } from "../bff/store/types";

function makeNotice(overrides: Partial<StoredNotice> = {}): Omit<StoredNotice, "id" | "dismissed" | "at"> {
  return {
    severity: "info",
    title: "Test notice",
    detail: "Something happened",
    context: null,
    ...overrides,
  };
}

describe("recordNotice", () => {
  it("adds a notice to empty state", () => {
    const state = recordNotice(EMPTY_ACTIVITY_STATE, makeNotice());
    expect(state.notices).toHaveLength(1);
    expect(state.notices[0].title).toBe("Test notice");
    expect(state.notices[0].dismissed).toBe(false);
    expect(state.notices[0].id).toBeDefined();
    expect(state.notices[0].at).toBeDefined();
  });

  it("prepends new notices (newest first)", () => {
    let state = recordNotice(EMPTY_ACTIVITY_STATE, makeNotice({ title: "First" }));
    state = recordNotice(state, makeNotice({ title: "Second" }));
    expect(state.notices).toHaveLength(2);
    expect(state.notices[0].title).toBe("Second");
    expect(state.notices[1].title).toBe("First");
  });

  it("caps at MAX_NOTICES (200)", () => {
    let state = EMPTY_ACTIVITY_STATE;
    for (let i = 0; i < 210; i++) {
      state = recordNotice(state, makeNotice({ title: `Notice ${i}` }));
    }
    expect(state.notices).toHaveLength(200);
    expect(state.notices[0].title).toBe("Notice 209");
    expect(state.notices[199].title).toBe("Notice 10");
  });

  it("dedupes same severity, title, detail within 60s", () => {
    const baseTime = Date.now();
    let state = recordNotice(EMPTY_ACTIVITY_STATE, makeNotice({ title: "Duplicate" }), baseTime);
    state = recordNotice(state, makeNotice({ title: "Duplicate" }), baseTime + 1000);
    expect(state.notices).toHaveLength(1);
  });

  it("allows duplicate after 60s window", () => {
    const baseTime = Date.now();
    let state = recordNotice(EMPTY_ACTIVITY_STATE, makeNotice({ title: "Duplicate" }), baseTime);
    state = recordNotice(state, makeNotice({ title: "Duplicate" }), baseTime + 61_000);
    expect(state.notices).toHaveLength(2);
  });

  it("does not dedupe different severity", () => {
    const baseTime = Date.now();
    let state = recordNotice(EMPTY_ACTIVITY_STATE, makeNotice({ severity: "info", title: "Same" }), baseTime);
    state = recordNotice(state, makeNotice({ severity: "warning", title: "Same" }), baseTime + 1000);
    expect(state.notices).toHaveLength(2);
  });

  it("does not dedupe different title", () => {
    const baseTime = Date.now();
    let state = recordNotice(EMPTY_ACTIVITY_STATE, makeNotice({ title: "First" }), baseTime);
    state = recordNotice(state, makeNotice({ title: "Second" }), baseTime + 1000);
    expect(state.notices).toHaveLength(2);
  });

  it("does not dedupe different detail", () => {
    const baseTime = Date.now();
    let state = recordNotice(EMPTY_ACTIVITY_STATE, makeNotice({ detail: "First" }), baseTime);
    state = recordNotice(state, makeNotice({ detail: "Second" }), baseTime + 1000);
    expect(state.notices).toHaveLength(2);
  });
});

describe("dismissNotice", () => {
  it("marks notice as dismissed", () => {
    let state = recordNotice(EMPTY_ACTIVITY_STATE, makeNotice({ id: "test-id" }));
    state = dismissNotice(state, state.notices[0].id);
    expect(state.notices[0].dismissed).toBe(true);
  });

  it("does nothing for unknown id", () => {
    let state = recordNotice(EMPTY_ACTIVITY_STATE, makeNotice());
    state = dismissNotice(state, "unknown-id");
    expect(state.notices[0].dismissed).toBe(false);
  });
});

describe("deleteNotice", () => {
  it("removes notice from history", () => {
    let state = recordNotice(EMPTY_ACTIVITY_STATE, makeNotice());
    const id = state.notices[0].id;
    state = deleteNotice(state, id);
    expect(state.notices).toHaveLength(0);
  });
});

describe("groupNoticesByDay", () => {
  it("groups notices by day", () => {
    const now = new Date();
    const yesterday = new Date(now.getTime() - 86_400_000);
    const notices: StoredNotice[] = [
      { id: "1", severity: "info", title: "Today", detail: "a", context: null, at: now.toISOString(), dismissed: false },
      { id: "2", severity: "info", title: "Yesterday", detail: "b", context: null, at: yesterday.toISOString(), dismissed: false },
    ];
    const groups = groupNoticesByDay(notices);
    expect(groups).toHaveLength(2);
    expect(groups[0].items).toHaveLength(1);
    expect(groups[1].items).toHaveLength(1);
  });

  it("returns empty array for no notices", () => {
    expect(groupNoticesByDay([])).toEqual([]);
  });
});

describe("severityWeight", () => {
  it("returns correct weights", () => {
    expect(severityWeight("critical")).toBe(4);
    expect(severityWeight("warning")).toBe(3);
    expect(severityWeight("info")).toBe(2);
    expect(severityWeight("success")).toBe(1);
  });
});

describe("severityLabel", () => {
  it("capitalizes severity", () => {
    expect(severityLabel("critical")).toBe("Critical");
    expect(severityLabel("warning")).toBe("Warning");
    expect(severityLabel("info")).toBe("Info");
    expect(severityLabel("success")).toBe("Success");
  });
});