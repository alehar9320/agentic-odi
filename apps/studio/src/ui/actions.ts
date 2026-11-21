import { createContext, useContext } from "react";

import type { WorkspacePanelId } from "../types";

/**
 * A detail target: the right region, pointed at one specific thing (#735).
 *
 * The panel id names which lens shows it; the subject names the record inside
 * it. Both are required, because a detail action that cannot say what it opens
 * would be a switcher wearing a finding's clothes.
 */
export interface DetailTarget {
  panel: WorkspacePanelId;
  subject?: { kind: string; id: string };
}

/**
 * Cards are views, never actors — with one exception.
 *
 * Most buttons resolve to a single intent string the agent receives as the
 * user's next message, so the agent keeps one authority and one audit trail.
 * A button that opens a detail does not: it mutates region state and must not
 * send a message. That is why the action is a union rather than a bare string,
 * and why a malformed entry is still dropped rather than guessed at.
 */
export type UiAction =
  | { kind: "intent"; label: string; intent: string; tone: "primary" | "ghost" }
  | { kind: "detail"; label: string; target: DetailTarget; tone: "primary" | "ghost" };

export interface UiActionDispatcher {
  onIntent: (intent: string) => void;
  onDetail: (target: DetailTarget) => void;
  busy: boolean;
}

export const UiActionContext = createContext<UiActionDispatcher | null>(null);

export function useUiActions(): UiActionDispatcher | null {
  return useContext(UiActionContext);
}

/**
 * Props arrive already validated, but this stays defensive: a malformed action
 * is dropped rather than allowed to break the card that holds it.
 *
 * A legacy action with a bare `intent` and no `kind` is read as an intent, so
 * cards that have not moved to the union keep working.
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
    if (typeof candidate.label !== "string") {
      continue;
    }
    const tone = candidate.tone === "primary" ? "primary" : "ghost";
    if (candidate.kind === "detail") {
      const target = readDetailTarget(candidate.target);
      if (!target) {
        continue;
      }
      actions.push({ kind: "detail", label: candidate.label, target, tone });
      continue;
    }
    if (typeof candidate.intent === "string") {
      actions.push({ kind: "intent", label: candidate.label, intent: candidate.intent, tone });
    }
  }
  return actions;
}

/** A detail target, or null when it cannot name both a panel and a record. */
function readDetailTarget(value: unknown): DetailTarget | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const target = value as Record<string, unknown>;
  if (typeof target.panel !== "string" || !target.panel) {
    return null;
  }
  const subject = readSubject(target.subject);
  return {
    panel: target.panel as WorkspacePanelId,
    ...(subject ? { subject } : {}),
  };
}

function readSubject(value: unknown): { kind: string; id: string } | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const subject = value as Record<string, unknown>;
  if (typeof subject.kind !== "string" || typeof subject.id !== "string") {
    return null;
  }
  if (!subject.kind || !subject.id) {
    return null;
  }
  return { kind: subject.kind, id: subject.id };
}
