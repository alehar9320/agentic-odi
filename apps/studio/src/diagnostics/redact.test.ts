import { describe, expect, it } from "vitest";

import { redactBundle, redactText } from "./redact";

describe("redactText", () => {
  it("removes the configured key, bearer tokens, email addresses, and URL credentials and queries", () => {
    const text = redactText(
      "api=live-key Bearer abc.def@mail.example https://user:pass@example.com/a/path?token=hidden#frag",
      "live-key",
    );

    expect(text).not.toContain("live-key");
    expect(text).not.toContain("abc.def");
    expect(text).not.toContain("user:pass");
    expect(text).not.toContain("token=hidden");
    expect(text).not.toContain("@example");
    expect(text).toContain("https://example.com/a/path");
  });
});

describe("redactBundle", () => {
  it("recursively redacts sensitive keys and reduces path fields to basenames", () => {
    const result = redactBundle(
      {
        context: [{ nested: { api_key: "secret", refresh_token: "refresh", label: "safe" } }],
        error: { file_path: "C:\\private\\work\\source.ts", module_path: "/private/module.py", message: "failed" },
        url: "https://user:secret@example.com/api/diagnostics?token=secret",
      },
      "live-key",
    );

    expect(result).toEqual({
      context: [{ nested: { api_key: "[redacted]", refresh_token: "[redacted]", label: "safe" } }],
      error: { file_path: "source.ts", module_path: "module.py", message: "failed" },
      url: "https://example.com/api/diagnostics",
    });
  });

  it("removes configured keys from nested free text", () => {
    const result = redactBundle(
      {
        context: {
          nested: {
            api_key: "live-secret",
            apikey: "apikey-secret",
            authorization: "Bearer auth-secret",
            password: "password-secret",
            secret: "secret-value",
            token: "token-value",
            access_token: "access-value",
            refresh_token: "refresh-value",
            quote: "private quote",
            transcript: "private transcript",
            customer_words: "private words",
          },
        },
        errors: [{ message: "request failed for live-secret" }],
        defaults: {
          base_url: "https://user:pass@example.com/v1?token=live-secret",
          mcp_url: "http://user:pass@localhost:8000/mcp?api_key=live-secret",
        },
      },
      "live-secret",
    );

    const serialized = JSON.stringify(result);
    expect(serialized).not.toContain("live-secret");
    expect(serialized).not.toContain("user:pass");
    expect(serialized).not.toContain("token=");
    expect(serialized).not.toContain("api_key=");
    expect(result).toMatchObject({
      context: {
        nested: {
          api_key: "[redacted]",
          apikey: "[redacted]",
          authorization: "[redacted]",
          password: "[redacted]",
          secret: "[redacted]",
          token: "[redacted]",
          access_token: "[redacted]",
          refresh_token: "[redacted]",
          quote: "[redacted]",
          transcript: "[redacted]",
          customer_words: "[redacted]",
        },
      },
      defaults: {
        base_url: "https://example.com/v1",
        mcp_url: "http://localhost:8000/mcp",
      },
    });
  });

  it("never carries seeded conversation content, even when passed alongside bundle fields", () => {
    const canary = "PRIVATE-CONVERSATION-CANARY customer words";
    const result = redactBundle({
      schema: 1,
      errors: [],
      console: [],
      streams: [{ assistant_id: "a-1", frames: 4, terminal: "completed", duration_ms: 50 }],
      messages: [{ role: "user", content: canary }],
      observations: [{ text: canary }],
      brief: { problem: canary },
      theses: [{ text: canary }],
      attachments: [{ text: canary }],
      canvas: { entities: [{ name: canary }] },
    } as unknown as Record<string, unknown>);

    expect(JSON.stringify(result)).not.toContain(canary);
  });

  it("drops oldest diagnostic entries first when the bundle exceeds 256 KiB", () => {
    const large = "x".repeat(90_000);
    const result = redactBundle({
      errors: [
        { at: "2026-01-01T00:00:00.000Z", message: large },
        { at: "2026-01-02T00:00:00.000Z", message: large },
        { at: "2026-01-03T00:00:00.000Z", message: large },
      ],
      console: [],
      streams: [],
    });

    expect((result as Record<string, unknown>).truncated).toBe(true);
    expect((result.errors as Array<{ at: string }>)[0].at).not.toBe("2026-01-01T00:00:00.000Z");
    expect(new TextEncoder().encode(JSON.stringify(result, null, 2)).length).toBeLessThanOrEqual(256 * 1024);
  });
});
