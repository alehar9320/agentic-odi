/**
 * The page-level owner of the edge engine: decides, per turn, whether the
 * browser should answer, then runs that turn and records the usage that
 * earns the next tier. StudioContext talks to this; it never touches
 * WebLLM or the ladder directly.
 */

import type { RawSseEvent } from "../api/sse";
import type { ChatStreamRequest, StudioConfig } from "../types";
import { isFeatureEnabled } from "../features/flags";
import { EDGE_TIERS, collectDeviceSignals, computeEligibility, firstEligibleTier, tierById } from "./ladder";
import { EdgeScheduler, type SchedulerEnvironment } from "./scheduler";
import { openEdgeState, type EdgeStateService } from "./storage";
import { edgeTurn } from "./turn";
import type {
  ConsentState,
  EdgeLLMEngine,
  EdgeTierId,
  Eligibility,
  LoadProgress,
} from "./types";

/** What the page can react to without knowing anything about WebLLM.
 * The banner layer (next iteration) subscribes to these. */
export type EdgeNotice =
  | { kind: "downloading"; tier: EdgeTierId; progress: LoadProgress }
  /** The first tier landed: this browser can answer now. */
  | { kind: "ready"; tier: EdgeTierId }
  /** A stronger tier landed on top of one that already answered. */
  | { kind: "unlocked"; tier: EdgeTierId }
  /** The person answered the consent question, either way. */
  | { kind: "consent-changed" };

/** The one-time ask, in the two numbers that matter: which model, how big. */
export interface EdgeOffer {
  tier: EdgeTierId;
  label: string;
  approxBytes: number;
}

export interface EdgeDecision {
  flagEnabled: boolean;
  endpointConfigured: boolean;
  llmHealthy: boolean;
  consent: ConsentState;
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

/** Read the device without importing the WebLLM chunk: deciding whether to
 * *ask* for consent must not cost a megabyte of JavaScript. */
async function defaultEligibility(): Promise<Eligibility> {
  return computeEligibility(await collectDeviceSignals());
}

export class EdgeManager {
  private engine: EdgeLLMEngine | null = null;
  private engineFactory = defaultEngineFactory;
  private eligibilityFactory = defaultEligibility;
  private state: EdgeStateService | null = null;
  private loadedTier: EdgeTierId | null = null;
  private scheduler: EdgeScheduler | null = null;
  private listener: ((notice: EdgeNotice) => void) | null = null;
  private environment: SchedulerEnvironment | null = null;
  private fetching = false;

  /** The seam tests and e2e use to drive an edge turn without WebGPU. */
  setEngineFactory(factory: () => Promise<EdgeLLMEngine>): void {
    this.engineFactory = factory;
  }

  /** Pretend a class of device (tests, e2e, a "try it anyway" control). */
  setEligibilityFactory(factory: () => Promise<Eligibility>): void {
    this.eligibilityFactory = factory;
  }

  /** Override when a background download may start (tests, demos, e2e). */
  setSchedulerEnvironment(env: SchedulerEnvironment | null): void {
    this.environment = env;
  }

  /** The seam the banner layer subscribes to. One subscriber by design: the
   * banner host owns the notices and re-emits them into the dock. */
  setListener(listener: ((notice: EdgeNotice) => void) | null): void {
    this.listener = listener;
  }

  /** Drop the cached engine and state so the next call re-opens everything.
   * Tests isolate per-case; the page never calls it. */
  reset(): void {
    this.scheduler?.stop();
    this.scheduler = null;
    this.engine = null;
    this.state = null;
    this.loadedTier = null;
    this.fetching = false;
  }

  private async ensureState(): Promise<EdgeStateService> {
    this.state ??= await openEdgeState();
    return this.state;
  }

  private async getEngine(): Promise<EdgeLLMEngine> {
    this.engine ??= await this.engineFactory();
    return this.engine;
  }

  private async ensureScheduler(): Promise<EdgeScheduler> {
    if (!this.scheduler) {
      const state = await this.ensureState();
      this.scheduler = new EdgeScheduler({
        state,
        engine: () => this.getEngine(),
        eligibility: () => this.eligibilityFactory(),
        onProgress: (tier, progress) => this.listener?.({ kind: "downloading", tier, progress }),
        onUnlocked: (tier, origin) => {
          // The prefetch loaded through this tab's engine, so the next turn
          // starts already on the stronger tier.
          this.loadedTier = tier;
          this.listener?.({ kind: origin === "bootstrap" ? "ready" : "unlocked", tier });
        },
        env: this.environment ?? undefined,
      });
    }
    return this.scheduler;
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

  /**
   * The one question worth asking a person with no model: may this browser
   * download one? Only asked when it would change the answer — the device can
   * host a tier, nothing is on disk yet, no paid endpoint is answering, and
   * the person has never said yes or no.
   */
  async offerFor(settings: StudioConfig, llmHealthy: boolean): Promise<EdgeOffer | null> {
    if (!isFeatureEnabled("edgeModel") || llmHealthy || hasRemoteEndpoint(settings)) {
      return null;
    }
    const state = await this.ensureState();
    if ((await state.getConsent()) !== "unset" || (await this.servedTier()) !== null) {
      return null;
    }
    const entry = firstEligibleTier(await this.eligibilityFactory());
    return entry === null
      ? null
      : { tier: entry.id, label: entry.label, approxBytes: entry.approxBytes };
  }

  /** Say yes, then earn nothing: fetch the entry tier now so the next turn
   * has a voice. Resolves to the tier hosted, or null when the moment was
   * wrong or another tab is already doing it. */
  async grantAndStart(): Promise<EdgeTierId | null> {
    const state = await this.ensureState();
    await state.setConsent("granted");
    // From this instant this tab is working on an answer, so "no model is
    // reachable" has stopped being true. The banner layer asks `isBusy`.
    this.fetching = true;
    this.listener?.({ kind: "consent-changed" });
    try {
      return await (await this.ensureScheduler()).bootstrap();
    } finally {
      this.fetching = false;
    }
  }

  /** True while this tab has a first-tier download in flight. */
  isBusy(): boolean {
    return this.fetching;
  }

  /** Say no, durably. Settings can change it; the studio cannot ask twice. */
  async decline(): Promise<void> {
    const state = await this.ensureState();
    await state.setConsent("denied");
    this.listener?.({ kind: "consent-changed" });
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
    const engine = await this.getEngine();
    if (this.loadedTier !== tier) {
      await engine.load(tierById(tier).modelId, () => {});
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
    await edgeTurn(request, { engine, modelId: tierById(tier).modelId }, emit, signal);
    // Failed and user-stopped turns don't count toward the next tier — the
    // ladder rewards a device that actually served the work.
    if (answered) {
      await state.recordEdgeTurn((Date.now() - startedAt) / 1000);
      void (await this.ensureScheduler())
        .noteTurn()
        .catch(() => {
          // A failed prefetch only means the next turn stays on the current
          // tier; the person never sees a second error for the same fault.
        });
    }
  }
}

export const edgeManager = new EdgeManager();
