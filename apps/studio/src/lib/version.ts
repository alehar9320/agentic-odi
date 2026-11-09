/**
 * The one source of truth for the build version. It is baked into the bundle
 * at build time from `apps/studio/package.json` (`__STUDIO_VERSION__` in
 * `vite.config.ts`) and re-exported here so no component carries a literal.
 *
 * On desktop the updater's version takes precedence once it has one; this is
 * the fallback, and the fallback is never a placeholder.
 */

/** Where the version on screen came from. The desktop updater wins when it
 * has reported one; otherwise the build is the honest answer. */
export interface VersionLabel {
  version: string;
  source: "build" | "desktop";
}

export const STUDIO_VERSION = __STUDIO_VERSION__;

/**
 * Label the version for display. A non-empty desktop version is authoritative;
 * anything else (no updater, an unsupported transport, a null) falls back to
 * the build version, which is always present.
 */
export function versionLabel(desktopVersion: string | null | undefined): VersionLabel {
  if (typeof desktopVersion === "string" && desktopVersion.trim().length > 0) {
    return { version: desktopVersion, source: "desktop" };
  }
  return { version: STUDIO_VERSION, source: "build" };
}