import { describe, expect, it } from "vitest";

import { CAPABILITY_CATALOG, CAPABILITY_IDS, definitionFor } from "./catalog";

describe("capability catalog", () => {
  it("lists the nine ids in stable order", () => {
    expect(CAPABILITY_IDS).toEqual([
      "local-data",
      "local-memory",
      "deterministic-assistant",
      "browser-model",
      "endpoint-model",
      "sidecar-llm",
      "sidecar-connectors",
      "sidecar-mcp",
      "sidecar-import",
    ]);
    expect(CAPABILITY_CATALOG.map((entry) => entry.id)).toEqual(CAPABILITY_IDS);
  });

  it("puts every entry in one of the three groups", () => {
    for (const entry of CAPABILITY_CATALOG) {
      expect(["local", "model", "sidecar"]).toContain(entry.group);
    }
  });

  it("gives every entry a non-empty label and description", () => {
    for (const entry of CAPABILITY_CATALOG) {
      expect(entry.label.length).toBeGreaterThan(0);
      expect(entry.description.length).toBeGreaterThan(0);
    }
  });

  it("looks a definition up by id", () => {
    expect(definitionFor("browser-model").group).toBe("model");
    expect(definitionFor("sidecar-mcp").label).toBe("Sidecar MCP");
  });
});
