/**
 * The vendor boundary, as data.
 *
 * `src/vendor` holds copied presentation: it takes props and renders. The
 * moment a copied file imports product state, the API client, the assistant
 * bridge, or the BFF, it is no longer vendor — it is application code that a
 * future re-copy cannot replace. Lint forbids the aliased forms; this module
 * resolves every specifier against the importing file, which a string pattern
 * cannot do.
 */

export const FORBIDDEN_SLICES = ["state", "api", "assistant", "bff"] as const;

export type ForbiddenSlice = (typeof FORBIDDEN_SLICES)[number];

const VENDOR_ROOT = "src/vendor";

/** Every module specifier a source imports or re-exports, in order. */
const SPECIFIER = /(?:^|[^.\w])(?:from|import)\s*\(?\s*["']([^"']+)["']/g;

function firstSegment(path: string): string {
  const withoutSrc = path.startsWith("src/") ? path.slice("src/".length) : path;
  return withoutSrc.split("/")[0] ?? "";
}

function isForbiddenSliceName(segment: string): segment is ForbiddenSlice {
  return (FORBIDDEN_SLICES as readonly string[]).includes(segment);
}

/** `src/vendor/components/ui` + `../assistant/plan` -> `src/vendor/components/assistant/plan`. */
export function resolveRelative(fromPath: string, specifier: string): string {
  const parts = fromPath.split("/").slice(0, -1);
  for (const part of specifier.split("/")) {
    if (part === "" || part === ".") {
      continue;
    }
    if (part === "..") {
      parts.pop();
    } else {
      parts.push(part);
    }
  }
  return parts.join("/");
}

/** Why a specifier crosses the boundary, or null when it stays inside it. */
export function boundaryViolation(specifier: string, fromPath: string): string | null {
  if (specifier.startsWith("@/")) {
    const segment = firstSegment(specifier.slice("@/".length));
    return isForbiddenSliceName(segment) ? `@/${segment} is a product slice` : null;
  }
  if (!specifier.startsWith(".")) {
    return null;
  }
  const resolved = resolveRelative(fromPath, specifier);
  if (resolved === VENDOR_ROOT || resolved.startsWith(`${VENDOR_ROOT}/`)) {
    return null;
  }
  const segment = firstSegment(resolved);
  return isForbiddenSliceName(segment) ? `${specifier} leaves the vendor tree for ${segment}` : null;
}

/**
 * The offending specifiers in one source file.
 *
 * `fromPath` is repo-relative, e.g. `src/vendor/components/ui/card.tsx`.
 */
export function forbiddenImports(source: string, fromPath = `${VENDOR_ROOT}/unknown.ts`): string[] {
  const offenders: string[] = [];
  for (const match of source.matchAll(SPECIFIER)) {
    const specifier = match[1];
    if (specifier !== undefined && boundaryViolation(specifier, fromPath) !== null) {
      offenders.push(specifier);
    }
  }
  return offenders;
}
