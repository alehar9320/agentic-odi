/**
 * Prefetching the next rung of the ladder without disturbing the person.
 *
 * Progression is earned, not scheduled: a tier moves up only once the edge
 * has actually served enough work (PROGRESSION in `ladder.ts`), and the
 * download itself waits for a quiet moment — an idle callback, a visible
 * tab, no Save Data request, and a device the user said yes to. A gigabyte
 * should never arrive while the device is busy or being economised.
 */

import { PROGRESSION, nextEligibleTier, tierById } from "./ladder";
import { withEngineLock } from "./storage";
import type { EdgeStateService } from "./storage";
import type { EdgeLLMEngine, EdgeTierId, Eligibility, LoadProgress, TierState } from "./types";

export interface SchedulerEnvironment {
  /** Schedule `callback` for a quiet moment; returns a cancel function. */
  requestIdle(callback: () => void): () => void;
  visible(): boolean;
  saveData(): boolean;
}

export interface SchedulerDeps {
  state: EdgeStateService;
  engine(): Promise<EdgeLLMEngine>;
  eligibility(): Promise<Eligibility>;
  onProgress(tier: EdgeTierId, progress: LoadProgress): void;
  onUnlocked(tier: EdgeTierId): void;
  env?: SchedulerEnvironment;
}

const browserEnv: SchedulerEnvironment = {
  requestIdle(callback) {
    if (typeof window === "undefined") {
      return () => {};
    }
    if (typeof window.requestIdleCallback === "function") {
      const handle = window.requestIdleCallback(callback, { timeout: 60_000 });
      return () => window.cancelIdleCallback(handle);
    }
    // Safari has no idle callback yet; a beat of setTimeout is the honest
    // approximation of "when the main thread next breathes".
    const timer = window.setTimeout(callback, 2_000);
    return () => window.clearTimeout(timer);
  },
  visible() {
    return typeof document === "undefined" || document.visibilityState === "visible";
  },
  saveData() {
    if (typeof navigator === "undefined") {
      return false;
    }
    const connection = (navigator as unknown as { connection?: { saveData?: boolean } })
      .connection;
    return connection?.saveData === true;
  },
};

export class EdgeScheduler {
  private readonly deps: SchedulerDeps;
  private readonly env: SchedulerEnvironment;
  private pending: Promise<EdgeTierId | null> | null = null;
  private cancelIdle: (() => void) | null = null;
  private stopped = false;

  constructor(deps: SchedulerDeps) {
    this.deps = deps;
    this.env = deps.env ?? browserEnv;
  }

  /** Call after a served edge turn. Resolves to the tier whose download it
   * started, or null when nothing is earned yet or the moment is wrong. */
  async noteTurn(): Promise<EdgeTierId | null> {
    if (this.pending) {
      return this.pending;
    }
    const { state } = this.deps;
    if ((await state.getConsent()) !== "granted") {
      return null;
    }
    const usage = await state.getUsage();
    const earned =
      usage.edgeTurns >= PROGRESSION.edgeTurns ||
      usage.streamedSeconds >= PROGRESSION.streamedSeconds;
    if (!earned) {
      return null;
    }
    const states = await state.getTierStates();
    const serving = strongestHosted(states);
    if (serving === null) {
      return null;
    }
    const next = nextEligibleTier(serving, await this.deps.eligibility());
    if (next === null || states[next.id].status !== "empty") {
      return null;
    }
    return this.prefetch(next.id);
  }

  /** Wait for a quiet moment, win the engine lock, then pull the tier. */
  prefetch(tier: EdgeTierId): Promise<EdgeTierId | null> {
    if (this.pending) {
      return this.pending;
    }
    this.pending = this.run(tier).finally(() => {
      this.pending = null;
    });
    return this.pending;
  }

  stop(): void {
    this.stopped = true;
    this.cancelIdle?.();
    this.cancelIdle = null;
  }

  private async run(tier: EdgeTierId): Promise<EdgeTierId | null> {
    if (!this.goodMoment()) {
      return null;
    }
    await this.waitIdle();
    // The moment may have turned bad — or the manager may have reset the
    // scheduler entirely — while we queued.
    if (!this.goodMoment()) {
      return null;
    }
    const { acquired } = await withEngineLock(async () => {
      const engine = await this.deps.engine();
      await engine.load(tierById(tier).modelId, (progress) => {
        this.deps.onProgress(tier, progress);
      });
      await this.deps.state.setTierState(tier, {
        status: "active",
        cachedAt: new Date().toISOString(),
      });
    });
    if (!acquired) {
      // Another tab is on it; its write to the shared state will show up
      // before the next turn is routed.
      return null;
    }
    this.deps.onUnlocked(tier);
    return tier;
  }

  private goodMoment(): boolean {
    return !this.stopped && this.env.visible() && !this.env.saveData();
  }

  private waitIdle(): Promise<void> {
    return new Promise((resolve) => {
      const cancelQueue = this.env.requestIdle(() => {
        this.cancelIdle = null;
        resolve();
      });
      this.cancelIdle = () => {
        cancelQueue();
        this.cancelIdle = null;
        resolve();
      };
    });
  }
}

function strongestHosted(states: Record<EdgeTierId, TierState>): EdgeTierId | null {
  const hosted = (id: EdgeTierId) =>
    states[id].status === "active" || states[id].status === "cached" ? id : null;
  return hosted("t3") ?? hosted("t2") ?? hosted("t1");
}
