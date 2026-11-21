import { act, render, screen } from "@testing-library/react";
import { memo, useState, type ReactNode } from "react";
import { describe, expect, it } from "vitest";

import {
  CanvasProvider,
  useCanvasActions,
  useCanvasState,
  type CanvasActionsValue,
  type CanvasStateValue,
} from "./CanvasContext";
import type { CanvasData } from "../../types";

const EMPTY: CanvasData = { jobs: [], steps: [], outcomes: [], source: "mcp" };

function stateValue(kind: CanvasStateValue["canvasState"]["kind"], data: CanvasData | null): CanvasStateValue {
  return { canvas: data, canvasLoading: kind === "loading", canvasCached: false, canvasState: { kind, data } as never, canvasError: null };
}

function actionsValue(onRefresh: () => void): CanvasActionsValue {
  const noop = async () => {};
  return {
    refreshCanvas: async () => onRefresh(),
    addStep: noop,
    addOutcome: noop,
    createJob: async () => null,
    updateJob: noop,
    deleteJob: noop,
    updateStep: noop,
    deleteStep: noop,
    updateOutcome: async () => null,
    deleteOutcome: noop,
    deleteEvidence: noop,
    promoteEvidence: noop,
  };
}

/**
 * The split (#505) is only real if the two values move independently: a canvas
 * change must re-render a reader, and must not re-render a surface that only
 * writes. These counters are the argument a reviewer can check.
 */
describe("CanvasContext (#505)", () => {
  function StateReader(): ReactNode {
    const { canvasState } = useCanvasState();
    stateRenders += 1;
    return <span data-testid="state">{canvasState.kind}</span>;
  }

  // Memoised so the parent's re-render does not re-create it: the only thing
  // left that can re-render this writer is a change in the actions context,
  // which is exactly what the split promises will not happen.
  const ActionsReader = memo(function ActionsReader(): ReactNode {
    const { refreshCanvas } = useCanvasActions();
    actionRenders += 1;
    return <button onClick={() => void refreshCanvas()}>refresh</button>;
  });

  function Harness({ initialActions }: { initialActions: CanvasActionsValue }): ReactNode {
    const [state, setState] = useState<CanvasStateValue>(() => stateValue("loading", null));
    const [actions] = useState(initialActions);
    return (
      <CanvasProvider state={state} actions={actions}>
        <StateReader />
        <ActionsReader />
        <button
          data-testid="advance"
          onClick={() => setState(stateValue("ready", EMPTY))}
        >
          advance
        </button>
      </CanvasProvider>
    );
  }

  let stateRenders = 0;
  let actionRenders = 0;

  it("re-renders a state reader on a canvas change but not an action-only reader", () => {
    stateRenders = 0;
    actionRenders = 0;
    render(<Harness initialActions={actionsValue(() => {})} />);

    expect(stateRenders).toBe(1);
    expect(actionRenders).toBe(1);

    act(() => {
      screen.getByTestId("advance").click();
    });

    expect(screen.getByTestId("state").textContent).toBe("ready");
    // The board changed, so the reader that watches it renders again...
    expect(stateRenders).toBe(2);
    // ...but the writer did not pay for the data change.
    expect(actionRenders).toBe(1);
  });

  it("throws a named error when used outside a provider", () => {
    function Orphan(): ReactNode {
      useCanvasState();
      return null;
    }
    expect(() => render(<Orphan />)).toThrow(/CanvasProvider/);
  });
});
