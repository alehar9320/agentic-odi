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
});
