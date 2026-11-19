/* eslint-disable react-refresh/only-export-components -- context module intentionally exports the hooks alongside the provider */
import { createContext, useContext, type ReactNode } from "react";

import type {
  AddOutcomePayload,
  AddStepPayload,
  CanvasData,
  CanvasState,
  Outcome,
  StudioError,
} from "../../types";

/**
 * The canvas's own context (#505).
 *
 * Canvas data and the mutators that write it used to ride in the same
 * `useMemo` value as the transcript, the notices, and the settings, so a
 * canvas refresh rebuilt that object and re-rendered every `useStudio()`
 * reader. Splitting the canvas out is what lets a surface subscribe to the
 * board without paying for a keystroke somewhere else — and vice versa.
 *
 * The two values are separate on purpose. The state changes on every refresh;
 * the actions are the stable handles a component uses to write. A reader that
 * only writes (or only reads) should never re-render because the other moved.
 */
export interface CanvasStateValue {
  canvas: CanvasData | null;
  canvasLoading: boolean;
  canvasCached: boolean;
  /** What the canvas is: loading, ready, empty, or failed. */
  canvasState: CanvasState;
  /** The failure behind `canvasState.kind === "error"`, if any. */
  canvasError: StudioError | null;
}

export interface CanvasActionsValue {
  refreshCanvas: () => Promise<void>;
  addStep: (payload: Omit<AddStepPayload, "mcp_url">) => Promise<void>;
  addOutcome: (payload: Omit<AddOutcomePayload, "mcp_url">) => Promise<void>;
  createJob: (payload: { name: string; description?: string }) => Promise<string | null>;
  updateJob: (jobId: string, payload: { name?: string; description?: string }) => Promise<void>;
  deleteJob: (jobId: string) => Promise<void>;
  updateStep: (stepId: string, payload: { name?: string; order?: number }) => Promise<void>;
  deleteStep: (stepId: string) => Promise<void>;
  /** Resolves with the outcome the server returned, or `null` when the write
   * failed — the caller may keep the editor open on the values it holds. */
  updateOutcome: (
    outcomeId: string,
    payload: { statement?: string; importance?: number; satisfaction?: number },
  ) => Promise<Outcome | null>;
  deleteOutcome: (outcomeId: string) => Promise<void>;
  deleteEvidence: (evidenceId: string) => Promise<void>;
  promoteEvidence: (
    evidenceId: string,
    payload: {
      target: "job" | "outcome";
      job_id?: string;
      statement?: string;
      name?: string;
      importance?: number;
      satisfaction?: number;
    },
  ) => Promise<void>;
}

/** Re-renders when the board changes; never on a write-only action. */
export const CanvasStateContext = createContext<CanvasStateValue | null>(null);
/** Identity-stable across canvas refreshes, so action-only consumers stay put. */
export const CanvasActionsContext = createContext<CanvasActionsValue | null>(null);

export function CanvasProvider({
  state,
  actions,
  children,
}: {
  state: CanvasStateValue;
  actions: CanvasActionsValue;
  children: ReactNode;
}) {
  return (
    <CanvasActionsContext.Provider value={actions}>
      <CanvasStateContext.Provider value={state}>{children}</CanvasStateContext.Provider>
    </CanvasActionsContext.Provider>
  );
}

/** The board's data and load state. Re-renders when the canvas changes. */
export function useCanvasState(): CanvasStateValue {
  const context = useContext(CanvasStateContext);
  if (!context) {
    throw new Error("useCanvasState must be used within a CanvasProvider");
  }
  return context;
}

/** The canvas mutators. Identity-stable, so they never cost a re-render. */
export function useCanvasActions(): CanvasActionsValue {
  const context = useContext(CanvasActionsContext);
  if (!context) {
    throw new Error("useCanvasActions must be used within a CanvasProvider");
  }
  return context;
}
