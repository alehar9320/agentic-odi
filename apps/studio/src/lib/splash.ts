/**
 * The desktop splash handover (#963).
 *
 * On launch the shell shows a `splashscreen` window and keeps `main` hidden. The
 * frontend calls `set_complete` once it has committed and finished first-boot
 * work, and the Rust side reveals `main` and retires the splash after a short
 * minimum display.
 *
 * Nothing here runs in the browser: the splash is a desktop window, and the
 * browser keeps its own boot shell. A browser build therefore never imports the
 * Tauri API, and a desktop build that fails to report still gets a window from
 * the shell's watchdog.
 */
import { isTauri } from "../bridge/desktopBridge";

/**
 * The longest the frontend waits for the shell to acknowledge.
 *
 * The shell reveals `main` on its own watchdog well inside this, so a lost
 * message cannot leave the app on the splash. The timeout only bounds the await,
 * never the handover.
 */
export const SPLASH_ACK_TIMEOUT_MS = 2_000;

/**
 * Tell the shell the app is up, so it can reveal `main` and close the splash.
 *
 * Safe to call anywhere: it is a no-op in the browser, and it never throws or
 * rejects, because a handover that failed to send must not become an error the
 * person sees. Resolves when the shell acknowledges or the timeout elapses.
 */
export async function signalSplashComplete(): Promise<void> {
  if (!isTauri()) {
    return;
  }
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await Promise.race([
      invoke("set_complete"),
      new Promise<void>((resolve) => {
        setTimeout(resolve, SPLASH_ACK_TIMEOUT_MS);
      }),
    ]);
  } catch {
    /* The shell's watchdog reveals the window; a failed report is not fatal. */
  }
}
