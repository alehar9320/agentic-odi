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
    };
  }
}

export function notFound(entity: string, id: string): BffError {
  return new BffError("not_found", `${entity} ${id} was not found.`, {
    suggestion: "Refresh the canvas and try again.",
  });
}

export function validation(message: string): BffError {
  return new BffError("validation", message, {
    suggestion: "Check the value and try again.",
  });
}
