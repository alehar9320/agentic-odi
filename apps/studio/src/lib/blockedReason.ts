import type { CapabilityId } from "../bff/capabilities/registry";

/**
 * What a person can do about a block. A reason always names one real control,
 * never a documentation link: the point of explaining in place is that the
 * next step is right there.
 */
export type BlockedActionKind =
  | "start-sidecar"
  | "add-model"
  | "install-connector"
  | "connect-source"
  | "keep-working";

export interface BlockedReason {
  /** One sentence, second person, present tense. */
  sentence: string;
  action: { label: string; kind: BlockedActionKind };
}

/**
 * The one vocabulary for a blocked action. Keyed by every capability the
 * registry models, so a new capability cannot ship without wording — the
 * exhaustiveness test fails first.
 */
const REASONS: Record<CapabilityId, BlockedReason> = {
  "local-data": {
    sentence: "This browser cannot store your work, so nothing can be saved here.",
    action: { label: "Check storage", kind: "keep-working" },
  },
  "local-memory": {
    sentence: "This browser cannot keep a local copy, so memory is unavailable.",
    action: { label: "Check storage", kind: "keep-working" },
  },
  "deterministic-assistant": {
    sentence: "The built-in assistant is unavailable, so the agent cannot answer yet.",
    action: { label: "Check what works here", kind: "keep-working" },
  },
  "browser-model": {
    sentence: "This browser has no built-in model, so the agent needs one you configure.",
    action: { label: "Add a model", kind: "add-model" },
  },
  "endpoint-model": {
    sentence: "No model endpoint is reachable, so the agent cannot answer.",
    action: { label: "Add a model", kind: "add-model" },
  },
  "sidecar-llm": {
    sentence: "The agent needs the local service, which is not running.",
    action: { label: "Start the local service", kind: "start-sidecar" },
  },
  "sidecar-connectors": {
    sentence: "Installing a connector needs the local service, which is not running.",
    action: { label: "Start the local service", kind: "start-sidecar" },
  },
  "sidecar-mcp": {
    sentence: "Running your own tools needs the local service, which is not running.",
    action: { label: "Start the local service", kind: "start-sidecar" },
  },
  "sidecar-import": {
    sentence: "Importing from another machine needs the local service, which is not running.",
    action: { label: "Start the local service", kind: "start-sidecar" },
  },
};

/** Why an action is blocked, in one sentence, with one thing to do about it. */
export function blockedReason(capability: CapabilityId): BlockedReason {
  return REASONS[capability];
}

/** Every reason, so a test can prove no registry key is left without wording. */
export function blockedReasons(): ReadonlyArray<[CapabilityId, BlockedReason]> {
  return Object.entries(REASONS) as ReadonlyArray<[CapabilityId, BlockedReason]>;
}
