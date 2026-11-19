/**
 * The interview conductor's rules (issue #397).
 *
 * The machine is pure, so the whole state graph is driven here with no renderer
 * and no network: a happy path, every exit, a refused submit, a partial write,
 * and the double-submit guard. The impure shell is then driven through a plain
 * port object, so a failure is a rejected promise rather than a mock framework.
 */

import { describe, expect, it, vi } from "vitest";

import {
  createConductor,
  firstMissing,
  initialState,
  INTERVIEW_QUESTIONS,
  planFromAnswers,
  reduce,
  type Answers,
  type InterviewPorts,
  type InterviewState,
  type InterviewPlan,
} from "./conductor";

const completeAnswers: Answers = {
  job: "Turn interview notes into one opportunity",
  outcome: "Minimize the time it takes to turn notes into a scored outcome",
  importance: 8.6,
  satisfaction: 4.9,
  evidence: "The PM retypes every quote by hand.",
};

/** Drive the pure machine through the events that lead to a submittable card. */
function asked(): InterviewState {
  return reduce(initialState(), { type: "ask", questions: INTERVIEW_QUESTIONS });
}

function collecting(answers: Answers = completeAnswers): InterviewState {
  let state = reduce(asked(), { type: "begin" });
  for (const [questionId, value] of Object.entries(answers)) {
    state = reduce(state, { type: "answer", questionId, value });
  }
  return state;
}

/** A port object whose three calls are recorded, and can be made to reject. */
function ports(options: { failOutcomeIndex?: number; failEvidence?: boolean } = {}) {
  const calls: { job: unknown[]; outcome: unknown[]; evidence: unknown[] } = {
    job: [],
    outcome: [],
    evidence: [],
  };
  let outcomeSeq = 0;
  const port: InterviewPorts = {
    createJob: vi.fn(async (payload) => {
      calls.job.push(payload);
      return "job-1";
    }),
    addOutcome: vi.fn(async (payload) => {
      const index = calls.outcome.length;
      calls.outcome.push(payload);
      if (options.failOutcomeIndex === index) {
        throw new Error("the second outcome was refused");
      }
      outcomeSeq += 1;
      return `outcome-${outcomeSeq}`;
    }),
    addEvidence: vi.fn(async (payload) => {
      calls.evidence.push(payload);
      if (options.failEvidence) {
        throw new Error("the evidence store is full");
      }
    }),
  };
  return { port, calls };
}

/** Let the shell's unawaited submit promise settle. */
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("interview conductor — the machine", () => {
  it("drives the full happy path without a renderer", () => {
    let state = reduce(initialState(), { type: "ask", questions: INTERVIEW_QUESTIONS });
    expect(state.status).toBe("asking");

    state = reduce(state, { type: "begin" });
    expect(state.status).toBe("collecting");
    expect(state.index).toBe(0);

    state = reduce(state, { type: "answer", questionId: "job", value: "A job" });
    state = reduce(state, { type: "next" });
    expect(state.index).toBe(1);
    expect(state.answers.job).toBe("A job");

    state = { ...state, answers: completeAnswers };
    state = reduce(state, { type: "submit" });
    expect(state.status).toBe("submitting");
    expect(state.invalid).toBeNull();

    state = reduce(state, {
      type: "submitted",
      created: { jobId: "job-1", outcomeIds: ["o-1"], evidenceCount: 1 },
    });
    expect(state.status).toBe("done");
    expect(state.created.jobId).toBe("job-1");
  });

  it("reaches every exit without a mock", () => {
    const abandoned = reduce(collecting(), { type: "abandon" });
    expect(abandoned.status).toBe("abandoned");

    const failed = reduce(collecting(), {
      type: "submit",
    });
    const reported = reduce(failed, {
      type: "failed",
      failure: { step: "outcome", index: 0, message: "nope" },
      created: { jobId: "job-1", outcomeIds: [], evidenceCount: 0 },
    });
    expect(reported.status).toBe("failed");
    expect(reported.failure?.step).toBe("outcome");
  });

  it("keeps a required empty answer in collecting, naming the question", () => {
    const state = reduce(collecting({ job: "A job", outcome: "  ", importance: 5, satisfaction: 5 }), {
      type: "submit",
    });
    expect(state.status).toBe("collecting");
    expect(state.invalid).toBe("outcome");
    expect(firstMissing(state.questions, state.answers)).toBe("outcome");
  });

  it("clears the refusal as soon as the blocked question is answered", () => {
    let state = reduce(collecting({ job: "A job", importance: 5, satisfaction: 5 }), {
      type: "submit",
    });
    expect(state.invalid).toBe("outcome");
    state = reduce(state, { type: "answer", questionId: "outcome", value: "Minimize the time" });
    expect(state.invalid).toBeNull();
  });

  it("ignores a second submit while a submit is in flight", () => {
    const submitting = reduce(collecting(), { type: "submit" });
    expect(reduce(submitting, { type: "submit" })).toBe(submitting);
  });

  it("ignores answers once the interview has left collecting", () => {
    const submitting = reduce(collecting(), { type: "submit" });
    expect(reduce(submitting, { type: "answer", questionId: "job", value: "changed" })).toBe(
      submitting,
    );
  });
});

describe("interview conductor — the plan", () => {
  it("reads a job, one outcome, and the evidence that supports it", () => {
    const plan = planFromAnswers(completeAnswers);
    expect(plan.job.name).toBe("Turn interview notes into one opportunity");
    expect(plan.outcomes).toEqual([
      {
        statement: "Minimize the time it takes to turn notes into a scored outcome",
        importance: 8.6,
        satisfaction: 4.9,
      },
    ]);
    expect(plan.evidence).toHaveLength(1);
    expect(plan.evidence[0].content).toBe("The PM retypes every quote by hand.");
    expect(plan.evidence[0].outcomeIndex).toBe(0);
  });

  it("writes no evidence for an unanswered optional question", () => {
    const plan = planFromAnswers({ ...completeAnswers, evidence: "   " });
    expect(plan.evidence).toEqual([]);
  });
});

describe("interview conductor — the shell", () => {
  it("creates the job, then the outcome, then the evidence, in order", async () => {
    const { port, calls } = ports();
    const conductor = createConductor({ ports: port, plan: planFromAnswers });

    conductor.send({ type: "ask", questions: INTERVIEW_QUESTIONS });
    conductor.send({ type: "begin" });
    for (const [questionId, value] of Object.entries(completeAnswers)) {
      conductor.send({ type: "answer", questionId, value });
    }
    conductor.send({ type: "submit" });
    await settle();

    expect(calls.job).toHaveLength(1);
    expect(calls.outcome).toHaveLength(1);
    expect(calls.evidence).toHaveLength(1);
    // The evidence is attached to the outcome that was created before it.
    expect(calls.evidence[0]).toMatchObject({ job_id: "job-1", outcome_id: "outcome-1" });
    expect(conductor.getState().status).toBe("done");
    expect(conductor.getState().created).toEqual({
      jobId: "job-1",
      outcomeIds: ["outcome-1"],
      evidenceCount: 1,
    });
  });

  it("creates nothing when a required answer is missing", () => {
    const { port, calls } = ports();
    const conductor = createConductor({ ports: port, plan: planFromAnswers });
    conductor.send({ type: "ask", questions: INTERVIEW_QUESTIONS });
    conductor.send({ type: "begin" });
    conductor.send({ type: "answer", questionId: "job", value: "A job" });
    conductor.send({ type: "submit" });

    expect(calls.job).toHaveLength(0);
    expect(calls.outcome).toHaveLength(0);
    expect(conductor.getState().status).toBe("collecting");
    expect(conductor.getState().invalid).toBe("outcome");
  });

  it("keeps the first outcome when the second is refused, and names it", async () => {
    const { port, calls } = ports({ failOutcomeIndex: 1 });
    const twoOutcomes: InterviewPlan = {
      job: { name: "A job" },
      outcomes: [
        { statement: "First outcome", importance: 8, satisfaction: 4 },
        { statement: "Second outcome", importance: 6, satisfaction: 6 },
      ],
      evidence: [],
    };
    const conductor = createConductor({ ports: port, plan: () => twoOutcomes });

    conductor.send({ type: "ask", questions: INTERVIEW_QUESTIONS });
    conductor.send({ type: "begin" });
    for (const [questionId, value] of Object.entries(completeAnswers)) {
      conductor.send({ type: "answer", questionId, value });
    }
    conductor.send({ type: "submit" });
    await settle();

    expect(calls.outcome).toHaveLength(2);
    const state = conductor.getState();
    expect(state.status).toBe("failed");
    // The first outcome survived the second one's refusal.
    expect(state.created.outcomeIds).toEqual(["outcome-1"]);
    expect(state.failure).toEqual({
      step: "outcome",
      index: 1,
      message: "the second outcome was refused",
    });
  });

  it("never asks the store to create the same record twice", async () => {
    const { port, calls } = ports();
    const conductor = createConductor({ ports: port, plan: planFromAnswers });
    conductor.send({ type: "ask", questions: INTERVIEW_QUESTIONS });
    conductor.send({ type: "begin" });
    for (const [questionId, value] of Object.entries(completeAnswers)) {
      conductor.send({ type: "answer", questionId, value });
    }
    conductor.send({ type: "submit" });
    conductor.send({ type: "submit" });
    await settle();

    expect(calls.job).toHaveLength(1);
    expect(calls.outcome).toHaveLength(1);
    expect(calls.evidence).toHaveLength(1);
  });

  it("reports the step and index when the evidence write fails", async () => {
    const { port } = ports({ failEvidence: true });
    const conductor = createConductor({ ports: port, plan: planFromAnswers });
    conductor.send({ type: "ask", questions: INTERVIEW_QUESTIONS });
    conductor.send({ type: "begin" });
    for (const [questionId, value] of Object.entries(completeAnswers)) {
      conductor.send({ type: "answer", questionId, value });
    }
    conductor.send({ type: "submit" });
    await settle();

    const state = conductor.getState();
    expect(state.status).toBe("failed");
    expect(state.failure).toMatchObject({ step: "evidence", index: 0 });
    expect(state.created.jobId).toBe("job-1");
  });

  it("hands the card's answers to the conductor and the records back", async () => {
    const { port, calls } = ports();
    const states: InterviewState[] = [];
    const conductor = createConductor({
      ports: port,
      plan: planFromAnswers,
      onState: (state) => states.push(state),
    });
    const unsubscribe = conductor.subscribe(() => undefined);

    // The wiring: the card reports answers, the conductor creates the records.
    conductor.send({ type: "ask", questions: INTERVIEW_QUESTIONS });
    conductor.send({ type: "begin" });
    for (const [questionId, value] of Object.entries(completeAnswers)) {
      conductor.send({ type: "answer", questionId, value });
    }
    conductor.send({ type: "submit" });
    await settle();

    expect(calls.outcome[0]).toMatchObject({
      statement: completeAnswers.outcome,
      importance: 8.6,
      satisfaction: 4.9,
    });
    expect(states.at(-1)?.status).toBe("done");
    unsubscribe();
  });
});
