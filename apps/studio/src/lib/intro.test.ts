import { beforeEach, describe, expect, it } from "vitest";

import type { StudioBrief } from "../types";
import {
  INTRO_DRAFT_KEY,
  INTRO_TURNS,
  INTRO_TURN_COUNT,
  LEGACY_DRAFT_KEY,
  LEGACY_STEP_KEY,
  MAX_VALUE_LENGTH,
  SUMMARY_INDEX,
  briefFromAnswers,
  clearIntroDraft,
  deriveProduct,
  deriveTeam,
  draftFromBrief,
  evidenceItems,
  firstUnansweredTurn,
  loadIntroDraft,
  migrateLegacyDraft,
  parseIntroReply,
  proposeDefaults,
  saveIntroDraft,
} from "./intro";

beforeEach(() => {
  window.localStorage.clear();
});

describe("the introduction script", () => {
  it("asks in the order a colleague would, each with two illustrations", () => {
    expect(INTRO_TURN_COUNT).toBe(5);
    expect(INTRO_TURNS.map((turn) => turn.id)).toEqual([
      "role",
      "customer",
      "win",
      "friction",
      "evidence",
    ]);
    expect(new Set(INTRO_TURNS.map((turn) => turn.question)).size).toBe(5);
    for (const turn of INTRO_TURNS) {
      expect(turn.examples).toHaveLength(2);
    }
  });

  it("never rejects an empty reply", () => {
    expect(parseIntroReply("role", "   ")).toEqual({ field: "role", value: "", quote: "" });
  });

  it("caps the stored value and keeps the whole sentence as a quote", () => {
    const long = "x".repeat(MAX_VALUE_LENGTH + 40);
    const answer = parseIntroReply("customer", long);
    expect(answer.value).toHaveLength(MAX_VALUE_LENGTH);
    expect(answer.quote).toBe(long);
  });

  it("keeps a three-fact answer whole in its named field", () => {
    const text = "I'm the PM for the deploy tool; the team is four engineers and a designer.";
    const answer = parseIntroReply("role", text);
    expect(answer.field).toBe("role");
    expect(answer.value).toBe(text);
    expect(answer.quote).toBe(text);
  });
});

describe("the defaults the agent proposes", () => {
  it("proposes nothing until there is something to build on", () => {
    expect(proposeDefaults({})).toEqual({});
  });

  it("offers a customer label, a job, and one outcome after their turns", () => {
    expect(
      proposeDefaults({ customer: "The on-call platform engineer at 2am." }),
    ).toEqual({ customerLabel: "on-call platform engineer at 2am" });

    expect(
      proposeDefaults({ win: "Ship a service without hand-copying config." }),
    ).toEqual({ jobStatement: "Ship a service without hand-copying config" });

    const defaults = proposeDefaults({ friction: "A missed key costs a deploy day." });
    expect(defaults.outcomeDraft?.startsWith("Minimize the time it takes to ")).toBe(true);
  });
});

describe("the brief the answers produce", () => {
  const answers = {
    role: "I'm the PM for the deploy tool; the team is four engineers and a designer.",
    customer: "The on-call platform engineer at 2am.",
    win: "Ship a service without hand-copying config.",
    friction: "A missed key costs a deploy day.",
    evidence: "Nine onboarding calls, a very angry ticket, and a Slack thread.",
  };

  it("carries role, team, and evidence beside the fields the brief already had", () => {
    const fields = briefFromAnswers(answers);
    expect(fields.role).toBe(answers.role);
    expect(fields.team).toBe("four engineers and a designer");
    expect(fields.product_name).toBe("deploy tool");
    expect(fields.target_user).toBe(answers.customer);
    expect(fields.job_statement).toBe(answers.win);
    expect(fields.core_problem).toBe(answers.friction);
    expect(fields.evidence_at_hand).toEqual([
      "Nine onboarding calls",
      "a very angry ticket",
      "a Slack thread",
    ]);
  });

  it("derives only what the sentence actually names", () => {
    expect(deriveTeam(undefined)).toBeUndefined();
    expect(deriveTeam("I am a designer.")).toBeUndefined();
    expect(deriveTeam("I am a designer; the team is three engineers.")).toBe("three engineers");
    expect(deriveProduct(undefined)).toBeUndefined();
    expect(deriveProduct("I am a designer.")).toBeUndefined();
    expect(deriveProduct("I'm building a deploy tool.")).toBe("deploy tool");
    expect(deriveProduct("I run support for a billing product.")).toBe("billing product");
  });

  it("turns an evidence sentence into separate items", () => {
    expect(evidenceItems("   ")).toBeUndefined();
    expect(evidenceItems("Nine onboarding calls")).toEqual(["Nine onboarding calls"]);
  });
});

describe("draft storage", () => {
  it("resumes on the same turn after a reload", () => {
    saveIntroDraft({ turn: 2, answers: { role: "PM" }, quotes: { role: "PM" } });
    expect(loadIntroDraft()).toEqual({
      turn: 2,
      answers: { role: "PM" },
      quotes: { role: "PM" },
    });
    clearIntroDraft();
    expect(loadIntroDraft()).toEqual({ turn: 0, answers: {}, quotes: {} });
  });

  it("treats malformed storage as an empty draft", () => {
    window.localStorage.setItem(INTRO_DRAFT_KEY, "{not json");
    expect(loadIntroDraft()).toEqual({ turn: 0, answers: {}, quotes: {} });
  });

  it("keeps the valid answers when the turn is malformed", () => {
    window.localStorage.setItem(
      INTRO_DRAFT_KEY,
      JSON.stringify({
        turn: "later",
        answers: { role: "PM", nope: "x" },
        quotes: { role: "PM" },
      }),
    );
    expect(loadIntroDraft()).toEqual({
      turn: 1,
      answers: { role: "PM" },
      quotes: { role: "PM" },
    });
  });

  it("resumes at the first unanswered turn", () => {
    expect(firstUnansweredTurn({})).toBe(0);
    expect(firstUnansweredTurn({ role: "PM", customer: "Engineers" })).toBe(2);
    expect(
      firstUnansweredTurn({
        role: "PM",
        customer: "Engineers",
        win: "Ship",
        friction: "Drift",
        evidence: "Calls",
      }),
    ).toBe(SUMMARY_INDEX);
  });
});

describe("migration from the five-field draft", () => {
  it("maps the old fields into turns once and keeps the vision as a note", () => {
    window.localStorage.setItem(
      LEGACY_DRAFT_KEY,
      JSON.stringify({
        product_name: "Ambient",
        target_user: "Platform engineers",
        job_statement: "Ship a service",
        core_problem: "Config drift",
        vision: "Zero downtime deploys",
      }),
    );
    window.localStorage.setItem(LEGACY_STEP_KEY, "3");

    expect(migrateLegacyDraft()).toBe(true);

    const draft = loadIntroDraft();
    expect(draft.answers).toEqual({
      role: "Ambient",
      customer: "Platform engineers",
      win: "Ship a service",
      friction: "Config drift",
    });
    expect(draft.quotes.role).toBe("Ambient");
    expect(draft.note).toBe("Zero downtime deploys");
    expect(draft.turn).toBe(4);
    expect(window.localStorage.getItem(LEGACY_DRAFT_KEY)).toBeNull();
    expect(window.localStorage.getItem(LEGACY_STEP_KEY)).toBeNull();

    const before = JSON.stringify(loadIntroDraft());
    expect(migrateLegacyDraft()).toBe(false);
    expect(JSON.stringify(loadIntroDraft())).toBe(before);
  });

  it("does nothing on a boot with no legacy draft", () => {
    expect(migrateLegacyDraft()).toBe(false);
    expect(loadIntroDraft()).toEqual({ turn: 0, answers: {}, quotes: {} });
  });

  it("does not overwrite an introduction already in progress", () => {
    saveIntroDraft({ turn: 3, answers: { role: "Mine" }, quotes: { role: "Mine" } });
    window.localStorage.setItem(LEGACY_DRAFT_KEY, JSON.stringify({ product_name: "Old" }));

    migrateLegacyDraft();

    expect(loadIntroDraft().answers.role).toBe("Mine");
    expect(window.localStorage.getItem(LEGACY_DRAFT_KEY)).toBeNull();
  });
});

describe("editing an existing brief", () => {
  it("opens on the summary with every stored answer in place", () => {
    const brief: StudioBrief = {
      product_name: "Ambient",
      target_user: "Platform engineers",
      job_statement: "Ship a service",
      core_problem: "Config drift",
      role: "PM",
      team: "four engineers",
      evidence_at_hand: ["Nine calls", "a ticket"],
      v2mom: { vision: "Zero downtime deploys" },
    };

    const draft = draftFromBrief(brief);
    expect(draft.turn).toBe(SUMMARY_INDEX);
    expect(draft.answers).toEqual({
      role: "PM",
      customer: "Platform engineers",
      win: "Ship a service",
      friction: "Config drift",
      evidence: "Nine calls; a ticket",
    });
    expect(draft.note).toBe("Zero downtime deploys");
  });
});
