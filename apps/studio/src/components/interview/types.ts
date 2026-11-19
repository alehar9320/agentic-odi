/**
 * The display contract for an interview card.
 *
 * This is deliberately not a domain model: it describes the three shapes a
 * question can take on screen and nothing about jobs, outcomes, or evidence.
 * The conductor that turns answers into records lives elsewhere (#397); this
 * file only says what a question *is* so the card can render one.
 */

/** The three ways a question can be asked. */
export type QuestionKind = "statement" | "text" | "scale";

export interface Question {
  id: string;
  kind: QuestionKind;
  prompt: string;
  help?: string;
  /** Bounds for a `scale` question. Both are required when `kind` is `scale`. */
  min?: number;
  max?: number;
  required: boolean;
}

const KINDS: readonly QuestionKind[] = ["statement", "text", "scale"];

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/**
 * Whether an untrusted value is a question the card can render.
 *
 * Questions arrive from a model, so the card treats them as input rather than
 * as code: an object missing its id or carrying an unknown kind is refused
 * here, before a malformed question can render as an empty control. A `scale`
 * must carry finite bounds so its range has a defined span.
 */
export function isQuestion(value: unknown): value is Question {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  if (typeof candidate.id !== "string" || candidate.id.trim() === "") {
    return false;
  }
  if (typeof candidate.prompt !== "string" || candidate.prompt.trim() === "") {
    return false;
  }
  if (typeof candidate.kind !== "string" || !KINDS.includes(candidate.kind as QuestionKind)) {
    return false;
  }
  if (typeof candidate.required !== "boolean") {
    return false;
  }
  if (candidate.help !== undefined && typeof candidate.help !== "string") {
    return false;
  }
  if (candidate.kind === "scale") {
    return (
      isFiniteNumber(candidate.min) && isFiniteNumber(candidate.max) && candidate.max > candidate.min
    );
  }
  return true;
}
