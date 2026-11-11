import { authHeaders } from "../../api/studioApi";
import { apiUrl } from "../../bridge/desktopBridge";
import {
  endpointReachability,
  isEndpointConfiguredForSettings,
  isPrivateHost,
} from "../../lib/modelEndpoint";
import type { StudioConfig } from "../../types";
import { browserModelProbe } from "./browserModel";
import {
  CAPABILITY_CATALOG,
  definitionFor,
  type CapabilityId,
  type CapabilityStatus,
} from "./catalog";

// The catalog owns the ids, labels, and descriptions; re-exporting the id type
// keeps existing imports working without churning every call site.
export type { CapabilityId } from "./catalog";

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
  check(settings: StudioConfig): Promise<{ ok: boolean; status?: CapabilityStatus; reason?: string }>;
}

const SIDECAR_UNREACHABLE_REASON = "The local sidecar is not reachable.";

/** One `GET /api/capabilities` for the whole sidecar group, not one probe per
 * route. In the browser this is the Worker origin; in Tauri it is the local
 * sidecar at 127.0.0.1:8100. `null` means the manifest could not be read, so
 * every sidecar row is unavailable rather than guessed. */
async function fetchSidecarManifest(): Promise<Map<string, { available: boolean; reason?: string }> | null> {
  try {
    const response = await fetch(apiUrl("/api/capabilities"), {
      headers: authHeaders(),
      signal: AbortSignal.timeout(2000),
    });
    if (!response.ok) {
      return null;
    }
    const body = (await response.json()) as {
      capabilities?: Array<{ id: string; available?: boolean; reason?: string }>;
    };
    const manifest = new Map<string, { available: boolean; reason?: string }>();
    for (const item of body.capabilities ?? []) {
      manifest.set(item.id, {
        available: item.available === true,
        ...(item.reason ? { reason: item.reason } : {}),
      });
    }
    return manifest;
  } catch {
    return null;
  }
}

export class CapabilityRegistry {
  private readonly probes: CapabilityProbe[] = [
    {
      id: "browser-model",
      label: definitionFor("browser-model").label,
      description: definitionFor("browser-model").description,
      check: async () => {
        const probe = browserModelProbe();
        const result = await probe.availability();
        return {
          ok: result.status === "available",
          status: result.status,
          ...(result.reason ? { reason: result.reason } : {}),
        };
      },
    },
    {
      id: "endpoint-model",
      label: definitionFor("endpoint-model").label,
      description: definitionFor("endpoint-model").description,
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
        return { ok: true };
      },
    },
  ];

  async statuses(settings: StudioConfig): Promise<Capability[]> {
    const [probeResults, manifest] = await Promise.all([
      Promise.all(
        this.probes.map(async (probe) => {
          let status: CapabilityStatus;
          let reason: string | undefined;
          try {
            const result = await probe.check(settings);
            status = result.status ?? (result.ok ? "available" : "unavailable");
            reason = result.reason;
          } catch (error) {
            status = "unavailable";
            reason = error instanceof Error ? error.message : "Probe failed.";
          }
          return {
            id: probe.id,
            label: probe.label,
            description: probe.description,
            status,
            ...(reason ? { reason } : {}),
          } satisfies Capability;
        }),
      ),
      fetchSidecarManifest(),
    ]);

    const byId = new Map<CapabilityId, Capability>(probeResults.map((result) => [result.id, result]));

    // Every row takes its label and description from the catalog, so a change to
    // the catalog moves the Worker and the SPA together. The catalog's `group`
    // is the device-status grouping (which is why `sidecar-llm` sits in `model`);
    // the status *source* is the id: the four `sidecar-*` rows come from the one
    // manifest fetch, the two model probes answer for themselves, and the local
    // rows are always available. No id list is kept beside the catalog.
    return CAPABILITY_CATALOG.map((definition): Capability => {
      const probed = byId.get(definition.id);
      if (probed) {
        return probed;
      }
      if (definition.id.startsWith("sidecar-")) {
        const entry = manifest?.get(definition.id);
        if (!entry || !entry.available) {
          return {
            ...definition,
            status: "unavailable",
            reason: entry?.reason ?? SIDECAR_UNREACHABLE_REASON,
          };
        }
        return { ...definition, status: "available" };
      }
      if (definition.group === "local") {
        return { ...definition, status: "available" };
      }
      return {
        ...definition,
        status: "unavailable",
        reason: "No probe reports this capability yet.",
      };
    });
  }
}

export const capabilityRegistry = new CapabilityRegistry();
