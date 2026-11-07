import { describe, expect, it } from "vitest";

import {
  CAPTURE_PROMPT,
  CHURN_PROMPT,
  FIND_PROMPT,
  NOTES_PROMPT,
  PRESSURE_TEST_PROMPT,
  ROADMAP_PROMPT,
  suggestionsFor,
  type StudioSuggestion,
} from "./StudioRuntime";

/**
 * The copy lint for the first-run starters (#316).
 *
 * These three cards are the product's first sentence, so their rules are
 * checked rather than trusted: each names a situation the person is in, opens
 * with the material they bring, promises an artifact instead of a
 * transformation, and never presents a number as a finding of ours.
 */

const EMPTY_CANVAS = suggestionsFor({ jobCount: 0, outcomeCount: 0 });

function cardAt(index: number): StudioSuggestion {
  const card = EMPTY_CANVAS[index];
  if (!card) {
    throw new Error(`starter ${index} is missing from the empty canvas`);
  }
  return card;
}

/** The three first-run cards, their exported prompts, and the object each names. */
const STARTERS = [
  { card: cardAt(0), prompt: NOTES_PROMPT, material: "notes" },
  { card: cardAt(1), prompt: CHURN_PROMPT, material: "churn" },
  { card: cardAt(2), prompt: ROADMAP_PROMPT, material: "roadmap" },
];

/**
 * A prompt must open with what the person brings. Card 2's verbatim prompt
 * opens with their own subject ("Our churn moved"), which names the material as
 * plainly as "I have"; the list stays explicit so a new card cannot slip in
 * with a benefit-first or interview-first opener.
 */
const OPENS_WITH_MATERIAL = [/^I have\b/, /^I've inherited\b/, /^I need\b/, /^Our churn\b/];

/** Quality adjectives the cards must earn with a concrete object instead. */
const BANNED_ADJECTIVES = [
  "powerful",
  "seamless",
  "defensible",
  "unlock",
  "insights",
];

/** Our nouns may appear in a title, but never as its only concrete noun. */
const OUR_NOUNS = ["opportunity", "bet", "job"];

/** Titles the first run retired. */
const RETIRED_TITLES = [
  "sharpen an opportunity",
  "find the next opportunity",
  "name the job",
];

/** Literals that would read as a claim about the person's own data. */
const CLAIM_LITERALS = [
  /[€£$]/,
  /\b\d+(\.\d+)?\s?%/,
  /\bpercent\b/i,
  /\b(19|20)\d{2}\b/,
  /\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/i,
  /\b(january|february|march|april|may|june|july|august|september|october|november|december)\b/i,
];

/** Vendors the copy must never name as a customer. */
const COMPANY_NAMES = [
  "salesforce",
  "hubspot",
  "gong",
  "zendesk",
  "jira",
  "snowflake",
  "figma",
  "notion",
  "slack",
  "stripe",
];

/** Promises the existing tools cannot keep. */
const UNAVAILABLE_PROMISES = [
  "simulate",
  "simulation",
  "benchmark",
  "forecast",
  "market size",
  "market estimate",
  "projected revenue",
  "roi",
];

/** Every string a first-run card puts in front of a person. */
function copyOf(): string[] {
  return EMPTY_CANVAS.flatMap((card) => [card.title, card.label, card.prompt, card.artifact ?? ""]);
}

describe("first-run starter copy", () => {
  it("offers the three situations in order", () => {
    expect(EMPTY_CANVAS.map((card) => card.title)).toEqual([
      "Turn 40 interview notes into one bet",
      "Find what the churn spike is telling you",
      "Inherit a roadmap without inheriting its assumptions",
    ]);
  });

  it("sends each card's exported prompt verbatim", () => {
    for (const { card, prompt } of STARTERS) {
      expect(card.prompt, card.title).toBe(prompt);
    }
  });

  it("retires the ontology-first titles from the first run", () => {
    const titles = EMPTY_CANVAS.map((card) => card.title).join("\n").toLowerCase();

    for (const retired of RETIRED_TITLES) {
      expect(titles).not.toContain(retired);
    }
  });

  it("opens every prompt with the material the person brought", () => {
    for (const { card } of STARTERS) {
      expect(
        OPENS_WITH_MATERIAL.some((opener) => opener.test(card.prompt)),
        `${card.title} opens with a request instead of the person's material`,
      ).toBe(true);
    }
  });

  it("keeps a concrete object in every title", () => {
    for (const { card, material } of STARTERS) {
      const title = card.title.toLowerCase();
      expect(title).toContain(material);

      // Strip our nouns: the object the person can see on their desk survives.
      const withoutOurNouns = OUR_NOUNS.reduce(
        (rest, noun) => rest.replace(new RegExp(`\\b${noun}\\b`, "g"), ""),
        title,
      );
      expect(withoutOurNouns, `${card.title} leans on our nouns alone`).toContain(material);
    }
  });

  it("promises an artifact in the subtitle and the artifact line", () => {
    for (const { card } of STARTERS) {
      expect(card.label, card.title).not.toBe("");
      expect(card.artifact, card.title).toBeTruthy();
      expect(card.artifact).not.toBe("");
    }
  });

  it("uses none of the banned quality adjectives in a title or subtitle", () => {
    for (const { card } of STARTERS) {
      const short = `${card.title} ${card.label}`.toLowerCase();
      for (const adjective of BANNED_ADJECTIVES) {
        expect(short, `${card.title}: "${adjective}"`).not.toContain(adjective);
      }
    }
  });

  it("names the shape of the artifact without a result, price, or date", () => {
    for (const { card } of STARTERS) {
      for (const literal of CLAIM_LITERALS) {
        expect(card.artifact, `${card.title}: ${String(literal)}`).not.toMatch(literal);
      }
    }
  });

  it("keeps the interview count as the person's own example and no other numeral", () => {
    // "40 interview notes" is the material a person brings, quoted as an
    // example. Every other number in the copy has to be removed or listed here
    // deliberately, so the cards never present a figure as our finding.
    const ALLOWED_NUMERALS = ["40"];

    const numerals = (copyOf().join(" ").match(/\b\d+\b/g) ?? []);
    expect([...new Set(numerals)]).toEqual(ALLOWED_NUMERALS);
  });

  it("names no company, metric, or price as the person's own work", () => {
    const copy = copyOf().join(" ").toLowerCase();

    for (const company of COMPANY_NAMES) {
      expect(copy, company).not.toContain(company);
    }
    for (const literal of CLAIM_LITERALS) {
      expect(copy).not.toMatch(literal);
    }
  });

  it("promises nothing the studio's tools cannot do", () => {
    for (const { card } of STARTERS) {
      for (const promise of UNAVAILABLE_PROMISES) {
        expect(card.prompt.toLowerCase(), `${card.title}: "${promise}"`).not.toContain(promise);
      }
    }
  });

  it("leaves the returning-user swaps untouched", () => {
    // Selection beyond the existing count swaps is out of scope for #316; this
    // pins the two swaps so a copy pass cannot quietly change them.
    const withOutcomes = suggestionsFor({ jobCount: 0, outcomeCount: 3 });
    expect(withOutcomes[1]?.prompt).toBe(PRESSURE_TEST_PROMPT);

    const withJobs = suggestionsFor({ jobCount: 2, outcomeCount: 0 });
    expect(withJobs[1]?.prompt).toBe(FIND_PROMPT);
    expect(withJobs[2]?.prompt).toBe(CAPTURE_PROMPT);
  });
});
