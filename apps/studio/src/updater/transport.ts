/**
 * The only module in the updater that knows Tauri exists.
 *
 * Everything above it — state machine, service, components — works against the
 * `UpdateTransport` interface, which is what lets the entire lifecycle run in
 * a plain test process.
 */
import { getVersion } from "@tauri-apps/api/app";
import { relaunch } from "@tauri-apps/plugin-process";
import { check, type DownloadEvent } from "@tauri-apps/plugin-updater";

import { isTauri } from "../bridge/desktopBridge";
import type { DownloadProgress, UpdateTransport, UpdaterHandle } from "./types";

function handleFor(update: NonNullable<Awaited<ReturnType<typeof check>>>): UpdaterHandle {
  return {
    version: update.version,
    currentVersion: update.currentVersion,
    date: update.date ?? null,
    notes: update.body ?? null,

    async download(onProgress: (progress: DownloadProgress) => void) {
      let received = 0;
      let total: number | null = null;

      await update.download((event: DownloadEvent) => {
        if (event.event === "Started") {
          total = event.data.contentLength ?? null;
          onProgress({ received, total });
          return;
        }
        if (event.event === "Progress") {
          received += event.data.chunkLength;
          onProgress({ received, total });
        }
      });
    },

    install: () => update.install(),
    close: () => update.close(),
  };
}

export function createDesktopTransport(): UpdateTransport {
  return {
    supported: () => isTauri(),

    async currentVersion() {
      return getVersion();
    },

    async check() {
      const update = await check();
      return update ? handleFor(update) : null;
    },

    async relaunch() {
      await relaunch();
    },
  };
}
