import type { Capability, CapabilityId } from "../bff/capabilities/registry";

export type Presence = "ready" | "absent" | "unknown";

export interface DeviceStatus {
  local: Presence;
  model: Presence;
  sidecar: Presence;
  checkedAt: string | null;
}

const LOCAL_IDS: CapabilityId[] = ["local-data", "local-memory"];

function isKnownCapability(capabilities: Capability[], id: CapabilityId): Capability | undefined {
  return capabilities.find((capability) => capability.id === id);
}

export function deriveDeviceStatus(capabilities: Capability[]): DeviceStatus {
  if (!capabilities || capabilities.length === 0) {
    return {
      local: "unknown",
      model: "unknown",
      sidecar: "unknown",
      checkedAt: null,
    };
  }

  // Local
  let local: Presence = "ready";
  for (const id of LOCAL_IDS) {
    const cap = isKnownCapability(capabilities, id);
    if (!cap) {
      local = "unknown";
      break;
    }
    if (cap.status === "unavailable") {
      local = "absent";
      break;
    }
  }

  // Model: any of browser-model, endpoint-model, sidecar-llm available
  const modelIds: CapabilityId[] = ["browser-model", "endpoint-model", "sidecar-llm"];
  let model: Presence = "unknown";
  let anyModelKnown = false;
  for (const id of modelIds) {
    const cap = isKnownCapability(capabilities, id);
    if (cap) {
      anyModelKnown = true;
      if (cap.status === "available") {
        model = "ready";
        break;
      }
    }
  }
  if (model !== "ready" && anyModelKnown) {
    // If we know about models and none are ready, treat as absent unless unknown overall
    model = "absent";
  } else if (model !== "ready" && !anyModelKnown) {
    model = "unknown";
  }

  // Sidecar: any of sidecar-connectors, sidecar-mcp, sidecar-import available
  const sidecarIds: CapabilityId[] = ["sidecar-connectors", "sidecar-mcp", "sidecar-import"];
  let sidecar: Presence = "unknown";
  let anySidecarKnown = false;
  for (const id of sidecarIds) {
    const cap = isKnownCapability(capabilities, id);
    if (cap) {
      anySidecarKnown = true;
      if (cap.status === "available") {
        sidecar = "ready";
        break;
      }
    }
  }
  if (sidecar !== "ready" && anySidecarKnown) {
    sidecar = "absent";
  } else if (sidecar !== "ready" && !anySidecarKnown) {
    sidecar = "unknown";
  }

  return {
    local,
    model,
    sidecar,
    checkedAt: new Date().toISOString(),
  };
}

export interface CapabilityGateResult {
  allowed: boolean;
  blockedBy?: CapabilityId;
  reason?: string;
}

export function useCapabilityGate(
  requires: CapabilityId[],
  capabilities: Capability[],
): CapabilityGateResult {
  if (!requires || requires.length === 0) {
    return { allowed: true };
  }
  for (const req of requires) {
    const cap = capabilities.find((c) => c.id === req);
    if (!cap) {
      return { allowed: false, blockedBy: req, reason: "Checking…" };
    }
    if (cap.status === "unavailable") {
      return { allowed: false, blockedBy: req, reason: cap.reason || "Not available" };
    }
    if (cap.status === "available") {
      continue;
    }
  }
  // If all required are known and available, allowed. If unknown, block with Checking…
  for (const req of requires) {
    const cap = capabilities.find((c) => c.id === req);
    if (!cap) {
      return { allowed: false, blockedBy: req, reason: "Checking…" };
    }
  }
  return { allowed: true };
}
