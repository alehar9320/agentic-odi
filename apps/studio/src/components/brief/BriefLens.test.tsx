import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CanvasData, ConnectorPreset, StudioBrief, Thesis } from "../../types";

/**
 * The brief sheet is the one place the document is read, so these tests hold it
 * to a single promise: what the preview shows is what the file contains.
 */

const studio = vi.hoisted(() => {
  const noop = () => {};
  return {
    canvas: null as unknown,
    brief: null as unknown,
    theses: [] as unknown[],
    presets: [] as unknown[],
    canvasCached: false,
    openPanel: noop,
    closePanel: noop,
  };
});

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => studio,
}));

const exporter = vi.hoisted(() => ({ downloadMarkdown: vi.fn() }));
vi.mock("../../lib/export", async (importActual) => ({
  ...(await importActual<typeof import("../../lib/export")>()),
  downloadMarkdown: exporter.downloadMarkdown,
}));

import { BriefLens } from "./BriefLens";

const setup: StudioBrief = {
  product_name: "Shipwell",
  target_user: "Release engineers",
  job_statement: "Ship a hotfix without breaking the rollout",
  core_problem: "Deploys take a day",
  v2mom: { vision: "Every team ships the same afternoon it decides to." },
};

function canvas(overrides: Partial<CanvasData> = {}): CanvasData {
  return {
    jobs: [{ id: "JOB-1", name: "Ship a hotfix" }],
    steps: [],
    outcomes: [
      {
        id: "O-1",
        statement: "Minimize the time between merge and production",
        importance: 9,
        satisfaction: 2,
        opportunity_score: 16,
      },
      {
        id: "O-2",
        statement: "Reduce the risk of rolling back the wrong build",
        importance: 8,
        satisfaction: 6,
        opportunity_score: 10,
      },
    ],
    evidence: [
      {
        id: "E-1",
        outcome_id: "O-1",
        source_name: "Gong",
        item_type: "call",
        name: "Interview with Dana",
        content: "We rebuild the release three times before it lands.",
        url: "https://gong.example/e-1",
      },
    ],
    source: "mcp",
    ...overrides,
  };
}

const catalog: ConnectorPreset[] = [
  {
    id: "gong",
    label: "Gong",
    area: "voice-of-customer",
    summary: "Call transcripts with customer quotes.",
    url: "https://mcp.gong.io/mcp",
    auth: "oauth",
    env_vars: [],
    headers: {},
    docs: "https://help.gong.io",
    tools: [],
    is_recommended: true,
  },
];

const thesis: Thesis = {
  id: "T-1",
  outcome_id: "O-1",
  statement: "Minimize the time between merge and production",
  importance: 9,
  satisfaction: 2,
  opportunity_score: 16,
  rationale: "Because leadership asked for it in October.",
  created_at: "2026-11-01T09:00:00Z",
};

beforeEach(() => {
  studio.canvas = canvas();
  studio.brief = setup;
  studio.theses = [thesis];
  studio.presets = catalog;
  studio.canvasCached = false;
  exporter.downloadMarkdown.mockClear();
  document.body.className = "";
});

describe("BriefLens", () => {
  it("previews the document, section by section", () => {
    render(<BriefLens />);

    const headings = screen
      .getAllByRole("heading")
      .map((heading) => heading.textContent);
    expect(headings).toEqual([
      "Shipwell",
      "Provenance",
      "Vision",
      "The decision",
      "Top opportunities",
      "Evidence",
      "Dissent",
      "Next evidence",
      "Method",
    ]);
    expect(screen.getByText(/We rebuild the release three times/)).toBeInTheDocument();
  });

  it("puts the primary action under the keyboard when the document opens", () => {
    render(<BriefLens />);

    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Download .md" }),
    );
  });

  it("writes the previewed document to the file", () => {
    render(<BriefLens />);

    fireEvent.click(screen.getByRole("button", { name: "Download .md" }));

    expect(exporter.downloadMarkdown).toHaveBeenCalledTimes(1);
    const [markdown, filename] = exporter.downloadMarkdown.mock.calls[0];
    expect(markdown).toContain("## Method");
    expect(markdown).toContain("Because leadership asked for it in October.");
    expect(filename).toMatch(/^agentic-odi-decision-brief-\d{4}-\d{2}-\d{2}\.md$/);
  });

  it("copies the same document to the clipboard", async () => {
    const writeText = vi.fn<(text: string) => Promise<void>>();
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    render(<BriefLens />);

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(writeText.mock.calls[0][0]).toContain("## Dissent");
  });

  it("prints the brief alone", () => {
    const print = vi.fn();
    Object.defineProperty(window, "print", { value: print, configurable: true });
    render(<BriefLens />);

    fireEvent.click(screen.getByRole("button", { name: "Print / PDF" }));

    expect(print).toHaveBeenCalledTimes(1);
    expect(document.body.classList.contains("brief-printing")).toBe(true);

    // The browser fires afterprint when the dialog closes; the flag has to go
    // with it, or the next print of the conversation loses the thread too.
    fireEvent(window, new Event("afterprint"));
    expect(document.body.classList.contains("brief-printing")).toBe(false);
  });

  it("carries the author's own objection into the dissent section", () => {
    render(<BriefLens />);

    fireEvent.change(screen.getByRole("textbox", { name: /what argues against this/i }), {
      target: { value: "Support already owns the triage tooling." },
    });

    // Scoped to the document: the objection is also sitting in the textarea.
    const doc = within(screen.getByRole("article", { name: "Decision brief" }));
    expect(doc.getByText(/Support already owns the triage tooling/)).toBeInTheDocument();
    expect(doc.getByText(/author-supplied/)).toBeInTheDocument();
  });

  it("says so when the board is sample data", () => {
    studio.canvas = canvas({ source: "seed" });

    render(<BriefLens />);

    expect(
      screen.getByText("Demo data. Nothing here comes from your research."),
    ).toBeInTheDocument();
  });

  it("still produces a document when the canvas holds nothing", () => {
    studio.canvas = null;
    studio.brief = null;

    render(<BriefLens />);

    expect(screen.getByText("Untitled product")).toBeInTheDocument();
    expect(screen.getAllByText("Not recorded.").length).toBeGreaterThan(0);
  });
});

/**
 * The brief is an artifact, so it is held to the structure every artifact is
 * audited against. The authoritative rule set is `scripts/artifact_a11y.py`,
 * which is Python and cannot reach a React tree; these are its rules for the
 * one document the studio renders in the browser and exports as a file.
 */
describe("the brief's structure", () => {
  function renderBrief(): Element {
    render(<BriefLens />);
    return screen.getByRole("article", { name: "Decision brief" });
  }

  function headingLevels(root: Element): number[] {
    return Array.from(root.querySelectorAll("h1, h2, h3, h4, h5, h6")).map((heading) =>
      Number(heading.tagName.slice(1)),
    );
  }

  it("carries exactly one title", () => {
    expect(renderBrief().querySelectorAll("h1")).toHaveLength(1);
  });

  it("never skips a heading level", () => {
    const levels = headingLevels(renderBrief());
    const skips = levels.slice(1).filter((level, index) => level > levels[index] + 1);
    expect(skips).toEqual([]);
  });

  it("labels every chart it draws", () => {
    const unlabelled = Array.from(renderBrief().querySelectorAll("svg")).filter(
      (chart) =>
        chart.getAttribute("aria-hidden") !== "true" &&
        !chart.getAttribute("aria-label") &&
        !chart.getAttribute("aria-labelledby") &&
        !chart.querySelector("title"),
    );
    expect(unlabelled).toEqual([]);
  });

  it("uses each id once", () => {
    const ids = Array.from(renderBrief().querySelectorAll("[id]")).map((node) => node.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("keeps what a reader must know inside the printed document", () => {
    studio.canvas = canvas({ source: "seed" });

    render(<BriefLens />);
    const doc = screen.getByRole("article", { name: "Decision brief" });

    // The print sheet hides the sheet's chrome; everything that tells a reader
    // how much to trust the page has to be in the part that survives.
    expect(
      within(doc).getByText("Demo data. Nothing here comes from your research."),
    ).toBeInTheDocument();
    expect(within(doc).getAllByText("Not recorded.").length).toBeGreaterThan(0);
  });

  it("renders research as text, never as markup", () => {
    studio.canvas = canvas({
      evidence: [
        {
          id: "E-9",
          outcome_id: "O-1",
          source_name: 'Supporter "Nick"',
          item_type: "call",
          name: "<h1>The upgrade that failed</h1>",
          content: 'He said "<script>alert(1)</script>" and meant it.',
          url: null,
        },
      ],
    });

    render(<BriefLens />);
    const doc = screen.getByRole("article", { name: "Decision brief" });

    // Nothing escaped the parser as an element…
    expect(document.querySelector("script")).toBeNull();
    expect(doc.querySelectorAll("h1")).toHaveLength(1);
    // …and a reader still gets every character of what the person said.
    expect(within(doc).getByText(/<script>alert\(1\)<\/script>/)).toBeInTheDocument();
    expect(within(doc).getByText(/The upgrade that failed/)).toBeInTheDocument();
    expect(within(doc).getByText(/Supporter "Nick"/)).toBeInTheDocument();
  });
});
