/**
 * Free-plan Living Studio Worker.
 *
 * Workers Static Assets serve the built SPA from `apps/studio/dist`. Requests under
 * `/api/*` are forwarded to the Python sidecar (`apps/studio-api`), which runs on
 * the developer's machine and is published by a free Cloudflare Quick Tunnel.
 * (Running the sidecar inside Cloudflare requires Workers Containers, which is
 * a paid-plan feature.)
 *
 * When `SIDECAR_URL` is absent, the Worker answers `/api/capabilities` with a
 * local-only manifest so the browser BFF can run fully offline. Every other
 * `/api/*` request returns a 502. The browser BFF then serves canvas data,
 * memory, conversations, and the deterministic assistant from IndexedDB.
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

function sidecarError(detail: string, env: Env): Response {
  return secure(Response.json({ detail }, { status: 502 }), env);
}

function localCapabilitiesResponse(env: Env): Response {
  return secure(Response.json(LOCAL_CAPABILITIES), env);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

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
      return sidecarError("SIDECAR_URL is not configured", env);
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
      return sidecarError(
        `Sidecar unreachable: ${(error as Error).message}`,
        env,
      );
    }
  },
} satisfies ExportedHandler<Env>;
