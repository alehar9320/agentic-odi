/**
 * What Settings accepts before it writes anything.
 *
 * The check lives here, not at a service, so a value the studio cannot use is
 * answered beside the field that holds it and the last good value stays in
 * effect. A reason returned from these functions is the text after "Not saved — ".
 */

export function validateUrl(value: string, example: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return `Enter a full URL, like ${example}.`;
  }
  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    return `Enter a full URL, like ${example}.`;
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return "Use an http:// or https:// address.";
  }
  return null;
}

export function validateBaseUrl(value: string): string | null {
  return validateUrl(value, "http://localhost:8001/v1");
}

export function validateMcpUrl(value: string): string | null {
  return validateUrl(value, "http://localhost:8000/mcp");
}

export function validateModelName(value: string): string | null {
  return value.trim() ? null : "Enter the model name your endpoint serves.";
}

/** A key is optional on a private network, so any value — including none — is fine. */
export function validateApiKey(): string | null {
  return null;
}
