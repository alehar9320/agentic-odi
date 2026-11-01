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
  | "edge-offer"
  | "edge-downloading"
  | "edge-ready"
  | "edge-unlocked"
  | "update-available"
  | "update-ready"
  | "write-rejected"
  | "info"
  | "success"
  | "error";

/** A studio action a banner button can invoke directly. */
export type BannerActionId =
  | "recheck-sidecar"
  | "open-setup"
  | "open-capture"
  | "open-jobmap"
  | "install-update"
  | "restart"
  | "enable-edge-model"
  | "decline-edge-model";

export interface BannerAction {
  label: string;
  /**
   * A studio action invoked directly. Preferred for things that are not
   * messages — rechecking a connection, opening a panel.
   */
  action?: BannerActionId;
  /**
   * A message to send as the user. Used when the right response is to ask the
   * agent for something, written as the user would say it.
   */
  intent?: string;
  tone: "primary" | "ghost";
}

/** What a caller passes. Everything but `kind` may be omitted. */
export interface BannerSpec {
  kind: BannerKind;
  /**
   * A stable identity for this banner. Two raises with the same key are the
   * same banner and update in place. Persistent banners default their key to
   * their kind; a transient banner with no key is an event and stacks.
   */
  key?: string;
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
