/**
 * A scripted stand-in for the WebLLM engine. The jsdom suite and the
 * Playwright specs have no WebGPU, so every test that needs to *see* an
 * edge reply drives this instead — it is the only honest way to test the
 * routing seam in CI.
 */

import type {
  EdgeLLMEngine,
  Eligibility,
  LoadProgress,
  StreamOptions,
} from "../edge/types";
import { computeEligibility } from "../edge/ladder";

export interface FakeEngineOptions {
  tokens?: string[];
  failWith?: Error;
  /** Eligibility `probe()` reports; defaults to a healthy desktop. */
  eligibility?: Eligibility;
  onStreamStart?: () => void;
}

export class FakeEdgeEngine implements EdgeLLMEngine {
  loads: string[] = [];
  private options: FakeEngineOptions;

  constructor(options: FakeEngineOptions = {}) {
    this.options = options;
  }

  async probe(): Promise<Eligibility> {
    return (
      this.options.eligibility ??
      computeEligibility({
        webgpu: true,
        shaderF16: true,
        vramGB: null,
        deviceMemoryGB: 16,
        freeStorageBytes: 40_000_000_000,
        saveData: false,
      })
    );
  }

  async load(modelId: string, onProgress: (p: LoadProgress) => void): Promise<void> {
    this.loads.push(modelId);
    onProgress({ phase: "download", percent: 0.5, text: "Download 50%" });
    onProgress({ phase: "ready", percent: 1, text: "Finish" });
  }

  async *stream(
    _messages: unknown,
    _options: StreamOptions,
    signal?: AbortSignal,
  ): AsyncIterable<string> {
    this.options.onStreamStart?.();
    if (this.options.failWith) {
      throw this.options.failWith;
    }
    const tokens = this.options.tokens ?? ["Hello", " from", " the", " edge."];
    for (const token of tokens) {
      if (signal?.aborted) {
        return;
      }
      yield token;
    }
  }

  async unload(): Promise<void> {
    // Nothing to release.
  }
}
