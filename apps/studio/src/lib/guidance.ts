import type { StudioBrief } from "../types";

/**
 * The studio's "one next thing".
 *
 * A first impression is not a tour, and it is not a wall of tips. After the
 * first exchange the studio may owe the person one sentence that changes what
 * they do next: context it does not have, or the evidence a score is missing.
 * Never both, never before they have experienced anything, and never a gate.
 *
 * The rules are pure so they can be reasoned about and tested without React.
 */

export type GuidanceId = "context" | "evidence";

export type GuidanceAction = "context" | "capture";

export interface Guidance {
  id: GuidanceId;
  line: string;
  actionLabel: string;
  action: GuidanceAction;
}

export interface GuidanceInput {
  brief: StudioBrief | null;
  messageCount: number;
  outcomeCount: number;
  /** Outcomes that carry a customer's words. */
  evidenceCount: number;
  dismissed: readonly GuidanceId[];
}

export const GUIDANCE_STORAGE_KEY = "studio.guidance";

export const GUIDANCE_CAPTURE_PROMPT =
  "I heard something from a customer that I want to make sense of. Ask me what they said, then help me turn it into something we can act on.";

const CONTEXT: Guidance = {
  id: "context",
  line: "I don't know your product yet. Tell me and every reply gets sharper.",
  actionLabel: "Add context",
  action: "context",
};

const EVIDENCE: Guidance = {
  id: "evidence",
  line: "A score is a guess until a customer says it. Capture what you heard.",
  actionLabel: "Capture what you heard",
  action: "capture",
};

/**
 * Choose the single hint worth showing, or nothing.
 *
 * Priority is deliberate: context is foundational and makes every later answer
 * better, so it outranks evidence. Both are dismissible forever.
 */
export function currentGuidance(input: GuidanceInput): Guidance | null {
  // The empty stage already extends an invitation; a hint there would be a
  // second voice competing with the first.
  if (input.messageCount === 0) {
    return null;
  }

  const dismissed = new Set(input.dismissed);
  if (!input.brief && !dismissed.has(CONTEXT.id)) {
    return CONTEXT;
  }
  if (
    input.outcomeCount > 0 &&
    input.evidenceCount === 0 &&
    !dismissed.has(EVIDENCE.id)
  ) {
    return EVIDENCE;
  }
  return null;
}

export type GuidanceStorage = Pick<Storage, "getItem" | "setItem">;

const KNOWN_IDS = new Set<string>([CONTEXT.id, EVIDENCE.id]);

function browserStorage(): GuidanceStorage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readDismissedGuidance(
  storage: GuidanceStorage | null = browserStorage(),
): GuidanceId[] {
  if (!storage) {
    return [];
  }
  try {
    const raw = storage.getItem(GUIDANCE_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(
      (value): value is GuidanceId => typeof value === "string" && KNOWN_IDS.has(value),
    );
  } catch {
    return [];
  }
}

export function writeDismissedGuidance(
  ids: readonly GuidanceId[],
  storage: GuidanceStorage | null = browserStorage(),
): void {
  if (!storage) {
    return;
  }
  try {
    storage.setItem(GUIDANCE_STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // Storage denied: the hint is dismissed for this session only.
  }
}
