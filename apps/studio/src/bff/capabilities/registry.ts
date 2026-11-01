import { apiUrl } from "../../bridge/desktopBridge";
import { collectDeviceSignals, computeEligibility, firstEligibleTier } from "../../edge/ladder";
import type { StudioConfig } from "../../types";

export type CapabilityId =
  | "local-data"
  | "local-memory"
  | "deterministic-assistant"
  | "browser-model"
  | "endpoint-model"
  | "sidecar-llm"
  | "sidecar-connectors"
  | "sidecar-mcp"
  | "sidecar-import";

export interface Capability {
  id: CapabilityId;
  label: string;
  description: string;
  status: "available" | "unavailable";
  reason?: string;
}

export interface CapabilityProbe {
  id: CapabilityId;
  label: string;
  description: string;
  check(settings: StudioConfig): Promise<ProbeResult>;
}

export interface ProbeResult {
  ok: boolean;
  /** One human sentence for why a capability is out of reach. */
  reason?: string;
}

const localStatuses: Record<CapabilityId, Capability> = {
  "local-data": {
    id: "local-data",
    label: "Local canvas data",
    description: "Jobs, steps, and outcomes stored in your browser.",
    status: "available",
  },
  "local-memory": {
    id: "local-memory",
    label: "Local memory and conversations",
    description: "Observations, conversation history, and context stored locally.",
    status: "available",
  },
  "deterministic-assistant": {
    id: "deterministic-assistant",
    label: "Deterministic assistant",
    description: "Answers about your canvas and updates it without a model.",
    status: "available",
  },
  "browser-model": {
    id: "browser-model",
    label: "In-browser model",
    description: "Runs free GPU-accelerated models on this device when no paid endpoint is set.",
    status: "unavailable",
  },
  "endpoint-model": {
    id: "endpoint-model",
    label: "Configured model endpoint",
    description: "Calls the model endpoint you configured in Settings directly.",
    status: "unavailable",
  },
  "sidecar-llm": {
    id: "sidecar-llm",
    label: "Sidecar model proxy",
    description: "Streams model responses through the local Python sidecar.",
    status: "unavailable",
  },
  "sidecar-connectors": {
    id: "sidecar-connectors",
    label: "Sidecar connectors",
    description: "Adds third-party data sources through the sidecar.",
    status: "unavailable",
  },
  "sidecar-mcp": {
    id: "sidecar-mcp",
    label: "Sidecar MCP",
    description: "Runs MCP servers through the sidecar.",
    status: "unavailable",
  },
  "sidecar-import": {
    id: "sidecar-import",
    label: "Sidecar import",
    description: "Imports canvas data and memory from a reachable sidecar.",
    status: "unavailable",
  },
};

async function browserModelProbe(): Promise<ProbeResult> {
  const eligibility = computeEligibility(await collectDeviceSignals());
  if (firstEligibleTier(eligibility)) {
    return { ok: true };
  }
  const reason =
    eligibility.reasons[0] ??
    eligibility.tiers.find((decision) => decision.reason)?.reason ??
    "No in-browser model fits this device right now.";
  return { ok: false, reason };
}

function isEndpointConfigured(settings: StudioConfig): boolean {
  return Boolean(
    settings.base_url &&
      settings.api_key &&
      settings.model_name &&
      settings.base_url !== "http://localhost:8001/v1",
  );
}

/** Probe a same-origin sidecar route. In the browser this is the Worker
 * origin; in Tauri it is the local sidecar at 127.0.0.1:8100. When
 * `capabilityId` is given the route is expected to return a capabilities
 * manifest and the probe only succeeds if that capability is advertised
 * as available. This keeps the Worker's local-only manifest (which marks
 * sidecar capabilities unavailable) from being mistaken for a real sidecar. */
async function probeSidecar(path: string, capabilityId?: CapabilityId): Promise<boolean> {
  try {
    const response = await fetch(apiUrl(path), {
      signal: AbortSignal.timeout(2000),
    });
    if (!response.ok) {
      return false;
    }
    if (!capabilityId) {
      return true;
    }
    const body = (await response.json()) as { capabilities?: Array<{ id: string; available?: boolean }> };
    return body.capabilities?.some(
      (capability) => capability.id === capabilityId && capability.available === true,
    ) ?? false;
  } catch {
    return false;
  }
}

export class CapabilityRegistry {
  private readonly probes: CapabilityProbe[] = [
    {
      id: "browser-model",
      label: localStatuses["browser-model"].label,
      description: localStatuses["browser-model"].description,
      check: async () => browserModelProbe(),
    },
    {
      id: "endpoint-model",
      label: localStatuses["endpoint-model"].label,
      description: localStatuses["endpoint-model"].description,
      check: async (settings) => ({ ok: isEndpointConfigured(settings) }),
    },
    {
      id: "sidecar-llm",
      label: localStatuses["sidecar-llm"].label,
      description: localStatuses["sidecar-llm"].description,
      check: async () => ({ ok: await probeSidecar("/api/capabilities", "sidecar-llm") }),
    },
    {
      id: "sidecar-connectors",
      label: localStatuses["sidecar-connectors"].label,
      description: localStatuses["sidecar-connectors"].description,
      check: async () => ({ ok: await probeSidecar("/api/connectors") }),
    },
    {
      id: "sidecar-mcp",
      label: localStatuses["sidecar-mcp"].label,
      description: localStatuses["sidecar-mcp"].description,
      check: async () => ({ ok: await probeSidecar("/api/health/mcp") }),
    },
    {
      id: "sidecar-import",
      label: localStatuses["sidecar-import"].label,
      description: localStatuses["sidecar-import"].description,
      check: async () => ({ ok: await probeSidecar("/api/capabilities", "sidecar-import") }),
    },
  ];

  async statuses(settings: StudioConfig): Promise<Capability[]> {
    const results = await Promise.all(
      this.probes.map(async (probe) => {
        let ok: boolean;
        let reason: string | undefined;
        try {
          const result = await probe.check(settings);
          ok = result.ok;
          reason = result.reason;
        } catch (error) {
          ok = false;
          reason = error instanceof Error ? error.message : "Probe failed.";
        }
        return {
          ...localStatuses[probe.id],
          status: (ok ? "available" : "unavailable") as Capability["status"],
          ...(ok ? {} : { reason }),
        };
      }),
    );
    return [
      localStatuses["local-data"],
      localStatuses["local-memory"],
      localStatuses["deterministic-assistant"],
      ...results,
    ];
  }
}

export const capabilityRegistry = new CapabilityRegistry();
