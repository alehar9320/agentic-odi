/**
 * Edge LLM contracts. Everything outside `edge/webllmEngine.ts` depends on
 * these types only, so the engine stays swappable (and fakeable in tests)
 * without touching routing, scheduling, or the UI.
 */

export type EdgeTierId = "t1" | "t2" | "t3";

export interface EdgeTier {
  id: EdgeTierId;
  /** Prebuilt `@mlc-ai/web-llm` model id. */
  modelId: string;
  label: string;
  /** Approximate download size, shown to the user before they consent. */
  approxBytes: number;
  /** `navigator.deviceMemory` floor for the tier to be considered usable. */
  minDeviceMemoryGB: number;
}

export interface DeviceSignals {
  webgpu: boolean;
  /** WebGPU `shader-f16` feature, required by the q4f16 quantizations. */
  shaderF16: boolean;
  /** VRAM estimate when the browser exposes one; null means unknown. */
  vramGB: number | null;
  /** `navigator.deviceMemory`; null on browsers that don't expose it (Safari). */
  deviceMemoryGB: number | null;
  /** Writable storage headroom from `navigator.storage.estimate()`; null unknown. */
  freeStorageBytes: number | null;
  saveData: boolean;
}

export interface TierDecision {
  tier: EdgeTier;
  eligible: boolean;
  /** One human-sentence reason a tier is out of reach, for Settings and banners. */
  reason: string | null;
}

export interface Eligibility {
  webgpu: boolean;
  /** Global blockers that retire every tier; empty when the device can host one. */
  reasons: string[];
  tiers: TierDecision[];
}

export type TierStatus = "empty" | "cached" | "active";

export interface TierState {
  status: TierStatus;
  cachedAt: string | null;
}

export interface EdgeUsage {
  edgeTurns: number;
  streamedSeconds: number;
}

export type ConsentState = "unset" | "granted" | "denied";

export interface EdgeChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface LoadProgress {
  /** Coarse phase for the banner copy: downloading weights, compiling, warming up. */
  phase: "init" | "download" | "reload" | "ready";
  /** 0..1 within `phase`; overall estimate when `total` is set. */
  percent: number;
  text: string;
}

export interface StreamOptions {
  maxTokens?: number;
  temperature?: number;
}

export interface EdgeLLMEngine {
  probe(): Promise<Eligibility>;
  load(modelId: string, onProgress: (progress: LoadProgress) => void): Promise<void>;
  stream(
    messages: EdgeChatMessage[],
    options: StreamOptions,
    signal?: AbortSignal,
  ): AsyncIterable<string>;
  unload(): Promise<void>;
  /** Drop the weights this browser kept for `modelId`, freeing the storage. */
  evict(modelId: string): Promise<void>;
}
