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

function isBrowserModelAvailable(): boolean {
  const ai = (globalThis as { ai?: { languageModel?: unknown } }).ai;
  return Boolean(ai && typeof ai.languageModel === "function");
}

function isEndpointConfigured(settings: StudioConfig): boolean {
  return Boolean(
    settings.base_url &&
      settings.api_key &&
      settings.model_name &&
      settings.base_url !== "http://localhost:8001/v1",
  );
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
      check: async (settings) => isEndpointConfigured(settings),
    },
    {
      id: "sidecar-llm",
      label: localStatuses["sidecar-llm"].label,
      description: localStatuses["sidecar-llm"].description,
      check: async (settings) => this.probeSidecar(settings.base_url, "/api/capabilities"),
    },
    {
      id: "sidecar-connectors",
      label: localStatuses["sidecar-connectors"].label,
      description: localStatuses["sidecar-connectors"].description,
      check: async (settings) => this.probeSidecar(settings.base_url, "/api/connectors"),
    },
    {
      id: "sidecar-mcp",
      label: localStatuses["sidecar-mcp"].label,
      description: localStatuses["sidecar-mcp"].description,
      check: async (settings) => this.probeSidecar(settings.base_url, "/api/health/mcp"),
    },
    {
      id: "sidecar-import",
      label: localStatuses["sidecar-import"].label,
      description: localStatuses["sidecar-import"].description,
      check: async (settings) => this.probeSidecar(settings.base_url, "/api/capabilities"),
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

  private async probeSidecar(baseUrl: string, path: string): Promise<boolean> {
    try {
      const response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
        signal: AbortSignal.timeout(2000),
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}

export const capabilityRegistry = new CapabilityRegistry();
