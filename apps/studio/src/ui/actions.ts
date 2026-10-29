import { createContext, useContext } from "react";

/**
 * Cards are views, never actors. Every button resolves to a single intent
 * string that the agent receives as the user's next message, so the agent keeps
 * one authority and one audit trail.
 */
export interface UiAction {
  label: string;
  intent: string;
  tone: "primary" | "ghost";
}

export interface UiActionDispatcher {
  onIntent: (intent: string) => void;
  busy: boolean;
}

export const UiActionContext = createContext<UiActionDispatcher | null>(null);

export function useUiActions(): UiActionDispatcher | null {
  return useContext(UiActionContext);
}

/**
 * Props arrive already validated, but this stays defensive: a malformed action
 * is dropped rather than allowed to break the card that holds it.
 */
export function readActions(props: Record<string, unknown>): UiAction[] {
  const raw = props.actions;
  if (!Array.isArray(raw)) {
    return [];
  }

  const actions: UiAction[] = [];
  for (const entry of raw) {
    if (typeof entry !== "object" || entry === null) {
      continue;
    }
    const candidate = entry as Record<string, unknown>;
    if (typeof candidate.label !== "string" || typeof candidate.intent !== "string") {
      continue;
    }
    actions.push({
      label: candidate.label,
      intent: candidate.intent,
      tone: candidate.tone === "primary" ? "primary" : "ghost",
    });
  }
  return actions;
}
