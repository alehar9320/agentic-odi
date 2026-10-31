/**
 * Route table for The Living Studio.
 *
 * One pure module owns parsing and formatting. Panel ids are exactly
 * `WorkspacePanelId`; subject kinds are exactly `SignalSubjectKind`.
 *
 * `parseRoute(pathname, search)` returns a discriminated union and never
 * throws; anything unrecognised becomes `{ name: "home" }`.
 * `routeToPath(route)` is the inverse and is the only place that builds
 * strings, so encoding is tested once. Unknown query parameters are
 * preserved, not rebuilt.
 */

import type { SignalSubjectKind, WorkspacePanelId } from "../types";

export type Route =
  | { name: "home" }
  | { name: "thread"; threadId: string }
  | {
      name: "threadPanel";
      threadId: string;
      panel: WorkspacePanelId;
    }
  | {
      name: "threadPanelSubject";
      threadId: string;
      panel: WorkspacePanelId;
      subjectKind: SignalSubjectKind;
      subjectId: string;
    }
  | { name: "customize" }
  | { name: "customizeListing"; listingId: string }
  | { name: "search" };

const THREAD_RE = /^\/t\/([^/]+)$/;
const THREAD_PANEL_RE = /^\/t\/([^/]+)\/([^/]+)$/;
const THREAD_PANEL_SUBJECT_RE = /^\/t\/([^/]+)\/([^/]+)\/([^/]+)\/([^/]+)$/;
const CUSTOMIZE_RE = /^\/customize$/;
const CUSTOMIZE_LISTING_RE = /^\/customize\/([^/]+)$/;
const SEARCH_RE = /^\/search$/;

/**
 * Parse a browser pathname + search into a route.
 * Never throws: anything unrecognised becomes { name: "home" }.
 * Unknown query parameters are preserved, not rebuilt.
 */
export function parseRoute(
  pathname: string,
  search: string = ""
): Route {
  const homeMatch = pathname.match(/^\/$/);
  if (homeMatch) {
    return { name: "home", search };
  }

  const threadMatch = pathname.match(THREAD_RE);
  if (threadMatch) {
    return { name: "thread", threadId: threadMatch[1], search };
  }

  const threadPanelMatch = pathname.match(THREAD_PANEL_RE);
  if (threadPanelMatch) {
    return {
      name: "threadPanel",
      threadId: threadPanelMatch[1],
      panel: threadPanelMatch[2] as WorkspacePanelId,
      search,
    };
  }

  const threadPanelSubjectMatch = pathname.match(THREAD_PANEL_SUBJECT_RE);
  if (threadPanelSubjectMatch) {
    return {
      name: "threadPanelSubject",
      threadId: threadPanelSubjectMatch[1],
      panel: threadPanelSubjectMatch[2] as WorkspacePanelId,
      subjectKind: threadPanelSubjectMatch[3] as SignalSubjectKind,
      subjectId: threadPanelSubjectMatch[4],
      search,
    };
  }

  const customizeMatch = pathname.match(CUSTOMIZE_RE);
  if (customizeMatch) {
    return { name: "customize", search };
  }

  const customizeListingMatch = pathname.match(CUSTOMIZE_LISTING_RE);
  if (customizeListingMatch) {
    return { name: "customizeListing", listingId: customizeListingMatch[1], search };
  }

  const searchMatch = pathname.match(SEARCH_RE);
  if (searchMatch) {
    return { name: "search", search };
  }

  return { name: "home", search };
}

/**
 * Build a pathname from a route. The only place strings are assembled, so
 * encoding is tested once.
 */
export function routeToPath(route: Route): string {
  switch (route.name) {
    case "home":
      return "/";
    case "thread":
      return `/t/${encodeURIComponent(route.threadId)}`;
    case "threadPanel":
      return `/t/${encodeURIComponent(route.threadId)}/${encodeURIComponent(route.panel)}`;
    case "threadPanelSubject":
      return `/t/${encodeURIComponent(route.threadId)}/${encodeURIComponent(route.panel)}/${encodeURIComponent(route.subjectKind)}/${encodeURIComponent(route.subjectId)}`;
    case "customize":
      return "/customize";
    case "customizeListing":
      return `/customize/${encodeURIComponent(route.listingId)}`;
    case "search":
      return "/search";
  }
}

/**
 * Append preserved query parameters to a path.
 */
export function withSearch(path: string, search: string): string {
  if (!search || search === "?") {
    return path;
  }
  return `${path}${search}`;
}

export type { WorkspacePanelId, SignalSubjectKind };
