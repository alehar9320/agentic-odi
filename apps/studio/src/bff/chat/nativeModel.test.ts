import { afterEach, describe, expect, it, vi } from "vitest";

import { resolveNativeModel, type BrowserLanguageModelApi } from "./nativeModel";

function stubLanguageModel(api: Partial<BrowserLanguageModelApi>): void {
  vi.stubGlobal("LanguageModel", api);
}

describe("resolveNativeModel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns nothing when the browser has no built-in model", () => {
    expect(resolveNativeModel()).toBeNull();
  });

  it("prefers the LanguageModel global over ai.languageModel", () => {
    stubLanguageModel({ availability: vi.fn(), create: vi.fn() });
    const adapter = resolveNativeModel();
    expect(adapter).not.toBeNull();
  });

  it("falls back to ai.languageModel when the global is absent", () => {
    vi.stubGlobal("ai", {
      languageModel: { availability: vi.fn(), create: vi.fn() },
    });
    expect(resolveNativeModel()).not.toBeNull();
  });

  it("ignores an object that cannot report availability", () => {
    stubLanguageModel({ create: vi.fn() });
    expect(resolveNativeModel()).toBeNull();
  });
});

describe("NativeModelAdapter availability", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("names a ready model available and a downloadable one not", async () => {
    stubLanguageModel({
      availability: vi.fn(async () => "available"),
      create: vi.fn(),
    });
    const adapter = resolveNativeModel();
    expect(await adapter!.availability()).toBe("available");

    stubLanguageModel({
      availability: vi.fn(async () => "downloadable"),
      create: vi.fn(),
    });
    expect(await resolveNativeModel()!.availability()).toBe("downloadable");
  });

  it("never lets a probe failure look like a ready model", async () => {
    stubLanguageModel({
      availability: vi.fn(async () => {
        throw new Error("probe exploded");
      }),
      create: vi.fn(),
    });
    expect(await resolveNativeModel()!.availability()).toBe("unavailable");
  });
});

describe("NativeModelAdapter session", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("yields from promptStreaming when the session has it", async () => {
    const session = {
      promptStreaming: vi.fn(() =>
        new ReadableStream<string>({
          start(controller) {
            controller.enqueue("prose ");
            controller.enqueue("answer");
            controller.close();
          },
        }),
      ),
      prompt: vi.fn(),
      destroy: vi.fn(),
    };
    stubLanguageModel({
      availability: vi.fn(async () => "available"),
      create: vi.fn(async () => session),
    });

    const adapter = resolveNativeModel()!;
    const created = await adapter.create({ system: "system prompt" });
    const chunks: string[] = [];
    for await (const chunk of created.stream("hello")) {
      chunks.push(chunk);
    }
    expect(chunks.join("")).toBe("prose answer");
    expect(session.prompt).not.toHaveBeenCalled();
  });

  it("falls back to a single prompt result when streaming is absent", async () => {
    const session = {
      prompt: vi.fn(async () => "one answer"),
      destroy: vi.fn(),
    };
    stubLanguageModel({
      availability: vi.fn(async () => "available"),
      create: vi.fn(async () => session),
    });

    const created = await resolveNativeModel()!.create({ system: "s" });
    const chunks: string[] = [];
    for await (const chunk of created.stream("hello")) {
      chunks.push(chunk);
    }
    expect(chunks).toEqual(["one answer"]);
  });

  it("surfaces an abort as AbortError rather than a wrapped failure", async () => {
    const controller = new AbortController();
    const session = {
      promptStreaming: vi.fn(() =>
        new ReadableStream<string>({
          start(streamController) {
            controller.abort();
            streamController.enqueue("partial");
            streamController.close();
          },
        }),
      ),
      destroy: vi.fn(),
    };
    stubLanguageModel({
      availability: vi.fn(async () => "available"),
      create: vi.fn(async () => session),
    });

    const created = await resolveNativeModel()!.create({ system: "s" });
    await expect(async () => {
      for await (const _chunk of created.stream("hello", controller.signal)) {
        void _chunk;
      }
    }).rejects.toMatchObject({ name: "AbortError" });
  });

  it("destroys once and stays quiet if the session cannot be destroyed", async () => {
    const session = {
      prompt: vi.fn(async () => "answer"),
      destroy: vi.fn(() => {
        throw new Error("already gone");
      }),
    };
    stubLanguageModel({
      availability: vi.fn(async () => "available"),
      create: vi.fn(async () => session),
    });

    const created = await resolveNativeModel()!.create({ system: "s" });
    await expect(created.destroy()).resolves.toBeUndefined();
    await expect(created.destroy()).resolves.toBeUndefined();
    expect(session.destroy).toHaveBeenCalledTimes(1);
  });
});
