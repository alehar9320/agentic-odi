import { describe, expect, it } from "vitest";

import {
  bannerView,
  canRestartNow,
  describeCheckedAt,
  initialSnapshot,
  progressPercent,
  reduce,
  statusLine,
} from "./machine";
import type { UpdateEvent, UpdateSnapshot } from "./types";

const NOW = 1_700_000_000_000;

const UPDATE = { version: "0.12.0", date: "2026-10-21T10:00:00Z", notes: "Faster canvas." };

function found(): UpdateSnapshot {
  return reduce(initialSnapshot(), {
    type: "check-found",
    currentVersion: "0.11.0",
    update: UPDATE,
    at: NOW,
  });
}

function ready(installed = true): UpdateSnapshot {
  return reduce(
    reduce(found(), { type: "download-finished" }),
    installed ? { type: "installed" } : { type: "download-finished-pending" },
  );
}

describe("reduce", () => {
  it("marks the runtime unsupported", () => {
    expect(reduce(initialSnapshot(), { type: "unsupported" }).phase).toBe("unsupported");
  });

  it("records the running version", () => {
    expect(
      reduce(initialSnapshot(), { type: "current-version", version: "0.11.0" }).currentVersion,
    ).toBe("0.11.0");
  });

  it("enters checking and clears a stale error", () => {
    const errored = reduce(initialSnapshot(), { type: "failed", message: "offline", at: NOW });
    const next = reduce(errored, { type: "check-started" });
    expect(next.phase).toBe("checking");
    expect(next.error).toBeNull();
  });

  it("records an up-to-date check and forgets any old update", () => {
    const next = reduce(found(), { type: "check-none", currentVersion: "0.12.0", at: NOW });
    expect(next.phase).toBe("up-to-date");
    expect(next.available).toBeNull();
    expect(next.progress).toBeNull();
    expect(next.lastCheckedAt).toBe(NOW);
  });

  it("keeps a skipped version visible to Settings but not to the banner", () => {
    const next = reduce(initialSnapshot(), {
      type: "check-skipped",
      currentVersion: "0.11.0",
      update: UPDATE,
      at: NOW,
    });
    expect(next.phase).toBe("up-to-date");
    expect(next.available).toEqual(UPDATE);
    expect(bannerView(next)).toBeNull();
  });

  it("starts downloading as soon as an update is found", () => {
    const next = found();
    expect(next.phase).toBe("downloading");
    expect(next.available).toEqual(UPDATE);
    expect(next.progress).toEqual({ received: 0, total: null });
    expect(next.lastCheckedAt).toBe(NOW);
  });

  it("accumulates download progress", () => {
    const next = reduce(found(), {
      type: "download-progress",
      received: 512,
      total: 2048,
    });
    expect(next.progress).toEqual({ received: 512, total: 2048 });
    expect(progressPercent(next)).toBe(0.25);
  });

  it("ignores progress outside a download", () => {
    const idle = initialSnapshot();
    expect(
      reduce(idle, { type: "download-progress", received: 1, total: 2 }),
    ).toBe(idle);
  });

  it("moves to installing once the bytes are downloaded", () => {
    const next = reduce(
      reduce(found(), { type: "download-progress", received: 10, total: 10 }),
      { type: "download-finished" },
    );
    expect(next.phase).toBe("installing");
    expect(next.progress).toEqual({ received: 10, total: 10 });
  });

  it("leaves Windows updates pending until the person restarts", () => {
    const next = reduce(found(), { type: "download-finished-pending" });
    expect(next.phase).toBe("ready");
    expect(next.pendingInstall).toBe(true);
    expect(next.installed).toBe(false);
    expect(canRestartNow(next)).toBe(false);
  });

  it("marks a staged update as installed and restartable", () => {
    const next = ready();
    expect(next.phase).toBe("ready");
    expect(next.installed).toBe(true);
    expect(next.pendingInstall).toBe(false);
    expect(canRestartNow(next)).toBe(true);
    expect(progressPercent(next)).toBeNull();
  });

  it("keeps the available version when a download fails so the person can retry", () => {
    const next = reduce(found(), {
      type: "failed",
      message: "The update could not be verified.",
      at: NOW,
    });
    expect(next.phase).toBe("error");
    expect(next.available).toEqual(UPDATE);
    expect(next.error).toBe("The update could not be verified.");
    expect(bannerView(next)?.kind).toBe("error");
  });

  it("keeps a staged update when only the relaunch failed", () => {
    const next = reduce(ready(), { type: "relaunch-failed", message: "Couldn't restart" });
    expect(next.phase).toBe("error");
    expect(next.installed).toBe(true);
    expect(next.error).toBe("Couldn't restart");
  });

  it("hides the banner after a dismissal without forgetting the update", () => {
    const next = reduce(ready(), { type: "dismissed" });
    expect(next.dismissedVersion).toBe("0.12.0");
    expect(next.available).toEqual(UPDATE);
    expect(bannerView(next)).toBeNull();
  });

  it("clears a previous dismissal when a newer version appears", () => {
    const dismissed = reduce(ready(), { type: "dismissed" });
    const next = reduce(dismissed, {
      type: "check-found",
      currentVersion: "0.11.0",
      update: { ...UPDATE, version: "0.13.0" },
      at: NOW,
    });
    expect(next.dismissedVersion).toBeNull();
    expect(bannerView(next)?.version).toBe("0.13.0");
  });

  it("skips a version and stops offering it", () => {
    const next = reduce(ready(), { type: "skipped", version: "0.12.0" });
    expect(next.skippedVersion).toBe("0.12.0");
    expect(next.phase).toBe("up-to-date");
    expect(bannerView(next)).toBeNull();
  });

  it("toggles automatic checks", () => {
    const off = reduce(initialSnapshot(), { type: "auto-check-changed", enabled: false });
    expect(off.autoCheck).toBe(false);
    const on = reduce(off, { type: "auto-check-changed", enabled: true });
    expect(on.autoCheck).toBe(true);
  });

  it("resets an update while keeping the person's preferences", () => {
    const prefs = { ...ready(), autoCheck: false, skippedVersion: "0.9.0" };
    const next = reduce(prefs, { type: "reset" });
    expect(next.phase).toBe("idle");
    expect(next.available).toBeNull();
    expect(next.autoCheck).toBe(false);
    expect(next.skippedVersion).toBe("0.9.0");
    expect(next.currentVersion).toBe("0.11.0");
  });

  it("ignores unknown events", () => {
    const snapshot = initialSnapshot();
    expect(reduce(snapshot, { type: "nope" } as unknown as UpdateEvent)).toBe(snapshot);
  });
});

describe("bannerView", () => {
  it("stays silent while a background check fails", () => {
    const next = reduce(initialSnapshot(), { type: "failed", message: "offline", at: NOW });
    expect(bannerView(next)).toBeNull();
  });

  it("stays silent when there is nothing to install", () => {
    expect(bannerView(initialSnapshot())).toBeNull();
    expect(
      bannerView(reduce(initialSnapshot(), { type: "check-none", currentVersion: "0.11.0", at: NOW })),
    ).toBeNull();
  });

  it("stays silent in the browser", () => {
    expect(bannerView(reduce(found(), { type: "unsupported" }))).toBeNull();
  });

  it("shows downloading with a percentage when the size is known", () => {
    const next = reduce(found(), {
      type: "download-progress",
      received: 5,
      total: 10,
    });
    expect(bannerView(next)).toEqual({
      kind: "downloading",
      version: "0.12.0",
      percent: 0.5,
      pendingInstall: false,
    });
  });

  it("shows the restart action once an update is staged", () => {
    expect(bannerView(ready())).toMatchObject({ kind: "ready", version: "0.12.0" });
  });
});

describe("progressPercent", () => {
  it("is null while the total is unknown", () => {
    expect(progressPercent(found())).toBeNull();
  });

  it("clamps to a full bar", () => {
    const next = reduce(found(), {
      type: "download-progress",
      received: 20,
      total: 10,
    });
    expect(progressPercent(next)).toBe(1);
  });
});

describe("describeCheckedAt", () => {
  it("describes the check in plain language", () => {
    expect(describeCheckedAt(null, NOW)).toBe("Not checked yet");
    expect(describeCheckedAt(NOW - 20_000, NOW)).toBe("Checked just now");
    expect(describeCheckedAt(NOW - 60_000, NOW)).toBe("Checked 1 minute ago");
    expect(describeCheckedAt(NOW - 5 * 60_000, NOW)).toBe("Checked 5 minutes ago");
    expect(describeCheckedAt(NOW - 2 * 3_600_000, NOW)).toBe("Checked 2 hours ago");
    expect(describeCheckedAt(NOW - 2 * 86_400_000, NOW)).toBe("Checked 2 days ago");
  });
});

describe("statusLine", () => {
  it("explains where updates live in the browser", () => {
    expect(statusLine(reduce(initialSnapshot(), { type: "unsupported" }), NOW)).toMatch(
      /desktop app/i,
    );
  });

  it("reports progress", () => {
    const next = reduce(found(), {
      type: "download-progress",
      received: 3,
      total: 4,
    });
    expect(statusLine(next, NOW)).toBe("Downloading Living Studio 0.12.0 — 75%");
  });

  it("reports a staged update and the restart", () => {
    expect(statusLine(ready(), NOW)).toBe("Living Studio 0.12.0 is ready. Restart to finish.");
  });

  it("explains a pending Windows install", () => {
    expect(statusLine(ready(false), NOW)).toMatch(/restarts the app/i);
  });

  it("reports an error verbatim", () => {
    const next = reduce(found(), { type: "failed", message: "Signature mismatch", at: NOW });
    expect(statusLine(next, NOW)).toBe("Signature mismatch");
  });

  it("reports an up-to-date app and a skipped release", () => {
    const current = reduce(initialSnapshot(), {
      type: "check-none",
      currentVersion: "0.12.0",
      at: NOW,
    });
    expect(statusLine(current, NOW)).toBe("You're up to date.");

    const skipped = reduce(ready(), { type: "skipped", version: "0.12.0" });
    expect(statusLine(skipped, NOW)).toMatch(/skipped/);
  });

  it("falls back to when the last check happened", () => {
    expect(statusLine(initialSnapshot(), NOW)).toBe("Not checked yet");
  });
});
