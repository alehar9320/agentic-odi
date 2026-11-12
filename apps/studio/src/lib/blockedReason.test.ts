import { describe, expect, it } from "vitest";

import { blockedReason, blockedReasons } from "./blockedReason";

/** Every id the capability registry models, spelled out so a new one fails here. */
const REGISTRY_IDS = [
  "local-data",
  "local-memory",
  "deterministic-assistant",
  "browser-model",
  "endpoint-model",
  "sidecar-llm",
  "sidecar-connectors",
  "sidecar-mcp",
  "sidecar-import",
] as const;

describe("blockedReason", () => {
  it("gives every capability the registry models a sentence and one real action", () => {
    for (const id of REGISTRY_IDS) {
      const reason = blockedReason(id);
      expect(reason.sentence.trim().length).toBeGreaterThan(0);
      expect(reason.action.label.trim().length).toBeGreaterThan(0);
      expect(reason.action.kind.trim().length).toBeGreaterThan(0);
    }
  });

  it("has one entry per registry id, with none left unwritten", () => {
    const ids = blockedReasons().map(([id]) => id);
    expect(new Set(ids).size).toBe(ids.length);
    expect([...ids].sort()).toEqual([...REGISTRY_IDS].sort());
  });

  it("names a real next step for a missing sidecar", () => {
    expect(blockedReason("sidecar-connectors").action).toEqual({
      label: "Start the local service",
      kind: "start-sidecar",
    });
  });

  it("sends a missing model to the model settings", () => {
    expect(blockedReason("browser-model").action.kind).toBe("add-model");
    expect(blockedReason("endpoint-model").action.label).toBe("Add a model");
  });
});
