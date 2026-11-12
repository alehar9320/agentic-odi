import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

import "fake-indexeddb/auto";

import { ActivityCentre, recordNotice } from "./ActivityCentre";
import { openLocalStore } from "../../bff/store/openStore";
import type { StoredNotice } from "../../bff/store/types";

function baseNotice(overrides: Partial<StoredNotice> = {}): StoredNotice {
  return {
    id: crypto.randomUUID(),
    severity: "info",
    title: "Test notice",
    detail: "A test detail",
    context: null,
    at: new Date().toISOString(),
    read: false,
    dismissed: false,
    ...overrides,
  };
}

async function seedStore(notices: StoredNotice[]) {
  const store = await openLocalStore();
  for (const notice of notices) {
    await store.putNotice(notice);
  }
  store.close();
}

describe("recordNotice", () => {
  let store: ReturnType<typeof openLocalStore>;

  beforeEach(async () => {
    store = await openLocalStore();
  });

  afterEach(async () => {
    await store.clearAll();
    store.close();
  });

  it("writes a notice with read false", async () => {
    await recordNotice({ severity: "info", title: "Hello", detail: "World" });
    const list = await store.listNotices();
    expect(list).toHaveLength(1);
    expect(list[0].title).toBe("Hello");
    expect(list[0].read).toBe(false);
  });

  it("dedupes the same notice within 60 seconds", async () => {
    await recordNotice({
      severity: "info",
      title: "Same",
      detail: "Same detail",
      at: "2026-01-01T00:00:00Z",
    });
    await recordNotice({
      severity: "info",
      title: "Same",
      detail: "Same detail",
      at: "2026-01-01T00:00:30Z",
    });
    const list = await store.listNotices();
    expect(list).toHaveLength(1);
  });

  it("does not dedupe after 60 seconds", async () => {
    await recordNotice({
      severity: "info",
      title: "Same",
      detail: "Same detail",
      at: "2026-01-01T00:00:00Z",
    });
    await recordNotice({
      severity: "info",
      title: "Same",
      detail: "Same detail",
      at: "2026-01-01T00:01:00Z",
    });
    const list = await store.listNotices();
    expect(list).toHaveLength(2);
  });

  it("treats different severities as different notices", async () => {
    await recordNotice({
      severity: "info",
      title: "Same",
      detail: "Same detail",
    });
    await recordNotice({
      severity: "critical",
      title: "Same",
      detail: "Same detail",
    });
    const list = await store.listNotices();
    expect(list).toHaveLength(2);
  });

  it("caps the list at 200 entries, dropping the oldest", async () => {
    for (let i = 0; i < 205; i += 1) {
      await recordNotice({
        severity: "info",
        title: `Notice ${i}`,
        detail: `Detail ${i}`,
        at: new Date(Date.now() + i).toISOString(),
      });
    }
    const list = await store.listNotices();
    expect(list).toHaveLength(200);
    expect(list[0].title).toBe("Notice 204");
    expect(list[199].title).toBe("Notice 5");
  });
});

describe("ActivityCentre", () => {
  let store: ReturnType<typeof openLocalStore>;

  beforeEach(async () => {
    store = await openLocalStore();
  });

  afterEach(async () => {
    await store.clearAll();
    store.close();
  });

  it("renders the empty state when there are no notices", async () => {
    render(<ActivityCentre open={true} onClose={() => undefined} />);
    expect(
      await screen.findByText("Nothing has happened yet in this workspace."),
    ).toBeInTheDocument();
  });

  it("renders notices grouped by day", async () => {
    const today = new Date().toISOString();
    const yesterday = new Date(Date.now() - 86_400_000).toISOString();
    await seedStore([
      baseNotice({ id: "n-1", title: "Today notice", at: today }),
      baseNotice({ id: "n-2", title: "Yesterday notice", at: yesterday }),
    ]);
    render(<ActivityCentre open={true} onClose={() => undefined} />);
    await waitFor(() => expect(screen.getByText("Today")).toBeInTheDocument());
    await waitFor(() =>
      expect(screen.getByText("Yesterday")).toBeInTheDocument(),
    );
    expect(screen.getByText("Today notice")).toBeInTheDocument();
    expect(screen.getByText("Yesterday notice")).toBeInTheDocument();
  });

  it("shows severity and time on each row", async () => {
    const now = new Date().toISOString();
    await seedStore([
      baseNotice({
        id: "n-1",
        severity: "critical",
        title: "Critical thing",
        at: now,
      }),
    ]);
    render(<ActivityCentre open={true} onClose={() => undefined} />);
    await waitFor(() => expect(screen.getByText("Critical thing")).toBeInTheDocument());
    expect(screen.getByText("critical")).toBeInTheDocument();
    expect(screen.getByRole("time")).toBeInTheDocument();
  });

  it("dismissing removes a notice from the list", async () => {
    const now = new Date().toISOString();
    await seedStore([
      baseNotice({ id: "n-1", title: "Dismiss me", at: now }),
      baseNotice({ id: "n-2", title: "Keep me", at: now }),
    ]);
    render(<ActivityCentre open={true} onClose={() => undefined} />);
    await waitFor(() => expect(screen.getByText("Dismiss me")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("Dismiss Dismiss me"));
    await waitFor(() => expect(screen.queryByText("Dismiss me")).not.toBeInTheDocument());
    expect(screen.getByText("Keep me")).toBeInTheDocument();
  });

  it("mark all read marks every notice as read", async () => {
    const now = new Date().toISOString();
    await seedStore([
      baseNotice({ id: "n-1", title: "One", at: now, read: false }),
      baseNotice({ id: "n-2", title: "Two", at: now, read: false }),
    ]);
    render(<ActivityCentre open={true} onClose={() => undefined} />);
    await waitFor(() => expect(screen.getByText("Mark all read")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Mark all read"));
    await waitFor(() => {
      const notices = store.listNotices();
      return notices.then((list) => list.every((n) => n.read));
    });
    expect((await store.listNotices()).every((n) => n.read)).toBe(true);
  });
});
