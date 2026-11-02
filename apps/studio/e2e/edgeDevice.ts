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

/**
 * The page-side controls `holdNextFetch` / `releaseNextFetch` reach. Installed
 * by the init script below, and only ever used by the two-tab scenario.
 */
interface EdgeDeviceWindow extends Window {
  __odiEdgeHoldFetch?: () => void;
  __odiEdgeReleaseFetch?: () => void;
  __odiEdgeFailNextFetch?: () => void;
}

/**
 * Park the page's next model fetch after its first progress tick, until
 * `releaseNextFetch` is called.
 *
 * The lock the studio takes around a fetch is only held while the engine is
 * loading, so a scenario that wants to meet a second tab at that lock cannot
 * race a 1.2 GB download on a timer. This holds the door open in one tab for as
 * long as the other one needs, which is the only way to make "another tab is
 * already on it" a fact rather than a coincidence.
 */
export async function holdNextFetch(page: Page): Promise<void> {
  await page.evaluate(() => (window as unknown as EdgeDeviceWindow).__odiEdgeHoldFetch?.());
}

/** Let a held fetch finish. Releasing before the fetch parks is not an error:
 * it simply means the fetch was never held. */
export async function releaseNextFetch(page: Page): Promise<void> {
  await page.evaluate(() => (window as unknown as EdgeDeviceWindow).__odiEdgeReleaseFetch?.());
}

/**
 * Make the page's next model fetch throw, once, after it has started.
 *
 * Weights do fail in real life — the network drops, the CDN refuses, the
 * browser rejects the cache — and a scenario cannot wait for that. One armed
 * throw is the only honest way to put the studio in front of a download that
 * stopped, and to make the retry it offers something a test can press.
 */
export async function failNextFetch(page: Page): Promise<void> {
  await page.evaluate(() => (window as unknown as EdgeDeviceWindow).__odiEdgeFailNextFetch?.());
}

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

    // The hold the two-tab scenario arms from outside. Sticky in the direction
    // that matters: releasing first means the fetch simply is not held.
    const gate: { held: boolean; release: (() => void) | null } = {
      held: false,
      release: null,
    };
    (window as unknown as EdgeDeviceWindow).__odiEdgeHoldFetch = () => {
      gate.held = true;
    };
    (window as unknown as EdgeDeviceWindow).__odiEdgeReleaseFetch = () => {
      gate.held = false;
      gate.release?.();
      gate.release = null;
    };

    // Armed once by `failNextFetch`, spent by the next fetch that starts.
    const broken = { next: false };
    (window as unknown as EdgeDeviceWindow).__odiEdgeFailNextFetch = () => {
      broken.next = true;
    };

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
        if (gate.held) {
          gate.held = false;
          await new Promise<void>((resolve) => {
            gate.release = resolve;
          });
        }
        await wait(400);
        onProgress({ phase: "download", percent: 0.4, text: "weights" });
        if (broken.next) {
          // Spent here, so the retry the strip offers is a fetch that works.
          broken.next = false;
          throw new Error("e2e: the weights did not land");
        }
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
