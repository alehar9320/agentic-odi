import type { CanvasData } from "../types";

const REASON_TEXT: Record<string, string> = {
  mcp_unreachable: "the MCP server could not be reached",
  mcp_unreadable: "the MCP server returned nothing usable",
  demo: "demonstration data",
};

export interface CanvasStatus {
  label: "DEMO" | "OFFLINE";
  detail: string;
}

/**
 * True when the canvas is the seed prototype rather than the user's own work.
 * Falls back to `source` so a canvas cached by an older build is still labelled.
 */
export function isSimulatedCanvas(data: CanvasData | null | undefined): boolean {
  if (!data) {
    return false;
  }
  return data.provenance ? data.provenance.kind === "seed" : data.source === "seed";
}

/** The chip the rail shows, or `null` when the canvas is genuinely the user's. */
export function canvasStatus(data: CanvasData | null | undefined): CanvasStatus | null {
  if (!isSimulatedCanvas(data)) {
    return null;
  }
  const reason = data?.provenance?.reason ?? "demo";
  const detail = REASON_TEXT[reason] ?? reason.replaceAll("_", " ");
  const label = reason.startsWith("mcp_") ? "OFFLINE" : "DEMO";
  return { label, detail: `sample data — ${detail}` };
}
