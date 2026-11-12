import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CanvasData } from "../../types";
import { buildRecords, type RecordKind, type RecordRow } from "../../lib/records";
import { RecordDetail } from "./RecordDetail";
import { RecordsPanel } from "./RecordsPanel";

const studio = vi.hoisted(() => ({
  canvas: null as CanvasData | null,
  updateOutcome: vi.fn(),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => studio,
}));

function canvas(overrides: Partial<CanvasData> = {}): CanvasData {
  return { jobs: [], steps: [], outcomes: [], source: "local", ...overrides };
}

function firstRow(rows: RecordRow[], kind: RecordKind): RecordRow {
  const row = rows.filter((candidate) => candidate.kind === kind)[0];
  if (!row) {
    throw new Error(`no ${kind} row in the fixture`);
  }
  return row;
}

/**
 * The detail as the lens renders it: a real row out of the real builder, so a field the
 * table would lose cannot quietly survive here.
 */
function renderDetail(overrides: Partial<CanvasData>, kind: RecordKind) {
  studio.canvas = canvas(overrides);
  const rows = buildRecords(studio.canvas);
  const onFilter = vi.fn();
  const onClose = vi.fn();
  const result = render(
    <RecordDetail row={firstRow(rows, kind)} rows={rows} onFilter={onFilter} onClose={onClose} />,
  );
  return { ...result, onFilter, onClose };
}

beforeEach(() => {
  studio.canvas = null;
  studio.updateOutcome.mockReset();
  studio.updateOutcome.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("RecordDetail stored fields", () => {
  // The detail exists because a row is a summary. Every field the store holds for the
  // kind appears, under the name the store uses for it.
  it("shows a job under its real field names", () => {
    const { container } = renderDetail({ jobs: [{ id: "J-1", name: "Activation", description: "Get to first value" }] }, "job");
    for (const field of ["id", "name", "description"]) {
      expect(screen.getByText(field)).toBeInTheDocument();
    }
    expect(container.textContent).toContain("J-1");
    expect(container.textContent).toContain("Activation");
    expect(container.textContent).toContain("Get to first value");
  });

  it("shows a step including the job it belongs to", () => {
    const { container } = renderDetail({ steps: [{ id: "S-1", job_id: "J-1", name: "Onboarding", order: 2 }] }, "step");
    for (const field of ["id", "job_id", "name", "order"]) {
      expect(screen.getByText(field)).toBeInTheDocument();
    }
    expect(container.textContent).toContain("Onboarding");
    expect(container.textContent).toContain("J-1");
  });

  it("shows an outcome including the evidence note it stores", () => {
    const { container } = renderDetail(
      {
        outcomes: [
          {
            id: "O-1",
            job_id: "J-1",
            statement: "Reach first value in a day",
            importance: 9,
            satisfaction: 2,
            opportunity_score: 17,
            evidence: "Two interviews",
          },
        ],
      },
      "outcome",
    );
    for (const field of [
      "id",
      "job_id",
      "statement",
      "importance",
      "satisfaction",
      "opportunity_score",
      "evidence",
    ]) {
      expect(screen.getByText(field)).toBeInTheDocument();
    }
    expect(container.textContent).toContain("Two interviews");
    expect(container.textContent).toContain("17");
  });

  it("shows every evidence field the store carries", () => {
    const { container } = renderDetail(
      {
        evidence: [
          {
            id: "E-1",
            source_name: "Gong",
            source_kind: "call",
            item_type: "quote",
            name: "Call with Acme",
            content: "We still do this by hand.",
            url: "https://example.test/c/1",
            job_id: "J-1",
            step_id: "S-1",
            outcome_id: "O-1",
          },
        ],
      },
      "evidence",
    );
    for (const field of [
      "id",
      "source_name",
      "source_kind",
      "item_type",
      "name",
      "content",
      "url",
      "job_id",
      "step_id",
      "outcome_id",
    ]) {
      expect(screen.getByText(field)).toBeInTheDocument();
    }
    expect(container.textContent).toContain("We still do this by hand.");
  });

  // Telemetry is an opaque client string with no defined shape: not rendered, and not
  // removed from the record the detail was handed.
  it("neither renders nor removes an outcome's telemetry", () => {
    const { container } = renderDetail(
      { outcomes: [{ id: "O-1", statement: "Reach first value", telemetry: "opaque-client-blob" }] },
      "outcome",
    );
    expect(container.textContent).not.toContain("opaque-client-blob");
    expect(studio.canvas?.outcomes[0].telemetry).toBe("opaque-client-blob");
  });

  it("names a field the record does not hold as a gap, never as a guess", () => {
    const { container } = renderDetail(
      { outcomes: [{ id: "O-1", statement: "Reach first value", importance: null }] },
      "outcome",
    );
    const values = Array.from(container.querySelectorAll("dd")).map((node) => node.textContent);
    expect(values).toContain("—");
    expect(values).toContain("unscored");
    expect(container.textContent).not.toMatch(/Unknown|N\/A|TODO|undefined/);
  });

  it("says plainly what the record cannot know", () => {
    renderDetail({ jobs: [{ id: "J-1", name: "Activation" }] }, "job");
    expect(
      screen.getByText("This record stores only the fields above — no author and no timestamp."),
    ).toBeInTheDocument();
  });

  it("spells out the two estimates and the computed score for an outcome", () => {
    renderDetail({ outcomes: [{ id: "O-1", importance: 9, satisfaction: 2 }] }, "outcome");
    expect(
      screen.getByText(
        "An outcome stores its statement and two estimates — not who set them, or when.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "The score is computed from importance and satisfaction; it is not stored input.",
      ),
    ).toBeInTheDocument();
  });
});

describe("RecordDetail parents", () => {
  // A parent that exists in the lens is a way to narrow it; one that does not is just a
  // string the record happens to hold.
  it("offers a parent that exists in the lens as a filter", () => {
    const { onFilter } = renderDetail(
      {
        jobs: [{ id: "J-1", name: "Activation" }],
        outcomes: [{ id: "O-1", job_id: "J-1", statement: "Reach first value" }],
      },
      "outcome",
    );
    fireEvent.click(screen.getByRole("button", { name: /J-1/ }));
    expect(onFilter).toHaveBeenCalledWith("J-1");
  });

  it("renders a parent that is not in the lens as text, not a button", () => {
    const { container, onFilter } = renderDetail(
      { outcomes: [{ id: "O-1", job_id: "J-9", statement: "Reach first value" }] },
      "outcome",
    );
    expect(screen.queryByRole("button", { name: /J-9/ })).toBeNull();
    expect(container.textContent).toContain("J-9");
    expect(onFilter).not.toHaveBeenCalled();
  });

  it("names the region after the kind it is showing", () => {
    renderDetail({ jobs: [{ id: "J-1", name: "Activation" }] }, "job");
    expect(screen.getByRole("complementary", { name: "Jobs detail" })).toBeInTheDocument();
  });
});

describe("RecordDetail copy id", () => {
  let writeText: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeText = vi.fn(async () => {});
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
  });

  it("copies the id and says so for two seconds", async () => {
    vi.useFakeTimers();
    renderDetail({ jobs: [{ id: "J-1", name: "Activation" }] }, "job");

    fireEvent.click(screen.getByRole("button", { name: "Copy id" }));
    await act(async () => {
      vi.advanceTimersByTime(0);
    });

    expect(writeText).toHaveBeenCalledWith("J-1");
    expect(screen.getByText("Copied")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.queryByText("Copied")).toBeNull();
  });

  it("offers nothing to copy for a record with no id", () => {
    renderDetail({ steps: [{ name: "Onboarding" }] }, "step");
    expect(screen.queryByRole("button", { name: "Copy id" })).toBeNull();
  });

  it("stays quiet when the clipboard refuses", async () => {
    writeText.mockRejectedValue(new Error("denied"));
    renderDetail({ jobs: [{ id: "J-1", name: "Activation" }] }, "job");

    fireEvent.click(screen.getByRole("button", { name: "Copy id" }));

    await waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(screen.queryByText("Copied")).toBeNull();
  });
});

describe("RecordDetail editing an outcome's two estimates", () => {
  const outcome = {
    id: "O-1",
    statement: "Reach first value in a day",
    importance: 8,
    satisfaction: 4,
    opportunity_score: 12.3,
  };

  it("offers number inputs for an outcome and none for an evidence record", () => {
    renderDetail({ outcomes: [outcome] }, "outcome");
    expect(screen.getByLabelText("Importance (1–10)")).toHaveAttribute("type", "number");
    expect(screen.getByLabelText("Satisfaction (1–10)")).toHaveAttribute("type", "number");

    cleanup();
    renderDetail({ evidence: [{ id: "E-1", name: "Call with Acme" }] }, "evidence");
    expect(screen.queryByLabelText("Importance (1–10)")).toBeNull();
    expect(screen.queryByLabelText("Satisfaction (1–10)")).toBeNull();
  });

  it("keeps Save disabled until a value changes", () => {
    renderDetail({ outcomes: [outcome] }, "outcome");
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Importance (1–10)"), { target: { value: "6" } });
    expect(save).toBeEnabled();

    fireEvent.change(screen.getByLabelText("Importance (1–10)"), { target: { value: "8" } });
    expect(save).toBeDisabled();
  });

  it("calls the mutation once with clamped integers", async () => {
    renderDetail({ outcomes: [outcome] }, "outcome");
    fireEvent.change(screen.getByLabelText("Importance (1–10)"), { target: { value: "42" } });
    fireEvent.change(screen.getByLabelText("Satisfaction (1–10)"), { target: { value: "0" } });

    fireEvent.submit(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(studio.updateOutcome).toHaveBeenCalledWith("O-1", { importance: 10, satisfaction: 1 }),
    );
    expect(studio.updateOutcome).toHaveBeenCalledTimes(1);
  });

  it("shows the sidecar's message and keeps the typed values when the save rejects", async () => {
    studio.updateOutcome.mockRejectedValue({
      code: "internal",
      message: "The outcome could not be saved.",
      suggestion: "Try again in a moment.",
      retryable: true,
    });
    renderDetail({ outcomes: [outcome] }, "outcome");
    fireEvent.change(screen.getByLabelText("Importance (1–10)"), { target: { value: "6" } });
    fireEvent.submit(screen.getByRole("button", { name: "Save" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The outcome could not be saved.");
    expect(alert).toHaveTextContent("Try again in a moment.");
    expect(screen.getByLabelText("Importance (1–10)")).toHaveValue(6);
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
  });

  // While the refreshed record is on its way the old score stays and says it is
  // being recomputed. The new number is never guessed here.
  it("keeps the old score and appends recomputing while the save is in flight", async () => {
    let resolveSave: () => void = () => {};
    studio.updateOutcome.mockImplementation(
      () => new Promise<void>((resolve) => {
        resolveSave = resolve;
      }),
    );
    renderDetail({ outcomes: [outcome] }, "outcome");
    fireEvent.change(screen.getByLabelText("Importance (1–10)"), { target: { value: "6" } });
    fireEvent.submit(screen.getByRole("button", { name: "Save" }));

    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
    expect(screen.getByText("12.3 recomputing")).toBeInTheDocument();

    await act(async () => {
      resolveSave();
    });
    expect(screen.getByText("12.3")).toBeInTheDocument();
  });

  // The score is the sidecar's. With no score on the record the detail says so,
  // and it never derives a number from the two estimates it was handed.
  it("shows unscored for a null score and never computes one", () => {
    const { container } = renderDetail(
      { outcomes: [{ id: "O-1", importance: 8, satisfaction: 4, opportunity_score: null }] },
      "outcome",
    );
    expect(container.textContent).toContain("unscored");
    expect(container.textContent).not.toContain("12");
  });
});

describe("opening a record in the lens", () => {
  const sample = canvas({
    jobs: [
      { id: "J-1", name: "Activation" },
      { id: "J-2", name: "Retention" },
    ],
    outcomes: [
      { id: "O-1", job_id: "J-1", statement: "Reach first value" },
      { id: "O-2", job_id: "J-2", statement: "Keep them" },
    ],
  });

  beforeEach(() => {
    studio.canvas = sample;
  });

  it("opens the row that was pressed and puts focus where the reading starts", () => {
    render(<RecordsPanel />);
    expect(screen.queryByRole("complementary")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Reach first value" }));

    const heading = screen.getByRole("heading", { name: "Desired outcomes detail" });
    expect(heading).toHaveFocus();
    expect(screen.getByRole("button", { name: "Reach first value" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByRole("button", { name: "Keep them" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("closes back onto the row it opened from", () => {
    render(<RecordsPanel />);
    const rowButton = screen.getByRole("button", { name: "Reach first value" });
    fireEvent.click(rowButton);
    expect(screen.getByRole("complementary")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(screen.queryByRole("complementary")).toBeNull();
    expect(rowButton).toHaveFocus();
  });

  // Filtering narrows the table; it never sends the person somewhere else.
  it("narrowing to a parent hides the rows that are not its, and clearing brings them back", () => {
    render(<RecordsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Reach first value" }));
    fireEvent.click(screen.getByRole("button", { name: /J-1/ }));

    expect(screen.queryByRole("button", { name: "Keep them" })).toBeNull();
    expect(screen.getByRole("button", { name: "Activation" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /clear filter/i }));

    expect(screen.getByRole("button", { name: "Keep them" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retention" })).toBeInTheDocument();
  });
});
