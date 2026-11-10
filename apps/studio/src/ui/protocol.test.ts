import { describe, expect, it } from "vitest";

import { CATALOG, catalogManifest } from "./catalog";
import { UI_LIMITS, parseUiSpec, type UiCatalogManifest } from "./protocol";

const manifest: UiCatalogManifest = catalogManifest();

const DOMAIN_CARDS = [
  "outcome-card",
  "opportunity-board",
  "impact-simulation",
  "evidence-quote",
  "job-map",
  "opportunity-thesis",
  "decision-record",
  "segment-card",
  "strategy-card",
];

function expectOk(spec: unknown) {
  const result = parseUiSpec(spec, manifest);
  if (!result.ok) {
    throw new Error(`expected a valid spec, got: ${result.reason}`);
  }
  return result.node;
}

function expectReason(spec: unknown): string {
  const result = parseUiSpec(spec, manifest);
  if (result.ok) {
    throw new Error("expected the spec to be rejected");
  }
  return result.reason;
}

const outcome = {
  type: "outcome-card",
  props: { id: "O-1", statement: "Minimize the time…", importance: 9, satisfaction: 3 },
};

describe("parseUiSpec", () => {
  it("accepts a valid card and keeps its props", () => {
    const node = expectOk(outcome);
    expect(node.type).toBe("outcome-card");
    expect(node.props).toEqual({
      id: "O-1",
      statement: "Minimize the time…",
      importance: 9,
      satisfaction: 3,
    });
    expect(node.children).toEqual([]);
  });

  it("accepts nested layout children", () => {
    const node = expectOk({
      type: "stack",
      props: { gap: "sm" },
      children: [outcome, { type: "divider" }],
    });
    expect(node.children.map((child) => child.type)).toEqual(["outcome-card", "divider"]);
  });

  it("degrades an unknown component type to a visible fallback", () => {
    const node = expectOk({ type: "salesforce-dashboard", props: { anything: true } });
    expect(node).toEqual({
      type: "salesforce-dashboard",
      props: {},
      children: [],
      unsupported: true,
    });
  });

  it("strips props the catalog does not declare", () => {
    const node = expectOk({
      ...outcome,
      props: { ...outcome.props, dangerouslySetInnerHTML: "<script/>", tone: "shout" },
    });
    expect(node.props).not.toHaveProperty("dangerouslySetInnerHTML");
    expect(node.props).not.toHaveProperty("tone");
  });

  it("drops an optional prop with the wrong type instead of failing the tree", () => {
    const node = expectOk({ ...outcome, props: { ...outcome.props, evidence: 42 } });
    expect(node.props).not.toHaveProperty("evidence");
    expect(node.props.id).toBe("O-1");
  });

  it("drops an over-long optional action list", () => {
    const actions = Array.from({ length: UI_LIMITS.maxActions + 1 }, (_, index) => ({
      label: `Action ${index}`,
      intent: "do it",
    }));
    const node = expectOk({ ...outcome, props: { ...outcome.props, actions } });
    expect(node.props).not.toHaveProperty("actions");
  });

  it("keeps a valid action list", () => {
    const node = expectOk({
      ...outcome,
      props: {
        ...outcome.props,
        actions: [{ label: "Simulate", intent: "Simulate outcome O-1", tone: "primary" }],
      },
    });
    expect(node.props.actions).toEqual([
      { label: "Simulate", intent: "Simulate outcome O-1", tone: "primary" },
    ]);
  });

  it("accepts an empty action list", () => {
    const node = expectOk({ ...outcome, props: { ...outcome.props, actions: [] } });
    expect(node.props.actions).toEqual([]);
  });

  it("rejects a required prop that is missing", () => {
    expect(expectReason({ type: "outcome-card", props: { id: "O-1" } })).toContain("outcome-card");
  });

  it("rejects a required score outside the 0–10 band", () => {
    const reason = expectReason({
      ...outcome,
      props: { ...outcome.props, importance: 11 },
    });
    expect(reason).toContain("importance");
  });

  it("rejects a required enum value outside the catalog", () => {
    expect(expectReason({ type: "callout", props: { tone: "sarcastic", body: "hi" } })).toContain(
      "tone",
    );
  });

  it("drops stray children on a leaf card instead of failing the whole tree", () => {
    const node = expectOk({ ...outcome, children: [{ type: "divider" }] });
    expect(node.children).toEqual([]);
  });

  it("rejects a non-object payload", () => {
    expect(expectReason("just text")).toBe("UI node must be an object");
  });

  it("rejects children that are not an array", () => {
    expect(expectReason({ type: "stack", props: {}, children: {} })).toContain("children");
  });

  it("rejects trees deeper than the limit", () => {
    let spec: unknown = { type: "divider" };
    for (let index = 0; index < UI_LIMITS.maxDepth + 1; index += 1) {
      spec = { type: "stack", props: {}, children: [spec] };
    }
    expect(expectReason(spec)).toContain("depth");
  });

  it("rejects trees with more nodes than the limit", () => {
    const branches = Array.from({ length: UI_LIMITS.maxChildren }, () => ({
      type: "stack",
      props: {},
      children: Array.from({ length: UI_LIMITS.maxChildren }, () => ({ type: "divider" })),
    }));
    expect(expectReason({ type: "stack", props: {}, children: branches })).toContain("nodes");
  });

  it("rejects a tree wider than the child limit", () => {
    const children = Array.from({ length: UI_LIMITS.maxChildren + 1 }, () => ({ type: "divider" }));
    expect(expectReason({ type: "stack", props: {}, children })).toContain("children");
  });

  it("rejects a string over the length ceiling", () => {
    expect(
      expectReason({ type: "text", props: { text: "x".repeat(UI_LIMITS.maxStringLength + 1) } }),
    ).toContain("text");
  });

  it("validates nested object props inside arrays", () => {
    const board = {
      type: "opportunity-board",
      props: {
        outcomes: [{ id: "O-1", statement: "Minimize time", importance: 9, satisfaction: 2 }],
      },
    };
    expect(expectOk(board).props.outcomes).toHaveLength(1);

    expect(
      expectReason({
        type: "opportunity-board",
        props: { outcomes: [{ id: "O-1", statement: "Minimize time", importance: "nine" }] },
      }),
    ).toContain("opportunity-board");
  });

  it("rejects a strategy card that records no rejected path", () => {
    // A recommendation without its alternatives is a conclusion. The catalog
    // enforces that at the protocol boundary, so the model cannot stream one.
    const reason = expectReason({
      type: "strategy-card",
      props: {
        kind: "differentiated",
        thesis: "Finance leads are underserved on matching each line.",
      },
    });
    expect(reason).toContain("strategy-card");
    expect(reason).toContain("rejected");
  });

  it("accepts a strategy card with both rejected paths", () => {
    const node = expectOk({
      type: "strategy-card",
      props: {
        kind: "differentiated",
        thesis: "Finance leads are underserved on matching each line.",
        rejected: [
          { kind: "disruptive", why: "no segment is overserved" },
          { kind: "new_market", why: "every outcome maps to a known job" },
        ],
      },
    });
    expect(node.props.rejected).toHaveLength(2);
  });

  it("drops a segment's evidence list when it rests on a single outcome", () => {
    // Two is the floor: one outcome is a hypothesis, not a market. The list is
    // optional, so the protocol drops it rather than letting a one-outcome
    // "segment" through with its evidence intact.
    const node = expectOk({
      type: "segment-card",
      props: {
        id: "SEG-1",
        name: "Finance leads, match each line",
        people: "Finance leads",
        jobStatement: "Reconcile invoices without manual effort",
        verdict: "underserved",
        confidence: 0.8,
        outcomeIds: ["O-14"],
        rationale: "One outcome scores above 10.",
      },
    });
    expect(node.props).not.toHaveProperty("outcomeIds");
    expect(node.props.id).toBe("SEG-1");
  });
});

describe("catalogManifest", () => {
  it("declares every type exactly once", () => {
    const types = CATALOG.map((component) => component.type);
    expect(new Set(types).size).toBe(types.length);
  });

  it("round-trips through JSON unchanged", () => {
    expect(JSON.parse(JSON.stringify(manifest))).toEqual(manifest);
  });

  it("gives every domain card an action list", () => {
    for (const type of DOMAIN_CARDS) {
      const component = CATALOG.find((candidate) => candidate.type === type);
      expect(component, type).toBeDefined();
      expect(Object.keys(component?.props.properties ?? {})).toContain("actions");
    }
  });

  it("only allows children on layouts", () => {
    for (const component of CATALOG) {
      if (component.acceptsChildren) {
        expect(component.kind).toBe("layout");
      }
    }
    expect(CATALOG.find((component) => component.type === "stack")?.acceptsChildren).toBe(true);
  });

  it("describes every component for the model", () => {
    for (const component of CATALOG) {
      expect(component.description.length).toBeGreaterThan(20);
    }
  });
});
