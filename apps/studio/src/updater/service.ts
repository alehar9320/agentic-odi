/**
 * The update lifecycle: when to check, what to download, when to install, and
 * when to hand control back to the person.
 *
 * It has no idea what Tauri is. A transport supplies the runtime, timers come
 * from the environment, and preferences come from injected storage — which is
 * what makes the whole thing testable without a desktop build.
 */
import {
  initialSnapshot,
  reduce,
  progressPercent,
  type BannerView,
  bannerView,
  canRestartNow,
  describeCheckedAt,
  statusLine,
} from "./machine";
import { detectPlatform, installAfterDownload, type DesktopPlatform } from "./platform";
import type {
  UpdateEvent,
  UpdatePreferences,
  UpdateSnapshot,
  UpdateTransport,
  UpdaterHandle,
} from "./types";

export const AUTO_CHECK_KEY = "studio.update.autoCheck";
export const SKIPPED_VERSION_KEY = "studio.update.skippedVersion";

const DEFAULT_INITIAL_DELAY_MS = 4_000;
const DEFAULT_INTERVAL_MS = 6 * 60 * 60 * 1_000;

type PreferenceStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export interface UpdateServiceOptions {
  transport: UpdateTransport;
  storage?: PreferenceStorage | null;
  platform?: DesktopPlatform;
  now?: () => number;
  initialDelayMs?: number;
  intervalMs?: number;
  document?: Pick<Document, "addEventListener" | "removeEventListener" | "visibilityState"> | null;
}

export interface UpdateService {
  getSnapshot(): UpdateSnapshot;
  subscribe(listener: () => void): () => void;
  start(): void;
  stop(): void;
  dispose(): void;
  check(): Promise<void>;
  /** Retry after a failure: installs staged bytes, otherwise checks again. */
  retry(): Promise<void>;
  installAndRestart(): Promise<void>;
  dismiss(): void;
  skipCurrent(): void;
  setAutoCheck(enabled: boolean): void;
  bannerView(): BannerView | null;
  statusLine(): string;
  checkedAtLabel(): string;
  canRestartNow(): boolean;
  progressPercent(): number | null;
}

function readStorage(storage: PreferenceStorage | null): UpdatePreferences {
  if (!storage) {
    return { autoCheck: true, skippedVersion: null };
  }
  try {
    return {
      autoCheck: storage.getItem(AUTO_CHECK_KEY) !== "off",
      skippedVersion: storage.getItem(SKIPPED_VERSION_KEY),
    };
  } catch {
    return { autoCheck: true, skippedVersion: null };
  }
}

function defaultStorage(): PreferenceStorage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** Plain language, never a stack trace. */
export function describeUpdateFailure(
  error: unknown,
  stage: "check" | "download" | "install",
): string {
  const raw = error instanceof Error ? error.message : String(error ?? "");

  if (/signature/i.test(raw)) {
    return "The update couldn't be verified. Try again, or install the latest release.";
  }
  if (/permission|denied|not permitted|read-only|readonly|privilege/i.test(raw)) {
    return "The app couldn't replace itself. Install the latest release instead.";
  }
  if (stage === "check") {
    return "Couldn't reach the update server.";
  }
  if (stage === "download") {
    return "The download didn't finish. Check your connection and try again.";
  }
  return "The update couldn't be installed. Try again.";
}

export function createUpdateService(options: UpdateServiceOptions): UpdateService {
  const { transport } = options;
  const platform = options.platform ?? detectPlatform();
  const now = options.now ?? (() => Date.now());
  const storage = options.storage === undefined ? defaultStorage() : options.storage;
  const documentRef =
    options.document === undefined
      ? typeof document === "undefined"
        ? null
        : document
      : options.document;
  const initialDelayMs = options.initialDelayMs ?? DEFAULT_INITIAL_DELAY_MS;
  const intervalMs = options.intervalMs ?? DEFAULT_INTERVAL_MS;

  const preferences = readStorage(storage);
  let snapshot: UpdateSnapshot = initialSnapshot({
    autoCheck: preferences.autoCheck,
    skippedVersion: preferences.skippedVersion,
  });

  const listeners = new Set<() => void>();
  let handle: UpdaterHandle | null = null;
  let downloaded = false;
  let inFlight: Promise<void> | null = null;
  let started = false;
  let firstCheck: ReturnType<typeof setTimeout> | null = null;
  let poller: ReturnType<typeof setInterval> | null = null;

  function emit(event: UpdateEvent): void {
    const next = reduce(snapshot, event);
    if (next === snapshot) {
      return;
    }
    snapshot = next;
    for (const listener of listeners) {
      listener();
    }
  }

  function forgetHandle(): void {
    const previous = handle;
    handle = null;
    downloaded = false;
    if (previous) {
      void previous.close().catch(() => undefined);
    }
  }

  function persistSkipped(version: string | null): void {
    if (!storage) {
      return;
    }
    try {
      if (version) {
        storage.setItem(SKIPPED_VERSION_KEY, version);
      } else {
        storage.removeItem(SKIPPED_VERSION_KEY);
      }
    } catch {
      /* preferences are a convenience, never a blocker */
    }
  }

  async function syncCurrentVersion(): Promise<void> {
    try {
      const version = await transport.currentVersion();
      if (version) {
        emit({ type: "current-version", version });
      }
    } catch {
      /* the version is cosmetic until a check succeeds */
    }
  }

  async function runCheck(): Promise<void> {
    if (inFlight) {
      return inFlight;
    }
    if (!transport.supported()) {
      emit({ type: "unsupported" });
      return;
    }
    if (snapshot.phase === "ready" || snapshot.phase === "installing") {
      return;
    }

    emit({ type: "check-started" });

    inFlight = (async () => {
      let stage: "check" | "download" | "install" = "check";
      try {
        const update = await transport.check();
        if (!update) {
          forgetHandle();
          emit({
            type: "check-none",
            currentVersion: snapshot.currentVersion,
            at: now(),
          });
          return;
        }

        const current = update.currentVersion || snapshot.currentVersion || "";
        if (snapshot.currentVersion !== current) {
          emit({ type: "current-version", version: current });
        }

        const info = {
          version: update.version,
          date: update.date,
          notes: update.notes,
        };

        if (snapshot.skippedVersion === update.version) {
          forgetHandle();
          emit({
            type: "check-skipped",
            currentVersion: current,
            update: info,
            at: now(),
          });
          return;
        }

        forgetHandle();
        handle = update;

        emit({
          type: "check-found",
          currentVersion: current,
          update: info,
          at: now(),
        });

        stage = "download";
        await update.download((progress) => {
          emit({
            type: "download-progress",
            received: progress.received,
            total: progress.total,
          });
        });
        downloaded = true;

        emit({ type: "download-finished" });

        if (!installAfterDownload(platform)) {
          emit({ type: "download-finished-pending" });
          return;
        }

        stage = "install";
        emit({ type: "install-started" });
        await update.install();
        emit({ type: "installed" });
      } catch (error) {
        emit({
          type: "failed",
          message: describeUpdateFailure(error, stage),
          at: now(),
        });
      }
    })().finally(() => {
      inFlight = null;
    });

    return inFlight;
  }

  async function installThenRelaunch(): Promise<void> {
    if (handle && !snapshot.installed && snapshot.pendingInstall) {
      try {
        emit({ type: "install-started" });
        await handle.install();
        emit({ type: "installed" });
      } catch (error) {
        emit({
          type: "failed",
          message: describeUpdateFailure(error, "install"),
          at: now(),
        });
        return;
      }
    }

    try {
      await transport.relaunch();
    } catch {
      emit({
        type: "relaunch-failed",
        message: "The app couldn't restart. Close and reopen it to finish updating.",
      });
    }
  }

  function stopTimers(): void {
    started = false;
    if (firstCheck !== null) {
      clearTimeout(firstCheck);
      firstCheck = null;
    }
    if (poller !== null) {
      clearInterval(poller);
      poller = null;
    }
    documentRef?.removeEventListener("visibilitychange", onVisibilityChange);
  }

  function onVisibilityChange(): void {
    if (!snapshot.autoCheck || documentRef?.visibilityState !== "visible") {
      return;
    }
    const last = snapshot.lastCheckedAt;
    if (last === null || now() - last >= intervalMs) {
      void runCheck();
    }
  }

  return {
    getSnapshot: () => snapshot,

    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },

    start() {
      if (started) {
        return;
      }
      started = true;

      if (!transport.supported()) {
        emit({ type: "unsupported" });
        return;
      }

      void syncCurrentVersion();

      if (snapshot.autoCheck) {
        firstCheck = setTimeout(() => {
          if (snapshot.autoCheck) {
            void runCheck();
          }
        }, initialDelayMs);
      }

      poller = setInterval(() => {
        if (snapshot.autoCheck) {
          void runCheck();
        }
      }, intervalMs);

      documentRef?.addEventListener("visibilitychange", onVisibilityChange);
    },

    stop() {
      stopTimers();
    },

    dispose() {
      stopTimers();
      listeners.clear();
      forgetHandle();
    },

    check() {
      return runCheck();
    },

    async retry() {
      if (snapshot.installed) {
        await installThenRelaunch();
        return;
      }
      if (downloaded && handle && snapshot.error) {
        try {
          emit({ type: "install-started" });
          await handle.install();
          emit({ type: "installed" });
          return;
        } catch (error) {
          emit({
            type: "failed",
            message: describeUpdateFailure(error, "install"),
            at: now(),
          });
          return;
        }
      }
      await runCheck();
    },

    installAndRestart() {
      return installThenRelaunch();
    },

    dismiss() {
      emit({ type: "dismissed" });
    },

    skipCurrent() {
      const version = snapshot.available?.version;
      if (!version) {
        return;
      }
      persistSkipped(version);
      forgetHandle();
      emit({ type: "skipped", version });
    },

    setAutoCheck(enabled: boolean) {
      if (storage) {
        try {
          storage.setItem(AUTO_CHECK_KEY, enabled ? "on" : "off");
        } catch {
          /* preferences are a convenience, never a blocker */
        }
      }
      emit({ type: "auto-check-changed", enabled });
      if (enabled) {
        const last = snapshot.lastCheckedAt;
        if (last === null || now() - last >= intervalMs) {
          void runCheck();
        }
      }
    },

    bannerView: () => bannerView(snapshot),
    statusLine: () => statusLine(snapshot, now()),
    checkedAtLabel: () => describeCheckedAt(snapshot.lastCheckedAt, now()),
    canRestartNow: () => canRestartNow(snapshot),
    progressPercent: () => progressPercent(snapshot),
  };
}
