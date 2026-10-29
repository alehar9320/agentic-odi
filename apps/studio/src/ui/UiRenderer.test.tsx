import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const toast = vi.hoisted(() => ({ pushToast: vi.fn() }));

vi.mock("../state/StudioContext", () => ({
  useStudio: () => ({ pushToast: toast.pushToast }),
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
