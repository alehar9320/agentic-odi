import { describe, expect, it } from "vitest";

import type { Capability } from "../bff/capabilities/registry";
import { deriveDeviceStatus, useCapabilityGate } from "./deviceStatus";

function cap(id: any, status: "available" | "unavailable"): Capability {
  return {
    id,
    label: id,
    description: id,
    status,
  };
}

describe("deriveDeviceStatus", () => {
  it("returns unknowns when nothing probed", () => {
    const status = deriveDeviceStatus([]);
    expect(status.local).toBe("unknown");
    expect(status.model).toBe("unknown");
    expect(status.sidecar).toBe("unknown");
  });

  it("local only", () => {
    const caps = [cap("local-data", "available"), cap("local-memory", "available")];
    const status = deriveDeviceStatus(caps);
    expect(status.local).toBe("ready");
  });

  it("local plus model", () => {
    const caps = [
      cap("local-data", "available"),
      cap("local-memory", "available"),
      cap("browser-model", "available"),
    ];
    const status = deriveDeviceStatus(caps);
    expect(status.local).toBe("ready");
    expect(status.model).toBe("ready");
  });

  it("local plus sidecar", () => {
    const caps = [
      cap("local-data", "available"),
      cap("local-memory", "available"),
      cap("sidecar-mcp", "available"),
    ];
    const status = deriveDeviceStatus(caps);
    expect(status.local).toBe("ready");
    expect(status.sidecar).toBe("ready");
  });

  it("all three", () => {
    const caps = [
      cap("local-data", "available"),
      cap("local-memory", "available"),
      cap("endpoint-model", "available"),
      cap("sidecar-connectors", "available"),
    ];
    const status = deriveDeviceStatus(caps);
    expect(status.local).toBe("ready");
    expect(status.model).toBe("ready");
    expect(status.sidecar).toBe("ready");
  });

  it("never returns absent from empty list", () => {
    const status = deriveDeviceStatus([]);
    expect(status.local).not.toBe("absent");
    expect(status.model).not.toBe("absent");
    expect(status.sidecar).not.toBe("absent");
  });
});

describe("useCapabilityGate", () => {
  it("allows with no requirements", () => {
    const result = useCapabilityGate([], []);
    expect(result.allowed).toBe(true);
  });

  it("blocks when required missing/unknown", () => {
    const result = useCapabilityGate(["sidecar-mcp" as any], []);
    expect(result.allowed).toBe(false);
    expect(result.reason).toBe("Checking…");
  });

  it("blocks when required unavailable", () => {
    const result = useCapabilityGate(["sidecar-mcp" as any], [cap("sidecar-mcp", "unavailable")]);
    expect(result.allowed).toBe(false);
  });

  it("allows when required available", () => {
    const result = useCapabilityGate(["sidecar-mcp" as any], [cap("sidecar-mcp", "available")]);
    expect(result.allowed).toBe(true);
  });
});
