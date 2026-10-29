/**
 * The updater's vocabulary.
 *
 * Nothing in this module talks to Tauri, the network, or React. The state
 * machine and the service are the only consumers, which keeps the whole
 * lifecycle testable in a plain jsdom process.
 */

export type UpdatePhase =
  /** Not running inside the desktop shell (browser tab or `tauri dev`). */
  | "unsupported"
  /** Supported, but no check has finished yet. */
  | "idle"
  | "checking"
  | "downloading"
  | "installing"
  /** Downloaded; `installed` says whether a relaunch is all that remains. */
  | "ready"
  | "up-to-date"
  | "error";

export interface AvailableUpdate {
  version: string;
  /** RFC 3339 date from the update manifest, when published. */
  date: string | null;
  /** Release notes from the update manifest, when published. */
  notes: string | null;
}

export interface DownloadProgress {
  received: number;
  total: number | null;
}

export interface UpdateSnapshot {
  phase: UpdatePhase;
  currentVersion: string | null;
  available: AvailableUpdate | null;
  progress: DownloadProgress | null;
  lastCheckedAt: number | null;
  /** True when the artifact is staged and the next launch runs it. */
  installed: boolean;
  /** True when the artifact is downloaded but needs an app exit to install. */
  pendingInstall: boolean;
  error: string | null;
  autoCheck: boolean;
  /** Persisted: the person asked not to be offered this version again. */
  skippedVersion: string | null;
  /** Session-only: the person hid the banner. */
  dismissedVersion: string | null;
}

export type UpdateEvent =
  | { type: "unsupported" }
  | { type: "current-version"; version: string }
  | { type: "check-started" }
  | { type: "check-none"; currentVersion: string | null; at: number }
  | {
      type: "check-skipped";
      currentVersion: string;
      update: AvailableUpdate;
      at: number;
    }
  | {
      type: "check-found";
      currentVersion: string;
      update: AvailableUpdate;
      at: number;
    }
  | { type: "download-progress"; received: number; total: number | null }
  | { type: "download-finished" }
  | { type: "download-finished-pending" }
  | { type: "install-started" }
  | { type: "installed" }
  | { type: "failed"; message: string; at: number }
  | { type: "relaunch-failed"; message: string }
  | { type: "dismissed" }
  | { type: "skipped"; version: string }
  | { type: "auto-check-changed"; enabled: boolean }
  | { type: "reset"; currentVersion?: string | null };

/** The Update resource exposed by `@tauri-apps/plugin-updater`, narrowed down. */
export interface UpdaterHandle {
  version: string;
  currentVersion: string;
  date: string | null;
  notes: string | null;
  download(onProgress: (progress: DownloadProgress) => void): Promise<void>;
  install(): Promise<void>;
  close(): Promise<void>;
}

/**
 * The seam between the updater lifecycle and the desktop runtime. The service
 * only ever sees this interface; tests supply a fake.
 */
export interface UpdateTransport {
  supported(): boolean;
  currentVersion(): Promise<string>;
  check(): Promise<UpdaterHandle | null>;
  relaunch(): Promise<void>;
}

export interface UpdatePreferences {
  autoCheck: boolean;
  skippedVersion: string | null;
}
