import type { StudioError } from "../types";

/** A local BFF failure carrying the same shape the sidecar uses. */
export class BffError extends Error {
  readonly studioError: StudioError;

  constructor(
    code: string,
    message: string,
    options: {
      detail?: string | null;
      suggestion?: string | null;
      retryable?: boolean;
      field?: string | null;
    } = {},
  ) {
    super(message);
    this.name = "BffError";
    this.studioError = {
      code,
      message,
      detail: options.detail ?? null,
      suggestion: options.suggestion ?? null,
      retryable: options.retryable ?? false,
      field: options.field ?? null,
    };
  }
}

export function notFound(entity: string, id: string): BffError {
  return new BffError("not_found", `${entity} ${id} was not found.`, {
    suggestion: "Refresh the canvas and try again.",
  });
}

export function validation(message: string, field?: string | null): BffError {
  return new BffError("validation", message, {
    suggestion: "Check the value and try again.",
    field: field ?? null,
  });
}

/**
 * The one message a full disk gets. It says what happened, that nothing was
 * lost, and the single next step — never "something went wrong", and never a
 * suggestion to clear data.
 */
export const STORAGE_FULL_MESSAGE =
  "This browser is out of space for this site. Your existing work is safe — export it, or free space and try again.";
export const STORAGE_FULL_SUGGESTION =
  "Export your workspace from Settings, or free space, then try again.";

/**
 * A write the browser refused because the origin is out of space.
 *
 * `retryable` is false on purpose: the condition clears when the person frees
 * space or exports, not when a timer fires again.
 */
export class StorageFullError extends BffError {
  constructor() {
    super("storage_full", STORAGE_FULL_MESSAGE, {
      suggestion: STORAGE_FULL_SUGGESTION,
      retryable: false,
    });
    this.name = "StorageFullError";
  }
}

/**
 * Whether a thrown value is a browser quota failure.
 *
 * Chrome, Safari, and the IndexedDB spec raise `QuotaExceededError` (code 22);
 * Firefox raises `NS_ERROR_DOM_QUOTA_REACHED` (code 1014) and, in some paths, a
 * bare `DOMException` with that message. All three mean the same thing, so they
 * are recognized here and nowhere else.
 */
export function isQuotaExceededError(error: unknown): boolean {
  if (!error || typeof error !== "object") {
    return false;
  }
  const candidate = error as { name?: unknown; code?: unknown; message?: unknown };
  if (candidate.name === "QuotaExceededError") {
    return true;
  }
  if (candidate.code === 22 || candidate.code === 1014) {
    return true;
  }
  if (typeof candidate.message === "string" && /quota/i.test(candidate.message)) {
    return true;
  }
  return false;
}

export function storageFull(): StorageFullError {
  return new StorageFullError();
}
