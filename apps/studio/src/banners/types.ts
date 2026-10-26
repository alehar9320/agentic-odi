/**
 * The shape of a banner.
 *
 * A banner is a statement about the state of the studio. `kind` is its identity:
 * raising the same kind twice updates the banner in place rather than adding a
 * second, so a retry loop can never paint ten copies of the same warning.
 */

export type BannerSeverity = "info" | "success" | "warning" | "critical";

/**
 * `persistent` waits for the condition to clear or the user to dismiss it;
 * `transient` expires on its own after `durationMs`.
 */
export type BannerLife = "persistent" | "transient";

/** `top` is a page strip; `corner` is the floating stack. */
export type BannerDock = "top" | "corner";

export type BannerKind =
  | "sidecar-down"
  | "model-offline"
  | "update-available"
  | "update-ready"
  | "write-rejected"
  | "info"
  | "success"
  | "error";

export interface BannerAction {
  label: string;
  /** The message sent when the action is taken, written as the user would say it. */
  intent: string;
  tone: "primary" | "ghost";
}

/** What a caller passes. Everything but `kind` may be omitted. */
export interface BannerSpec {
  kind: BannerKind;
  title?: string;
  body?: string;
  severity?: BannerSeverity;
  life?: BannerLife;
  durationMs?: number;
  actions?: BannerAction[];
  dismissible?: boolean;
}

/** A banner with every field resolved from its kind's defaults. */
export interface Banner {
  id: string;
  kind: BannerKind;
  title: string;
  body: string;
  severity: BannerSeverity;
  life: BannerLife;
  dock: BannerDock;
  durationMs: number;
  actions: BannerAction[];
  dismissible: boolean;
  raisedAt: number;
}

/** The catalog entry: the defaults a caller may override. */
export interface BannerDefaults {
  severity: BannerSeverity;
  life: BannerLife;
  dock: BannerDock;
  title: string;
  body: string;
  durationMs?: number;
  actions?: BannerAction[];
  dismissible: boolean;
}
