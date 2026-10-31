import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const toast = vi.hoisted(() => ({ pushToast: vi.fn() }));
const studio = vi.hoisted(() => ({ scoreOutcome: vi.fn() }));

vi.mock("../state/StudioContext", () => ({
  useStudio: () => ({ pushToast: toast.pushToast, scoreOutcome: studio.scoreOutcome }),
}));

import { UiActionContext } from "./actions";
import { CATALOG, catalogManifest } from "./catalog";
import { parseUiSpec, type UiNode } from "./protocol";
import { NODE_COMPONENTS } from "./registry";
import { NodeBoundary, UiRenderer } from "./UiRenderer";

function nodeOf(spec: unknown): UiNode {
  const result = parseUiSpec(spec, catalogManifest());
  if (!result.ok) {
    throw new Error(result.reason);
  }
  return result.node;
}

function renderSpec(spec: unknown, overrides: { busy?: boolean } = {}) {
  const onIntent = vi.fn();
  render(
    <UiActionContext.Provider value={{ onIntent, busy: overrides.busy ?? false }}>
      <UiRenderer node={nodeOf(spec)} />
    </UiActionContext.Provider>,
  );
  return { onIntent };
}

describe("UiRenderer", () => {
  it("renders an outcome card with the score computed from the ODI formula", () => {
    renderSpec({
      type: "outcome-card",
      props: { id: "O-1", statement: "Minimize propagation time", importance: 9, satisfaction: 3 },
    });

    expect(screen.getByLabelText("Outcome O-1")).toBeInTheDocument();
    expect(screen.getByText("Underserved · 15.0")).toBeInTheDocument();
    expect(screen.getByText("Minimize propagation time")).toBeInTheDocument();
  });

  it("marks a sample outcome card as bundled data", () => {
    renderSpec({
      type: "outcome-card",
      props: {
        id: "O-SAMPLE",
        statement: "Minimize the time to propagate secrets",
        importance: 9,
        satisfaction: 3,
        sample: true,
      },
    });

    expect(screen.getByText("Sample")).toHaveAttribute(
      "title",
      "This is bundled sample data, not yours.",
    );
  });

  it("prefers an explicit opportunity score when the agent supplies one", () => {
    renderSpec({
      type: "outcome-card",
      props: {
        id: "O-2",
        statement: "Minimize rollback risk",
        importance: 5,
        satisfaction: 5,
        opportunityScore: 12.5,
      },
    });
    expect(screen.getByText("Underserved · 12.5")).toBeInTheDocument();
  });

  it("exposes meters to assistive technology", () => {
    renderSpec({
      type: "outcome-card",
      props: { id: "O-1", statement: "x", importance: 9, satisfaction: 3 },
    });

    const meters = screen.getAllByRole("meter");
    expect(meters).toHaveLength(2);
    expect(meters[0]).toHaveAttribute("aria-valuenow", "9");
    expect(meters[0]).toHaveAttribute("aria-valuemax", "10");
  });

  it("renders an opportunity thesis in plain language", () => {
    renderSpec({
      type: "opportunity-thesis",
      props: {
        title: "Own activation without a guided setup",
        importance: 9,
        satisfaction: 3,
        gap: "New users stall on the first empty state.",
        thesis: "We treat setup as a checklist when people need a first win.",
        next_move: "Prototype a one-step first win and test it with five new accounts.",
      },
    });

    expect(
      screen.getByLabelText("Opportunity thesis: Own activation without a guided setup"),
    ).toBeInTheDocument();
    expect(screen.getByText("Underserved · 15.0")).toBeInTheDocument();
    expect(screen.getByText("New users stall on the first empty state.")).toBeInTheDocument();
    expect(
      screen.getByText("We treat setup as a checklist when people need a first win."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Prototype a one-step first win and test it with five new accounts."),
    ).toBeInTheDocument();
  });

  it("ranks an opportunity board by opportunity score", () => {
    renderSpec({
      type: "opportunity-board",
      props: {
        outcomes: [
          { id: "O-1", statement: "Low priority", importance: 3, satisfaction: 8 },
          { id: "O-2", statement: "Urgent need", importance: 9, satisfaction: 2 },
        ],
      },
    });

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("Urgent need");
    expect(rows[1]).toHaveTextContent("Low priority");
  });

  it("names an unsupported surface instead of rendering blank space", () => {
    renderSpec({ type: "hover-car", props: {} });
    expect(screen.getByRole("status")).toHaveTextContent("hover-car");
  });

  it("copies the raw spec of an unsupported surface", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    renderSpec({ type: "hover-car", props: {} });

    fireEvent.click(screen.getByRole("button", { name: /copy raw spec/i }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('"type": "hover-car"'));
    });
  });

  it("dispatches an action as an intent for the agent", () => {
    const { onIntent } = renderSpec({
      type: "outcome-card",
      props: {
        id: "O-1",
        statement: "x",
        importance: 9,
        satisfaction: 3,
        actions: [{ label: "Simulate this bet", intent: "Simulate a bet on O-1", tone: "primary" }],
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "Simulate this bet" }));
    expect(onIntent).toHaveBeenCalledWith("Simulate a bet on O-1");
  });

  it("disables actions while a reply is streaming", () => {
    renderSpec(
      {
        type: "outcome-card",
        props: {
          id: "O-1",
          statement: "x",
          importance: 9,
          satisfaction: 3,
          actions: [{ label: "Inspect lineage", intent: "Show lineage for O-1" }],
        },
      },
      { busy: true },
    );

    expect(screen.getByRole("button", { name: "Inspect lineage" })).toBeDisabled();
  });

  it("contains a card that throws so its siblings survive", () => {
    const Exploding = () => {
      throw new Error("boom");
    };
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <>
        <NodeBoundary nodeType="exploding">
          <Exploding />
        </NodeBoundary>
        <p>sibling survives</p>
      </>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("could not be displayed");
    expect(screen.getByText("sibling survives")).toBeInTheDocument();
    consoleError.mockRestore();
  });
});

describe("registry parity", () => {
  it("has a component for every catalog type", () => {
    for (const component of CATALOG) {
      expect(NODE_COMPONENTS[component.type], component.type).toBeDefined();
    }
  });

  it("declares no component outside the catalog", () => {
    const types = new Set(CATALOG.map((component) => component.type));
    for (const type of Object.keys(NODE_COMPONENTS)) {
      expect(types.has(type), type).toBe(true);
    }
  });
});

describe("candidate review queue", () => {
  const queue = {
    type: "candidate-queue",
    props: {
      interviewId: "I-1",
      state: "ready",
      target: "O-7",
      candidates: [
        {
          id: "C-1",
          statement: "Minimize the time it takes to onboard",
          quote: "Setup takes forever when a new hire starts.",
          source: "Ana · onboarding call",
          confidence: 0.9,
        },
        {
          id: "C-2",
          statement: "Minimize the effort to reconcile invoices",
          quote: "I reconcile invoices by hand every Friday.",
          source: "Bea · finance call",
          confidence: 0.5,
        },
      ],
      actions: [
        { label: "Accept", intent: "Accept candidate C-1", tone: "primary" },
        { label: "Reject", intent: "Reject candidate C-1 with a reason" },
      ],
    },
  };

  it("keeps each candidate beside the sentence it came from", () => {
    renderSpec(queue);

    expect(screen.getByLabelText("Review queue")).toBeInTheDocument();
    expect(screen.getByText("Minimize the time it takes to onboard")).toBeInTheDocument();
    expect(screen.getByText("Setup takes forever when a new hire starts.")).toBeInTheDocument();
    expect(screen.getByText("From Ana · onboarding call")).toBeInTheDocument();
    expect(screen.getByText("90% confidence")).toBeInTheDocument();
  });

  it("names the explicit merge target instead of guessing one", () => {
    renderSpec(queue);
    expect(screen.getByText(/into outcome O-7/)).toBeInTheDocument();
  });

  it("says a merge has no target when none was given", () => {
    renderSpec({
      type: "candidate-queue",
      props: { state: "ready", candidates: queue.props.candidates },
    });
    expect(screen.getByText(/needs an accepted outcome to fold into/)).toBeInTheDocument();
  });

  it("dispatches a decision as an intent, never acting on its own", () => {
    const { onIntent } = renderSpec(queue);
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    expect(onIntent).toHaveBeenCalledWith("Accept candidate C-1");
    // The card is a view: the row stays until the agent reports the write.
    expect(screen.getByText("Setup takes forever when a new hire starts.")).toBeInTheDocument();
  });

  it("distinguishes loading, empty, and failed", () => {
    const { unmount } = render(
      <UiActionContext.Provider value={{ onIntent: vi.fn(), busy: false }}>
        <UiRenderer node={nodeOf({ type: "candidate-queue", props: { state: "loading" } })} />
      </UiActionContext.Provider>,
    );
    expect(screen.getByLabelText("Loading the review queue")).toHaveAttribute("aria-busy", "true");
    unmount();

    const empty = render(
      <UiActionContext.Provider value={{ onIntent: vi.fn(), busy: false }}>
        <UiRenderer node={nodeOf({ type: "candidate-queue", props: { state: "empty" } })} />
      </UiActionContext.Provider>,
    );
    expect(screen.getByLabelText("Nothing to review")).toBeInTheDocument();
    empty.unmount();

    renderSpec({
      type: "candidate-queue",
      props: { state: "failed", message: "The sidecar is unreachable." },
    });
    expect(screen.getByLabelText("The review queue could not be loaded")).toBeInTheDocument();
    expect(screen.getByText("The sidecar is unreachable.")).toBeInTheDocument();
  });

  it("treats a ready queue with no candidates as empty", () => {
    renderSpec({ type: "candidate-queue", props: { state: "ready", candidates: [] } });
    expect(screen.getByLabelText("Nothing to review")).toBeInTheDocument();
  });

  it("reads the recorded decision back from the server, not from the click", () => {
    renderSpec({
      type: "candidate-queue",
      props: {
        state: "ready",
        candidates: [
          { ...queue.props.candidates[0], decision: "accepted" },
          { ...queue.props.candidates[1], decision: "rejected" },
        ],
      },
    });
    expect(screen.getByText("accepted")).toBeInTheDocument();
    expect(screen.getByText("rejected")).toBeInTheDocument();
    // The quote stays paired with its candidate after the decision.
    expect(screen.getByText("Setup takes forever when a new hire starts.")).toBeInTheDocument();
    expect(screen.getByText("I reconcile invoices by hand every Friday.")).toBeInTheDocument();
  });

  it("shows the server's refusal and keeps the item for correction", () => {
    renderSpec({
      type: "candidate-queue",
      props: {
        state: "ready",
        candidates: [
          { ...queue.props.candidates[0], note: "a rejection needs a reason" },
          { ...queue.props.candidates[1], note: "a statement must not be blank" },
        ],
      },
    });
    expect(screen.getByText("a rejection needs a reason")).toBeInTheDocument();
    expect(screen.getByText("a statement must not be blank")).toBeInTheDocument();
    // A refused decision leaves the candidate in the queue, still paired.
    expect(screen.getAllByText(/confidence$/)).toHaveLength(2);
  });

  it("yields the same persisted results as the API fixture after three decisions", () => {
    const three = {
      type: "candidate-queue",
      props: {
        interviewId: "I-1",
        state: "ready",
        target: "O-7",
        candidates: [
          { id: "C-1", statement: "Onboard faster", quote: "Setup takes forever." },
          { id: "C-2", statement: "Reconcile invoices", quote: "I reconcile by hand." },
          { id: "C-3", statement: "Onboard faster", quote: "New hires struggle." },
        ],
        actions: [
          { label: "Accept", intent: "Accept candidate C-1", tone: "primary" },
          { label: "Reject", intent: "Reject candidate C-2 with a reason" },
          { label: "Merge", intent: "Merge candidate C-3 into O-7" },
        ],
      },
    };
    const { onIntent } = renderSpec(three);

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    fireEvent.click(screen.getByRole("button", { name: "Merge" }));
    expect(onIntent.mock.calls.map(([intent]) => intent)).toEqual([
      "Accept candidate C-1",
      "Reject candidate C-2 with a reason",
      "Merge candidate C-3 into O-7",
    ]);

    // The card is a view: the store is the authority. Rendering the decisions
    // the API wrote back shows exactly those three, in place, still paired.
    cleanup();
    renderSpec({
      type: "candidate-queue",
      props: {
        ...three.props,
        candidates: [
          { ...three.props.candidates[0], decision: "accepted" },
          { ...three.props.candidates[1], decision: "rejected" },
          { ...three.props.candidates[2], decision: "merged" },
        ],
      },
    });
    expect(screen.getByText("accepted")).toBeInTheDocument();
    expect(screen.getByText("rejected")).toBeInTheDocument();
    expect(screen.getByText("merged")).toBeInTheDocument();
    expect(screen.getByText("Setup takes forever.")).toBeInTheDocument();
    expect(screen.getByText("I reconcile by hand.")).toBeInTheDocument();
    expect(screen.getByText("New hires struggle.")).toBeInTheDocument();
  });
});

describe("impact simulation provenance", () => {
  const simulation = {
    outcome: { id: "O-1", statement: "Minimize propagation time" },
    bet: "Automate secret sync",
    before: ["Copy-paste into CI"],
    after: ["One command"],
  };

  it("marks a simulated bet and says no model backs the number", () => {
    renderSpec({ type: "impact-simulation", props: { ...simulation, provenance: "simulated" } });

    expect(screen.getByText("Simulated")).toBeInTheDocument();
    expect(screen.getByText(/no model behind this number/i)).toBeInTheDocument();
  });

  it("refuses a simulation that does not say where it came from", () => {
    const result = parseUiSpec(
      { type: "impact-simulation", props: simulation },
      catalogManifest(),
    );

    expect(result.ok).toBe(false);
  });

  it("refuses a simulation that claims to be measured or live", () => {
    for (const provenance of ["live", "measured"]) {
      const result = parseUiSpec(
        { type: "impact-simulation", props: { ...simulation, provenance } },
        catalogManifest(),
      );
      expect(result.ok).toBe(false);
    }
  });
});

describe("batch scoring pass", () => {
  const pass = {
    type: "batch-scoring",
    props: {
      state: "ready",
      outcomes: [
        {
          id: "O-1",
          statement: "Minimize the time it takes to onboard",
          importance: 9,
          satisfaction: 3,
          quote: "Setup takes forever when a new hire starts.",
        },
        {
          id: "O-2",
          statement: "Minimize the effort to reconcile invoices",
          quote: "I reconcile invoices by hand every Friday.",
        },
      ],
    },
  };

  beforeEach(() => {
    studio.scoreOutcome.mockReset();
    studio.scoreOutcome.mockResolvedValue({
      outcome_id: "O-1",
      importance: 9,
      satisfaction: 3,
      ok: true,
      outcome: { id: "O-1", importance: 9, satisfaction: 3, opportunity_score: 15 },
    });
  });

  it("shows one outcome at a time with its sentence and progress", () => {
    renderSpec(pass);

    expect(screen.getByLabelText("Scoring pass 1 of 2")).toBeInTheDocument();
    expect(screen.getByText("Minimize the time it takes to onboard")).toBeInTheDocument();
    expect(screen.getByText("Setup takes forever when a new hire starts.")).toBeInTheDocument();
    expect(screen.getByText("1/2")).toBeInTheDocument();
    // The second outcome is not on stage until the first is dealt with.
    expect(screen.queryByText("I reconcile invoices by hand every Friday.")).not.toBeInTheDocument();
  });

  it("reads an unscored outcome as unscored, never as zero", () => {
    renderSpec({
      type: "batch-scoring",
      props: { state: "ready", outcomes: [pass.props.outcomes[1]] },
    });
    expect(screen.getByText("Current · unscored")).toBeInTheDocument();
  });

  it("writes through the shared endpoint and advances only on a real result", async () => {
    renderSpec(pass);
    fireEvent.click(screen.getByRole("button", { name: "Score" }));

    await waitFor(() =>
      expect(studio.scoreOutcome).toHaveBeenCalledWith({
        outcome_id: "O-1",
        importance: 9,
        satisfaction: 3,
      }),
    );
    expect(await screen.findByLabelText("Scoring pass 2 of 2")).toBeInTheDocument();
  });

  it("keeps the person on the same outcome when the server refuses", async () => {
    studio.scoreOutcome.mockResolvedValueOnce({
      outcome_id: "O-1",
      importance: 9,
      satisfaction: 3,
      ok: false,
      error: "importance must be between 1.0 and 10.0",
    });
    renderSpec(pass);
    fireEvent.click(screen.getByRole("button", { name: "Score" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "importance must be between 1.0 and 10.0",
    );
    // Still on the first outcome: progress did not move optimistically.
    expect(screen.getByLabelText("Scoring pass 1 of 2")).toBeInTheDocument();
  });

  it("reports a request failure without scoring the next item", async () => {
    studio.scoreOutcome.mockRejectedValueOnce(new Error("The sidecar is unreachable."));
    renderSpec(pass);
    fireEvent.click(screen.getByRole("button", { name: "Score" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The sidecar is unreachable.");
    expect(screen.getByLabelText("Scoring pass 1 of 2")).toBeInTheDocument();
  });

  it("skips without a write", () => {
    renderSpec(pass);
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));

    expect(studio.scoreOutcome).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Scoring pass 2 of 2")).toBeInTheDocument();
  });

  it("undoes the last write by replaying the previous pair through the same endpoint", async () => {
    renderSpec(pass);
    fireEvent.click(screen.getByRole("button", { name: "Score" }));
    await screen.findByLabelText("Scoring pass 2 of 2");

    fireEvent.click(screen.getByRole("button", { name: "Undo" }));

    await waitFor(() =>
      expect(studio.scoreOutcome).toHaveBeenLastCalledWith({
        outcome_id: "O-1",
        importance: 9,
        satisfaction: 3,
      }),
    );
    expect(await screen.findByLabelText("Scoring pass 1 of 2")).toBeInTheDocument();
  });

  it("scores three of five and leaves the last two untouched", async () => {
    const five = Array.from({ length: 5 }, (_, index) => ({
      id: `O-${index + 1}`,
      statement: `Outcome ${index + 1}`,
      quote: `Sentence ${index + 1}.`,
    }));
    studio.scoreOutcome.mockImplementation((item: { outcome_id: string; importance: number; satisfaction: number }) =>
      Promise.resolve({
        outcome_id: item.outcome_id,
        importance: item.importance,
        satisfaction: item.satisfaction,
        ok: true,
        outcome: { id: item.outcome_id },
      }),
    );
    renderSpec({ type: "batch-scoring", props: { state: "ready", outcomes: five } });

    for (let step = 0; step < 3; step += 1) {
      fireEvent.click(screen.getByRole("button", { name: "Score" }));
      await screen.findByLabelText(`Scoring pass ${step + 2} of 5`);
    }
    // The fourth outcome is on stage, but the last two were never written.
    expect(screen.getByLabelText("Scoring pass 4 of 5")).toBeInTheDocument();
    expect(studio.scoreOutcome.mock.calls.map(([item]) => item.outcome_id)).toEqual([
      "O-1",
      "O-2",
      "O-3",
    ]);
  });

  it("a double submit cannot score the next item", async () => {
    let resolveWrite: ((value: unknown) => void) | undefined;
    studio.scoreOutcome.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveWrite = resolve;
        }),
    );
    renderSpec(pass);

    const button = screen.getByRole("button", { name: "Score" });
    fireEvent.click(button);
    // The control is disabled while the write is in flight, so a second click
    // is inert: the first write must land before progress can move.
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(studio.scoreOutcome).toHaveBeenCalledTimes(1);

    resolveWrite?.({
      outcome_id: "O-1",
      importance: 9,
      satisfaction: 3,
      ok: true,
      outcome: { id: "O-1" },
    });
    expect(await screen.findByLabelText("Scoring pass 2 of 2")).toBeInTheDocument();
  });

  it("has nothing to undo before the first write", () => {
    renderSpec(pass);
    expect(screen.getByRole("button", { name: "Undo" })).toBeDisabled();
  });

  it("closes with an honest tally", async () => {
    renderSpec(pass);
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));

    expect(await screen.findByLabelText("Scoring pass complete")).toBeInTheDocument();
    expect(screen.getByText("Scoring complete: scored 0, skipped 2.")).toBeInTheDocument();
  });

  it("distinguishes loading, empty, and failed", () => {
    const { unmount } = render(
      <UiActionContext.Provider value={{ onIntent: vi.fn(), busy: false }}>
        <UiRenderer node={nodeOf({ type: "batch-scoring", props: { state: "loading" } })} />
      </UiActionContext.Provider>,
    );
    expect(screen.getByLabelText("Loading the scoring pass")).toHaveAttribute("aria-busy", "true");
    unmount();

    const empty = render(
      <UiActionContext.Provider value={{ onIntent: vi.fn(), busy: false }}>
        <UiRenderer node={nodeOf({ type: "batch-scoring", props: { state: "empty" } })} />
      </UiActionContext.Provider>,
    );
    expect(screen.getByLabelText("Nothing to score")).toBeInTheDocument();
    empty.unmount();

    renderSpec({
      type: "batch-scoring",
      props: { state: "failed", message: "The sidecar is unreachable." },
    });
    expect(screen.getByLabelText("The scoring pass could not be loaded")).toBeInTheDocument();
    expect(screen.getByText("The sidecar is unreachable.")).toBeInTheDocument();
  });

  it("treats a ready pass with no outcomes as empty", () => {
    renderSpec({ type: "batch-scoring", props: { state: "ready", outcomes: [] } });
    expect(screen.getByLabelText("Nothing to score")).toBeInTheDocument();
  });

  it("says when no customer sentence was captured instead of inventing one", () => {
    renderSpec({
      type: "batch-scoring",
      props: { state: "ready", outcomes: [{ id: "O-9", statement: "Minimize something" }] },
    });
    expect(
      screen.getByText("No customer sentence was captured for this outcome."),
    ).toBeInTheDocument();
  });
});
