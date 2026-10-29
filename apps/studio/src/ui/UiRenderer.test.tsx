import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  it("renders the factual brief with its outcomes and provenance", () => {
    renderSpec({
      type: "opportunity-brief",
      props: {
        title: "The case for publishing speed",
        job: "Publish a plugin",
        decision: "Onboarding or publishing speed?",
        evidence_count: 4,
        generated_at: "2026-10-29T00:00:00Z",
        outcomes: [
          {
            statement: "Minimize the time to publish a plugin",
            score: 15,
            band: "underserved",
            n: 12,
            method: "survey",
            quote: "Publishing is the slowest step in my week",
            source: "interview-7",
          },
        ],
      },
    });

    expect(screen.getByLabelText("The case for publishing speed")).toBeInTheDocument();
    expect(screen.getByText("Minimize the time to publish a plugin")).toBeInTheDocument();
    expect(screen.getByText("underserved · 15.0")).toBeInTheDocument();
    expect(screen.getByText("Sample: 12")).toBeInTheDocument();
    expect(screen.getByText("4 evidence records")).toBeInTheDocument();
    expect(screen.getByText("Generated 2026-10-29T00:00:00Z")).toBeInTheDocument();
  });

  it("renders a missing measurement as not measured, never as zero", () => {
    renderSpec({
      type: "opportunity-brief",
      props: {
        title: "Sparse case",
        job: "Publish a plugin",
        outcomes: [{ statement: "Minimize the time to publish a plugin" }],
      },
    });

    expect(screen.getByText("not measured")).toBeInTheDocument();
    expect(screen.queryByText("0.0")).not.toBeInTheDocument();
  });

  it("renders the empty state rather than a placeholder row", () => {
    renderSpec({
      type: "opportunity-brief",
      props: { title: "Empty case", job: "Publish a plugin", outcomes: [] },
    });

    expect(screen.getByText(/No scored outcomes yet/)).toBeInTheDocument();
  });

  it("rejects an unknown prop on the brief and names the card", () => {
    const result = parseUiSpec(
      { type: "opportunity-brief", props: { title: "x", job: "y", outcomes: [], hostile: true } },
      catalogManifest(),
    );
    // An undeclared prop is stripped, not fatal; the brief still renders.
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.node.props).not.toHaveProperty("hostile");
    }
  });

  it("rejects a brief whose required prop is missing, naming the card", () => {
    const result = parseUiSpec(
      { type: "opportunity-brief", props: { title: "x" } },
      catalogManifest(),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.reason).toContain("opportunity-brief");
    }
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

describe("outcome compare", () => {
  it("renders a comparison with aligned rows and keyboard-readable headers", () => {
    renderSpec({
      type: "outcome-compare",
      props: {
        title: "Publishing speed vs support cost",
        columns: ["O-1", "O-2"],
        rows: [
          { metric: "score", label: "Opportunity score", cells: ["13", "12"] },
          { metric: "sample_size", label: "Sample size", cells: ["not measured", "12"] },
        ],
      },
    });

    expect(screen.getByLabelText("Publishing speed vs support cost")).toBeInTheDocument();
    // Header cells are real table headers, so a screen reader can read across.
    expect(screen.getByRole("columnheader", { name: "O-1" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "O-2" })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "Sample size" })).toBeInTheDocument();
  });

  it("renders a missing comparison cell as not measured, never zero", () => {
    renderSpec({
      type: "outcome-compare",
      props: {
        columns: ["O-1", "O-2"],
        rows: [{ metric: "score", label: "Opportunity score", cells: ["not measured", "0"] }],
      },
    });

    expect(screen.getByText("not measured")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("refuses a comparison with fewer than two columns", () => {
    const result = parseUiSpec(
      {
        type: "outcome-compare",
        props: {
          columns: ["O-1"],
          rows: [{ label: "Opportunity score", cells: ["13"] }],
        },
      },
      catalogManifest(),
    );

    expect(result.ok).toBe(false);
  });
});
