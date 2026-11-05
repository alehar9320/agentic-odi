/**
 * Every surface the contrast gate paints (ALH-216).
 *
 * The gate used to walk six screens because those six were the ones someone had
 * thought to open in a browser. `src/components/workspace/panels.tsx` is the
 * registry the app actually renders from, and
 * `src/components/workspace/panels.test.tsx` holds this list against it: a
 * registry entry that appears in neither list fails the build. That is the
 * point of the file — "every surface reads the palette" is worth nil unless it
 * can be pointed at the list it was measured against.
 *
 * This module is deliberately plain data with no Playwright import, because the
 * unit suite reads it. The routes to these surfaces are in `routes.ts`.
 */

/** A surface, and the registry entry it covers. */
export interface Surface {
  /** The name in the report and in a known-pair note. */
  readonly id: string;
  /** The `WORKSPACE_PANELS` id it measures, or `null` for the page that is not a lens. */
  readonly panel: string | null;
}

export const SURFACES: Surface[] = [
  { id: "home", panel: null },
  { id: "landscape", panel: "landscape" },
  { id: "records", panel: "records" },
  { id: "brief", panel: "brief" },
  { id: "jobmap", panel: "jobmap" },
  { id: "segments", panel: "segments" },
  { id: "evidence", panel: "evidence" },
  { id: "memory", panel: "memory" },
  { id: "catchup", panel: "catchup" },
  { id: "capture", panel: "capture" },
  { id: "settings", panel: "settings" },
];

/**
 * A registered lens the shipped UI never opens, so no browser can paint it.
 *
 * This list has to stay short and has to stay honest: each entry says why the
 * gate cannot reach it and who owns the missing route. Cloud Agent scheduling
 * is rendered by `panels.tsx` and reachable from nothing — no rail chip, no
 * command, no link — because there is no scheduler yet.
 */
export const UNMEASURED_PANELS: { panel: string; issue: string; reason: string }[] = [
  {
    panel: "schedule",
    issue: "#95",
    reason: "no affordance opens it: the scheduler does not exist yet",
  },
];
