/**
 * The first-run context conversation, as data.
 *
 * Four questions, one at a time, each skippable. Keeping the script pure makes
 * the pacing and the copy testable without rendering anything.
 */

import type { StudioBrief } from "../types";

export type BriefField = "product_name" | "target_user" | "job_statement" | "core_problem" | "vision";

export type SetupDraft = Record<BriefField, string>;

export interface SetupQuestion {
  field: BriefField;
  /** Short label used by the review and the change chips. */
  label: string;
  ask: string;
  hint: string;
  placeholder: string;
  quickReplies?: string[];
}

export const SETUP_QUESTIONS: SetupQuestion[] = [
  {
    field: "product_name",
    label: "Product",
    ask: "What are you building?",
    hint: "A product, a service, a team — whatever the work is.",
    placeholder: "Ambient — a deployment tool",
  },
  {
    field: "target_user",
    label: "Customer",
    ask: "Who feels the problem most?",
    hint: "The people whose job you are trying to make easier.",
    placeholder: "Platform engineers shipping services",
  },
  {
    field: "job_statement",
    label: "Job",
    ask: "What job are they trying to get done?",
    hint: "The progress they want, not a feature.",
    placeholder: "Get a service from commit to production without hand-copying config",
  },
  {
    field: "core_problem",
    label: "Friction",
    ask: "Where does it hurt most?",
    hint: "One frustration is enough.",
    placeholder: "A missed config key costs hours on deploy day",
    quickReplies: [
      "It takes too long",
      "It is error-prone",
      "It is too manual",
      "It is hard to find what I need",
    ],
  },
  {
    field: "vision",
    label: "Vision (V2MOM)",
    ask: "What is your vision for this domain?",
    hint: "What you want to achieve or create long-term.",
    placeholder: "Empower developers to ship securely without friction",
  },
];

export const QUESTION_COUNT = SETUP_QUESTIONS.length;

/** The phase index meaning "show the review instead of a question". */
export const REVIEW_INDEX = QUESTION_COUNT;

export function emptyDraft(): SetupDraft {
  return {
    product_name: "",
    target_user: "",
    job_statement: "",
    core_problem: "",
    vision: "",
  };
}

export function draftFromBrief(brief: Partial<StudioBrief> | null): SetupDraft {
  return {
    product_name: brief?.product_name ?? "",
    target_user: brief?.target_user ?? "",
    job_statement: brief?.job_statement ?? "",
    core_problem: brief?.core_problem ?? "",
    vision: brief?.v2mom?.vision ?? "",
  };
}

export function draftHasContent(draft: SetupDraft): boolean {
  return SETUP_QUESTIONS.some((question) => draft[question.field].trim().length > 0);
}

/** Where a resumed conversation should pick up: the first unanswered question. */
export function firstUnanswered(draft: SetupDraft): number {
  const index = SETUP_QUESTIONS.findIndex(
    (question) => draft[question.field].trim().length === 0,
  );
  return index === -1 ? REVIEW_INDEX : index;
}

const REFLECTIONS: Record<BriefField, (value: string) => string> = {
  product_name: (value) => `Got it — ${value}.`,
  target_user: (value) => `So it is for ${value}.`,
  job_statement: (value) => `That is the job: ${value}.`,
  core_problem: () => "Then that is where we start.",
  vision: (value) => `Vision set: ${value}.`,
};

export function reflectionFor(field: BriefField, value: string): string {
  return REFLECTIONS[field](value);
}

export function questionContent(
  index: number,
  draft: SetupDraft,
  lead?: string,
): string {
  const question = SETUP_QUESTIONS[index];
  if (!question) {
    return reviewContent(draft);
  }
  const current = draft[question.field].trim();
  return [lead, `**${question.ask}**`, `_${question.hint}_`, current ? `You said: “${current}”.` : ""]
    .filter(Boolean)
    .join("\n\n");
}

export function reviewContent(draft: SetupDraft): string {
  if (!draftHasContent(draft)) {
    return "Nothing yet — that is completely fine. We can start exploring and I will ask when it matters.";
  }
  const lines = SETUP_QUESTIONS.map((question) => {
    const value = draft[question.field].trim();
    return `- **${question.label}** — ${value || "—"}`;
  });
  return ["Here is what I will hold:", "", ...lines].join("\n");
}

const SAVE_PHRASE = /\b(looks? right|save|done|good|yes|ok|okay|ship it|let'?s go|go ahead)\b/i;

export function isSavePhrase(text: string): boolean {
  return SAVE_PHRASE.test(text.trim());
}

const FIELD_HINTS: Array<{ field: BriefField; pattern: RegExp }> = [
  { field: "target_user", pattern: /\b(customer|audience|user|who it|who is|who feels)\b/i },
  { field: "job_statement", pattern: /\b(job|trying to do|progress|outcome)\b/i },
  { field: "core_problem", pattern: /\b(friction|pain|problem|hurt|stuck|frustrat)\b/i },
  { field: "vision", pattern: /\b(vision|v2mom|aspiration|long term|future state)\b/i },
  { field: "product_name", pattern: /\b(product|building|service|tool|what it is)\b/i },
];

/** Recognise "change the job" style replies in the review. */
export function fieldFromText(text: string): BriefField | null {
  return FIELD_HINTS.find((entry) => entry.pattern.test(text))?.field ?? null;
}

export function isQuestionFilled(draft: SetupDraft, index: number): boolean {
  const question = SETUP_QUESTIONS[index];
  return Boolean(question && draft[question.field].trim());
}

export type SetupIntent =
  | { kind: "skip" }
  | { kind: "explore" }
  | {
      kind: "panel";
      panel: "landscape" | "jobmap" | "impact" | "evidence" | "capture" | "settings";
    };

const SKIP_PHRASE = /\b(skip|pass|not sure|no idea|don'?t know|unsure)\b/i;
const EXPLORE_PHRASE = /^(explore|later|not now|maybe later|let me look around)\b/i;
const OPEN_PHRASE = /^(show|open|go to|take me to|view)\b/i;

/**
 * Read a free-text reply as an intent before treating it as an answer.
 * This is what keeps the conversation from swallowing "skip" or "show me the
 * landscape" as a product name.
 */
export function parseSetupIntent(text: string): SetupIntent | null {
  const value = text.trim();
  if (!value) {
    return null;
  }
  if (SKIP_PHRASE.test(value)) {
    return { kind: "skip" };
  }
  if (EXPLORE_PHRASE.test(value)) {
    return { kind: "explore" };
  }
  const opening = OPEN_PHRASE.test(value);
  const lower = value.toLowerCase();
  if (opening || lower === "landscape") {
    if (/landscape|opportunit/.test(lower)) {
      return { kind: "panel", panel: "landscape" };
    }
    if (/job map|steps?/.test(lower)) {
      return { kind: "panel", panel: "jobmap" };
    }
    if (/impact|simulat/.test(lower)) {
      return { kind: "panel", panel: "impact" };
    }
    if (/evidence/.test(lower)) {
      return { kind: "panel", panel: "evidence" };
    }
    if (/capture|add an outcome/.test(lower)) {
      return { kind: "panel", panel: "capture" };
    }
    if (/settings?/.test(lower)) {
      return { kind: "panel", panel: "settings" };
    }
  }
  return null;
}
