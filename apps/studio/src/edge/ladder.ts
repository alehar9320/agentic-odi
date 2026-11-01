/**
 * The model ladder: which browser-hostable models exist, which ones this
 * device could host, and when the user has earned the next step up.
 *
 * Strength is a function of patience, not payment — a brand-new visitor gets
 * the smallest tier immediately, and the ladder only climbs after real usage
 * and with the device's permission.
 */

import type { DeviceSignals, EdgeTier, EdgeTierId, Eligibility, TierDecision } from "./types";

export const EDGE_TIERS: readonly EdgeTier[] = [
  {
    id: "t1",
    modelId: "Llama-3.2-1B-Instruct-q4f16_1-MLC",
    label: "Llama 3.2 1B",
    approxBytes: 1_300_000_000,
    minDeviceMemoryGB: 2,
  },
  {
    id: "t2",
    modelId: "Llama-3.2-3B-Instruct-q4f16_1-MLC",
    label: "Llama 3.2 3B",
    approxBytes: 2_000_000_000,
    minDeviceMemoryGB: 4,
  },
  {
    id: "t3",
    modelId: "Llama-3.1-8B-Instruct-q4f16_1-MLC",
    label: "Llama 3.1 8B",
    approxBytes: 4_700_000_000,
    minDeviceMemoryGB: 8,
  },
] as const;

/** Cross-tier progression: enough live usage that a bigger model is worth it. */
export const PROGRESSION = {
  edgeTurns: 10,
  streamedSeconds: 15 * 60,
} as const;

/** Quantized weights need headroom for context tensors on top of the file. */
const STORAGE_HEADROOM = 2;

export function tierById(id: EdgeTierId): EdgeTier {
  const tier = EDGE_TIERS.find((candidate) => candidate.id === id);
  if (!tier) {
    throw new Error(`Unknown edge tier: ${id}`);
  }
  return tier;
}

function formatGB(bytes: number): string {
  return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
}

function decideTier(tier: EdgeTier, signals: DeviceSignals): TierDecision {
  const { deviceMemoryGB, vramGB, freeStorageBytes, shaderF16 } = signals;
  const memory = vramGB === null ? deviceMemoryGB : Math.min(vramGB, deviceMemoryGB ?? vramGB);

  if (!shaderF16) {
    return {
      tier,
      eligible: false,
      reason: "This GPU can't run the fast 16-bit model format this browser needs.",
    };
  }
  if (memory === null) {
    // Unmeasurable devices get the entry tier only; we refuse to gamble the
    // user's afternoon on a download their hardware probably can't serve.
    if (tier.id === "t1") {
      return { tier, eligible: true, reason: null };
    }
    return {
      tier,
      eligible: false,
      reason: "This browser can't confirm the device has enough memory for a model this size.",
    };
  }
  if (memory < tier.minDeviceMemoryGB) {
    return {
      tier,
      eligible: false,
      reason: `Needs about a ${tier.minDeviceMemoryGB} GB-class device; this one reports ${memory} GB.`,
    };
  }
  if (freeStorageBytes !== null && freeStorageBytes < tier.approxBytes * STORAGE_HEADROOM) {
    return {
      tier,
      eligible: false,
      reason: `Needs about ${formatGB(tier.approxBytes * STORAGE_HEADROOM)} of free storage.`,
    };
  }
  return { tier, eligible: true, reason: null };
}

export function computeEligibility(signals: DeviceSignals): Eligibility {
  if (!signals.webgpu) {
    return {
      webgpu: false,
      reasons: ["This browser doesn't support GPU-accelerated models yet."],
      tiers: EDGE_TIERS.map((tier) => ({ tier, eligible: false, reason: null })),
    };
  }
  const tiers = EDGE_TIERS.map((tier) => decideTier(tier, signals));
  return { webgpu: true, reasons: [], tiers };
}

/** The strongest tier the device could host that is still ahead of `current`. */
export function nextEligibleTier(
  current: EdgeTierId | null,
  eligibility: Eligibility,
): EdgeTier | null {
  const rank = (id: EdgeTierId) => EDGE_TIERS.findIndex((tier) => tier.id === id);
  const candidates = eligibility.tiers.filter(
    (decision) => decision.eligible && (current === null || rank(decision.tier.id) > rank(current)),
  );
  if (candidates.length === 0) {
    return null;
  }
  return candidates[0].tier;
}

/** The weakest tier a device can host — the entry point for a new visitor. */
export function firstEligibleTier(eligibility: Eligibility): EdgeTier | null {
  return eligibility.tiers.find((decision) => decision.eligible)?.tier ?? null;
}

interface GpuAdapterLike {
  features: { has(name: string): boolean };
}

/**
 * Read the device signals the ladder needs. Every capability is probed
 * defensively: in jsdom, in old browsers, and under privacy modes the whole
 * function degrades to "unknown" rather than throwing.
 */
export async function collectDeviceSignals(): Promise<DeviceSignals> {
  const gpu = (navigator as { gpu?: { requestAdapter(): Promise<GpuAdapterLike | null> } }).gpu;
  let webgpu = false;
  let shaderF16 = false;
  if (gpu?.requestAdapter) {
    try {
      const adapter = await gpu.requestAdapter();
      webgpu = adapter !== null;
      shaderF16 = adapter?.features.has("shader-f16") ?? false;
    } catch {
      webgpu = false;
    }
  }

  const deviceMemory = (navigator as { deviceMemory?: number }).deviceMemory ?? null;

  let freeStorageBytes: number | null = null;
  if (navigator.storage?.estimate) {
    try {
      const estimate = await navigator.storage.estimate();
      if (typeof estimate.quota === "number" && typeof estimate.usage === "number") {
        freeStorageBytes = Math.max(0, estimate.quota - estimate.usage);
      }
    } catch {
      freeStorageBytes = null;
    }
  }

  const connection = (navigator as { connection?: { saveData?: boolean } }).connection;
  const saveData = connection?.saveData === true;

  return {
    webgpu,
    shaderF16,
    // A VRAM estimate needs the web-llm engine's GPU probe, which lives in
    // iteration 3; until then the memory floor falls back to deviceMemory.
    vramGB: null,
    deviceMemoryGB: deviceMemory ?? null,
    freeStorageBytes,
    saveData,
  };
}
