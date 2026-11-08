/**
 * The one behaviour that differs per desktop OS.
 *
 * macOS and Linux can replace their own bundle while the app is running, so an
 * update is staged as soon as it downloads and the next ordinary launch runs it.
 * Windows runs an NSIS installer that needs the app to exit first, so installing
 * is bound to the explicit "Update & restart" action.
 */
export type DesktopPlatform = "macos" | "windows" | "linux" | "unknown";

export function detectPlatform(userAgent?: string): DesktopPlatform {
  const ua = (
    userAgent ??
    (typeof navigator === "undefined" ? "" : navigator.userAgent)
  ).toLowerCase();

  if (ua.includes("windows")) {
    return "windows";
  }
  if (ua.includes("mac os") || ua.includes("macintosh")) {
    return "macos";
  }
  if (ua.includes("linux") || ua.includes("x11")) {
    return "linux";
  }
  return "unknown";
}

export function installAfterDownload(platform: DesktopPlatform): boolean {
  return platform !== "windows";
}

/**
 * The keycaps the person's own keyboard prints.
 *
 * macOS writes modifiers and Enter as symbols; Windows and Linux spell them
 * out. The label comes from here rather than from a branch in JSX, so the hint
 * cannot drift from the shortcuts the shell actually implements.
 */
export interface ShortcutLabels {
  /** Focus the composer from anywhere. */
  focus: string;
  /** Send the drafted message. */
  send: string;
}

export function shortcutLabels(platform: DesktopPlatform): ShortcutLabels {
  return platform === "macos"
    ? { focus: "⌘K", send: "↵" }
    : { focus: "Ctrl K", send: "Enter" };
}
