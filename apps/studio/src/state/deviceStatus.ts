import { useMemo } from "react";

import type { Capability, CapabilityId } from "../bff/capabilities/registry";
import { CAPABILITY_CATALOG, type CapabilityGroup } from "../bff/capabilities/catalog";
import { useStudio } from "./StudioContext";

/**
 * What a capability group can say about this device. `unknown` is the state
 * before the first probe resolves: it is deliberately distinct from `absent`,
 * because an empty list is not evidence that anything is missing. `setup` means
 * a capability exists but is not ready — the browser can download its model, so
 * the group is neither ready nor absent.
 */
export type Presence = "ready" | "setup" | "absent" | "unknown";

export interface DeviceStatus {
  local: Presence;
  model: Presence;
  sidecar: Presence;
  checkedAt: string | null;
}

function idsInGroup(group: CapabilityGroup): CapabilityId[] {
  return CAPABILITY_CATALOG.filter((definition) => definition.group === group).map(
    (definition) => definition.id,
  );
}

const LOCAL_IDS = idsInGroup("local");
const MODEL_IDS = idsInGroup("model");
const SIDECAR_IDS = idsInGroup("sidecar");

function statusOf(capabilities: Capability[], id: CapabilityId): Capability | undefined {
  return capabilities.find((capability) => capability.id === id);
}

function presenceFor(
  capabilities: Capability[],
  ids: CapabilityId[],
  requireAll: boolean,
): Presence {
  // An empty or not-yet-probed list knows nothing: it must never read as absent.
  if (capabilities.length === 0) return "unknown";
  const present = ids
    .map((id) => statusOf(capabilities, id))
    .filter((capability): capability is Capability => capability !== undefined);
  // A group that has not been probed at all is unknown, not absent.
  if (present.length === 0) return "unknown";
  const available = present.filter((capability) => capability.status === "available");
  if (requireAll) {
    if (present.length < ids.length) return "unknown";
    return available.length === ids.length ? "ready" : "absent";
  }
  if (available.length > 0) return "ready";
  // A group with nothing available but something downloadable is a setup state,
  // not an absence: the person can make it work.
  if (present.some((capability) => capability.status === "downloadable")) return "setup";
  return "absent";
}

/** Derive one answer for what works here from the probed capability list. */
export function deriveDeviceStatus(
  capabilities: Capability[],
  checkedAt: string | null,
): DeviceStatus {
  return {
    local: presenceFor(capabilities, LOCAL_IDS, true),
    model: presenceFor(capabilities, MODEL_IDS, false),
    sidecar: presenceFor(capabilities, SIDECAR_IDS, false),
    checkedAt,
  };
}

export interface CapabilityGate {
  /** False only when a required capability is known to be absent. */
  allowed: boolean;
  /** The first required capability that is absent, if any. */
  blockedBy: CapabilityId | null;
  /** Why a person cannot act yet, or why they are only waiting. */
  reason: string | null;
}

/** Decide whether a set of capabilities blocks an action, without a provider. */
export function capabilityGate(
  capabilities: Capability[],
  requires: CapabilityId[],
): CapabilityGate {
  if (requires.length === 0) {
    return { allowed: true, blockedBy: null, reason: null };
  }
  for (const id of requires) {
    const capability = statusOf(capabilities, id);
    // `downloadable` is not `available`: it must never create a session.
    if (capability && capability.status !== "available") {
      return {
        allowed: false,
        blockedBy: id,
        reason: capability.reason ?? `${capability.label} is not available on this device.`,
      };
    }
  }
  // A requirement that has not been probed yet blocks nothing; it is only a wait.
  if (requires.some((id) => statusOf(capabilities, id) === undefined)) {
    return { allowed: true, blockedBy: null, reason: "Checking…" };
  }
  return { allowed: true, blockedBy: null, reason: null };
}

/** The capability gate for the current studio state. */
export function useCapabilityGate(requires: CapabilityId[]): CapabilityGate {
  const { capabilities } = useStudio();
  return useMemo(() => capabilityGate(capabilities, requires), [capabilities, requires]);
}
