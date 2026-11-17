/**
 * The interview host's wiring (issue #397).
 *
 * One card, one conductor, and the calls it makes: this test drives the card a
 * person sees and asserts the store actions that result, so the seam between
 * the display contract (#396) and the machine is covered without a runtime.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Interview } from "./Interview";
import { MemoryLocalStore } from "../../bff/store/memoryStore";
import type { InterviewPorts } from "./conductor";

function ports() {
  const calls = { job: [] as unknown[], outcome: [] as unknown[], evidence: [] as unknown[] };
  const port: InterviewPorts = {
    createJob: vi.fn(async (payload) => {
      calls.job.push(payload);
      return "job-1";
    }),
    addOutcome: vi.fn(async (payload) => {
      calls.outcome.push(payload);
      return "outcome-1";
    }),
    addEvidence: vi.fn(async (payload) => {
      calls.evidence.push(payload);
    }),
  };
  return { port, calls };
}

async function answerEveryQuestion() {
  fireEvent.change(
    screen.getByRole("textbox", { name: /what job is this market trying to get done/i }),
    { target: { value: "Turn interview notes into one opportunity" } },
  );
  fireEvent.change(screen.getByRole("textbox", { name: /what is the customer trying to get done/i }), {
    target: { value: "Minimize the time it takes to turn notes into a scored outcome" },
  });
  fireEvent.change(screen.getByRole("slider", { name: /how important is this outcome/i }), {
    target: { value: "9" },
  });
  fireEvent.change(screen.getByRole("slider", { name: /how satisfied are they with it today/i }), {
    target: { value: "4" },
  });
  fireEvent.change(screen.getByRole("textbox", { name: /what did you hear that supports this/i }), {
    target: { value: "The PM retypes every quote by hand." },
  });
}

describe("Interview", () => {
  it("turns one card's answers into the records the conductor creates", async () => {
    const { port, calls } = ports();
    const onComplete = vi.fn();
    render(<Interview ports={port} onComplete={onComplete} />);

    await answerEveryQuestion();
    fireEvent.click(screen.getByRole("button", { name: /save answers/i }));

    await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
    expect(calls.job).toHaveLength(1);
    expect(calls.outcome).toHaveLength(1);
    expect(calls.evidence).toHaveLength(1);
    expect(calls.outcome[0]).toMatchObject({ importance: 9, satisfaction: 4 });
    expect(onComplete).toHaveBeenCalledWith({
      jobId: "job-1",
      outcomeIds: ["outcome-1"],
      evidenceCount: 1,
    });
  });

  it("refuses a submit with a required answer missing, creating nothing", async () => {
    const { port, calls } = ports();
    render(<Interview ports={port} />);

    fireEvent.click(screen.getByRole("button", { name: /save answers/i }));

    expect(screen.getByRole("textbox", { name: /what job is this market/i })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(calls.job).toHaveLength(0);
    expect(calls.outcome).toHaveLength(0);
  });

  it("collapses into the record of itself once the answers are saved (#400)", async () => {
    const { port } = ports();
    render(<Interview ports={port} />);

    await answerEveryQuestion();
    fireEvent.click(screen.getByRole("button", { name: /save answers/i }));

    const summary = await screen.findByRole("button", { name: /Answered/ });
    expect(summary).toHaveTextContent("Answered · 5 of 5 · 1 outcome, 1 evidence");
    // The live form is gone; the record of the interview stands in its place.
    expect(screen.queryByRole("button", { name: /save answers/i })).not.toBeInTheDocument();
  });

  it("opens a created record through the focus action", async () => {
    const { port } = ports();
    const onOpenRecord = vi.fn();
    render(<Interview ports={port} onOpenRecord={onOpenRecord} />);

    await answerEveryQuestion();
    fireEvent.click(screen.getByRole("button", { name: /save answers/i }));

    fireEvent.click(await screen.findByRole("button", { name: /Answered/ }));
    fireEvent.click(screen.getByRole("button", { name: "Outcome 1" }));

    expect(onOpenRecord).toHaveBeenCalledWith("outcome-1");
  });

  it("keeps the live card when a write fails, naming what stopped (#400)", async () => {
    const port: InterviewPorts = {
      createJob: vi.fn(async () => "job-1"),
      addOutcome: vi.fn(async () => {
        throw new Error("the store refused it");
      }),
      addEvidence: vi.fn(async () => undefined),
    };
    render(<Interview ports={port} />);

    await answerEveryQuestion();
    fireEvent.click(screen.getByRole("button", { name: /save answers/i }));

    expect(await screen.findByText("Not saved — the store refused it")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save answers/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Answered/ })).not.toBeInTheDocument();
  });
});

describe("Interview — the draft (#402)", () => {
  it("reopens the same question with the same answers after a remount", async () => {
    const { port } = ports();
    const store = new MemoryLocalStore();
    const draft = { store, jobId: "j-1", debounceMs: 0 };

    const first = render(<Interview ports={port} draft={draft} />);
    fireEvent.change(
      screen.getByRole("textbox", { name: /what job is this market trying to get done/i }),
      { target: { value: "Turn interview notes into one opportunity" } },
    );
    fireEvent.change(
      screen.getByRole("textbox", { name: /what is the customer trying to get done/i }),
      { target: { value: "Minimize the time it takes to decide" } },
    );
    await waitFor(async () =>
      expect((await store.listInterviewDrafts("j-1")).length).toBeGreaterThan(0),
    );
    first.unmount();

    // A reload: the same job's draft is read back and the answers are there.
    render(<Interview ports={port} draft={draft} />);
    await waitFor(() =>
      expect(
        screen.getByRole("textbox", { name: /what job is this market trying to get done/i }),
      ).toHaveValue("Turn interview notes into one opportunity"),
    );
    expect(
      screen.getByRole("textbox", { name: /what is the customer trying to get done/i }),
    ).toHaveValue("Minimize the time it takes to decide");
  });

  it("ignores a draft that belongs to another job", async () => {
    const { port } = ports();
    const store = new MemoryLocalStore();
    await store.putInterviewDraft({
      id: "other",
      jobId: "j-2",
      answers: { job: "Another job entirely" },
      index: 2,
      updatedAt: "2026-01-01T00:00:00.000Z",
    });

    render(<Interview ports={port} draft={{ store, jobId: "j-1" }} />);

    await waitFor(() =>
      expect(
        screen.getByRole("textbox", { name: /what job is this market trying to get done/i }),
      ).toHaveValue(""),
    );
  });

  it("leaves no draft behind once the interview is submitted", async () => {
    const { port } = ports();
    const store = new MemoryLocalStore();
    render(<Interview ports={port} draft={{ store, jobId: "j-1", debounceMs: 0 }} />);

    await answerEveryQuestion();
    fireEvent.click(screen.getByRole("button", { name: /save answers/i }));

    await waitFor(async () => expect(await store.listInterviewDrafts("j-1")).toEqual([]));
  });
});
