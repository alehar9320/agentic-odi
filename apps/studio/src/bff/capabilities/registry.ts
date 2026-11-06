import { apiUrl } from "../../bridge/desktopBridge";
import { isEndpointConfiguredForSettings } from "../../lib/modelEndpoint";
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
  /** True when `check` proves configuration only, not that anything answers. */
  configuredOnly?: boolean;
  check(settings: StudioConfig): Promise<boolean>;
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

/** Ask the sidecar whether the configured MCP server answers.
 *
 * The route is POST-only (`apps/studio-api/.../studio/router.py`), so the probe
 * posts the same body `healthMcp` does. It used to GET, so a healthy sidecar
 * answered 405 and the row said MCP was missing. The body's `reachable` is the
 * fact, not the status code: an MCP server that does not answer is unavailable
 * even when the sidecar itself replied. */
async function probeMcp(mcpUrl: string): Promise<boolean> {
  try {
    const response = await fetch(apiUrl("/api/health/mcp"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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

export class CapabilityRegistry {
  private readonly probes: CapabilityProbe[] = [
    {
      id: "browser-model",
      label: localStatuses["browser-model"].label,
      description: localStatuses["browser-model"].description,
      check: async () => isBrowserModelAvailable(),
    },
    {
      id: "endpoint-model",
      label: localStatuses["endpoint-model"].label,
      description: localStatuses["endpoint-model"].description,
      // Present in Settings is not the same as answering: configuration is all
      // this check can see, so it can only ever reach `unknown` (#515).
      configuredOnly: true,
      check: async (settings) => isEndpointConfiguredForSettings(settings),
    },
    {
      id: "sidecar-llm",
      label: localStatuses["sidecar-llm"].label,
      description: localStatuses["sidecar-llm"].description,
      check: async () => probeSidecar("/api/capabilities", "sidecar-llm"),
    },
    {
      id: "sidecar-connectors",
      label: localStatuses["sidecar-connectors"].label,
      description: localStatuses["sidecar-connectors"].description,
      check: async () => probeSidecar("/api/connectors"),
    },
    {
      id: "sidecar-mcp",
      label: localStatuses["sidecar-mcp"].label,
      description: localStatuses["sidecar-mcp"].description,
      check: async (settings) => probeMcp(settings.mcp_url),
    },
    {
      id: "sidecar-import",
      label: localStatuses["sidecar-import"].label,
      description: localStatuses["sidecar-import"].description,
      check: async () => probeSidecar("/api/capabilities", "sidecar-import"),
    },
  ];

  async statuses(settings: StudioConfig): Promise<Capability[]> {
    const results = await Promise.all(
      this.probes.map(async (probe) => {
        let ok: boolean;
        let reason: string | undefined;
        try {
          ok = await probe.check(settings);
        } catch (error) {
          ok = false;
          reason = error instanceof Error ? error.message : "Probe failed.";
        }
        const status: Capability["status"] = ok
          ? probe.configuredOnly
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
