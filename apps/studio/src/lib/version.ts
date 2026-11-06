export const STUDIO_VERSION = __STUDIO_VERSION__;

export interface VersionLabel {
  version: string;
  source: "build" | "desktop";
}

/**
 * Pick the version to show. A desktop build that has asked the updater and
 * received a version wins; otherwise fall back to the build-time define so a
 * hosted page or PWA is never left showing "—".
 */
export function versionLabel(desktopVersion: string | null): VersionLabel {
  if (desktopVersion) {
    return { version: desktopVersion, source: "desktop" };
  }
  return { version: STUDIO_VERSION, source: "build" };
}
