/**
 * Free-plan Living Studio Worker.
 *
 * Workers Static Assets serve the built SPA from `apps/studio/dist`. Requests under
 * `/api/*` are forwarded to the Python sidecar (`apps/studio-api`), which runs on
 * the developer's machine and is published by a free Cloudflare Quick Tunnel.
 * (Running the sidecar inside Cloudflare requires Workers Containers, which is
 * a paid-plan feature.)
 */

interface Env {
  ASSETS: Fetcher;
  /** Public origin of the sidecar, e.g. https://random.trycloudflare.com */
  SIDECAR_URL?: string;
}

const API_PREFIX = "/api/";

/**
 * Defense-in-depth headers on every Response, assets and API alike.
 *
 * The SPA loads only its own bundle, talks to the Worker origin at `/api/*`, and
 * uses React inline styles, hence `'unsafe-inline'` for styles but nothing for
 * scripts. `connect-src 'self'` keeps a compromised bundle from exfiltrating
 * to another origin; `frame-ancestors` repeats the `X-Frame-Options` intent for
 * browsers that only honor the CSP directive.
 */
const SECURITY_HEADERS: Record<string, string> = {
  "Content-Security-Policy": [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "connect-src 'self'",
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

function secure(response: Response): Response {
  const headers = new Headers(response.headers);
  for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
    headers.set(name, value);
  }
  // Reuse the body stream so SSE (`/api/chat`) keeps streaming.
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function sidecarError(detail: string): Response {
  return Response.json({ detail }, { status: 502 });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (!url.pathname.startsWith(API_PREFIX)) {
      return secure(await env.ASSETS.fetch(request));
    }

    const sidecar = env.SIDECAR_URL?.trim().replace(/\/+$/, "");
    if (!sidecar) {
      return secure(sidecarError("SIDECAR_URL is not configured"));
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
      );
    } catch (error) {
      return secure(sidecarError(`Sidecar unreachable: ${(error as Error).message}`));
    }
  },
} satisfies ExportedHandler<Env>;
