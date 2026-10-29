import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { UpdateProvider } from "./UpdateProvider";
import { UpdateSettings } from "./UpdateSettings";
import { AUTO_CHECK_KEY, SKIPPED_VERSION_KEY, createUpdateService } from "./service";
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

  it("shows the running version and an up-to-date status", async () => {
    const transport = makeTransport();
    const service = renderSettings(transport);

    await act(async () => {
      await service.check();
    });

    expect(await screen.findByText("v0.11.0")).toBeInTheDocument();
    expect(screen.getByText("You're up to date.")).toBeInTheDocument();
    expect(screen.getByText(/checked just now/i)).toBeInTheDocument();
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

  it("offers release notes for the available version", async () => {
    const transport = makeTransport({ check: vi.fn(async () => makeHandle()) });
    const service = renderSettings(transport);

    await act(async () => {
      await service.check();
    });

    expect(screen.getByText("What's new in 0.12.0")).toBeInTheDocument();
    expect(screen.getByText("The canvas now follows the conversation.")).toBeInTheDocument();
  });

  it("lets a person skip a release that cannot be installed", async () => {
    const storage = memoryStorage();
    const transport = makeTransport({ check: vi.fn(async () => makeHandle()) });
    const service = renderSettings(transport, { platform: "windows", storage });

    await act(async () => {
      await service.check();
    });

    fireEvent.click(screen.getByRole("button", { name: "Skip this version" }));

    expect(storage.data.get(SKIPPED_VERSION_KEY)).toBe("0.12.0");
    expect(await screen.findByText(/is skipped/i)).toBeInTheDocument();
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
