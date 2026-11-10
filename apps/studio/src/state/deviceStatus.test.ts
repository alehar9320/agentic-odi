import { describe, expect, it } from "vitest";

import type { Capability, CapabilityId } from "../bff/capabilities/registry";
import { capabilityGate, deriveDeviceStatus, type Presence } from "./deviceStatus";

function capability(
  id: CapabilityId,
  status: Capability["status"],
  reason?: string,
): Capability {
  return {
    id,
    label: id,
    description: `${id} on this device.`,
    status,
    ...(reason ? { reason } : {}),
  };
}

/** A probed list shaped like the registry's: every id present, all unavailable. */
function probed(available: CapabilityId[]): Capability[] {
  const ids: CapabilityId[] = [
    "local-data",
    "local-memory",
    "deterministic-assistant",
    "browser-model",
    "endpoint-model",
    "sidecar-llm",
    "sidecar-connectors",
    "sidecar-mcp",
    "sidecar-import",
  ];
  return ids.map((id) => capability(id, available.includes(id) ? "available" : "unavailable"));
}

const LOCAL: CapabilityId[] = ["local-data", "local-memory"];
const MODEL: CapabilityId[] = ["endpoint-model"];
const SIDECAR: CapabilityId[] = ["sidecar-mcp"];
const CHECKED = "2026-11-06T00:00:00.000Z";

describe("deriveDeviceStatus", () => {
  it("reports unknown everywhere before anything is probed", () => {
    const status = deriveDeviceStatus([], null);
    expect(status.local).toBe("unknown");
    expect(status.model).toBe("unknown");
    expect(status.sidecar).toBe("unknown");
    expect(status.checkedAt).toBeNull();
  });

  it("never reports absent from an empty list", () => {
    const { local, model, sidecar } = deriveDeviceStatus([], null);
    for (const presence of [local, model, sidecar]) {
      expect(presence).not.toBe("absent");
    }
  });

  it("reports local only, with model and sidecar absent", () => {
    const status = deriveDeviceStatus(probed(LOCAL), CHECKED);
    expect(status.local).toBe("ready");
    expect(status.model).toBe("absent");
    expect(status.sidecar).toBe("absent");
    expect(status.checkedAt).toBe(CHECKED);
  });

  it("reports local plus model, with sidecar absent", () => {
    const status = deriveDeviceStatus(probed([...LOCAL, ...MODEL]), CHECKED);
    expect(status.local).toBe("ready");
    expect(status.model).toBe("ready");
    expect(status.sidecar).toBe("absent");
  });

  it("reports local plus sidecar, with model absent", () => {
    const status = deriveDeviceStatus(probed([...LOCAL, ...SIDECAR]), CHECKED);
    expect(status.local).toBe("ready");
    expect(status.model).toBe("absent");
    expect(status.sidecar).toBe("ready");
  });

  it("reports all three ready", () => {
    const status = deriveDeviceStatus(probed([...LOCAL, ...MODEL, ...SIDECAR]), CHECKED);
    expect(status.local).toBe("ready");
    expect(status.model).toBe("ready");
    expect(status.sidecar).toBe("ready");
  });

  it("treats an unavailable local capability as absent", () => {
    const status = deriveDeviceStatus(probed(["local-data"]), CHECKED);
    expect(status.local).toBe("absent");
  });

  it("stays unknown for a group whose capabilities were never probed", () => {
    const status = deriveDeviceStatus([capability("local-data", "available")], CHECKED);
    expect(status.local).toBe("unknown");
  });

  it("names no derivation path offline for the local state", () => {
    const statuses: Presence[] = [
      deriveDeviceStatus([], null).local,
      deriveDeviceStatus(probed(LOCAL), CHECKED).local,
      deriveDeviceStatus(probed([]), CHECKED).local,
    ];
    for (const presence of statuses) {
      expect(presence).not.toMatch(/offline/i);
    }
  });
});

describe("capabilityGate", () => {
  it("is always allowed with no requirements", () => {
    expect(capabilityGate([], [])).toEqual({ allowed: true, blockedBy: null, reason: null });
  });

  it("blocks on a capability that is absent, naming it and its reason", () => {
    const gate = capabilityGate(
      [capability("sidecar-llm", "unavailable", "The sidecar did not answer.")],
      ["sidecar-llm"],
    );
    expect(gate.allowed).toBe(false);
    expect(gate.blockedBy).toBe("sidecar-llm");
    expect(gate.reason).toBe("The sidecar did not answer.");
  });

  it("falls back to a default reason when the capability names none", () => {
    const gate = capabilityGate([capability("sidecar-mcp", "unavailable")], ["sidecar-mcp"]);
    expect(gate.allowed).toBe(false);
    expect(gate.reason).toBe("sidecar-mcp is not available on this device.");
  });

  it("does not block on a capability that has not been probed yet", () => {
    const gate = capabilityGate([], ["sidecar-llm"]);
    expect(gate.allowed).toBe(true);
    expect(gate.blockedBy).toBeNull();
    expect(gate.reason).toBe("Checking…");
  });

  it("is allowed with no reason once a requirement is available", () => {
    const gate = capabilityGate([capability("sidecar-llm", "available")], ["sidecar-llm"]);
    expect(gate).toEqual({ allowed: true, blockedBy: null, reason: null });
  });
});
