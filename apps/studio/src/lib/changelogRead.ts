/**
 * Remember which release notes the reader has already acknowledged.
 *
 * The mark lives in localStorage rather than the sidecar database because it is
 * per-browser reading state, and because the changelog must work with the
 * sidecar down (the release notes are served by it, the acknowledgement is not).
 */

import type { ChangelogRelease } from "../types";

export const CHANGELOG_READ_KEY = "agentic-odi.changelog.read";

/**
 * Announced after an acknowledgement is stored, so the dot that advertised the
 * notes clears at the same moment the modal says they are read (#695). The
 * event carries nothing: every listener re-reads the same acknowledgement.
 */
export const CHANGELOG_READ_EVENT = "agentic-odi:changelog-read";

/** Old versions fall off the end; nobody scrolls back further than this. */
const MAX_REMEMBERED = 200;

export function readReleaseVersions(): string[] {
  try {
    const raw = window.localStorage.getItem(CHANGELOG_READ_KEY);
    if (!raw) {
      return [];
    }
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((value): value is string => typeof value === "string");
  } catch {
    return [];
  }
}

/** Persist every version in `versions` as read and return the merged list. */
export function markReleasesRead(versions: readonly string[]): string[] {
  const merged = [...new Set([...readReleaseVersions(), ...versions])];
  const next = merged.slice(-MAX_REMEMBERED);
  try {
    window.localStorage.setItem(CHANGELOG_READ_KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable: the badge still clears for this session */
  }
  try {
    window.dispatchEvent(new Event(CHANGELOG_READ_EVENT));
  } catch {
    /* no window to tell: the next read of the acknowledgement still agrees */
  }
  return next;
}

export function unreadReleases(
  releases: readonly ChangelogRelease[],
  read: readonly string[],
): ChangelogRelease[] {
  const seen = new Set(read);
  return releases.filter((release) => !seen.has(release.version));
}
