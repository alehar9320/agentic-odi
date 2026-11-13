/**
 * One data-only catalog of what the Studio can do, imported by both the SPA and
 * the Cloudflare Worker so a capability cannot be added in one host only.
 *
 * It imports nothing and touches no DOM, which is what keeps it bundleable by
 * Wrangler (`infra/cloudflare/worker.ts`). Availability is never decided here:
 * each host probes for it and reports `available` / `downloadable` /
 * `unavailable`, so this file stays a description, not an answer.
 */

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

export type CapabilityGroup = "local" | "model" | "sidecar";

/**
 * `downloadable` is a setup state, not an available one: the browser offers the
 * model but it is not ready to answer yet. It must never render as available
 * and must never start a session.
 */
export type CapabilityStatus = "available" | "downloadable" | "unavailable";

export interface CapabilityDefinition {
  id: CapabilityId;
  label: string;
  description: string;
  group: CapabilityGroup;
}

/** The ids in stable order. Every host reports them in this order. */
export const CAPABILITY_IDS: CapabilityId[] = [
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

export const CAPABILITY_CATALOG: CapabilityDefinition[] = [
  {
    id: "local-data",
    label: "Local canvas data",
    description: "Jobs, steps, and outcomes stored in your browser.",
    group: "local",
  },
  {
    id: "local-memory",
    label: "Local memory and conversations",
    description: "Observations, conversation history, and context stored locally.",
    group: "local",
  },
  {
    id: "deterministic-assistant",
    label: "Deterministic assistant",
    description: "Answers about your canvas and updates it without a model.",
    group: "local",
  },
  {
    id: "browser-model",
    label: "Browser built-in model",
    description: "Uses the browser's built-in large language model when present.",
    group: "model",
  },
  {
    id: "endpoint-model",
    label: "Configured model endpoint",
    description: "Calls the model endpoint you configured in Settings directly.",
    group: "model",
  },
  {
    id: "sidecar-llm",
    label: "Sidecar model proxy",
    description: "Streams model responses through the local Python sidecar.",
    group: "model",
  },
  {
    id: "sidecar-connectors",
    label: "Sidecar connectors",
    description: "Adds third-party data sources through the sidecar.",
    group: "sidecar",
  },
  {
    id: "sidecar-mcp",
    label: "Sidecar MCP",
    description: "Runs MCP servers through the sidecar.",
    group: "sidecar",
  },
  {
    id: "sidecar-import",
    label: "Sidecar import",
    description: "Imports canvas data and memory from a reachable sidecar.",
    group: "sidecar",
  },
];

const BY_ID = new Map(CAPABILITY_CATALOG.map((definition) => [definition.id, definition]));

/** The catalog entry for an id. The catalog owns every id, so this never misses. */
export function definitionFor(id: CapabilityId): CapabilityDefinition {
  const definition = BY_ID.get(id);
  if (!definition) {
    throw new Error(`Unknown capability id: ${id}`);
  }
  return definition;
}
