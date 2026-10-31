import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createDiagnosticsBundle,
  diagnosticsEntryCount,
  installDiagnosticsConsoleCapture,
  recordStream,
  recordStudioError,
  startDiagnosticsCapture,
} from "./bundle";

const options = {
  version: "1.2.3",
  build: "2026-10-30",
  platform: "Desktop",
  theme: "light",
  reachable: false,
  defaults: null,
  engine: null,
  capabilities: [],
  apiKey: "configured-secret",
};

describe("diagnostics bundle", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not capture before consent and only emits metadata after consent", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    installDiagnosticsConsoleCapture();
    console.warn("PRIVATE-LOG-CANARY");
    recordStudioError({
      code: "internal",
      message: "failed",
      retryable: false,
      request_id: "req-1",
    }, "/api/canvas");
    recordStream({ assistant_id: "assistant-1", frames: 3, terminal: "completed", duration_ms: 8 });

    const beforeConsent = createDiagnosticsBundle(options);
    expect(diagnosticsEntryCount(beforeConsent)).toBe(0);
    expect(warn).toHaveBeenCalledWith("PRIVATE-LOG-CANARY");

    startDiagnosticsCapture();
    console.warn("failure configured-secret", { api_key: "configured-secret" });
    recordStudioError({
      code: "internal",
      message: "failure configured-secret",
      detail: "Bearer abc.def",
      retryable: false,
      request_id: "req-2",
    }, "/api/canvas");
    recordStream({ assistant_id: "assistant-2", frames: 4, terminal: "failed", duration_ms: 12 });

    const bundle = createDiagnosticsBundle(options);
    const serialized = JSON.stringify(bundle);
    expect(serialized).toContain("[redacted]");
    expect(serialized).not.toContain("configured-secret");
    expect(serialized).not.toContain("PRIVATE-LOG-CANARY");
    expect(serialized).not.toContain("abc.def");
    expect(serialized).not.toContain("PRIVATE-CONVERSATION");
    expect(bundle).toMatchObject({ schema: 1, sidecar: { reachable: false }, engine: null });
    expect(bundle).not.toHaveProperty("messages");
    expect(bundle).not.toHaveProperty("canvas");
    expect(diagnosticsEntryCount(bundle)).toBe(3);
  });
});
