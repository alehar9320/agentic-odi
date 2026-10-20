import { check, type DownloadEvent, type Update } from "@tauri-apps/plugin-updater";
import { useCallback, useState } from "react";

import { isTauri } from "../../bridge/desktopBridge";

export interface UpdaterState {
  checking: boolean;
  available: boolean;
  version: string | null;
  progress: number | null;
  error: string | null;
  check: () => Promise<void>;
}

const IDLE: Omit<UpdaterState, "check"> = {
  checking: false,
  available: false,
  version: null,
  progress: null,
  error: null,
};

export function useUpdater(): UpdaterState {
  const [state, setState] = useState<Omit<UpdaterState, "check">>(IDLE);

  const runCheck = useCallback(async () => {
    if (!isTauri()) {
      setState({ ...IDLE, error: "In-app updates are only available in the desktop build." });
      return;
    }

    setState({ ...IDLE, checking: true });
    try {
      const update: Update | null = await check();
      if (!update) {
        setState(IDLE);
        return;
      }

      let total = 0;
      let downloaded = 0;
      setState({ checking: true, available: true, version: update.version, progress: 0, error: null });

      await update.downloadAndInstall((event: DownloadEvent) => {
        if (event.event === "Started") {
          total = event.data.contentLength ?? 0;
        } else if (event.event === "Progress") {
          downloaded += event.data.chunkLength;
          setState((prev) => ({ ...prev, progress: total ? downloaded / total : null }));
        }
      });

      setState({ checking: false, available: true, version: update.version, progress: 1, error: null });
    } catch (error) {
      setState({ ...IDLE, error: (error as Error).message });
    }
  }, []);

  return { ...state, check: runCheck };
}
