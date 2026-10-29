/**
 * Narrowing helpers for validated props. The catalog guarantees the shapes;
 * these keep the components honest anyway, so a hand-built node (like the
 * welcome surface) cannot crash a card.
 */

export type Tone = "neutral" | "positive" | "warning" | "critical" | "info";

export function str(props: Record<string, unknown>, key: string, fallback = ""): string {
  const value = props[key];
  return typeof value === "string" ? value : fallback;
}

export function num(props: Record<string, unknown>, key: string, fallback: number): number {
  const value = props[key];
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function tone(props: Record<string, unknown>, fallback: Tone = "neutral"): Tone {
  const value = props.tone;
  return typeof value === "string" ? (value as Tone) : fallback;
}
