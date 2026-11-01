/**
 * The one file that knows `@mlc-ai/web-llm` exists. Loaded lazily, after the
 * device probe has passed, so the WebLLM chunk never costs a visitor who
 * can't (or won't) run a browser model. Everything upstream codes against
 * `EdgeLLMEngine` in ./types.ts.
 */

import { CreateMLCEngine } from "@mlc-ai/web-llm";
import type { InitProgressReport, MLCEngineInterface } from "@mlc-ai/web-llm";

import type {
  EdgeLLMEngine,
  Eligibility,
  LoadProgress,
} from "./types";
import { collectDeviceSignals, computeEligibility } from "./ladder";

// A conversational answer from a 1-8B quantized model rarely needs more;
// keeping the window honest is what stops small devices from stalling.
const DEFAULT_MAX_TOKENS = 512;

function toLoadProgress(report: InitProgressReport): LoadProgress {
  const text = report.text ?? "";
  const phase: LoadProgress["phase"] = text.includes("Download")
    ? "download"
    : text.includes("Load") || text.includes("cache")
      ? "reload"
      : text.includes("Finish") || text.includes("compiled")
        ? "ready"
        : "init";
  return { phase, percent: report.progress, text };
}

export function createWebLLMEngine(): EdgeLLMEngine {
  let engine: MLCEngineInterface | null = null;
  let loadedModelId: string | null = null;

  return {
    async probe(): Promise<Eligibility> {
      return computeEligibility(await collectDeviceSignals());
    },

    async load(modelId, onProgress) {
      const initProgressCallback = (report: InitProgressReport) =>
        onProgress(toLoadProgress(report));
      if (!engine) {
        engine = (await CreateMLCEngine(modelId, { initProgressCallback })) as MLCEngineInterface;
      } else if (loadedModelId !== modelId) {
        engine.setInitProgressCallback(initProgressCallback);
        await engine.reload(modelId);
      }
      loadedModelId = modelId;
    },

    async *stream(messages, options, signal) {
      if (!engine || !loadedModelId) {
        throw new Error("Edge engine used before a model was loaded.");
      }
      const active = engine;
      let aborted = false;
      const onAbort = () => {
        aborted = true;
        active.interruptGenerate();
      };
      signal?.addEventListener("abort", onAbort, { once: true });
      try {
        const response = await active.chat.completions.create({
          messages,
          stream: true,
          max_tokens: options.maxTokens ?? DEFAULT_MAX_TOKENS,
          temperature: options.temperature ?? 0.6,
        });
        for await (const chunk of response) {
          if (aborted) {
            break;
          }
          const delta = chunk.choices[0]?.delta?.content;
          if (delta) {
            yield delta;
          }
        }
      } finally {
        signal?.removeEventListener("abort", onAbort);
      }
    },

    async unload() {
      if (engine) {
        await engine.unload();
      }
      loadedModelId = null;
    },
  };
}
