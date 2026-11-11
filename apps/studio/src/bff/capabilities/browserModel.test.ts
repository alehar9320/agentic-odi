import { describe, expect, it } from "vitest";

import { browserModelProbe } from "./browserModel";

describe("browserModelProbe", () => {
  it("maps the new availability() values", async () => {
    for (const [value, status] of [
      ["available", "available"],
      ["readily", "available"],
      ["downloadable", "downloadable"],
      ["after-download", "downloadable"],
      ["downloading", "downloadable"],
    ] as const) {
      const probe = browserModelProbe({ LanguageModel: { availability: () => value } });
      await expect(probe.availability()).resolves.toMatchObject({ status });
    }
  });

  it("reports unavailable with no reason when there is no global", async () => {
    const probe = browserModelProbe({});
    await expect(probe.availability()).resolves.toEqual({ status: "unavailable" });
  });

  it("maps the legacy ai.languageModel global", async () => {
    const probe = browserModelProbe({ ai: { languageModel: { availability: () => "available" } } });
    await expect(probe.availability()).resolves.toMatchObject({ status: "available" });
  });

  it("names WebGPU and claims no model when only navigator.gpu is present", async () => {
    const probe = browserModelProbe({ navigator: { gpu: {} } });
    const result = await probe.availability();
    expect(result.status).toBe("unavailable");
    expect(result.reason).toMatch(/WebGPU/);
  });

  it("resolves a throwing availability() to unavailable with the error, never rejects", async () => {
    const probe = browserModelProbe({
      LanguageModel: {
        availability: () => {
          throw new Error("boom");
        },
      },
    });
    await expect(probe.availability()).resolves.toEqual({
      status: "unavailable",
      reason: "boom",
    });
  });

  it("reports an unknown availability value as unavailable", async () => {
    const probe = browserModelProbe({ LanguageModel: { availability: () => "maybe" } });
    await expect(probe.availability()).resolves.toMatchObject({ status: "unavailable" });
  });

  it("gives a downloadable model a reason", async () => {
    const probe = browserModelProbe({ LanguageModel: { availability: () => "downloadable" } });
    const result = await probe.availability();
    expect(result.status).toBe("downloadable");
    expect(result.reason).toBeTruthy();
  });

  it("exposes the last reason through reason(), and null once the model is ready", async () => {
    const probe = browserModelProbe({ LanguageModel: { availability: () => "downloadable" } });
    await probe.availability();
    expect(probe.reason()).toBeTruthy();

    const ready = browserModelProbe({ LanguageModel: { availability: () => "available" } });
    await ready.availability();
    expect(ready.reason()).toBeNull();
  });
});
