import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  AUTO_CHECK_KEY,
  SKIPPED_VERSION_KEY,
  createUpdateService,
  describeUpdateFailure,
} from "./service";
import type { UpdateTransport, UpdaterHandle } from "./types";

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
    notes: "Faster canvas, quieter sync.",
    download: vi.fn(async (onProgress) => {
      onProgress({ received: 5, total: 10 });
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

function createService(
  transport: UpdateTransport,
  extra: { storage?: ReturnType<typeof memoryStorage> | null; platform?: "linux" | "windows" | "macos" | "unknown"; document?: null } = {},
) {
  return createUpdateService({
    transport,
    storage: extra.storage === undefined ? memoryStorage() : extra.storage,
    platform: extra.platform ?? "linux",
    document: extra.document ?? null,
    initialDelayMs: 4_000,
    intervalMs: 60_000,
  });
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("runtime support", () => {
  it("reports an unsupported runtime instead of pretending to check", async () => {
    const transport = makeTransport({ supported: () => false });
    const service = createService(transport);

    service.start();
    await service.check();

    expect(service.getSnapshot().phase).toBe("unsupported");
    expect(transport.check).not.toHaveBeenCalled();
    expect(service.bannerView()).toBeNull();
  });
});

describe("checking", () => {
  it("checks after the startup delay, never during first paint", async () => {
    const transport = makeTransport();
    const service = createService(transport);

    service.start();
    await vi.advanceTimersByTimeAsync(3_999);
    expect(transport.check).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(transport.check).toHaveBeenCalledTimes(1);
  });

  it("records the running version at startup", async () => {
    const service = createService(makeTransport());
    service.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(service.getSnapshot().currentVersion).toBe("0.11.0");
  });

  it("records an up-to-date app", async () => {
    const service = createService(makeTransport());
    await service.check();

    const snapshot = service.getSnapshot();
    expect(snapshot.phase).toBe("up-to-date");
    expect(snapshot.lastCheckedAt).not.toBeNull();
    expect(service.bannerView()).toBeNull();
  });

  it("never runs two checks at once", async () => {
    let release: (value: null) => void = () => undefined;
    const pending = new Promise<null>((resolve) => {
      release = resolve;
    });
    const transport = makeTransport({ check: vi.fn(() => pending) });
    const service = createService(transport);

    const first = service.check();
    const second = service.check();
    release(null);
    await Promise.all([first, second]);

    expect(transport.check).toHaveBeenCalledTimes(1);
  });

  it("stops polling after stop()", async () => {
    const transport = makeTransport();
    const service = createService(transport);
    service.start();
    service.stop();

    await vi.advanceTimersByTimeAsync(10_000);
    expect(transport.check).not.toHaveBeenCalled();
  });

  it("re-checks when the window returns after the interval", async () => {
    const pending: { listener: (() => void) | null } = { listener: null };
    const fakeDocument = {
      visibilityState: "visible" as DocumentVisibilityState,
      addEventListener: (_type: string, callback: () => void) => {
        pending.listener = callback;
      },
      removeEventListener: () => {
        pending.listener = null;
      },
    } as unknown as Pick<
      Document,
      "addEventListener" | "removeEventListener" | "visibilityState"
    >;
    const transport = makeTransport();
    const service = createUpdateService({
      transport,
      storage: memoryStorage(),
      platform: "linux",
      document: fakeDocument,
      initialDelayMs: 1_000,
      intervalMs: 60_000,
    });

    service.start();
    await vi.advanceTimersByTimeAsync(1_000);
    expect(transport.check).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1);
    pending.listener?.();
    expect(transport.check).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(60_000);
    pending.listener?.();
    expect(transport.check).toHaveBeenCalledTimes(2);
  });
});

describe("downloading and installing", () => {
  it("downloads, installs, and reports progress on macOS and Linux", async () => {
    const handle = makeHandle();
    const transport = makeTransport({ check: vi.fn(async () => handle) });
    const service = createService(transport, { platform: "linux" });

    await service.check();

    expect(handle.download).toHaveBeenCalledTimes(1);
    expect(handle.install).toHaveBeenCalledTimes(1);
    const snapshot = service.getSnapshot();
    expect(snapshot.phase).toBe("ready");
    expect(snapshot.installed).toBe(true);
    expect(snapshot.pendingInstall).toBe(false);
    expect(snapshot.available?.version).toBe("0.12.0");
    expect(service.bannerView()?.kind).toBe("ready");
    expect(service.canRestartNow()).toBe(true);
  });

  it("shows the percentage while bytes arrive", async () => {
    const seen: (number | null)[] = [];
    const handle = makeHandle({
      download: vi.fn(async (onProgress) => {
        onProgress({ received: 5, total: 10 });
        seen.push(service.progressPercent());
        onProgress({ received: 10, total: 10 });
        seen.push(service.progressPercent());
      }),
    });
    const service = createService(makeTransport({ check: vi.fn(async () => handle) }));

    await service.check();

    expect(seen).toEqual([0.5, 1]);
  });

  it("stages a Windows download without exiting the app", async () => {
    const handle = makeHandle();
    const transport = makeTransport({ check: vi.fn(async () => handle) });
    const service = createService(transport, { platform: "windows" });

    await service.check();

    expect(handle.install).not.toHaveBeenCalled();
    expect(service.getSnapshot().pendingInstall).toBe(true);
    expect(service.getSnapshot().installed).toBe(false);
    expect(service.canRestartNow()).toBe(false);
    expect(service.bannerView()).toMatchObject({ kind: "ready", pendingInstall: true });
  });

  it("explains a download failure and retries from the beginning", async () => {
    const broken = makeHandle({
      download: vi.fn(async () => {
        throw new Error("connection reset");
      }),
    });
    const healthy = makeHandle();
    const transport = makeTransport({
      check: vi
        .fn()
        .mockResolvedValueOnce(broken)
        .mockResolvedValueOnce(healthy),
    });
    const service = createService(transport);

    await service.check();
    expect(service.getSnapshot().phase).toBe("error");
    expect(service.getSnapshot().error).toMatch(/download/i);
    expect(service.bannerView()?.kind).toBe("error");

    await service.retry();
    expect(transport.check).toHaveBeenCalledTimes(2);
    expect(service.getSnapshot().phase).toBe("ready");
  });

  it("retries a failed install without downloading again", async () => {
    const install = vi
      .fn<() => Promise<void>>()
      .mockRejectedValueOnce(new Error("permission denied"))
      .mockResolvedValueOnce(undefined);
    const handle = makeHandle({ install });
    const transport = makeTransport({ check: vi.fn(async () => handle) });
    const service = createService(transport);

    await service.check();
    expect(service.getSnapshot().error).toMatch(/latest release/i);

    await service.retry();
    expect(handle.download).toHaveBeenCalledTimes(1);
    expect(install).toHaveBeenCalledTimes(2);
    expect(service.getSnapshot().phase).toBe("ready");
  });

  it("reports a signature failure in plain language", async () => {
    const handle = makeHandle({
      download: vi.fn(async () => {
        throw new Error("signature verification failed");
      }),
    });
    const service = createService(makeTransport({ check: vi.fn(async () => handle) }));

    await service.check();

    expect(service.getSnapshot().error).toBe(
      "The update couldn't be verified. Try again, or install the latest release.",
    );
  });
});

describe("restarting", () => {
  it("relaunches a staged update without installing it again", async () => {
    const handle = makeHandle();
    const transport = makeTransport({ check: vi.fn(async () => handle) });
    const service = createService(transport);

    await service.check();
    await service.installAndRestart();

    expect(handle.install).toHaveBeenCalledTimes(1);
    expect(transport.relaunch).toHaveBeenCalledTimes(1);
  });

  it("installs first on Windows, then relaunches", async () => {
    const handle = makeHandle();
    const transport = makeTransport({ check: vi.fn(async () => handle) });
    const service = createService(transport, { platform: "windows" });

    await service.check();
    await service.installAndRestart();

    expect(handle.install).toHaveBeenCalledTimes(1);
    expect(transport.relaunch).toHaveBeenCalledTimes(1);
    expect(service.getSnapshot().installed).toBe(true);
  });

  it("reports a Windows install failure without pretending to relaunch", async () => {
    const handle = makeHandle({
      install: vi.fn(async () => {
        throw new Error("permission denied");
      }),
    });
    const transport = makeTransport({ check: vi.fn(async () => handle) });
    const service = createService(transport, { platform: "windows" });

    await service.check();
    await service.installAndRestart();

    expect(service.getSnapshot().error).toMatch(/latest release/i);
    expect(transport.relaunch).not.toHaveBeenCalled();
  });

  it("surfaces a relaunch failure without losing the staged update", async () => {
    const relaunch = vi
      .fn<() => Promise<void>>()
      .mockRejectedValueOnce(new Error("relaunch failed"))
      .mockResolvedValueOnce(undefined);
    const transport = makeTransport({
      check: vi.fn(async () => makeHandle()),
      relaunch,
    });
    const service = createService(transport);

    await service.check();
    await service.installAndRestart();

    expect(service.getSnapshot().phase).toBe("error");
    expect(service.getSnapshot().error).toMatch(/couldn't restart/i);
    expect(service.getSnapshot().installed).toBe(true);

    await service.retry();
    expect(relaunch).toHaveBeenCalledTimes(2);
  });
});

describe("preferences", () => {
  it("honours a version the person skipped, without downloading it", async () => {
    const handle = makeHandle();
    const transport = makeTransport({ check: vi.fn(async () => handle) });
    const storage = memoryStorage({ [SKIPPED_VERSION_KEY]: "0.12.0" });
    const service = createService(transport, { storage });

    await service.check();

    expect(handle.download).not.toHaveBeenCalled();
    expect(service.getSnapshot().phase).toBe("up-to-date");
    expect(service.getSnapshot().skippedVersion).toBe("0.12.0");
    expect(service.bannerView()).toBeNull();
  });

  it("remembers a skip for the next launch", async () => {
    const storage = memoryStorage();
    const service = createService(
      makeTransport({ check: vi.fn(async () => makeHandle()) }),
      { storage },
    );

    await service.check();
    service.skipCurrent();

    expect(storage.data.get(SKIPPED_VERSION_KEY)).toBe("0.12.0");
    expect(service.bannerView()).toBeNull();
  });

  it("does not check automatically when the person turned it off", async () => {
    const transport = makeTransport();
    const storage = memoryStorage({ [AUTO_CHECK_KEY]: "off" });
    const service = createService(transport, { storage });

    service.start();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(transport.check).not.toHaveBeenCalled();

    await service.check();
    expect(transport.check).toHaveBeenCalledTimes(1);
  });

  it("persists a preference change and checks right away when turned on", async () => {
    const transport = makeTransport();
    const storage = memoryStorage({ [AUTO_CHECK_KEY]: "off" });
    const service = createService(transport, { storage });

    service.setAutoCheck(true);
    await vi.advanceTimersByTimeAsync(0);

    expect(storage.data.get(AUTO_CHECK_KEY)).toBe("on");
    expect(transport.check).toHaveBeenCalledTimes(1);
  });

  it("keeps the banner hidden after a dismissal but keeps the update staged", async () => {
    const service = createService(makeTransport({ check: vi.fn(async () => makeHandle()) }));
    await service.check();

    service.dismiss();

    expect(service.bannerView()).toBeNull();
    expect(service.getSnapshot().installed).toBe(true);
    expect(service.getSnapshot().available?.version).toBe("0.12.0");
  });

  it("does not run a scheduled check after dispose", async () => {
    const transport = makeTransport();
    const service = createService(transport);
    service.start();
    service.dispose();

    await vi.advanceTimersByTimeAsync(10_000);
    expect(transport.check).not.toHaveBeenCalled();
  });
});

describe("describeUpdateFailure", () => {
  it("names the stage without leaking internals", () => {
    expect(describeUpdateFailure(new Error("ECONNREFUSED"), "check")).toBe(
      "Couldn't reach the update server.",
    );
    expect(describeUpdateFailure(new Error("stream ended"), "download")).toMatch(/connection/i);
    expect(describeUpdateFailure(new Error("nope"), "install")).toMatch(/installed/i);
  });
});
