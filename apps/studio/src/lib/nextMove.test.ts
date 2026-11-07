import { describe, expect, it } from "vitest";

import { JOB_STAGES } from "../domain/jobStages";
import type { ChatMessage, Signal, StudioBrief } from "../types";
import {
  lastAssistantTurn,
  recommendNextMove,
  type NextMoveCanvas,
  type NextMoveInput,
} from "./nextMove";

const BRIEF: StudioBrief = {
  product_name: "Ambient",
  target_user: "platform engineers",
  job_statement: "Get a service from commit to production",
  core_problem: "A missed config key costs hours",
  job_id: "job-1",
};

const TURN = { messageId: "turn-1", toolNames: ["add_outcome"], touchedOutcomeIds: [] };

function canvas(overrides: Partial<NextMoveCanvas> = {}): NextMoveCanvas {
  return { jobs: [], steps: [], outcomes: [], evidence: [], ...overrides };
}

function input(overrides: Partial<NextMoveInput> = {}): NextMoveInput {
  return {
    brief: BRIEF,
    lastTurn: TURN,
    canvas: canvas(),
    signals: [],
    theses: [],
    dismissedId: null,
    modelAvailable: true,
    ...overrides,
  };
}

function completeSteps(): NextMoveCanvas["steps"] {
  return JOB_STAGES.map((stage, index) => ({
    id: `step-${index}`,
    job_id: "job-1",
    name: stage.name,
    order: index + 1,
    stage: stage.id,
  }));
}

function scored(overrides: Record<string, unknown> = {}) {
  return {
    id: "o-1",
    job_id: "job-1",
    statement: "Minimize the time it takes to reconcile invoices when the month closes",
    importance: 8.6,
    satisfaction: 4.9,
    opportunity_score: 12.3,
    ...overrides,
  };
}

function urgentSignal(overrides: Partial<Signal> = {}): Signal {
  return {
    id: "s-1",
    kind: "opportunity_crossed",
    title: "Invoices crossed the threshold",
    severity: "urgent",
    created_at: "2026-10-31T09:00:00Z",
    fingerprint: "s-1",
    suppressed: false,
    read_at: null,
    dismissed_at: null,
    ...overrides,
  };
}

describe("recommendNextMove", () => {
  it("says nothing before the first assistant turn", () => {
    expect(recommendNextMove(input({ lastTurn: null }))).toBeNull();
  });

  it("asks for context when there is no brief", () => {
    const move = recommendNextMove(input({ brief: null }));
    expect(move?.kind).toBe("context");
    expect(move?.action).toEqual({ label: "Add context", kind: "setup" });
    expect(move?.rationale).not.toBe("");
    expect(move?.expectedEvidence).not.toBe("");
  });

  it("asks for evidence when the turn scored an outcome with none linked", () => {
    const move = recommendNextMove(
      input({ canvas: canvas({ outcomes: [scored()] }) }),
    );
    expect(move?.kind).toBe("evidence");
    expect(move?.move).toBe("Ask two platform engineers how they do this today.");
    expect(move?.rationale).toContain("12.3");
    expect(move?.action.kind).toBe("prompt");
  });

  it("joins linked evidence on outcome_id and suppresses the evidence move", () => {
    const move = recommendNextMove(
      input({
        canvas: canvas({
          outcomes: [scored()],
          evidence: [{ id: "e-1", outcome_id: "o-1" }],
        }),
      }),
    );
    expect(move?.kind).not.toBe("evidence");
  });

  it("does not count an outcome.evidence field that the API never sends", () => {
    const move = recommendNextMove(
      input({
        canvas: canvas({ outcomes: [scored({ evidence: "a sentence" })] }),
        lastTurn: { ...TURN, toolNames: [] },
      }),
    );
    // The field alone is not a record, and no scoring tool ran, so no evidence move.
    expect(move?.kind).not.toBe("evidence");
  });

  it("uses the capture panel instead of a chat prompt when no model is reachable", () => {
    const move = recommendNextMove(
      input({ canvas: canvas({ outcomes: [scored()] }), modelAvailable: false }),
    );
    expect(move?.kind).toBe("evidence");
    expect(move?.action).toEqual({ label: "Open capture", kind: "panel", panel: "capture" });
  });

  it("puts an urgent unread signal ahead of map hygiene", () => {
    const move = recommendNextMove(input({ signals: [urgentSignal()] }));
    expect(move?.kind).toBe("signal");
    expect(move?.action).toEqual({ label: "Open Catch Up", kind: "panel", panel: "catchup" });
  });

  it("ignores read, dismissed, and suppressed signals", () => {
    const move = recommendNextMove(
      input({
        signals: [
          urgentSignal({ id: "read", read_at: "2026-10-31T10:00:00Z" }),
          urgentSignal({ id: "dismissed", dismissed_at: "2026-10-31T10:00:00Z" }),
          urgentSignal({ id: "suppressed", suppressed: true }),
        ],
      }),
    );
    expect(move?.kind).not.toBe("signal");
  });

  it("names the first missing stage of the active job", () => {
    const move = recommendNextMove(
      input({
        canvas: canvas({ jobs: [{ id: "job-1", name: "Invoice close" }] }),
      }),
    );
    expect(move?.kind).toBe("map");
    expect(move?.move).toBe("Map the define stage of Invoice close.");
    expect(move?.rationale).toContain("0 of 8");
  });

  it("moves on once every stage is covered", () => {
    const move = recommendNextMove(
      input({
        canvas: canvas({
          jobs: [{ id: "job-1", name: "Invoice close" }],
          steps: completeSteps(),
        }),
      }),
    );
    expect(move?.kind).not.toBe("map");
  });

  it("asks to pressure-test an underserved outcome with no thesis", () => {
    const move = recommendNextMove(
      input({
        canvas: canvas({
          jobs: [{ id: "job-1", name: "Invoice close" }],
          steps: completeSteps(),
          outcomes: [scored()],
          evidence: [{ id: "e-1", outcome_id: "o-1" }],
        }),
      }),
    );
    expect(move?.kind).toBe("decide");
    expect(move?.rationale).toContain("12.3");
    expect(move?.action.kind).toBe("prompt");
  });

  it("stops asking once a thesis records the decision", () => {
    const move = recommendNextMove(
      input({
        canvas: canvas({
          jobs: [{ id: "job-1", name: "Invoice close" }],
          steps: completeSteps(),
          outcomes: [scored()],
          evidence: [{ id: "e-1", outcome_id: "o-1" }],
        }),
        theses: [
          {
            id: "t-1",
            outcome_id: "o-1",
            statement: "Chase it",
            importance: 8.6,
            satisfaction: 4.9,
            opportunity_score: 12.3,
            rationale: "Evidence supports it",
            created_at: "2026-10-31T10:00:00Z",
          },
        ],
      }),
    );
    expect(move?.kind).toBe("score");
    expect(move?.action).toEqual({ label: "Open capture", kind: "panel", panel: "capture" });
  });

  it("falls back to capturing one outcome on an empty canvas", () => {
    const move = recommendNextMove(
      input({ canvas: canvas({ jobs: [{ id: "job-1", name: "Invoice close" }], steps: completeSteps() }) }),
    );
    expect(move?.kind).toBe("score");
    expect(move?.move).toBe("Capture one outcome by hand.");
  });

  it("labels sample data and never claims research provenance", () => {
    const move = recommendNextMove(
      input({
        canvas: canvas({
          provenance: {
            kind: "seed",
            reason: "sample",
            generated_at: "2026-10-31T10:00:00Z",
            record_counts: { jobs: 1, steps: 0, outcomes: 1, evidence: 0 },
          },
        }),
      }),
    );
    expect(move?.rationale.startsWith("Sample data: ")).toBe(true);
  });

  it("keeps one id per move and turn, and a new id for a new turn", () => {
    const move = recommendNextMove(input({ canvas: canvas({ outcomes: [scored()] }) }));
    const again = recommendNextMove(input({ canvas: canvas({ outcomes: [scored()] }) }));
    const nextTurn = recommendNextMove(
      input({
        canvas: canvas({ outcomes: [scored()] }),
        lastTurn: { ...TURN, messageId: "turn-2" },
      }),
    );
    expect(move?.id).toBe(again?.id);
    expect(nextTurn?.id).not.toBe(move?.id);
  });
});

describe("lastAssistantTurn", () => {
  it("finds the newest assistant turn and the tools it called", () => {
    const messages: ChatMessage[] = [
      { id: "u-1", parentId: null, role: "user", content: "score this" },
      {
        id: "a-1",
        parentId: "u-1",
        role: "assistant",
        content: "done",
        parts: [{ kind: "tool", id: "t-1", name: "add_outcome", status: "ok" }],
      },
      { id: "u-2", parentId: "a-1", role: "user", content: "and this" },
    ];
    expect(lastAssistantTurn(messages)).toEqual({
      messageId: "a-1",
      toolNames: ["add_outcome"],
      touchedOutcomeIds: [],
    });
  });

  it("returns null when the studio has not replied", () => {
    const messages: ChatMessage[] = [
      { id: "u-1", parentId: null, role: "user", content: "hello" },
    ];
    expect(lastAssistantTurn(messages)).toBeNull();
  });
});

