export const STUDIO_VERSION = __STUDIO_VERSION__;

export interface VersionLabel {
  version: string;
  source: "build" | "desktop";
}

export function versionLabel(desktopVersion: string | null): VersionLabel {
  if (desktopVersion) {
    return { version: desktopVersion, source: "desktop" };
  }
  return { version: STUDIO_VERSION, source: "build" };
}
