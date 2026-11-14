import { describe, expect, it } from "vitest";

import {
  NOTICE_CAP,
  dismissNotice,
  groupNoticesByDay,
  markAllRead,
  recordNotice,
  unreadCount,
} from "./recorder";
import type { Notice, NoticeInput } from "./types";

function input(overrides: Partial<NoticeInput> = {}): NoticeInput {
  return {
    severity: "info",
    title: "The sidecar isn't running.",
    detail: "Live data is frozen until it comes back.",
    context: "Banner: sidecar-down",
    at: 1_700_000_000_000,
    ...overrides,
  };
}

describe("recordNotice", () => {
  it("records a notice, newest first", () => {
    let list: Notice[] = [];
    list = recordNotice(list, input({ title: "First", at: 1_000 }));
    list = recordNotice(list, input({ title: "Second", at: 2_000 }));

    expect(list.map((notice) => notice.title)).toEqual(["Second", "First"]);
    expect(list[0].read).toBe(false);
    expect(list[0].id).toBeTruthy();
  });

  it("dedupes the same statement raised twice inside the window", () => {
    let list: Notice[] = [];
    list = recordNotice(list, input({ at: 1_000 }));
    list = recordNotice(list, input({ at: 1_000 + 30_000 }));

    expect(list).toHaveLength(1);
  });

  it("keeps a repeat raised outside the window", () => {
    let list: Notice[] = [];
    list = recordNotice(list, input({ at: 1_000 }));
    list = recordNotice(list, input({ at: 1_000 + 61_000 }));

    expect(list).toHaveLength(2);
  });

  it("treats a different severity as a different fact", () => {
    let list: Notice[] = [];
    list = recordNotice(list, input({ severity: "info", at: 1_000 }));
    list = recordNotice(list, input({ severity: "critical", at: 1_000 }));

    expect(list).toHaveLength(2);
  });

  it("caps the history and drops the oldest", () => {
    let list: Notice[] = [];
    for (let index = 0; index < NOTICE_CAP + 5; index += 1) {
      list = recordNotice(
        list,
        input({ title: `Notice ${index}`, detail: `body ${index}`, at: 1_000 + index * 100 }),
      );
    }

    expect(list).toHaveLength(NOTICE_CAP);
    expect(list[0].title).toBe(`Notice ${NOTICE_CAP + 4}`);
    expect(list.some((notice) => notice.title === "Notice 0")).toBe(false);
  });
});

describe("dismissNotice", () => {
  it("removes one row and leaves its neighbours", () => {
    let list: Notice[] = [];
    list = recordNotice(list, input({ title: "A", at: 1_000 }));
    list = recordNotice(list, input({ title: "B", at: 2_000 }));

    list = dismissNotice(list, list[0].id);

    expect(list.map((notice) => notice.title)).toEqual(["A"]);
  });
});

describe("markAllRead and unreadCount", () => {
  it("counts unread rows and clears them without removing rows", () => {
    let list: Notice[] = [];
    list = recordNotice(list, input({ title: "A", at: 1_000 }));
    list = recordNotice(list, input({ title: "B", at: 2_000 }));
    expect(unreadCount(list)).toBe(2);

    list = markAllRead(list);
    expect(unreadCount(list)).toBe(0);
    expect(list).toHaveLength(2);
  });
});

describe("groupNoticesByDay", () => {
  it("groups by calendar day, newest day first, with a readable label", () => {
    const now = new Date("2026-11-13T12:00:00Z");
    let list: Notice[] = [];
    list = recordNotice(list, input({ title: "Old", at: now.getTime() - 3 * 86_400_000 }));
    list = recordNotice(list, input({ title: "New", at: now.getTime() }));

    const groups = groupNoticesByDay(list, now);

    expect(groups[0].label).toBe("Today");
    expect(groups[0].items.map((notice) => notice.title)).toEqual(["New"]);
    expect(groups[1].items.map((notice) => notice.title)).toEqual(["Old"]);
  });
});
