/**
 * The vocabulary a shared read-only link needs, kept apart from the app so the
 * page can be reasoned about — and tested — without a workspace behind it.
 *
 * Nothing here touches the canvas, the sidecar config, or local storage: a
 * shared link is a capability, and the page that opens it holds no state beyond
 * the scoped payload the token returns.
 */

const SHARED_PREFIX = "/shared/";

/**
 * The token in a `/shared/<token>` path, or `null` for any other route.
 *
 * `decodeURIComponent` throws on a malformed escape; a path that cannot be read
 * is simply not a shared link, so the boot falls through to the app instead of
 * crashing on the way to the stage.
 */
export function sharedTokenFromPath(pathname: string): string | null {
  if (!pathname.startsWith(SHARED_PREFIX)) {
    return null;
  }
  const rest = pathname.slice(SHARED_PREFIX.length);
  // A single segment is the token; a trailing slash is tolerated, a deeper path
  // is a different route and gets no artifact.
  const segment = rest.endsWith("/") ? rest.slice(0, -1) : rest;
  if (!segment || segment.includes("/")) {
    return null;
  }
  try {
    return decodeURIComponent(segment);
  } catch {
    return null;
  }
}

function parsedTime(iso: string): number | null {
  const at = Date.parse(iso);
  return Number.isNaN(at) ? null : at;
}

/**
 * Whether the link is past its expiry. A timestamp that will not parse is not
 * treated as expired: hiding a live artifact behind a parse bug is worse than
 * showing a link whose expiry the header cannot name.
 */
export function isShareExpired(expiresAt: string, now: number = Date.now()): boolean {
  const at = parsedTime(expiresAt);
  return at !== null && at <= now;
}

/**
 * The expiry line the header carries, or `null` when the link has expired (the
 * page says so in its own sentence) or the timestamp will not parse.
 */
export function formatShareExpiry(expiresAt: string, now: number = Date.now()): string | null {
  const at = parsedTime(expiresAt);
  if (at === null || at <= now) {
    return null;
  }
  const days = Math.floor((at - now) / (24 * 60 * 60 * 1000));
  if (days < 1) {
    return "expires today";
  }
  return `expires in ${days} day${days === 1 ? "" : "s"}`;
}
