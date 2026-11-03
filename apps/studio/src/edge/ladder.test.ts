import { afterEach, describe, expect, it, vi } from "vitest";

import {
  EDGE_TIERS,
  collectDeviceSignals,
  computeEligibility,
  firstEligibleTier,
  nextEligibleTier,
  tierById,
} from "./ladder";
import type { DeviceSignals } from "./types";

function signals(overrides: Partial<DeviceSignals> = {}): DeviceSignals {
  return {
    webgpu: true,
    shaderF16: true,
    vramGB: null,
    deviceMemoryGB: 16,
    freeStorageBytes: 40_000_000_000,
    saveData: false,
    ...overrides,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const stubbedKeys = new Map<string, PropertyDescriptor | undefined>();

function stubNavigator(key: string, value: unknown): void {
  if (!stubbedKeys.has(key)) {
    stubbedKeys.set(key, Object.getOwnPropertyDescriptor(navigator, key));
  }
  Object.defineProperty(navigator, key, { value, configurable: true });
}

afterEach(() => {
  for (const [key, descriptor] of stubbedKeys) {
    if (descriptor) {
      Object.defineProperty(navigator, key, descriptor);
    } else {
      delete (navigator as unknown as Record<string, unknown>)[key];
    }
  }
  stubbedKeys.clear();
});

describe("computeEligibility", () => {
  it("retires every tier without WebGPU", () => {
    const eligibility = computeEligibility(signals({ webgpu: false }));
    expect(eligibility.reasons.join(" ")).toMatch(/WebGPU|GPU/i);
    expect(eligibility.tiers.every((decision) => !decision.eligible)).toBe(true);
  });

  it("offers the whole ladder to a capable desktop", () => {
    const eligibility = computeEligibility(signals());
    expect(eligibility.tiers.filter((decision) => decision.eligible).map((d) => d.tier.id)).toEqual(
      ["t1", "t2", "t3"],
    );
  });

  it("caps a 4 GB device below the 8B tier", () => {
    const eligibility = computeEligibility(signals({ deviceMemoryGB: 4 }));
    expect(eligibility.tiers.map((d) => d.eligible)).toEqual([true, true, false]);
    expect(eligibility.tiers[2].reason).toMatch(/8 GB/);
  });

  it("trusts only the entry tier when memory is unmeasurable", () => {
    const eligibility = computeEligibility(signals({ deviceMemoryGB: null }));
    expect(eligibility.tiers.map((d) => d.eligible)).toEqual([true, false, false]);
    expect(eligibility.tiers[1].reason).toMatch(/can't confirm/i);
  });

  it("blocks tiers whose download does not fit the storage headroom", () => {
    const eligibility = computeEligibility(signals({ freeStorageBytes: 3_000_000_000 }));
    expect(eligibility.tiers.map((d) => d.eligible)).toEqual([true, false, false]);
    expect(eligibility.tiers[1].reason).toMatch(/storage/i);
  });

  it("requires the shader-f16 feature for the quantized formats", () => {
    const eligibility = computeEligibility(signals({ shaderF16: false }));
    expect(eligibility.tiers.every((d) => !d.eligible)).toBe(true);
    expect(eligibility.tiers[0].reason).toMatch(/16-bit/i);
  });
});

describe("tier navigation", () => {
  it("walks up one rung at a time and stops at the top", () => {
    const eligibility = computeEligibility(signals());
    expect(nextEligibleTier(null, eligibility)?.id).toBe("t1");
    expect(nextEligibleTier("t1", eligibility)?.id).toBe("t2");
    expect(nextEligibleTier("t3", eligibility)).toBeNull();
  });

  it("skips rungs the device can't host", () => {
    const eligibility = computeEligibility(signals({ deviceMemoryGB: 4 }));
    expect(nextEligibleTier("t1", eligibility)?.id).toBe("t2");
    expect(nextEligibleTier("t2", eligibility)).toBeNull();
  });

  it("returns null when nothing fits", () => {
    const eligibility = computeEligibility(signals({ webgpu: false }));
    expect(firstEligibleTier(eligibility)).toBeNull();
    expect(nextEligibleTier(null, eligibility)).toBeNull();
  });

  it("knows its tiers by id", () => {
    expect(tierById("t2").modelId).toContain("3B");
    expect(() => tierById("t9" as never)).toThrow(/Unknown edge tier/);
    expect(EDGE_TIERS.map((tier) => tier.approxBytes)).toEqual([
      1_300_000_000, 2_000_000_000, 4_700_000_000,
    ]);
  });
});

describe("collectDeviceSignals", () => {
  it("reads WebGPU, memory, quota, and save-data behind capability guards", async () => {
    const adapter = { features: { has: vi.fn(() => true) } };
    stubNavigator("gpu", { requestAdapter: vi.fn(async () => adapter) });
    stubNavigator("deviceMemory", 8);
    stubNavigator("storage", { estimate: async () => ({ quota: 100, usage: 20 }) });
    stubNavigator("connection", { saveData: true });

    const collected = await collectDeviceSignals();
    expect(collected).toEqual({
      webgpu: true,
      shaderF16: true,
      vramGB: null,
      deviceMemoryGB: 8,
      freeStorageBytes: 80,
      saveData: true,
    });
  });

  it("degrades to all-unknown in bare jsdom", async () => {
    stubNavigator("gpu", undefined);
    stubNavigator("deviceMemory", undefined);
    stubNavigator("storage", undefined);
    stubNavigator("connection", undefined);
    const collected = await collectDeviceSignals();
    expect(collected.webgpu).toBe(false);
    expect(collected.deviceMemoryGB).toBeNull();
    expect(collected.freeStorageBytes).toBeNull();
    expect(collected.saveData).toBe(false);
  });

  it("treats a null adapter as no WebGPU", async () => {
    stubNavigator("gpu", { requestAdapter: async () => null });
    const collected = await collectDeviceSignals();
    expect(collected.webgpu).toBe(false);
  });
});
