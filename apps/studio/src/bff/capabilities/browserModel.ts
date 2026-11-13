/**
 * The browser's own model, probed honestly.
 *
 * Chrome exposes the built-in model as `LanguageModel` with an
 * `availability()` method; older builds exposed `ai.languageModel`. The old
 * check here only asked whether `ai.languageModel` existed, so a Chrome that
 * offered a downloadable model still read as `Unavailable`.
 *
 * `availability()` can be asynchronous and can throw. This module resolves the
 * new global first, then the legacy one, and never rejects: an unknown value, a
 * missing global, or a throw becomes `unavailable` with a reason that names
 * what happened.
 */

import type { CapabilityStatus } from "./catalog";

export interface BrowserModelAvailability {
  status: CapabilityStatus;
  /** Why the model is not `available`. Present whenever it is not. */
  reason?: string;
}

export interface BrowserModelProbe {
  availability(): Promise<BrowserModelAvailability>;
  reason(): string | null;
}

type AvailabilityValue = string | null | undefined;

interface LanguageModelLike {
  availability?: () => AvailabilityValue | Promise<AvailabilityValue>;
  create?: (options?: unknown) => unknown;
}

interface GlobalScope {
  LanguageModel?: LanguageModelLike;
  ai?: { languageModel?: LanguageModelLike };
  navigator?: { gpu?: unknown };
}

function mapAvailability(value: AvailabilityValue): CapabilityStatus | null {
  switch (value) {
    case "available":
    case "readily":
      return "available";
    case "downloadable":
    case "after-download":
    case "downloading":
      return "downloadable";
    case "unavailable":
      return "unavailable";
    default:
      return null;
  }
}

function resolveModel(scope: GlobalScope): LanguageModelLike | null {
  const modern = scope.LanguageModel;
  if (modern && typeof modern === "object") {
    return modern;
  }
  const legacy = scope.ai?.languageModel;
  if (legacy && typeof legacy === "object") {
    return legacy;
  }
  return null;
}

/** The download reason to show when a model exists but is not ready yet. */
const DOWNLOAD_REASON = "The browser can download this model. It is not ready yet.";
const NO_GPU_REASON =
  "The browser offers no built-in model. WebGPU is required for a local model.";
const UNKNOWN_REASON = "The browser did not report whether its built-in model is ready.";

export function browserModelProbe(scope?: GlobalScope): BrowserModelProbe {
  const target: GlobalScope = scope ?? (globalThis as GlobalScope);
  let last: BrowserModelAvailability | null = null;

  async function availability(): Promise<BrowserModelAvailability> {
    last = await resolveAvailability(target);
    return last;
  }

  return {
    availability,
    /** The reason from the most recent `availability()` call, or null if none
     * has run yet or the model is ready. */
    reason() {
      return last && last.status !== "available" ? (last.reason ?? null) : null;
    },
  };
}

async function resolveAvailability(target: GlobalScope): Promise<BrowserModelAvailability> {
  const model = resolveModel(target);
  if (!model) {
    if (target.navigator?.gpu) {
      // WebGPU alone is not a model: say so rather than claim one.
      return { status: "unavailable", reason: NO_GPU_REASON };
    }
    return { status: "unavailable" };
  }
  if (typeof model.availability !== "function") {
    // A model object with no probe cannot be trusted to be ready.
    return { status: "unavailable", reason: UNKNOWN_REASON };
  }
  try {
    const value = await model.availability();
    const status = mapAvailability(value);
    if (status === null) {
      return { status: "unavailable", reason: UNKNOWN_REASON };
    }
    if (status === "downloadable") {
      return { status, reason: DOWNLOAD_REASON };
    }
    return { status };
  } catch (error) {
    return {
      status: "unavailable",
      reason: error instanceof Error ? error.message : UNKNOWN_REASON,
    };
  }
}
