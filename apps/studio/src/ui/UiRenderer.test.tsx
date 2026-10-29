import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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
