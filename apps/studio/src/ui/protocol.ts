/**
 * The wire contract for agent-composed UI.
 *
 * A payload is a tree of `{ type, props, children }` nodes validated against a
 * catalog manifest. The manifest is plain JSON Schema (draft 2020-12 subset),
 * so the same document can be handed to the model as a tool schema and used
 * here to validate what comes back. Nothing is eval'd, no HTML is injected, and
 * every node is bounded before it can reach React.
 *
 * Parsing is deliberately forgiving where it is safe (unknown props are
 * stripped, unknown component types degrade to a visible fallback) and strict
 * where it matters (structure, required props, and size ceilings).
 */

export const UI_LIMITS = {
  maxDepth: 12,
  maxNodes: 200,
  maxStringLength: 2000,
  maxChildren: 32,
  maxActions: 40,
} as const;

/** A JSON Schema subset: enough to describe every prop in the catalog. */
export interface UiPropSchema {
  type?: "string" | "number" | "integer" | "boolean" | "array" | "object";
  description?: string;
  enum?: readonly string[];
  minimum?: number;
  maximum?: number;
  items?: UiPropSchema;
  properties?: Record<string, UiPropSchema>;
  required?: readonly string[];
  minItems?: number;
  maxItems?: number;
}

export interface UiCatalogEntry {
  type: string;
  kind: "layout" | "leaf";
  description: string;
  acceptsChildren: boolean;
  props: UiPropSchema;
}

export interface UiCatalogManifest {
  version: 1;
  components: UiCatalogEntry[];
}

export interface UiNode {
  type: string;
  props: Record<string, unknown>;
  children: UiNode[];
  /** Set when the manifest has no component for this type. */
  unsupported?: boolean;
}

export type ParseResult = { ok: true; node: UiNode } | { ok: false; reason: string };

type ValueResult = { ok: true; value: unknown } | { ok: false };

interface ParseState {
  entries: Map<string, UiCatalogEntry>;
  nodes: number;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function catalogIndex(manifest: UiCatalogManifest): Map<string, UiCatalogEntry> {
  return new Map(manifest.components.map((entry) => [entry.type, entry]));
}

function ok(value: unknown): ValueResult {
  return { ok: true, value };
}

const INVALID: ValueResult = { ok: false };

function validateValue(raw: unknown, schema: UiPropSchema, depth: number): ValueResult {
  if (depth > UI_LIMITS.maxDepth + 4) {
    return INVALID;
  }

  if (schema.enum) {
    return typeof raw === "string" && schema.enum.includes(raw) ? ok(raw) : INVALID;
  }

  switch (schema.type) {
    case "string":
      if (typeof raw !== "string" || raw.length > UI_LIMITS.maxStringLength) {
        return INVALID;
      }
      return ok(raw);

    case "number":
    case "integer": {
      if (typeof raw !== "number" || !Number.isFinite(raw)) {
        return INVALID;
      }
      if (schema.type === "integer" && !Number.isInteger(raw)) {
        return INVALID;
      }
      if (schema.minimum !== undefined && raw < schema.minimum) {
        return INVALID;
      }
      if (schema.maximum !== undefined && raw > schema.maximum) {
        return INVALID;
      }
      return ok(raw);
    }

    case "boolean":
      return typeof raw === "boolean" ? ok(raw) : INVALID;

    case "array": {
      if (!Array.isArray(raw)) {
        return INVALID;
      }
      if (schema.minItems !== undefined && raw.length < schema.minItems) {
        return INVALID;
      }
      if (schema.maxItems !== undefined && raw.length > schema.maxItems) {
        return INVALID;
      }
      const items: unknown[] = [];
      for (const entry of raw) {
        const validated = schema.items ? validateValue(entry, schema.items, depth + 1) : ok(entry);
        if (!validated.ok) {
          return INVALID;
        }
        items.push(validated.value);
      }
      return ok(items);
    }

    case "object": {
      if (!isPlainObject(raw)) {
        return INVALID;
      }
      const result = validateProps(raw, schema, depth + 1);
      return result.ok ? ok(result.value) : INVALID;
    }

    default:
      return INVALID;
  }
}

function validateProps(
  raw: Record<string, unknown>,
  schema: UiPropSchema,
  depth: number,
): { ok: true; value: Record<string, unknown> } | { ok: false } {
  const properties = schema.properties ?? {};
  const result: Record<string, unknown> = {};

  for (const key of schema.required ?? []) {
    if (!(key in raw)) {
      return { ok: false };
    }
  }

  for (const [key, value] of Object.entries(raw)) {
    const propertySchema = properties[key];
    if (!propertySchema) {
      // Unknown props are stripped rather than trusted.
      continue;
    }
    const validated = validateValue(value, propertySchema, depth);
    if (!validated.ok) {
      if ((schema.required ?? []).includes(key)) {
        return { ok: false };
      }
      continue;
    }
    result[key] = validated.value;
  }

  return { ok: true, value: result };
}

function describePropFailure(entry: UiCatalogEntry, key: string): string {
  const schema = entry.props.properties?.[key];
  if (!schema) {
    return `unknown prop "${key}"`;
  }
  if (schema.enum) {
    return `prop "${key}" must be one of ${schema.enum.join(", ")}`;
  }
  if (schema.type === "number" || schema.type === "integer") {
    const bounds =
      schema.minimum !== undefined || schema.maximum !== undefined
        ? ` between ${schema.minimum ?? "-∞"} and ${schema.maximum ?? "∞"}`
        : "";
    return `prop "${key}" must be a ${schema.type}${bounds}`;
  }
  if (schema.type === "array") {
    return `prop "${key}" must be an array of valid items`;
  }
  if (schema.type === "object") {
    return `prop "${key}" must be an object with the documented fields`;
  }
  if (schema.type === "boolean") {
    return `prop "${key}" must be a boolean`;
  }
  return `prop "${key}" must be a ${schema.type ?? "valid value"}`;
}

function parseNode(raw: unknown, depth: number, state: ParseState): ParseResult {
  if (depth > UI_LIMITS.maxDepth) {
    return { ok: false, reason: `UI tree exceeds the maximum depth of ${UI_LIMITS.maxDepth}` };
  }
  state.nodes += 1;
  if (state.nodes > UI_LIMITS.maxNodes) {
    return { ok: false, reason: `UI tree exceeds the maximum of ${UI_LIMITS.maxNodes} nodes` };
  }

  if (!isPlainObject(raw)) {
    return { ok: false, reason: "UI node must be an object" };
  }

  const type = raw.type;
  if (typeof type !== "string" || type.trim() === "" || type.length > 100) {
    return { ok: false, reason: "UI node needs a component type" };
  }

  if (raw.props !== undefined && !isPlainObject(raw.props)) {
    return { ok: false, reason: `UI node "${type}" has non-object props` };
  }
  if (raw.children !== undefined && !Array.isArray(raw.children)) {
    return { ok: false, reason: `UI node "${type}" has non-array children` };
  }

  const entry = state.entries.get(type);
  if (!entry) {
    return { ok: true, node: { type, props: {}, children: [], unsupported: true } };
  }

  const props = validateProps(isPlainObject(raw.props) ? raw.props : {}, entry.props, 0);
  if (!props.ok) {
    const failed = Object.keys(entry.props.properties ?? {}).find((key) => {
      const schema = entry.props.properties?.[key];
      const value = isPlainObject(raw.props) ? raw.props[key] : undefined;
      if (!(entry.props.required ?? []).includes(key)) {
        return false;
      }
      return !schema || !validateValue(value, schema, 0).ok;
    });
    return {
      ok: false,
      reason: failed
        ? `${type}: ${describePropFailure(entry, failed)}`
        : `${type}: props failed validation`,
    };
  }

  const rawChildren = Array.isArray(raw.children) ? raw.children : [];
  const children: UiNode[] = [];

  if (entry.acceptsChildren) {
    if (rawChildren.length > UI_LIMITS.maxChildren) {
      return {
        ok: false,
        reason: `${type} accepts at most ${UI_LIMITS.maxChildren} children`,
      };
    }
    for (const child of rawChildren) {
      const parsed = parseNode(child, depth + 1, state);
      if (!parsed.ok) {
        return parsed;
      }
      children.push(parsed.node);
    }
  }

  return { ok: true, node: { type, props: props.value, children } };
}

export function parseUiSpec(raw: unknown, manifest: UiCatalogManifest): ParseResult {
  return parseNode(raw, 0, {
    entries: catalogIndex(manifest),
    nodes: 0,
  });
}

/** Serializable projection of the catalog sent to the sidecar with each turn. */
export function toManifest(components: UiCatalogEntry[]): UiCatalogManifest {
  return { version: 1, components };
}
