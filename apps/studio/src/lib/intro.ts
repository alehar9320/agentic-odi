/**
 * The first-run introduction, as data.
 *
 * Five turns in the order a colleague would ask: the person, the customer, the
 * win, the friction, and what they already have. Keeping the script, the
 * parsing, and the migration pure makes the pacing and the copy testable
 * without rendering anything.
 */

import type { StudioBrief } from "../types";

export type IntroField = "role" | "customer" | "win" | "friction" | "evidence";

export interface IntroTurn {
  id: IntroField;
  question: string;
  /** Illustrations, never quick replies: choosing one must not store it. */
  examples: [string, string];
}

export const INTRO_TURNS: IntroTurn[] = [
  {
    id: "role",
    question: "What are you working on, and what's your part in it?",
    examples: [
      "I'm the PM for the deploy tool; the team is four engineers and a designer.",
      "I run support for a billing product; I'm the only designer on the team.",
    ],
  },
  {
    id: "customer",
    question: "Who feels the problem first, not the buyer, the person who hits it?",
    examples: [
      "The on-call platform engineer at 2am.",
      "The finance lead closing the books on the last day of the month.",
    ],
  },
  {
    id: "win",
    question: "What are they trying to win in the next quarter?",
    examples: [
      "Ship a service without hand-copying config.",
      "Close the month without a spreadsheet of missed invoices.",
    ],
  },
  {
    id: "friction",
    question: "Where does it break today? One sentence is enough.",
    examples: [
      "A missed key costs a deploy day.",
      "Every refund is retyped into three systems.",
    ],
  },
  {
    id: "evidence",
    question: "What do you already have: interview notes, tickets, a Slack thread?",
    examples: [
      "Nine onboarding calls and a very angry ticket.",
      "Twelve support threads and a spreadsheet of churn reasons.",
    ],
  },
];

export const INTRO_TURN_COUNT = INTRO_TURNS.length;

/** The draft turn meaning "show the summary instead of a question". */
export const SUMMARY_INDEX = INTRO_TURN_COUNT;

export const INTRO_DRAFT_KEY = "studio.intro";
export const LEGACY_DRAFT_KEY = "studio.setupDraft";
export const LEGACY_STEP_KEY = "studio.setupStep";

/** The cap on a stored answer. The full sentence stays as the quote. */
export const MAX_VALUE_LENGTH = 280;

export type IntroAnswers = Partial<Record<IntroField, string>>;
export type IntroQuotes = Partial<Record<IntroField, string>>;

export interface IntroDraft {
  turn: number;
  answers: IntroAnswers;
  quotes: IntroQuotes;
  /** A line kept from an earlier setup draft. Never invented. */
  note?: string;
}

export interface IntroAnswer {
  field: IntroField;
  value: string;
  quote: string;
}

/**
 * Read a reply as an answer to its turn.
 *
 * It never rejects a sentence: the turn's field gets the value, capped, and
 * `quote` keeps the whole thing so nothing the person said is lost.
 */
export function parseIntroReply(id: IntroField, text: string): IntroAnswer {
  const quote = text.trim();
  return { field: id, value: quote.slice(0, MAX_VALUE_LENGTH), quote };
}

export interface IntroDefaults {
  customerLabel?: string;
  jobStatement?: string;
  outcomeDraft?: string;
}

const OUTCOME_PREFIX = "Minimize the time it takes to ";

function firstClause(value: string): string {
  return value.replace(/\s+/g, " ").split(/[.;]/)[0].trim();
}

function lowerFirst(value: string): string {
  return value ? value.charAt(0).toLowerCase() + value.slice(1) : value;
}

function outcomeTail(friction: string): string {
  const clause = firstClause(friction).replace(/[.!?]+$/, "").trim();
  if (!clause) {
    return "finish the job";
  }
  if (/^(a|an|the|every|each)\b/i.test(clause)) {
    return `recover when ${lowerFirst(clause)}`;
  }
  return lowerFirst(clause.replace(/^(it|this|that|they|we)\s+(is|are|takes|costs)\s+/i, ""));
}

/**
 * Defaults the agent may offer after a turn. Each one is a suggestion until the
 * summary is accepted; nothing here is written to the brief on its own.
 */
export function proposeDefaults(answers: IntroAnswers): IntroDefaults {
  const defaults: IntroDefaults = {};

  const customer = answers.customer?.trim();
  if (customer) {
    defaults.customerLabel = firstClause(customer).replace(/^the\s+/i, "");
  }

  const win = answers.win?.trim();
  if (win) {
    defaults.jobStatement = firstClause(win).replace(/[.!?]+$/, "");
  }

  const friction = answers.friction?.trim();
  if (friction) {
    defaults.outcomeDraft = `${OUTCOME_PREFIX}${outcomeTail(friction)}`;
  }

  return defaults;
}

/** The team a person named in their first answer, if they named one. */
export function deriveTeam(role: string | undefined): string | undefined {
  const value = role?.trim();
  if (!value) {
    return undefined;
  }
  const match = /\bteam(?:\s+is|'s|\s+of|:)\s+(.+)$/i.exec(value);
  return match?.[1].replace(/[.!?]+$/, "").trim() || undefined;
}

/**
 * The product a person works on, taken from the object of "building", "working
 * on", or "for". A mechanical extraction, shown in the summary beside the
 * answer it came from, not an invented name.
 */
export function deriveProduct(role: string | undefined): string | undefined {
  const value = role?.trim();
  if (!value) {
    return undefined;
  }
  const patterns = [
    /\b(?:building|working on)\s+(?:a|an|the)?\s*([^;,.]{3,60})/i,
    /\bfor\s+(?:the|a|an)?\s*([^;,.]{3,60})/i,
  ];
  for (const pattern of patterns) {
    const match = pattern.exec(value);
    const candidate = match?.[1]
      .replace(/[.!?]+$/, "")
      .replace(/\s+/g, " ")
      .trim();
    if (candidate && !/^team\b/i.test(candidate)) {
      return candidate;
    }
  }
  return undefined;
}

/** What a person already has, as separate items. The whole sentence stays a quote. */
export function evidenceItems(value: string | undefined): string[] | undefined {
  const trimmed = value?.trim();
  if (!trimmed) {
    return undefined;
  }
  const items = trimmed
    .split(/\s*;\s*|\s*,\s*(?:and\s+)?|(?<=\w)\s+and\s+/i)
    .map((item) =>
      item
        .replace(/^(?:and|plus)\s+/i, "")
        .replace(/[.!]+$/, "")
        .trim(),
    )
    .filter(Boolean);
  return items.length ? items : undefined;
}

/** The brief fields the five answers produce. */
export interface IntroBriefFields {
  product_name: string;
  target_user: string;
  job_statement: string;
  core_problem: string;
  role?: string;
  team?: string;
  evidence_at_hand?: string[];
}

export function briefFromAnswers(answers: IntroAnswers): IntroBriefFields {
  const role = answers.role?.trim();
  return {
    product_name: deriveProduct(role) ?? "",
    target_user: answers.customer?.trim() ?? "",
    job_statement: answers.win?.trim() ?? "",
    core_problem: answers.friction?.trim() ?? "",
    role: role || undefined,
    team: deriveTeam(role),
    evidence_at_hand: evidenceItems(answers.evidence),
  };
}

export function hasIntroAnswers(answers: IntroAnswers): boolean {
  return INTRO_TURNS.some((turn) => Boolean(answers[turn.id]?.trim()));
}

/** Where a resumed introduction picks up: the first unanswered turn. */
export function firstUnansweredTurn(answers: IntroAnswers): number {
  const index = INTRO_TURNS.findIndex((turn) => !answers[turn.id]?.trim());
  return index === -1 ? SUMMARY_INDEX : index;
}

export function emptyIntroDraft(): IntroDraft {
  return { turn: 0, answers: {}, quotes: {} };
}

/**
 * An existing brief as introduction answers. Editing opens on the summary:
 * the person already answered, and is here to change something.
 */
export function draftFromBrief(brief: Partial<StudioBrief> | null): IntroDraft {
  const source: IntroAnswers = {
    role: brief?.role?.trim() || undefined,
    customer: brief?.target_user?.trim() || undefined,
    win: brief?.job_statement?.trim() || undefined,
    friction: brief?.core_problem?.trim() || undefined,
    evidence: brief?.evidence_at_hand?.join("; ") || undefined,
  };
  const answers: IntroAnswers = {};
  const quotes: IntroQuotes = {};
  for (const turn of INTRO_TURNS) {
    const value = source[turn.id]?.trim();
    if (value) {
      answers[turn.id] = value;
      quotes[turn.id] = value;
    }
  }
  return {
    turn: SUMMARY_INDEX,
    answers,
    quotes,
    note: brief?.v2mom?.vision?.trim() || undefined,
  };
}

const SKIP_REPLY = /^(skip|skip this|pass|not sure|no idea|i don'?t know|unsure|next)$/i;
const EXPLORE_REPLY = /^(explore|explore on my own|not now|maybe later|later|let me look around)$/i;

/** A reply that means "leave this one" rather than an answer. */
export function isSkipReply(text: string): boolean {
  return SKIP_REPLY.test(text.trim().replace(/[.!]+$/, ""));
}

/** A reply that means "close this without saving". */
export function isExploreReply(text: string): boolean {
  return EXPLORE_REPLY.test(text.trim().replace(/[.!]+$/, ""));
}

const REFLECTIONS: Record<IntroField, string> = {
  role: "Got it.",
  customer: "That is who feels it first.",
  win: "That is what they are trying to win.",
  friction: "Then that is where we start.",
  evidence: "Good — that is what we have to work with.",
};

export function introReflection(field: IntroField): string {
  return REFLECTIONS[field];
}

function browserStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function read(key: string): string | null {
  try {
    return browserStorage()?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    browserStorage()?.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
}

function remove(key: string): void {
  try {
    browserStorage()?.removeItem(key);
  } catch {
    /* storage unavailable */
  }
}

function cleanAnswers(value: unknown): IntroAnswers {
  if (!value || typeof value !== "object") {
    return {};
  }
  const source = value as Record<string, unknown>;
  const answers: IntroAnswers = {};
  for (const turn of INTRO_TURNS) {
    const raw = source[turn.id];
    if (typeof raw === "string" && raw.trim()) {
      answers[turn.id] = raw;
    }
  }
  return answers;
}

function normaliseDraft(value: unknown): IntroDraft {
  if (!value || typeof value !== "object") {
    return emptyIntroDraft();
  }
  const source = value as Record<string, unknown>;
  const answers = cleanAnswers(source.answers);
  const turn =
    typeof source.turn === "number" &&
    Number.isInteger(source.turn) &&
    source.turn >= 0 &&
    source.turn <= SUMMARY_INDEX
      ? source.turn
      : firstUnansweredTurn(answers);
  const note = typeof source.note === "string" && source.note.trim() ? source.note.trim() : undefined;
  return {
    turn,
    answers,
    quotes: cleanAnswers(source.quotes),
    ...(note ? { note } : {}),
  };
}

export function loadIntroDraft(): IntroDraft {
  const raw = read(INTRO_DRAFT_KEY);
  if (!raw) {
    return emptyIntroDraft();
  }
  try {
    return normaliseDraft(JSON.parse(raw));
  } catch {
    return emptyIntroDraft();
  }
}

export function saveIntroDraft(draft: IntroDraft): void {
  write(INTRO_DRAFT_KEY, JSON.stringify(normaliseDraft(draft)));
}

export function clearIntroDraft(): void {
  remove(INTRO_DRAFT_KEY);
}

function legacyValue(record: Record<string, unknown>, key: string): string | undefined {
  const value = record[key];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

/**
 * Carry an old five-field draft into the introduction, once.
 *
 * Safe to call on every boot: with no legacy key it does nothing, and with a
 * new draft already present it only removes the stale keys.
 */
export function migrateLegacyDraft(): boolean {
  const raw = read(LEGACY_DRAFT_KEY);
  if (raw === null) {
    return false;
  }

  if (read(INTRO_DRAFT_KEY) === null) {
    try {
      const legacy = JSON.parse(raw) as Record<string, unknown>;
      const vision =
        legacyValue(legacy, "vision") ??
        (legacy.v2mom && typeof legacy.v2mom === "object"
          ? legacyValue(legacy.v2mom as Record<string, unknown>, "vision")
          : undefined);
      const answers: IntroAnswers = {
        role: legacyValue(legacy, "product_name"),
        customer: legacyValue(legacy, "target_user"),
        win: legacyValue(legacy, "job_statement"),
        friction: legacyValue(legacy, "core_problem"),
      };
      const quotes: IntroQuotes = { ...answers };
      for (const field of Object.keys(answers) as IntroField[]) {
        if (!answers[field]) {
          delete answers[field];
          delete quotes[field];
        }
      }
      saveIntroDraft({
        turn: firstUnansweredTurn(answers),
        answers,
        quotes,
        ...(vision ? { note: vision } : {}),
      });
    } catch {
      /* malformed legacy draft: drop it so boot stays quiet */
    }
  }

  remove(LEGACY_DRAFT_KEY);
  remove(LEGACY_STEP_KEY);
  return true;
}
