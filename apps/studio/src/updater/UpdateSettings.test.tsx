import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { UpdateProvider } from "./UpdateProvider";
import { UpdateSettings } from "./UpdateSettings";
import { AUTO_CHECK_KEY, createUpdateService } from "./service";
import type { DownloadProgress, UpdateTransport, UpdaterHandle } from "./types";

function memoryStorage(initial: Record<string, string> = {}) {
  const data = new Map<string, string>(Object.entries(initial));
  return {
    data,
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => {
      data.set(key, value);
    },
    removeItem: (key: string) => {
      data.delete(key);
    },
  };
}

function makeHandle(overrides: Partial<UpdaterHandle> = {}): UpdaterHandle {
  return {
    version: "0.12.0",
    currentVersion: "0.11.0",
    date: "2026-10-21T10:00:00Z",
    notes: "The canvas now follows the conversation.",
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

function renderSettings(
  transport: UpdateTransport,
  options: {
    platform?: "linux" | "windows";
    storage?: ReturnType<typeof memoryStorage> | null;
  } = {},
) {
  const service = createUpdateService({
    transport,
    storage: options.storage === undefined ? memoryStorage() : options.storage,
    platform: options.platform ?? "linux",
    document: null,
    initialDelayMs: 60_000,
  });

  render(
    <UpdateProvider service={service}>
      <UpdateSettings />
    </UpdateProvider>,
  );

  return service;
}

describe("UpdateSettings", () => {
  it("says where updates live in a browser", async () => {
    renderSettings(makeTransport({ supported: () => false }));

    expect(
      await screen.findByText(/in-app updates live in the installed desktop app/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Check now" })).toBeNull();
  });

  it("shows one state line and at most one action", async () => {
    const transport = makeTransport();
    const service = renderSettings(transport);

    await act(async () => {
      await service.check();
    });

    expect(await screen.findByText("You're up to date.")).toBeInTheDocument();
    // The updater's detail (the running version, the last check, the release
    // notes) lives in About or the banner, never in this row.
    expect(screen.queryByText("v0.11.0")).toBeNull();
    expect(screen.queryByText(/checked just now/i)).toBeNull();

    const section = screen.getByRole("region", { name: "Updates" });
    expect(within(section).getAllByRole("button")).toHaveLength(1);
  });

  it("says it could not check, and when it last could", async () => {
    const healthy = makeTransport();
    const service = renderSettings(healthy);

    await act(async () => {
      await service.check();
    });

    healthy.check = vi.fn(async () => {
      throw new Error("offline");
    });
    await act(async () => {
      await service.retry();
    });

    expect(
      await screen.findByText(/couldn't reach the update server\. last successful check was/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^checked .* ago$/i)).toBeNull();
  });

  it("shows a bounded, newest-first list of what the updater did", async () => {
    const service = renderSettings(makeTransport());

    await act(async () => {
      await service.check();
    });

    fireEvent.click(screen.getByText("Recent update activity"));

    expect(screen.getByText("Reached the update server")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("checks on request", async () => {
    const transport = makeTransport();
    renderSettings(transport);

    fireEvent.click(screen.getByRole("button", { name: "Check now" }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(transport.check).toHaveBeenCalledTimes(1);
  });

  it("remembers turning automatic checks off", async () => {
    const storage = memoryStorage();
    renderSettings(makeTransport(), { storage });

    const toggle = screen.getByRole("checkbox", { name: /check for updates automatically/i });
    expect(toggle).toBeChecked();

    fireEvent.click(toggle);

    expect(storage.data.get(AUTO_CHECK_KEY)).toBe("off");
    expect(toggle).not.toBeChecked();
  });

  it("offers the restart once an update is ready", async () => {
    const transport = makeTransport({ check: vi.fn(async () => makeHandle()) });
    const service = renderSettings(transport);

    await act(async () => {
      await service.check();
    });

    fireEvent.click(screen.getByRole("button", { name: "Restart now" }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(transport.relaunch).toHaveBeenCalledTimes(1);
  });
});
