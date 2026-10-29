import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  check: vi.fn(),
  relaunch: vi.fn(),
  getVersion: vi.fn(),
}));

vi.mock("@tauri-apps/plugin-updater", () => ({ check: mocks.check }));
vi.mock("@tauri-apps/plugin-process", () => ({ relaunch: mocks.relaunch }));
vi.mock("@tauri-apps/api/app", () => ({ getVersion: mocks.getVersion }));

import { createDesktopTransport } from "./transport";
import type { DownloadProgress } from "./types";

type DownloadCallback = (event:
  | { event: "Started"; data: { contentLength?: number } }
  | { event: "Progress"; data: { chunkLength: number } }
  | { event: "Finished" }) => void;

function fakeUpdate(overrides: Record<string, unknown> = {}) {
  return {
    version: "0.12.0",
    currentVersion: "0.11.0",
    date: "2026-10-21T10:00:00Z",
    body: "Quieter sync.",
    download: vi.fn(async (callback: DownloadCallback) => {
      callback({ event: "Started", data: { contentLength: 100 } });
      callback({ event: "Progress", data: { chunkLength: 40 } });
      callback({ event: "Progress", data: { chunkLength: 60 } });
      callback({ event: "Finished" });
    }),
    install: vi.fn(async () => undefined),
    close: vi.fn(async () => undefined),
    ...overrides,
  };
}

function markTauri(): void {
  (window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__ = {};
}

beforeEach(() => {
  mocks.check.mockReset();
  mocks.relaunch.mockReset();
  mocks.getVersion.mockReset();
  markTauri();
});

afterEach(() => {
  delete (window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__;
});

describe("createDesktopTransport", () => {
  it("is only supported inside the desktop shell", () => {
    expect(createDesktopTransport().supported()).toBe(true);
    delete (window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__;
    expect(createDesktopTransport().supported()).toBe(false);
  });

  it("reads the running app version", async () => {
    mocks.getVersion.mockResolvedValue("0.11.0");
    await expect(createDesktopTransport().currentVersion()).resolves.toBe("0.11.0");
  });

  it("maps a release into the domain shape", async () => {
    mocks.check.mockResolvedValue(fakeUpdate());

    const handle = await createDesktopTransport().check();

    expect(handle).toMatchObject({
      version: "0.12.0",
      currentVersion: "0.11.0",
      date: "2026-10-21T10:00:00Z",
      notes: "Quieter sync.",
    });
  });

  it("returns null when the app is current", async () => {
    mocks.check.mockResolvedValue(null);
    await expect(createDesktopTransport().check()).resolves.toBeNull();
  });

  it("accumulates download chunks into received and total", async () => {
    const update = fakeUpdate();
    mocks.check.mockResolvedValue(update);
    const handle = await createDesktopTransport().check();
    const events: DownloadProgress[] = [];

    await handle?.download((progress) => events.push(progress));

    expect(events).toEqual([
      { received: 0, total: 100 },
      { received: 40, total: 100 },
      { received: 100, total: 100 },
    ]);
  });

  it("reports an unknown total when the server omits the length", async () => {
    const update = fakeUpdate({
      download: vi.fn(async (callback: DownloadCallback) => {
        callback({ event: "Started", data: {} });
        callback({ event: "Progress", data: { chunkLength: 12 } });
      }),
    });
    mocks.check.mockResolvedValue(update);
    const handle = await createDesktopTransport().check();
    const events: DownloadProgress[] = [];

    await handle?.download((progress) => events.push(progress));

    expect(events).toEqual([
      { received: 0, total: null },
      { received: 12, total: null },
    ]);
  });

  it("delegates install, close, and relaunch to the plugins", async () => {
    const update = fakeUpdate();
    mocks.check.mockResolvedValue(update);
    mocks.relaunch.mockResolvedValue(undefined);

    const handle = await createDesktopTransport().check();
    await handle?.install();
    await handle?.close();
    await createDesktopTransport().relaunch();

    expect(update.install).toHaveBeenCalledTimes(1);
    expect(update.close).toHaveBeenCalledTimes(1);
    expect(mocks.relaunch).toHaveBeenCalledTimes(1);
  });
});
