import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { UpdateBanner } from "./UpdateBanner";
import { UpdateProvider } from "./UpdateProvider";
import { createUpdateService } from "./service";
import type { DownloadProgress, UpdateTransport, UpdaterHandle } from "./types";

function makeHandle(overrides: Partial<UpdaterHandle> = {}): UpdaterHandle {
  return {
    version: "0.12.0",
    currentVersion: "0.11.0",
    date: "2026-10-21T10:00:00Z",
    notes: "Faster canvas.",
    download: vi.fn(async (onProgress: (progress: DownloadProgress) => void) => {
      onProgress({ received: 10, total: 10 });
    }),
    install: vi.fn(async () => undefined),
    close: vi.fn(async () => undefined),
    ...overrides,
  };
}

function makeTransport(overrides: Partial<UpdateTransport> = {}): UpdateTransport {
  return {
    supported: () => true,
    currentVersion: vi.fn(async () => "0.11.0"),
    check: vi.fn(async () => null),
    relaunch: vi.fn(async () => undefined),
    ...overrides,
  };
}

function renderBanner(transport: UpdateTransport, platform: "linux" | "windows" = "linux") {
  const service = createUpdateService({
    transport,
    storage: null,
    platform,
    document: null,
    initialDelayMs: 60_000,
  });

  render(
    <UpdateProvider service={service}>
      <UpdateBanner />
    </UpdateProvider>,
  );

  return service;
}

describe("UpdateBanner", () => {
  it("stays out of the way when there is nothing to say", async () => {
    const service = renderBanner(makeTransport());
    await act(async () => {
      await service.check();
    });

    expect(screen.queryByRole("status", { name: "Software update" })).toBeNull();
  });

  it("shows quiet progress while the update downloads", async () => {
    let push: ((progress: DownloadProgress) => void) | null = null;
    const transport = makeTransport({
      check: vi.fn(async () =>
        makeHandle({
          download: (onProgress) => {
            push = onProgress;
            return new Promise<void>(() => undefined);
          },
        }),
      ),
    });
    const service = renderBanner(transport);

    await act(async () => {
      void service.check();
      await Promise.resolve();
    });
    act(() => push?.({ received: 5, total: 10 }));

    expect(screen.getByText("Downloading version 0.12.0")).toBeInTheDocument();
    expect(screen.getByText(/keep working/i)).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("offers one clear restart once the update is staged", async () => {
    const transport = makeTransport({ check: vi.fn(async () => makeHandle()) });
    const service = renderBanner(transport);

    await act(async () => {
      await service.check();
    });

    expect(screen.getByText("Version 0.12.0 is ready")).toBeInTheDocument();
    expect(screen.getByText(/next time you open the studio/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Restart now" }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(transport.relaunch).toHaveBeenCalledTimes(1);
  });

  it("asks before exiting on Windows", async () => {
    const transport = makeTransport({ check: vi.fn(async () => makeHandle()) });
    const service = renderBanner(transport, "windows");

    await act(async () => {
      await service.check();
    });

    expect(screen.getByText(/closes and reopens/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Update & restart" }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(transport.relaunch).toHaveBeenCalledTimes(1);
  });

  it("can be dismissed without losing the staged update", async () => {
    const transport = makeTransport({ check: vi.fn(async () => makeHandle()) });
    const service = renderBanner(transport);

    await act(async () => {
      await service.check();
    });

    fireEvent.click(screen.getByRole("button", { name: "Dismiss update notice" }));

    expect(screen.queryByText("Version 0.12.0 is ready")).toBeNull();
    expect(service.getSnapshot().installed).toBe(true);
  });

  it("offers a retry when the update fails", async () => {
    const broken = makeHandle({
      download: vi.fn(async () => {
        throw new Error("connection reset");
      }),
    });
    const healthy = makeHandle();
    const transport = makeTransport({
      check: vi.fn().mockResolvedValueOnce(broken).mockResolvedValueOnce(healthy),
    });
    const service = renderBanner(transport);

    await act(async () => {
      await service.check();
    });

    expect(screen.getByText("The update didn't finish")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(
      await screen.findByText("Version 0.12.0 is ready"),
    ).toBeInTheDocument();
  });
});
