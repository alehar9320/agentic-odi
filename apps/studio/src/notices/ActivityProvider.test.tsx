import { act, render, screen, waitFor } from "@testing-library/react";
import "fake-indexeddb/auto";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { getStudioBff, resetStudioBffForTests } from "../bff";
import { ActivityProvider, useActivity } from "./ActivityProvider";

/**
 * A probe that records one notice on demand, so the provider can be driven
 * without a banner, a studio, or a socket. The persistence path is the real
 * one: it goes through `getStudioBff()` into IndexedDB.
 */
function Probe() {
  const { notices, unread, record, dismiss, markAllRead } = useActivity();
  return (
    <div>
      <span data-testid="count">{notices.length}</span>
      <span data-testid="unread">{unread}</span>
      <span data-testid="titles">{notices.map((n) => n.title).join(",")}</span>
      <button
        type="button"
        onClick={() =>
          record({
            severity: "critical",
            title: "Sidecar down",
            detail: "The assistant is paused.",
            context: "Banner: sidecar-down",
          })
        }
      >
        record
      </button>
      <button type="button" onClick={markAllRead}>
        read
      </button>
      <button type="button" onClick={() => dismiss(notices[0]?.id ?? "")}>
        dismiss
      </button>
    </div>
  );
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
  });
}

describe("ActivityProvider", () => {
  beforeEach(async () => {
    await resetStudioBffForTests();
    const bff = await getStudioBff();
    await bff.store.putNotices([]);
  });

  afterEach(async () => {
    await resetStudioBffForTests();
  });

  it("starts empty and records a notice into the store", async () => {
    render(
      <ActivityProvider>
        <Probe />
      </ActivityProvider>,
    );
    await flush();

    await act(async () => {
      screen.getByRole("button", { name: "record" }).click();
    });
    await flush();

    expect(screen.getByTestId("count").textContent).toBe("1");
    expect(screen.getByTestId("unread").textContent).toBe("1");

    const bff = await getStudioBff();
    await waitFor(async () => {
      expect((await bff.store.listNotices()).map((n) => n.title)).toEqual(["Sidecar down"]);
    });
  });

  it("reads a previously stored history back on mount", async () => {
    const bff = await getStudioBff();
    await bff.store.putNotices([
      {
        id: "n-1",
        severity: "warning",
        title: "Model unreachable",
        detail: "Retrying.",
        context: "Banner: model-offline",
        at: 5_000,
        read: false,
      },
    ]);

    render(
      <ActivityProvider>
        <Probe />
      </ActivityProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("titles").textContent).toBe("Model unreachable");
    });
  });

  it("persists a dismissal so it does not return", async () => {
    const { unmount } = render(
      <ActivityProvider>
        <Probe />
      </ActivityProvider>,
    );
    await flush();
    await act(async () => {
      screen.getByRole("button", { name: "record" }).click();
    });
    await flush();
    await act(async () => {
      screen.getByRole("button", { name: "dismiss" }).click();
    });
    await flush();
    unmount();

    const bff = await getStudioBff();
    await waitFor(async () => {
      expect(await bff.store.listNotices()).toEqual([]);
    });
  });
});
