export const STUDIO_VERSION = __STUDIO_VERSION__;

export interface VersionLabel {
  version: string;
  source: "build" | "desktop";
}

/** Pick the version to show: desktop updater wins when it has one. */
export function versionLabel(desktopVersion: string | null): VersionLabel {
  if (desktopVersion) {
    return { version: desktopVersion, source: "desktop" };
  }
  return { version: STUDIO_VERSION, source: "build" };
}
