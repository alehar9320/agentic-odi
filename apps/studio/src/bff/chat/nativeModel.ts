/**
 * The browser's own model, behind one small interface.
 *
 * The Studio already knows how to talk to a configured endpoint and how to answer
 * deterministically. This is the third tier: a model that ships with the browser
 * (the Chrome `LanguageModel` API, and its `ai.languageModel` spelling), used only
 * when no endpoint is configured and the model is already on the device.
 *
 * Nothing here reads or writes the canvas. The native model produces prose; the
 * deterministic commands remain the only way a browser-only turn changes anything.
 */

export type NativeAvailability = "available" | "downloadable" | "unavailable";

/** The shape the browser exposes; both spellings answer to this. */
export interface BrowserLanguageModelSession {
  promptStreaming?(text: string, options?: unknown): unknown;
  prompt?(text: string, options?: unknown): Promise<string>;
  destroy?(): void;
}

export interface BrowserLanguageModelApi {
  availability(options?: unknown): Promise<string> | string;
  create(options?: { system?: string; signal?: AbortSignal }): Promise<BrowserLanguageModelSession>;
}

/** One open model session. */
export interface NativeModelSession {
  stream(text: string, signal?: AbortSignal): AsyncIterable<string>;
  destroy(): Promise<void>;
}

export interface NativeModelAdapter {
  availability(): Promise<NativeAvailability>;
  create(options: { system: string; signal?: AbortSignal }): Promise<NativeModelSession>;
}

function abortError(): Error {
  if (typeof DOMException === "function") {
    return new DOMException("Aborted", "AbortError");
  }
  const error = new Error("Aborted");
  error.name = "AbortError";
  return error;
}

function isApi(value: unknown): value is BrowserLanguageModelApi {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as { availability?: unknown; create?: unknown };
  return (
    typeof candidate.availability === "function" && typeof candidate.create === "function"
  );
}

/**
 * The first usable browser model, or nothing.
 *
 * `LanguageModel` is the current global; `ai.languageModel` is the older spelling
 * some builds still expose. A browser with neither gets `null`, which reads as
 * "this device has no model" rather than as an error.
 */
export function resolveNativeModel(
  scope: typeof globalThis = globalThis,
): NativeModelAdapter | null {
  const direct = (scope as { LanguageModel?: unknown }).LanguageModel;
  if (isApi(direct)) {
    return wrapApi(direct);
  }
  const ai = (scope as { ai?: { languageModel?: unknown } }).ai;
  if (ai && isApi(ai.languageModel)) {
    return wrapApi(ai.languageModel);
  }
  return null;
}

function wrapApi(api: BrowserLanguageModelApi): NativeModelAdapter {
  return {
    async availability() {
      try {
        const value = await api.availability();
        return value === "available" || value === "downloadable" ? value : "unavailable";
      } catch {
        // A probe that throws is a model that cannot be used, not one that can.
        return "unavailable";
      }
    },
    async create({ system, signal }) {
      const session = await api.create({ system, signal });
      return wrapSession(session);
    },
  };
}

function wrapSession(session: BrowserLanguageModelSession): NativeModelSession {
  let destroyed = false;
  return {
    async *stream(text, signal) {
      if (signal?.aborted) {
        throw abortError();
      }
      if (typeof session.promptStreaming === "function") {
        // Both a ReadableStream and an async iterable are consumed the same way.
        const chunks = session.promptStreaming(
          text,
          signal ? { signal } : undefined,
        ) as AsyncIterable<unknown>;
        for await (const chunk of chunks) {
          if (signal?.aborted) {
            throw abortError();
          }
          if (typeof chunk === "string" && chunk.length > 0) {
            yield chunk;
          }
        }
        return;
      }
      if (typeof session.prompt !== "function") {
        return;
      }
      const answer = await session.prompt(text, signal ? { signal } : undefined);
      if (signal?.aborted) {
        throw abortError();
      }
      if (typeof answer === "string" && answer.length > 0) {
        yield answer;
      }
    },
    async destroy() {
      if (destroyed) {
        return;
      }
      destroyed = true;
      try {
        session.destroy?.();
      } catch {
        // A session that is already gone is exactly the state we wanted.
      }
    },
  };
}
