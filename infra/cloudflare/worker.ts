/**
 * Free-plan Living Studio Worker.
 *
 * Workers Static Assets serve the built SPA from `apps/studio/dist`. Requests
 * under `/api/*` are forwarded to the Python sidecar (`apps/studio-api`), which
 * runs on the developer's machine and is published by a free Cloudflare Quick
 * Tunnel. (Running the sidecar inside Cloudflare requires Workers Containers,
 * which is a paid-plan feature.)
 *
 * When `SIDECAR_URL` is absent, the Worker answers `/api/capabilities` with a
 * local-only manifest so the browser BFF can run fully offline. Every other
 * `/api/*` request returns a 502 carrying the shared `{"error": StudioError}`
 * shape, so a dead tunnel reads as a recoverable, actionable failure instead of
 * a blank page or a legacy `{"detail": ...}` blob. The browser BFF then serves
 * canvas data, memory, conversations, and the deterministic assistant from
 * IndexedDB.
 */

interface Env {
  ASSETS: Fetcher;
  /** Public origin of the sidecar, e.g. https://random.trycloudflare.com */
  SIDECAR_URL?: string;
  /** Comma/space-separated extra origins the browser may call directly for a
   * model endpoint, e.g. "https://api.myprovider.com". Curated defaults are
   * always included. */
  LLM_ORIGINS?: string;
}

const API_PREFIX = "/api/";

/**
 * Capabilities the Worker can guarantee without any sidecar: local-only data,
 * memory, and the deterministic assistant. Everything that needs a sidecar
 * (connectors, MCP, model proxy, import) is unavailable until one is reachable.
 */
const LOCAL_CAPABILITIES = {
  capabilities: [
    {
      id: "local-data",
      label: "Local canvas data",
      description: "Jobs, steps, and outcomes stored in your browser.",
      available: true,
    },
    {
      id: "local-memory",
      label: "Local memory and conversations",
      description: "Observations, conversation history, and context stored locally.",
      available: true,
    },
    {
      id: "deterministic-assistant",
      label: "Deterministic assistant",
      description: "Answers about your canvas and updates it without a model.",
      available: true,
    },
    {
      id: "browser-model",
      label: "Browser built-in model",
      description: "Uses the browser's built-in large language model when present.",
      available: false,
    },
    {
      id: "endpoint-model",
      label: "Configured model endpoint",
      description: "Calls the model endpoint you configured in Settings directly.",
      available: false,
    },
    {
      id: "sidecar-llm",
      label: "Sidecar model proxy",
      description: "Streams model responses through the local Python sidecar.",
      available: false,
    },
    {
      id: "sidecar-connectors",
      label: "Sidecar connectors",
      description: "Adds third-party data sources through the sidecar.",
      available: false,
    },
    {
      id: "sidecar-mcp",
      label: "Sidecar MCP",
      description: "Runs MCP servers through the sidecar.",
      available: false,
    },
    {
      id: "sidecar-import",
      label: "Sidecar import",
      description: "Imports canvas data and memory from a reachable sidecar.",
      available: false,
    },
  ],
} satisfies Record<string, unknown>;

/** Curated provider origins the browser may call directly in hosted mode. */
const DEFAULT_LLM_ORIGINS = [
  "https://api.openai.com",
  "https://api.anthropic.com",
  "https://generativelanguage.googleapis.com",
  "http://localhost:*",
  "http://127.0.0.1:*",
];

function buildConnectSrc(env: Env): string {
  const configured = env.LLM_ORIGINS
    ? String(env.LLM_ORIGINS)
        .split(/[,;\s]+/)
        .filter(Boolean)
    : [];
  return [...DEFAULT_LLM_ORIGINS, ...configured].join(" ");
}

function securityHeaders(env: Env): Record<string, string> {
  return {
    "Content-Security-Policy": [
      "default-src 'self'",
      "script-src 'self'",
      "style-src 'self' 'unsafe-inline'",
      `connect-src 'self' ${buildConnectSrc(env)}`.replace(/\s+/g, " ").trim(),
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
    ].join("; "),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
  };
}

function secure(response: Response, env: Env): Response {
  const headers = new Headers(response.headers);
  for (const [name, value] of Object.entries(securityHeaders(env))) {
    headers.set(name, value);
  }
  // Reuse the body stream so SSE (`/api/chat`) keeps streaming.
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

/** The one error body every Worker-generated failure carries. */
interface StudioError {
  code: string;
  message: string;
  suggestion?: string;
  retryable?: boolean;
  request_id?: string | null;
}

/**
 * Build a Worker-originated failure as the shared `{"error": StudioError}` the
 * sidecar returns, so a dead tunnel reads as a recoverable, actionable failure
 * instead of a blank page or a legacy `{"detail": ...}` blob. The returned
 * Response is wrapped with `secure(...)` by its callers.
 */
function sidecarError(error: StudioError, requestId: string | null): Response {
  return Response.json(
    {
      error: {
        code: error.code,
        message: error.message,
        suggestion: error.suggestion ?? null,
        retryable: error.retryable ?? false,
        request_id: requestId,
      },
    },
    { status: 502 },
  );
}

function localCapabilitiesResponse(env: Env): Response {
  return secure(Response.json(LOCAL_CAPABILITIES), env);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const requestId = request.headers.get("X-Request-ID");

    if (!url.pathname.startsWith(API_PREFIX)) {
      return secure(await env.ASSETS.fetch(request), env);
    }

    const sidecar = env.SIDECAR_URL?.trim().replace(/\/+$/, "");

    // Without a sidecar the Worker can still serve a local-only capabilities
    // manifest so the browser BFF knows what works offline. Anything else
    // under /api needs the sidecar.
    if (!sidecar) {
      if (url.pathname === "/api/capabilities" || url.pathname === "/api/capabilities/") {
        return localCapabilitiesResponse(env);
      }
      console.error(
        "sidecar proxy: SIDECAR_URL is not configured (request_id=%s)",
        requestId ?? "-",
      );
      return secure(
        sidecarError(
          {
            code: "mcp_unreachable",
            message: "The studio sidecar isn't configured.",
            suggestion: "Set SIDECAR_URL and redeploy.",
            retryable: false,
          },
          requestId,
        ),
        env,
      );
    }

    // The Quick Tunnel routes by hostname, so the Worker's Host must not leak.
    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.delete("cf-connecting-ip");

    const target = new URL(`${url.pathname}${url.search}`, `${sidecar}/`);

    try {
      // Returning the upstream Response directly preserves SSE streaming for
      // `/api/chat`.
      return secure(
        await fetch(
          new Request(target, {
            method: request.method,
            headers,
            body: request.body,
            redirect: "manual",
          }),
        ),
        env,
      );
    } catch (error) {
      const cause = error instanceof Error ? error.message : String(error);
      console.error(
        "sidecar proxy: sidecar unreachable at %s (request_id=%s): %s",
        sidecar,
        requestId ?? "-",
        cause,
      );
      return secure(
        sidecarError(
          {
            code: "mcp_unreachable",
            message: "The studio sidecar isn't reachable.",
            suggestion: "Start the sidecar locally (python scripts/dev.py), then try again.",
            retryable: true,
          },
          requestId,
        ),
        env,
      );
    }
  },
} satisfies ExportedHandler<Env>;
