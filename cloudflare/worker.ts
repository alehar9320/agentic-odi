/**
 * Free-plan Living Studio Worker.
 *
 * Workers Static Assets serve the built SPA from `studio/dist`. Requests under
 * `/api/*` are forwarded to the Python sidecar (`local_server`), which runs on
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

function sidecarError(detail: string): Response {
  return Response.json({ detail }, { status: 502 });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (!url.pathname.startsWith(API_PREFIX)) {
      return env.ASSETS.fetch(request);
    }

    const sidecar = env.SIDECAR_URL?.trim().replace(/\/+$/, "");
    if (!sidecar) {
      return sidecarError("SIDECAR_URL is not configured");
    }

    // The Quick Tunnel routes by hostname, so the Worker's Host must not leak.
    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.delete("cf-connecting-ip");

    const target = new URL(`${url.pathname}${url.search}`, `${sidecar}/`);

    try {
      // Returning the upstream Response directly preserves SSE streaming for
      // `/api/chat`.
      return await fetch(
        new Request(target, {
          method: request.method,
          headers,
          body: request.body,
          redirect: "manual",
        }),
      );
    } catch (error) {
      return sidecarError(`Sidecar unreachable: ${(error as Error).message}`);
    }
  },
} satisfies ExportedHandler<Env>;
