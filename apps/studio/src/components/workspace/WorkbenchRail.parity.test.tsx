import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  CanvasData,
  Evidence,
  Job,
  Observation,
  Outcome,
  ScheduledWork,
  Segment,
  Signal,
  Step,
} from "../../types";

const studio = vi.hoisted(() => ({
  canvas: null as CanvasData | null,
  canvasState: { kind: "ready", data: null } as unknown,
  memory: [] as Observation[],
  memoryLoading: false,
  segments: [] as Segment[],
  signals: [] as Signal[],
  unreadSignalCount: 0,
  canvasCached: false,
  theses: [] as unknown[],
  strategy: null as unknown,
  segmentsError: null as unknown,
  signalsError: null as unknown,
  focusedSubject: null as unknown,
  settings: {} as Record<string, unknown>,
  activePanel: null as string | null,
  openPanel: vi.fn(),
  closePanel: vi.fn(),
  pushToast: vi.fn(),
  refreshCanvas: vi.fn(),
  updateObservation: vi.fn(),
  updateStep: vi.fn(),
  updateOutcome: vi.fn(),
  sendMessage: vi.fn(),
  deleteThesis: vi.fn(),
  focusSubject: vi.fn(),
  focusSignalSubject: vi.fn(),
  refreshSegments: vi.fn(),
  refreshSignals: vi.fn(),
  markSignalAsRead: vi.fn(),
  dismissSignal: vi.fn(),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => studio,
}));

import { WorkbenchRail } from "./WorkbenchRail";
import { findPanel } from "./panels";

function outcome(id: string, evidence?: string): Outcome {
  return { id, statement: `Opportunity ${id}`, importance: 8, satisfaction: 2, evidence };
}

function evidenceRecords(count: number): Evidence[] {
  return Array.from({ length: count }, (_unused, index) => ({
    id: `E-${index}`,
    name: `Quote ${index}`,
    content: `A customer said ${index}`,
    item_type: "quote",
  }));
}

/** The number the map prints for a destination, exactly as a person reads it. */
function mapCount(id: string): string {
  const row = screen
    .getByRole("navigation", { name: "Studio" })
    .querySelector<HTMLButtonElement>(`[data-panel="${id}"]`);
  return row?.querySelector(".rail__count")?.textContent ?? "";
}

/**
 * Each case names the destination, the data it is given, and the selector that
 * marks one row inside its panel. The assertion is the amendment's: the number
 * on the map equals the rows below it.
 */
const CASES: {
  id: string;
  rows: string;
  given: () => void;
}[] = [
  {
    id: "records",
    rows: ".records__row-button",
    given: () => {
      studio.canvas = {
        jobs: [{ id: "J-1", name: "Ship" }],
        steps: [{ id: "S-1", job_id: "J-1", name: "Plan" }],
        outcomes: [outcome("O-1"), outcome("O-2")],
        evidence: evidenceRecords(1),
        source: "mcp",
      };
    },
  },
  {
    id: "landscape",
    rows: ".matrix-node",
    given: () => {
      studio.canvas = {
        jobs: [],
        steps: [],
        outcomes: [outcome("O-1"), outcome("O-2"), outcome("O-3")],
        source: "mcp",
      };
    },
  },
  {
    id: "jobmap",
    rows: ".step-row",
    given: () => {
      studio.canvas = {
        jobs: [{ id: "J-1", name: "Ship" }, { id: "J-2", name: "Run" }] as Job[],
        steps: [
          { id: "S-1", job_id: "J-1", name: "Plan" },
          { id: "S-2", job_id: "J-1", name: "Build" },
          { id: "S-3", job_id: "J-2", name: "Watch" },
        ] as Step[],
        outcomes: [],
        source: "mcp",
      };
    },
  },
  {
    id: "evidence",
    rows: "li.evidence",
    given: () => {
      // Three outcomes carry a note and twelve records were captured: the old
      // rail promised 3 and the panel showed 12.
      studio.canvas = {
        jobs: [],
        steps: [],
        outcomes: [outcome("O-1", "a quote"), outcome("O-2", "another"), outcome("O-3", "a third")],
        evidence: evidenceRecords(12),
        source: "mcp",
      };
    },
  },
  {
    id: "memory",
    rows: "li.memory-item",
    given: () => {
      studio.memory = [
        { id: "M-1", text: "Owns activation.", status: "confirmed" },
        { id: "M-2", text: "Prefers short updates.", status: "suggested" },
        { id: "M-3", text: "Retired note.", status: "dismissed" },
      ] as Observation[];
    },
  },
  {
    id: "segments",
    rows: '.ui-card--segment[role="article"], article.ui-card--segment',
    given: () => {
      studio.segments = [
        { id: "SEG-1", name: "Releasers", people: "3 teams", job_statement: "Ship safely", outcome_ids: [], rationale: "r", confidence: 0.8, created_at: "2026-10-01T00:00:00+00:00" },
        { id: "SEG-2", name: "Night ops", people: "9 engineers", job_statement: "Ship safely", outcome_ids: [], rationale: "r", confidence: 0.6, created_at: "2026-10-01T00:00:00+00:00" },
      ] as Segment[];
    },
  },
  {
    id: "schedule",
    rows: ".schedule__item, article.card",
    given: () => {
      studio.canvas = {
        jobs: [],
        steps: [],
        outcomes: [],
        scheduled_work: [
          { id: "W-1", name: "Weekly scan", agent_id: "a", trigger_type: "cron", schedule_expression: "0 9 * * 1", status: "scheduled", created_at: "2026-10-01T00:00:00+00:00" },
          { id: "W-2", name: "Nightly digest", agent_id: "a", trigger_type: "interval", schedule_expression: "24h", status: "pending", created_at: "2026-10-01T00:00:00+00:00" },
        ] as ScheduledWork[],
        source: "mcp",
      };
    },
  },
];

describe("the map counts what the panel shows", () => {
  beforeEach(() => {
    studio.canvas = { jobs: [], steps: [], outcomes: [], source: "mcp" };
    studio.memory = [];
    studio.segments = [];
    studio.signals = [];
    studio.unreadSignalCount = 0;
    studio.canvasState = { kind: "ready", data: studio.canvas };
  });

  for (const testCase of CASES) {
    it(`${testCase.id}: one number, that many rows`, () => {
      testCase.given();
      studio.canvasState = { kind: "ready", data: studio.canvas };

      const { container } = render(
        <>
          <WorkbenchRail />
          <div data-testid="panel">{findPanel(testCase.id as never).render()}</div>
        </>,
      );

      const shown = Number(mapCount(testCase.id).replace("+", ""));
      const rows = container.querySelectorAll(`[data-testid="panel"] ${testCase.rows}`).length;

      expect({ destination: testCase.id, shown, rows }).toEqual({
        destination: testCase.id,
        shown: rows,
        rows,
      });
      expect(rows).toBeGreaterThan(0);
    });
  }

  it("Catch up counts what is unread, which is not what the feed lists", () => {
    studio.signals = [
      { id: "SIG-1", title: "A signal", severity: "info", created_at: "2026-10-01T00:00:00+00:00", suppressed: false, fingerprint: "f1", kind: "outcome_scored" },
      { id: "SIG-2", title: "Another", severity: "info", created_at: "2026-10-01T00:00:00+00:00", suppressed: false, fingerprint: "f2", kind: "outcome_scored" },
    ] as Signal[];
    studio.unreadSignalCount = 1;

    const { container } = render(
      <>
        <WorkbenchRail />
        <div data-testid="panel">{findPanel("catchup").render()}</div>
      </>,
    );

    expect(mapCount("catchup")).toBe("1");
    expect(container.querySelectorAll('[data-testid="panel"] .catchup-card')).toHaveLength(2);
  });
});
