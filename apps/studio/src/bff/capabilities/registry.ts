import { authHeaders } from "../../api/studioApi";
import { apiUrl } from "../../bridge/desktopBridge";
import {
  endpointReachability,
  isEndpointConfiguredForSettings,
  isPrivateHost,
} from "../../lib/modelEndpoint";
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

/**
 * What a probe has actually established. `unknown` is its own answer: a thing
 * can be configured and still unproven, and that must never read as available.
 */
export type CapabilityStatus = "available" | "unavailable" | "unknown";

export interface Capability {
  id: CapabilityId;
  label: string;
  description: string;
  status: CapabilityStatus;
  reason?: string;
}

export interface CapabilityProbe {
  id: CapabilityId;
  label: string;
  description: string;
  check(settings: StudioConfig): Promise<{ ok: boolean; reason?: string; unproven?: boolean }>;
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
    label: "Browser built-in model",
    description: "Uses the browser's built-in large language model when present.",
    status: "unavailable",
  },
  "endpoint-model": {
    id: "endpoint-model",
    label: "Configured",
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

function isBrowserModelAvailable(): boolean {
  const ai = (globalThis as { ai?: { languageModel?: unknown } }).ai;
  return Boolean(ai && typeof ai.languageModel === "function");
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
      headers: authHeaders(),
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

async function probeMcp(mcpUrl: string): Promise<boolean> {
  try {
    const response = await fetch(apiUrl("/api/health/mcp"), {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ mcp_url: mcpUrl }),
      signal: AbortSignal.timeout(2000),
    });
    if (!response.ok) {
      return false;
    }
    const body = (await response.json()) as { reachable?: boolean };
    return body.reachable === true;
  } catch {
    return false;
  }
}


/** The same loopback rule `modelEndpoint.ts` uses before it calls a host private. */
function isLoopbackHost(hostname: string): boolean {
  const host = hostname.replace(/^\[|\]$/g, "").toLowerCase();
  return host === "localhost" || host.endsWith(".localhost") || host === "::1" || host.startsWith("127.");
}

export class CapabilityRegistry {
  private readonly probes: CapabilityProbe[] = [
    {
      id: "browser-model",
      label: localStatuses["browser-model"].label,
      description: localStatuses["browser-model"].description,
      check: async () => ({ ok: isBrowserModelAvailable() }),
    },
    {
      id: "endpoint-model",
      label: localStatuses["endpoint-model"].label,
      description: localStatuses["endpoint-model"].description,
      // Present in Settings is not the same as answering. Reachability is only
      // proven when the page and the endpoint sit on the same side: a hosted
      // page can reach a public endpoint, a device page a loopback one. Anything
      // else is configured, not checked (#515).
      check: async (settings) => {
        if (!isEndpointConfiguredForSettings(settings)) {
          return { ok: false };
        }
        const originClass = isPrivateHost(window.location.hostname) ? "device" : "hosted";
        const reachability = endpointReachability(
          {
            base_url: settings.base_url,
            api_key: settings.api_key,
            model: settings.model_name,
          },
          { originClass },
        );
        if (reachability === "device-only") {
          return {
            ok: false,
            reason:
              "This endpoint is on your machine. A hosted page cannot reach it; use the desktop app or open the Studio on this device.",
          };
        }
        let hostname: string;
        try {
          hostname = new URL(settings.base_url.trim()).hostname;
        } catch {
          hostname = "";
        }
        const proven =
          hostname === ""
            ? true
            : originClass === "hosted"
              ? !isPrivateHost(hostname)
              : isLoopbackHost(hostname);
        return proven ? { ok: true } : { ok: true, unproven: true };
      },
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
      check: async (settings) => ({ ok: await probeMcp(settings.mcp_url) }),
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
        let unproven = false;
        try {
          const result = await probe.check(settings);
          ok = result.ok;
          reason = result.reason;
          unproven = result.unproven === true;
        } catch (error) {
          ok = false;
          reason = error instanceof Error ? error.message : "Probe failed.";
        }
        const status: Capability["status"] = ok
          ? unproven
            ? "unknown"
            : "available"
          : "unavailable";
        return {
          ...localStatuses[probe.id],
          status,
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
