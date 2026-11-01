/**
 * The page-level owner of the edge engine: decides, per turn, whether the
 * browser should answer, then runs that turn and records the usage that
 * earns the next tier. StudioContext talks to this; it never touches
 * WebLLM or the ladder directly.
 */

import type { RawSseEvent } from "../api/sse";
import type { ChatStreamRequest, StudioConfig } from "../types";
import { isFeatureEnabled } from "../features/flags";
import { EDGE_TIERS, tierById } from "./ladder";
import { openEdgeState, type EdgeStateService } from "./storage";
import { edgeTurn } from "./turn";
import type { EdgeLLMEngine, EdgeTierId } from "./types";

export interface EdgeDecision {
  flagEnabled: boolean;
  endpointConfigured: boolean;
  llmHealthy: boolean;
  consent: "unset" | "granted" | "denied";
  servedTier: EdgeTierId | null;
}

/** Pure so the routing rule can be tested like a unit, not only via the store. */
export function shouldUseEdge(input: EdgeDecision): boolean {
  return (
    input.flagEnabled &&
    !input.endpointConfigured &&
    !input.llmHealthy &&
    input.consent === "granted" &&
    input.servedTier !== null
  );
}

export function hasRemoteEndpoint(settings: StudioConfig): boolean {
  return Boolean(
    settings.base_url &&
      settings.api_key &&
      settings.model_name &&
      settings.base_url !== "http://localhost:8001/v1",
  );
}

async function defaultEngineFactory(): Promise<EdgeLLMEngine> {
  const { createWebLLMEngine } = await import("./webllmEngine");
  return createWebLLMEngine();
}

export class EdgeManager {
  private engine: EdgeLLMEngine | null = null;
  private engineFactory = defaultEngineFactory;
  private state: EdgeStateService | null = null;
  private loadedTier: EdgeTierId | null = null;

  /** The seam tests and e2e use to drive an edge turn without WebGPU. */
  setEngineFactory(factory: () => Promise<EdgeLLMEngine>): void {
    this.engineFactory = factory;
  }

  /** Drop the cached engine and state so the next call re-opens everything.
   * Tests isolate per-case; the page never calls it. */
  reset(): void {
    this.engine = null;
    this.state = null;
    this.loadedTier = null;
  }

  private async ensureState(): Promise<EdgeStateService> {
    this.state ??= await openEdgeState();
    return this.state;
  }

  /** Cached-or-active tiers, strongest first. */
  async servedTier(): Promise<EdgeTierId | null> {
    const states = await (await this.ensureState()).getTierStates();
    for (let index = EDGE_TIERS.length - 1; index >= 0; index -= 1) {
      const tier = EDGE_TIERS[index];
      const status = states[tier.id].status;
      if (status === "active" || status === "cached") {
        return tier.id;
      }
    }
    return null;
  }

  async canServe(settings: StudioConfig, llmHealthy: boolean): Promise<boolean> {
    const state = await this.ensureState();
    return shouldUseEdge({
      flagEnabled: isFeatureEnabled("edgeModel"),
      endpointConfigured: hasRemoteEndpoint(settings),
      llmHealthy,
      consent: await state.getConsent(),
      servedTier: await this.servedTier(),
    });
  }

  /** Load (or reload into this tab) the tier that should answer, then stream
   * the turn through it. Records the usage that drives ladder progression. */
  async stream(
    request: ChatStreamRequest,
    onEvent: (event: RawSseEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    const state = await this.ensureState();
    const tier = await this.servedTier();
    if (!tier) {
      throw new Error("edge stream called with no cached tier");
    }
    if (!this.engine) {
      this.engine = await this.engineFactory();
    }
    if (this.loadedTier !== tier) {
      await this.engine.load(tierById(tier).modelId, () => {});
      await state.setTierState(tier, {
        status: "active",
        cachedAt: (await state.getTierStates())[tier].cachedAt ?? new Date().toISOString(),
      });
      this.loadedTier = tier;
    }
    const startedAt = Date.now();
    let answered = false;
    const emit: (event: RawSseEvent) => void = (event) => {
      if (event.event === "message") {
        answered = true;
      }
      onEvent(event);
    };
    await edgeTurn(request, { engine: this.engine, modelId: tierById(tier).modelId }, emit, signal);
    // Failed and user-stopped turns don't count toward the next tier — the
    // ladder rewards a device that actually served the work.
    if (answered) {
      await state.recordEdgeTurn((Date.now() - startedAt) / 1000);
    }
  }
}

export const edgeManager = new EdgeManager();
