/**
 * Whether a model endpoint is configured, decided in one place.
 *
 * Two callers need the same answer — the chat orchestrator picking a provider and
 * the capability registry reporting what is available — and a disagreement between
 * them shows a person a "no model" warning for an endpoint that is in fact answering.
 *
 * A key is required everywhere except a private network. A loopback or RFC1918 host
 * is on the person's own machine or LAN, where a keyless server (Ollama, LM Studio) is
 * the normal shape; a public host with no key is a misconfiguration, not an endpoint.
 */

export interface ModelEndpointConfig {
  base_url: string;
  api_key: string;
  model: string;
}

/**
 * The sidecar's own proxy, in the shapes a person may actually write it: localhost or
 * 127.0.0.1 or ::1, any case, with or without a trailing slash. It names a loopback
 * address, but it is the sidecar rather than a model server the browser may call
 * directly, so it never counts as a configured endpoint.
 */
function isSidecarProxy(baseUrl: string): boolean {
  let url: URL;
  try {
    url = new URL(baseUrl);
  } catch {
    return false;
  }
  const host = url.hostname.replace(/^\[|\]$/g, "").toLowerCase();
  const loopback = host === "localhost" || host === "::1" || host.startsWith("127.");
  const path = url.pathname.replace(/\/+$/, "").toLowerCase();
  return loopback && url.port === "8001" && path === "/v1";
}

function isPrivateHost(hostname: string): boolean {
  const host = hostname.replace(/^\[|\]$/g, "").toLowerCase();

  if (host === "localhost" || host.endsWith(".localhost") || host === "::1" || host === "0.0.0.0") {
    return true;
  }

  const octets = host.split(".").map((part) => Number(part));
  if (octets.length !== 4 || octets.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) {
    return false;
  }
  const [a, b] = octets;
  return a === 127 || a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168);
}

/** True when a request could be sent to this endpoint right now. */
export function isEndpointConfigured(config: ModelEndpointConfig): boolean {
  const baseUrl = config.base_url.trim();
  if (!baseUrl || !config.model.trim()) {
    return false;
  }
  if (isSidecarProxy(baseUrl)) {
    return false;
  }
  if (config.api_key.trim()) {
    return true;
  }

  let hostname: string;
  try {
    hostname = new URL(baseUrl).hostname;
  } catch {
    return false;
  }
  return isPrivateHost(hostname);
}

/** The same question asked of stored settings, which name the field differently. */
export function isEndpointConfiguredForSettings(settings: {
  base_url: string;
  api_key: string;
  model_name: string;
}): boolean {
  return isEndpointConfigured({
    base_url: settings.base_url,
    api_key: settings.api_key,
    model: settings.model_name,
  });
}
