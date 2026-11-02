import type { Page } from "@playwright/test";

import type { EdgeLLMEngine, LoadProgress } from "../src/edge/types";

/**
 * The device and the engine the end-to-end suite drives.
 *
 * Neither is product code: `installEdgeDevice` states facts about a machine
 * (a GPU that can run 16-bit models, room on disk) and hands the studio a
 * fake engine, so the bundle under test stays the one a person downloads.
 * A CI browser has no GPU and no 1.3 GB of weights, which is exactly why the
 * engine is replaced here and nothing else is.
 */

/** The answer the fake engine streams, one token at a time. */
export const FAKE_TOKENS = ["Start ", "with the ", "job, ", "then the ", "outcome."];

export async function installEdgeDevice(page: Page): Promise<void> {
  await page.addInitScript((tokens: string[]) => {
    Object.defineProperty(window.navigator, "gpu", {
      configurable: true,
      value: {
        requestAdapter: async () => ({
          features: { has: () => true },
        }),
      },
    });
    Object.defineProperty(window.navigator, "storage", {
      configurable: true,
      value: {
        estimate: async () => ({ quota: 20_000_000_000, usage: 1_000_000 }),
        persist: async () => true,
      },
    });

    const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    /**
     * `implements EdgeLLMEngine` is the point: if the seam the studio calls moves,
     * this stops compiling rather than passing a suite that no longer tests
     * anything. It answers with fixed tokens and ignores the prompt — what the
     * suite follows is the frames a reply is made of, and the prompt and those
     * frames are a unit test's job (`src/edge/turn.test.ts`).
     */
    class FakeEdgeEngine implements EdgeLLMEngine {
      async probe() {
        return { webgpu: true, reasons: [] as string[], tiers: [] };
      }

      // Slow enough that the dock has time to show the fetch it is narrating.
      async load(modelId: string, onProgress: (progress: LoadProgress) => void) {
        onProgress({ phase: "init", percent: 0.05, text: modelId });
        await wait(400);
        onProgress({ phase: "download", percent: 0.4, text: "weights" });
        await wait(400);
        onProgress({ phase: "download", percent: 0.9, text: "weights" });
        await wait(400);
        onProgress({ phase: "ready", percent: 1, text: "ready" });
      }

      async *stream(): AsyncIterable<string> {
        for (const token of tokens) {
          await wait(60);
          yield token;
        }
      }

      async unload() {}

      async evict() {}
    }

    (window as unknown as { __odiEdgeEngine?: () => EdgeLLMEngine }).__odiEdgeEngine =
      () => new FakeEdgeEngine();
  }, FAKE_TOKENS);
}
