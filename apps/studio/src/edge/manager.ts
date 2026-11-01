/**
 * The page-level owner of the edge engine: decides, per turn, whether the
 * browser should answer, then runs that turn and records the usage that
 * earns the next tier. StudioContext talks to this; it never touches
 * WebLLM or the ladder directly.
 */

import type { RawSseEvent } from "../api/sse";
import type { ChatStreamRequest, StudioConfig } from "../types";
import { isEndpointConfiguredForSettings } from "../lib/modelEndpoint";
import { isFeatureEnabled } from "../features/flags";
import { EDGE_TIERS, PROGRESSION, collectDeviceSignals, computeEligibility, firstEligibleTier, tierById } from "./ladder";
import { EdgeScheduler, type SchedulerEnvironment } from "./scheduler";
import { openEdgeState, type EdgeStateService } from "./storage";
import { edgeTurn } from "./turn";
import type {
  ConsentState,
  EdgeLLMEngine,
  EdgeTierId,
  Eligibility,
  LoadProgress,
  TierStatus,
} from "./types";

/** What the page can react to without knowing anything about WebLLM. The
 * banner layer and the Settings section both subscribe; neither may assume it
 * is the only listener. */
export type EdgeNotice =
  | { kind: "downloading"; tier: EdgeTierId; progress: LoadProgress }
  /** The first tier landed: this browser can answer now. */
  | { kind: "ready"; tier: EdgeTierId }
  /** A stronger tier landed on top of one that already answered. */
  | { kind: "unlocked"; tier: EdgeTierId }
  /** The person freed a tier's storage, so it has to be fetched again. */
  | { kind: "tier-freed"; tier: EdgeTierId }
  /** The person answered the consent question, either way. */
  | { kind: "consent-changed" };

/** The one-time ask, in the two numbers that matter: which model, how big. */
export interface EdgeOffer {
  tier: EdgeTierId;
  label: string;
  approxBytes: number;
}

/** Everything the Settings section shows, from one read. */
export interface EdgePanelState {
  flagEnabled: boolean;
  consent: ConsentState;
  tiers: Array<{
    id: EdgeTierId;
    label: string;
    approxBytes: number;
    status: TierStatus;
    eligible: boolean;
    reason: string | null;
  }>;
  /** What this browser has already served, and what the next tier still wants. */
  usage: { edgeTurns: number; streamedSeconds: number; turnsToNext: number; secondsToNext: number };
  /** False when no tier fits this device, which is the honest reason the
   * consent control cannot do anything. */
  downloadable: boolean;
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

/** Whether some server is already answering — the studio's one rule for that
 * lives in `lib/modelEndpoint`, and the browser tier defers to it. A keyless
 * model on the person's own network counts just as a paid key does; standing
 * down is the correct answer either way. */
export function hasModelEndpoint(settings: StudioConfig): boolean {
  return isEndpointConfiguredForSettings(settings);
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
  private listeners: Set<(notice: EdgeNotice) => void> = new Set();
  private environment: SchedulerEnvironment | null = null;
  private fetching = false;
  /** What this tab last read of consent and the tiers on disk. A person's
   * message is never made to wait on a storage read to learn who is answering
   * it, so the routing decision reads this and the read that follows corrects
   * the next turn. */
  private snapshot: { consent: ConsentState; servedTier: EdgeTierId | null } = {
    consent: "unset",
    servedTier: null,
  };

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

  /** The seam the banner layer and Settings subscribe to. Several listeners on
   * purpose: the strip and the control panel both react, and neither owns the
   * other's rendering. */
  addNoticeListener(listener: (notice: EdgeNotice) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private emit(notice: EdgeNotice): void {
    // Everything but a progress tick changed what storage says about the
    // ladder — consent given, a tier hosted or freed — so the routing snapshot
    // follows the notice. A tick changes nothing anyone could decide on.
    if (notice.kind !== "downloading") {
      this.reread();
    }
    for (const listener of [...this.listeners]) {
      listener(notice);
    }
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
    this.snapshot = { consent: "unset", servedTier: null };
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
        onProgress: (tier, progress) => this.emit({ kind: "downloading", tier, progress }),
        onUnlocked: (tier, origin) => {
          // The prefetch loaded through this tab's engine, so the next turn
          // starts already on the stronger tier.
          this.loadedTier = tier;
          this.emit({ kind: origin === "bootstrap" ? "ready" : "unlocked", tier });
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

  /** Refresh the snapshot a turn's routing decision is read from. Await it when
   * the answer has to be current; fire it when a person is waiting. */
  async sync(): Promise<void> {
    const state = await this.ensureState();
    const [consent, servedTier] = await Promise.all([state.getConsent(), this.servedTier()]);
    this.snapshot = { consent, servedTier };
  }

  /** A read that fails leaves the decision working from what it last knew —
   * the state before the change, which is a smaller fault than throwing in
   * front of someone who just pressed send. */
  private reread(): void {
    void this.sync().catch(() => undefined);
  }

  canServe(settings: StudioConfig, llmHealthy: boolean): boolean {
    // Keep the next turn better informed without delaying this one.
    this.reread();
    return shouldUseEdge({
      flagEnabled: isFeatureEnabled("edgeModel"),
      endpointConfigured: hasModelEndpoint(settings),
      llmHealthy,
      consent: this.snapshot.consent,
      servedTier: this.snapshot.servedTier,
    });
  }

  /**
   * The one question worth asking a person with no model: may this browser
   * download one? Only asked when it would change the answer — the device can
   * host a tier, nothing is on disk yet, no paid endpoint is answering, and
   * the person has never said yes or no.
   */
  async offerFor(settings: StudioConfig, llmHealthy: boolean): Promise<EdgeOffer | null> {
    if (!isFeatureEnabled("edgeModel") || llmHealthy || hasModelEndpoint(settings)) {
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
    this.emit({ kind: "consent-changed" });
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
    this.emit({ kind: "consent-changed" });
  }

  /** Everything the Settings section renders, from one read. Deliberately a
   * snapshot rather than live bindings: the section re-reads after each action
   * and on notices, so it never has to know how tiers are stored. */
  async panelState(): Promise<EdgePanelState> {
    const state = await this.ensureState();
    const [tierStates, usage, consent, eligibility] = await Promise.all([
      state.getTierStates(),
      state.getUsage(),
      state.getConsent(),
      this.eligibilityFactory(),
    ]);
    // A device without WebGPU has no per-tier story — only the one reason the
    // whole ladder is out of reach.
    const onlyReason = eligibility.webgpu ? null : (eligibility.reasons[0] ?? null);
    // Exactly one tier is answering: the strongest one on disk. Older tiers
    // that once served stay "on this device" rather than claiming a role they
    // no longer have.
    const serving = await this.servedTier();
    const statusOf = (id: EdgeTierId): TierStatus => {
      const stored = tierStates[id].status;
      if (id === serving) {
        return stored === "empty" ? "empty" : "active";
      }
      return stored === "active" ? "cached" : stored;
    };
    return {
      flagEnabled: isFeatureEnabled("edgeModel"),
      consent,
      tiers: eligibility.tiers.map((decision) => ({
        id: decision.tier.id,
        label: decision.tier.label,
        approxBytes: decision.tier.approxBytes,
        status: statusOf(decision.tier.id),
        eligible: decision.eligible,
        reason: decision.reason ?? onlyReason,
      })),
      usage: {
        edgeTurns: usage.edgeTurns,
        streamedSeconds: Math.round(usage.streamedSeconds),
        turnsToNext: Math.max(0, PROGRESSION.edgeTurns - usage.edgeTurns),
        secondsToNext: Math.max(0, Math.round(PROGRESSION.streamedSeconds - usage.streamedSeconds)),
      },
      downloadable: firstEligibleTier(eligibility) !== null,
    };
  }

  /** Give the storage back. The weights themselves are WebLLM's to delete, so
   * this is the one Settings action that may pull in the engine chunk — and
   * the honest price of a tier this tab has never streamed. */
  async freeTier(tier: EdgeTierId): Promise<void> {
    const state = await this.ensureState();
    if ((await state.getTierStates())[tier].status !== "empty") {
      await (await this.getEngine()).evict(tierById(tier).modelId);
    }
    if (this.loadedTier === tier) {
      this.loadedTier = null;
    }
    await state.setTierState(tier, { status: "empty", cachedAt: null });
    this.emit({ kind: "tier-freed", tier });
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
