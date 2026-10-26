/**
 * The closed catalog of banner kinds.
 *
 * One entry per kind, and a new banner is an entry here plus a `raise()` call —
 * never a new component and never a new CSS class. This file is the single
 * source of truth for a banner's severity, life, dock, and default copy.
 */

import type { Banner, BannerDefaults, BannerKind, BannerSeverity, BannerSpec } from "./types";

/** How long a transient banner lingers before it expires. */
export const DEFAULT_DURATION_MS = 6000;

export const BANNER_CATALOG: Record<BannerKind, BannerDefaults> = {
  "sidecar-down": {
    severity: "critical",
    life: "persistent",
    dock: "top",
    title: "The studio sidecar isn't running.",
    body: "The assistant is paused and live data is frozen until it comes back.",
    dismissible: true,
    actions: [
      { label: "Recheck", intent: "Recheck the connection to the studio sidecar.", tone: "ghost" },
      {
        label: "Start the sidecar",
        intent: "Open setup so I can start the studio sidecar.",
        tone: "ghost",
      },
    ],
  },
  "model-offline": {
    severity: "warning",
    life: "persistent",
    dock: "top",
    title: "Working by hand.",
    body: "No model is reachable, so the assistant is paused. Every change still writes to your ODI repository.",
    dismissible: false,
    actions: [
      {
        label: "Capture an outcome",
        intent: "Open capture so I can add an outcome by hand.",
        tone: "ghost",
      },
      { label: "Map the job", intent: "Open the job map.", tone: "ghost" },
      { label: "Set your context", intent: "Open setup so I can set my context.", tone: "ghost" },
    ],
  },
  "update-available": {
    severity: "info",
    life: "persistent",
    dock: "top",
    title: "An update is ready to download.",
    body: "A newer version of the desktop build is available.",
    dismissible: true,
    actions: [
      { label: "Install", intent: "Install the available update.", tone: "primary" },
      { label: "Later", intent: "Remind me about the update later.", tone: "ghost" },
    ],
  },
  "update-ready": {
    severity: "success",
    life: "persistent",
    dock: "top",
    title: "Update installed.",
    body: "Restart to finish the update.",
    dismissible: true,
    actions: [{ label: "Restart", intent: "Restart the studio.", tone: "primary" }],
  },
  "write-rejected": {
    severity: "critical",
    life: "persistent",
    dock: "top",
    title: "That write was rejected.",
    body: "The change was not saved. Nothing was written to your ODI repository.",
    dismissible: true,
  },
  info: {
    severity: "info",
    life: "transient",
    dock: "corner",
    title: "",
    body: "",
    durationMs: DEFAULT_DURATION_MS,
    dismissible: true,
  },
  success: {
    severity: "success",
    life: "transient",
    dock: "corner",
    title: "",
    body: "",
    durationMs: DEFAULT_DURATION_MS,
    dismissible: true,
  },
  error: {
    severity: "critical",
    life: "transient",
    dock: "corner",
    title: "",
    body: "",
    durationMs: DEFAULT_DURATION_MS,
    dismissible: true,
  },
};

const SEVERITY_WEIGHT: Record<BannerSeverity, number> = {
  critical: 4,
  warning: 3,
  info: 2,
  success: 1,
};

export function severityWeight(severity: BannerSeverity): number {
  return SEVERITY_WEIGHT[severity];
}

/** Merge a spec over its kind's defaults, with the caller winning. */
export function resolveSpec(spec: BannerSpec): Omit<Banner, "id" | "raisedAt"> {
  const defaults = BANNER_CATALOG[spec.kind];
  const life = spec.life ?? defaults.life;
  return {
    kind: spec.kind,
    title: spec.title ?? defaults.title,
    body: spec.body ?? defaults.body,
    severity: spec.severity ?? defaults.severity,
    life,
    dock: defaults.dock,
    durationMs: life === "transient" ? spec.durationMs ?? defaults.durationMs ?? DEFAULT_DURATION_MS : 0,
    actions: spec.actions ?? defaults.actions ?? [],
    dismissible: spec.dismissible ?? defaults.dismissible,
  };
}
