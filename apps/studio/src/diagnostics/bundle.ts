import type { StudioError } from "../types";
import { redactBundle } from "./redact";

export interface DiagnosticError extends StudioError {
  at: string;
  route: string;
}

export interface DiagnosticConsoleEntry {
  at: string;
  level: "error" | "warn";
  args: string[];
}

export interface DiagnosticStream {
  assistant_id: string;
  frames: number;
  terminal: "completed" | "failed" | "stopped";
  duration_ms: number;
}

export interface DiagnosticsBundleOptions {
  version: string;
  build: string;
  platform: string;
  theme: string;
  reachable: boolean;
  defaults: object | null;
  engine: object | null;
  capabilities: unknown[];
  apiKey: string;
}

interface RecordedStream extends DiagnosticStream {
  at: string;
}

const errors: DiagnosticError[] = [];
const consoleEntries: DiagnosticConsoleEntry[] = [];
const streams: RecordedStream[] = [];
let captureStarted = false;
let consoleCaptureInstalled = false;

function append<T>(ring: T[], value: T, limit: number): void {
  ring.push(value);
  if (ring.length > limit) {
    ring.splice(0, ring.length - limit);
  }
}

/** Install pass-through wrappers at boot; they store nothing until consent. */
function consoleArgument(arg: unknown): string {
  try {
    return String(arg);
  } catch {
    return "[unavailable]";
  }
}

export function installDiagnosticsConsoleCapture(): void {
  if (consoleCaptureInstalled) {
    return;
  }
  consoleCaptureInstalled = true;
  for (const level of ["error", "warn"] as const) {
    const original = console[level];
    console[level] = function (...args: unknown[]): void {
      if (captureStarted) {
        append(
          consoleEntries,
          {
            at: new Date().toISOString(),
            level,
            args: args.map(consoleArgument),
          },
          100,
        );
      }
      original.apply(console, args);
    };
  }
}

/** Enable tab-memory-only diagnostic capture after the user presses the button. */
export function startDiagnosticsCapture(): void {
  installDiagnosticsConsoleCapture();
  captureStarted = true;
}

export function recordStudioError(error: StudioError, route?: string): void {
  if (!captureStarted) {
    return;
  }
  append(
    errors,
    {
      at: new Date().toISOString(),
      code: error.code,
      message: error.message,
      detail: error.detail ?? null,
      suggestion: error.suggestion ?? null,
      retryable: error.retryable,
      request_id: error.request_id ?? null,
      route: route ?? (typeof window === "undefined" ? "unknown" : window.location.pathname),
    },
    50,
  );
}

/** Count stream events only; never accept or retain their payloads. */
export function recordStream(stream: DiagnosticStream): void {
  if (captureStarted) {
    append(streams, { ...stream, at: new Date().toISOString() }, 20);
  }
}

export function createDiagnosticsBundle(options: DiagnosticsBundleOptions): Record<string, unknown> {
  const defaults = options.defaults ? { ...options.defaults } : null;
  if (defaults && "api_key" in defaults) {
    defaults.api_key = "[redacted]";
  }
  const candidate = {
    schema: 1,
    app: {
      version: options.version,
      build: options.build,
      platform: options.platform,
      theme: options.theme,
    },
    sidecar: {
      reachable: options.reachable,
      defaults,
    },
    engine: options.engine,
    capabilities: options.capabilities,
    errors: [...errors],
    console: [...consoleEntries],
    streams: [...streams],
  };
  const bundle = redactBundle(candidate, options.apiKey) as Record<string, unknown>;
  bundle.streams = (bundle.streams as RecordedStream[]).map((stream) => {
    const output: DiagnosticStream = {
      assistant_id: stream.assistant_id,
      frames: stream.frames,
      terminal: stream.terminal,
      duration_ms: stream.duration_ms,
    };
    return output;
  });
  return bundle;
}

export function diagnosticsEntryCount(bundle: Record<string, unknown>): number {
  return ["errors", "console", "streams"].reduce((total, key) => {
    const entries = bundle[key];
    return total + (Array.isArray(entries) ? entries.length : 0);
  }, 0);
}
