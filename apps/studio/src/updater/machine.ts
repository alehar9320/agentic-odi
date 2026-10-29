/**
 * The updater's state machine — a pure reducer plus selectors.
 *
 * Every surface (banner, sidebar, Settings) reads the same snapshot, so they
 * can never disagree about whether an update is available, downloading, or
 * waiting for a restart.
 */
import type { UpdateEvent, UpdateSnapshot } from "./types";

export const INITIAL_SNAPSHOT: UpdateSnapshot = {
  phase: "idle",
  currentVersion: null,
  available: null,
  progress: null,
  lastCheckedAt: null,
  installed: false,
  pendingInstall: false,
  error: null,
  autoCheck: true,
  skippedVersion: null,
  dismissedVersion: null,
};

export function initialSnapshot(
  overrides: Partial<UpdateSnapshot> = {},
): UpdateSnapshot {
  return { ...INITIAL_SNAPSHOT, ...overrides };
}

/** Apply one event. Unknown phases fall back to the untouched snapshot. */
export function reduce(snapshot: UpdateSnapshot, event: UpdateEvent): UpdateSnapshot {
  switch (event.type) {
    case "unsupported":
      return { ...snapshot, phase: "unsupported", error: null };

    case "current-version":
      return event.version === snapshot.currentVersion
        ? snapshot
        : { ...snapshot, currentVersion: event.version };

    case "check-started":
      return { ...snapshot, phase: "checking", error: null };

    case "check-none":
      return {
        ...snapshot,
        phase: "up-to-date",
        currentVersion: event.currentVersion,
        available: null,
        progress: null,
        installed: false,
        pendingInstall: false,
        lastCheckedAt: event.at,
        error: null,
        dismissedVersion: null,
      };

    case "check-skipped":
      return {
        ...snapshot,
        phase: "up-to-date",
        currentVersion: event.currentVersion,
        available: event.update,
        progress: null,
        installed: false,
        pendingInstall: false,
        lastCheckedAt: event.at,
        error: null,
      };

    case "check-found":
      return {
        ...snapshot,
        phase: "downloading",
        currentVersion: event.currentVersion,
        available: event.update,
        progress: { received: 0, total: null },
        installed: false,
        pendingInstall: false,
        lastCheckedAt: event.at,
        error: null,
        dismissedVersion: null,
      };

    case "download-progress":
      if (snapshot.phase !== "downloading" && snapshot.phase !== "installing") {
        return snapshot;
      }
      return {
        ...snapshot,
        phase: "downloading",
        progress: { received: event.received, total: event.total },
      };

    case "download-finished":
      return {
        ...snapshot,
        phase: "installing",
        progress: snapshot.progress,
        error: null,
      };

    case "download-finished-pending":
      return {
        ...snapshot,
        phase: "ready",
        progress: null,
        installed: false,
        pendingInstall: true,
        error: null,
      };

    case "install-started":
      return { ...snapshot, phase: "installing", error: null };

    case "installed":
      return {
        ...snapshot,
        phase: "ready",
        progress: null,
        installed: true,
        pendingInstall: false,
        error: null,
      };

    case "failed":
      return {
        ...snapshot,
        phase: "error",
        progress: null,
        installed: false,
        pendingInstall: false,
        lastCheckedAt: event.at,
        error: event.message,
      };

    case "relaunch-failed":
      // The update is already staged; only the relaunch failed. Keep
      // `installed` so the next retry does not reinstall what is on disk.
      return { ...snapshot, phase: "error", error: event.message, progress: null };

    case "dismissed":
      return {
        ...snapshot,
        dismissedVersion: snapshot.available?.version ?? null,
      };

    case "skipped":
      return {
        ...snapshot,
        phase: "up-to-date",
        skippedVersion: event.version,
        dismissedVersion: event.version,
        progress: null,
        installed: false,
        pendingInstall: false,
      };

    case "auto-check-changed":
      return { ...snapshot, autoCheck: event.enabled };

    case "reset":
      return {
        ...snapshot,
        phase: "idle",
        currentVersion: event.currentVersion ?? snapshot.currentVersion,
        available: null,
        progress: null,
        installed: false,
        pendingInstall: false,
        error: null,
        dismissedVersion: null,
      };

    default:
      return snapshot;
  }
}

/** 0…1, or null while the server has not told us the size yet. */
export function progressPercent(snapshot: UpdateSnapshot): number | null {
  const progress = snapshot.progress;
  if (!progress || progress.total === null || progress.total <= 0) {
    return null;
  }
  return Math.max(0, Math.min(1, progress.received / progress.total));
}

export type BannerKind = "downloading" | "ready" | "installing" | "error";

export interface BannerView {
  kind: BannerKind;
  version: string;
  percent: number | null;
  pendingInstall: boolean;
}

/**
 * What the shell should show, if anything.
 *
 * Deliberately silent for background-check failures (nothing to act on), for
 * versions the person skipped or dismissed, and for an up-to-date app. The
 * Settings section is where failures remain visible.
 */
export function bannerView(snapshot: UpdateSnapshot): BannerView | null {
  const update = snapshot.available;
  if (!update || snapshot.phase === "unsupported") {
    return null;
  }
  if (
    update.version === snapshot.skippedVersion ||
    update.version === snapshot.dismissedVersion
  ) {
    return null;
  }

  const view = {
    version: update.version,
    percent: progressPercent(snapshot),
    pendingInstall: snapshot.pendingInstall,
  };

  switch (snapshot.phase) {
    case "downloading":
    case "installing":
    case "ready":
    case "error":
      return { ...view, kind: snapshot.phase === "installing" ? "installing" : snapshot.phase };
    default:
      return null;
  }
}

/** True when the primary action should restart (rather than install first). */
export function canRestartNow(snapshot: UpdateSnapshot): boolean {
  return snapshot.phase === "ready" && snapshot.installed;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export function describeCheckedAt(at: number | null, now: number): string {
  if (at === null) {
    return "Not checked yet";
  }
  const elapsed = Math.max(0, now - at);
  if (elapsed < MINUTE) {
    return "Checked just now";
  }
  if (elapsed < HOUR) {
    const minutes = Math.round(elapsed / MINUTE);
    return `Checked ${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  }
  if (elapsed < DAY) {
    const hours = Math.round(elapsed / HOUR);
    return `Checked ${hours} hour${hours === 1 ? "" : "s"} ago`;
  }
  const days = Math.round(elapsed / DAY);
  return `Checked ${days} day${days === 1 ? "" : "s"} ago`;
}

/** One plain sentence for Settings. Never an error code. */
export function statusLine(snapshot: UpdateSnapshot, now: number): string {
  const version = snapshot.available?.version ?? null;

  if (snapshot.phase === "unsupported") {
    return "In-app updates live in the installed desktop app.";
  }

  if (snapshot.phase === "error") {
    return snapshot.error ?? "The update could not be completed.";
  }

  if (snapshot.phase === "checking") {
    return "Checking for updates…";
  }

  if (snapshot.phase === "downloading") {
    const percent = progressPercent(snapshot);
    return percent === null
      ? `Downloading Living Studio ${version ?? ""}…`
      : `Downloading Living Studio ${version ?? ""} — ${Math.round(percent * 100)}%`;
  }

  if (snapshot.phase === "installing") {
    return `Installing Living Studio ${version ?? ""}…`;
  }

  if (snapshot.phase === "ready") {
    if (snapshot.pendingInstall) {
      return `Living Studio ${version ?? ""} is downloaded. Updating restarts the app.`;
    }
    return `Living Studio ${version ?? ""} is ready. Restart to finish.`;
  }

  if (version && version === snapshot.skippedVersion) {
    return `Living Studio ${version} is skipped. You will be offered the next release.`;
  }

  if (snapshot.phase === "up-to-date") {
    return "You're up to date.";
  }

  return describeCheckedAt(snapshot.lastCheckedAt, now);
}
