const REDACTED = "[redacted]";
const MAX_BYTES = 256 * 1024;
const SENSITIVE_KEY = /api[_-]?key|apikey|authorization|password|secret|token|access_token|refresh_token|quote|transcript|customer_words/i;
const PATH_KEY = /^(?:file|filename|file_name|file_path|path)$|(?:^|_)path$/i;
const BEARER = /\bBearer\s+[A-Za-z0-9._~+/-]+=*/gi;
const EMAIL = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;
const URL_PATTERN = /\b[a-z][a-z0-9+.-]*:\/\/[^\s"'<>]+/gi;
const FORBIDDEN_KEYS = new Set([
  "messages",
  "conversation",
  "conversations",
  "observations",
  "brief",
  "theses",
  "attachments",
  "canvas",
  "entities",
]);

export function redactText(value: string, apiKey = ""): string {
  let result = value;
  if (apiKey) {
    result = result.split(apiKey).join(REDACTED);
  }
  result = result.replace(URL_PATTERN, (raw) => {
    const suffix = raw.match(/[),.;!?]+$/)?.[0] ?? "";
    const candidate = suffix ? raw.slice(0, -suffix.length) : raw;
    try {
      const parsed = new URL(candidate);
      return `${parsed.protocol}//${parsed.host}${parsed.pathname}${suffix}`;
    } catch {
      return REDACTED;
    }
  });
  return result.replace(EMAIL, REDACTED).replace(BEARER, "Bearer [redacted]");
}

function basename(value: string): string {
  return value.split(/[\\/]/).filter(Boolean).at(-1) ?? value;
}

function redactValue(value: unknown, apiKey: string, key = ""): unknown {
  if (key.toLowerCase() === "url" || key.toLowerCase().endsWith("_url")) {
    return typeof value === "string" ? redactText(value, apiKey) : redactValue(value, apiKey);
  }
  if (SENSITIVE_KEY.test(key)) {
    return REDACTED;
  }
  if (FORBIDDEN_KEYS.has(key.toLowerCase())) {
    return undefined;
  }
  if (typeof value === "string") {
    if (PATH_KEY.test(key)) {
      return basename(value);
    }
    return redactText(value, apiKey);
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => redactValue(item, apiKey, key))
      .filter((item) => item !== undefined);
  }
  if (value && typeof value === "object") {
    const output: Record<string, unknown> = {};
    for (const [childKey, childValue] of Object.entries(value)) {
      if (FORBIDDEN_KEYS.has(childKey.toLowerCase())) {
        continue;
      }
      output[childKey] = redactValue(childValue, apiKey, childKey);
    }
    return output;
  }
  return value;
}

function removeOldestEntry(bundle: Record<string, unknown>): boolean {
  const collections = ["errors", "console", "streams"] as const;
  const oldest = collections
    .flatMap((key) => {
      const entries = bundle[key] as Array<{ at?: string }> | undefined;
      return entries?.length ? [{ key, at: entries[0].at ?? "" }] : [];
    })
    .sort((left, right) => left.at.localeCompare(right.at))[0];
  if (!oldest) {
    return false;
  }
  (bundle[oldest.key] as unknown[]).shift();
  return true;
}

function encodedSize(value: unknown): number {
  return new TextEncoder().encode(JSON.stringify(value, null, 2)).length;
}

/** Deep-copy, redact, and bound a diagnostics bundle without retaining work content. */
export function redactBundle<T extends Record<string, unknown>>(input: T, apiKey = ""): T {
  const bundle = redactValue(input, apiKey) as T;
  if (encodedSize(bundle) <= MAX_BYTES) {
    return bundle;
  }

  const truncated = { ...bundle, truncated: true } as T & { truncated: boolean };
  while (encodedSize(truncated) > MAX_BYTES && removeOldestEntry(truncated)) {
    // Drop oldest entries across the rings until the serialized bundle fits.
  }
  return truncated;
}
