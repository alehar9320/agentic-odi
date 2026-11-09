import { describe, expect, it } from "vitest";

import type { CanvasData, ConnectorPreset, StudioBrief, Thesis } from "../types";
import { briefFilename, briefToMarkdown } from "./export";
import { buildDecisionBrief, EXCERPT_LIMIT } from "./brief";

/**
 * The decision brief is the document a review reads, so these tests hold it to
 * the two things a reviewer depends on: every number came from a record, and
 * every section is present even when it has nothing to say.
 *
 * The default canvas scores O-1 at 16.0, O-3 at 13.0 and O-2 at 10.0, so O-1 is
 * the decision unless a test says otherwise.
 */

const generatedAt = new Date("2026-11-03T09:00:00Z");

const setup: StudioBrief = {
  product_name: "Shipwell",
  target_user: "Release engineers",
  job_statement: "Ship a hotfix to production without breaking the rollout",
  core_problem: "Deploys take a day",
  v2mom: { vision: "Every team ships the same afternoon it decides to." },
};

function outcome(
  id: string,
  statement: string,
  importance: number | null,
  satisfaction: number | null,
  overrides: Partial<CanvasData["outcomes"][number]> = {},
) {
  const score =
    importance != null && satisfaction != null
      ? importance + Math.max(importance - satisfaction, 0)
      : null;
  return { id, statement, importance, satisfaction, opportunity_score: score, ...overrides };
}

function canvas(overrides: Partial<CanvasData> = {}): CanvasData {
  return {
    jobs: [{ id: "JOB-1", name: "Ship a hotfix" }],
    steps: [],
    outcomes: [
      outcome("O-1", "Minimize the time between merge and production", 9, 2),
      outcome("O-2", "Reduce the risk of rolling back the wrong build", 8, 6),
      outcome("O-3", "Avoid re-reading the same incident thread when triaging", 7, 1),
    ],
    evidence: [],
    source: "mcp",
    ...overrides,
  };
}

function evidence(
  id: string,
  outcomeId: string | null,
  overrides: Partial<NonNullable<CanvasData["evidence"]>[number]> = {},
): NonNullable<CanvasData["evidence"]>[number] {
  return {
    id,
    outcome_id: outcomeId,
    source_name: "Gong",
    item_type: "call",
    name: `Interview ${id}`,
    content: "We rebuild the release three times before it lands.",
    url: null,
    ...overrides,
  };
}

function preset(
  id: string,
  area: ConnectorPreset["area"],
  label = id,
  isRecommended = false,
): ConnectorPreset {
  return {
    id,
    label,
    area,
    summary: `${label} summary.`,
    url: `https://mcp.example/${id}`,
    auth: "oauth",
    env_vars: [],
    headers: {},
    docs: `https://docs.example/${id}`,
    tools: [],
    is_recommended: isRecommended,
  };
}

const catalog: ConnectorPreset[] = [
  preset("posthog", "quantitative-data", "PostHog", true),
  preset("gong", "voice-of-customer", "Gong", true),
  preset("notion", "voice-of-customer", "Notion"),
  preset("similarweb", "market-intelligence", "Similarweb"),
];

function thesis(outcomeId: string, rationale: string, overrides: Partial<Thesis> = {}): Thesis {
  return {
    id: `T-${outcomeId}`,
    outcome_id: outcomeId,
    statement: "Minimize the time between merge and production",
    importance: 9,
    satisfaction: 2,
    opportunity_score: 16,
    rationale,
    created_at: "2026-11-01T09:00:00Z",
    ...overrides,
  };
}

/** Every call site supplies the canvas; the rest default to the setup above. */
type BuildInput = Partial<Parameters<typeof buildDecisionBrief>[0]> &
  Pick<Parameters<typeof buildDecisionBrief>[0], "canvas">;

function build(input: BuildInput) {
  return buildDecisionBrief({ brief: setup, theses: [], presets: catalog, generatedAt, ...input });
}

describe("buildDecisionBrief", () => {
  it("ranks the top five by the opportunity score the core uses", () => {
    const built = build({
      canvas: canvas({
        outcomes: [
          ...canvas().outcomes,
          outcome("O-4", "Cut the number of approval hops when shipping", 6, 5),
          outcome("O-5", "Shorten the queue before a release window when batching", 10, 3),
          outcome("O-6", "Reduce the time to find the owning team when escalating", 3, 3),
        ],
      }),
    });

    // 17.0, 16.0, 13.0, 10.0, 7.0; O-6 is the sixth and does not make the cut.
    expect(built.opportunities.map((entry) => entry.id)).toEqual([
      "O-5",
      "O-1",
      "O-3",
      "O-2",
      "O-4",
    ]);
    expect(built.opportunities[0]).toMatchObject({
      score: 17,
      importance: 10,
      satisfaction: 3,
      evidence_count: 0,
    });
    expect(built.decision?.id).toBe("O-5");
  });

  it("carries the saved thesis rationale into the decision", () => {
    const built = build({
      canvas: canvas(),
      theses: [thesis("O-1", "Because leadership asked for it in October.")],
    });

    expect(built.decision?.id).toBe("O-1");
    expect(built.decision?.rationale).toBe("Because leadership asked for it in October.");
  });

  it("keeps up to three linked records per opportunity and counts the rest", () => {
    const built = build({
      canvas: canvas({
        evidence: [
          evidence("E-1", "O-1"),
          evidence("E-2", "O-1", { url: "https://gong.example/e-2" }),
          evidence("E-3", "O-1"),
          evidence("E-4", "O-1"),
          evidence("E-5", "O-3"),
        ],
      }),
    });

    const shown = built.evidence.filter((entry) => entry.outcome_id === "O-1");
    expect(shown.map((entry) => entry.id)).toEqual(["E-1", "E-2", "E-3"]);
    expect(built.opportunities[0].evidence_count).toBe(4);
    expect(built.evidence.find((entry) => entry.id === "E-2")?.url).toBe(
      "https://gong.example/e-2",
    );
  });

  it("truncates an excerpt at the limit and marks it truncated", () => {
    const built = build({
      canvas: canvas({
        evidence: [evidence("E-1", "O-1", { content: "x".repeat(EXCERPT_LIMIT + 40) })],
      }),
    });

    const entry = built.evidence.find((item) => item.id === "E-1");
    expect(entry?.excerpt).toHaveLength(EXCERPT_LIMIT);
    expect(entry?.truncated).toBe(true);
  });

  it("counts evidence linked to no outcome as dissent", () => {
    const built = build({
      canvas: canvas({ evidence: [evidence("E-9", null), evidence("E-8", null)] }),
    });

    expect(built.unlinked_evidence_count).toBe(2);
    expect(built.dissent.map((entry) => entry.source)).toContain("unlinked-evidence");
  });

  it("assembles dissent from theses, warnings and the author's own objection", () => {
    const built = build({
      canvas: canvas({ warnings: ["3 outcomes have no importance rating."] }),
      theses: [
        thesis("O-3", "Another team already owns triage."),
        thesis("O-1", "The bet itself, not a counter-argument."),
      ],
      authorObjection: "Support already owns the tooling.",
    });

    // O-1 is the decision, so its rationale is already printed above; the rest
    // of the section is what argues against the bet.
    expect(built.dissent.map((entry) => entry.text)).toEqual([
      "Another team already owns triage.",
      "3 outcomes have no importance rating.",
      "Support already owns the tooling.",
    ]);
    expect(built.dissent.map((entry) => entry.source)).toEqual([
      "thesis",
      "warning",
      "author",
    ]);
  });

  it("keeps a thesis whose outcome left the landscape, and says so", () => {
    const built = build({
      canvas: canvas(),
      theses: [thesis("O-9", "Because we measured it in October.")],
    });

    const entry = built.dissent.find((item) => item.source === "thesis");
    expect(entry).toMatchObject({ outcome_id: "O-9", stale: true });
    expect(briefToMarkdown(built)).toContain("no longer on the landscape");
  });

  it("takes the next evidence step from the thinnest of the top three", () => {
    const built = build({
      canvas: canvas({
        evidence: [
          evidence("E-1", "O-1"),
          evidence("E-2", "O-1"),
          evidence("E-3", "O-1"),
          evidence("E-4", "O-3"),
        ],
      }),
    });

    // The top three are O-1 (3 records), O-3 (1) and O-2 (none): O-2 is thinnest.
    expect(built.next_evidence).toMatchObject({
      outcome_id: "O-2",
      evidence_count: 0,
      area: "voice-of-customer",
    });
    expect(built.next_evidence?.presets.map((item) => item.id)).toEqual(["gong", "notion"]);
  });

  it("breaks a tie for the thinnest outcome on score", () => {
    const built = build({ canvas: canvas() });

    expect(built.next_evidence).toMatchObject({ outcome_id: "O-1", evidence_count: 0 });
  });

  it("points at quantitative sources when the bet rests on quotes but no telemetry", () => {
    const built = build({
      canvas: canvas({
        outcomes: [
          outcome("O-1", "Minimize the time between merge and production", 9, 2, {
            telemetry: "deploy minutes",
          }),
          outcome("O-2", "Reduce the risk of rolling back the wrong build", 8, 6, {
            telemetry: "rollback rate",
          }),
          outcome("O-3", "Avoid re-reading the same incident thread when triaging", 7, 1, {
            telemetry: "",
          }),
        ],
        evidence: [
          evidence("E-1", "O-1"),
          evidence("E-2", "O-1"),
          evidence("E-3", "O-1"),
          evidence("E-4", "O-1"),
          evidence("E-5", "O-2"),
          evidence("E-6", "O-2"),
          evidence("E-7", "O-3"),
        ],
      }),
    });

    // O-3 is the thinnest of the top three and has a quote but no numbers.
    expect(built.next_evidence).toMatchObject({
      outcome_id: "O-3",
      evidence_count: 1,
      area: "quantitative-data",
    });
    expect(built.next_evidence?.presets.map((item) => item.id)).toEqual(["posthog"]);
  });

  it("says to connect a source when the catalog is not reachable", () => {
    const built = build({ canvas: canvas(), presets: [] });

    expect(built.next_evidence?.presets).toEqual([]);
    expect(built.next_evidence?.needs_connection).toBe(true);
  });

  it("reports the vision the setup conversation captured", () => {
    const built = build({ canvas: canvas() });

    expect(built.product_name).toBe("Shipwell");
    expect(built.vision).toBe("Every team ships the same afternoon it decides to.");
  });

  it("leaves the vision unset rather than inventing one", () => {
    const built = build({ canvas: canvas(), brief: { ...setup, v2mom: undefined } });

    expect(built.vision).toBeNull();
    expect(briefToMarkdown(built)).toContain("/start");
  });

  it("falls back to an untitled product when there is no brief", () => {
    const built = build({ canvas: canvas(), brief: null });

    expect(built.product_name).toBe("Untitled product");
    expect(built.vision).toBeNull();
  });

  it("excludes every seed row from every count and says how many were dropped", () => {
    const built = build({
      canvas: canvas({
        source: "seed",
        provenance: {
          kind: "seed",
          reason: "demo",
          generated_at: "2026-11-03T08:00:00Z",
          record_counts: { jobs: 1, steps: 0, outcomes: 3, evidence: 2 },
        },
        evidence: [evidence("E-1", "O-3"), evidence("E-2", "O-1")],
      }),
      theses: [thesis("O-1", "Carried over from the demo board.")],
    });

    expect(built.opportunities).toEqual([]);
    expect(built.evidence).toEqual([]);
    expect(built.decision).toBeNull();
    expect(built.next_evidence).toBeNull();
    expect(built.provenance).toMatchObject({
      kind: "seed",
      sample: true,
      excluded_sample_rows: { outcomes: 3, evidence: 2 },
    });
  });

  it("labels a cached snapshot and warns that it may be stale", () => {
    const built = build({
      canvas: canvas({
        provenance: {
          kind: "live",
          reason: "mcp_unreachable",
          generated_at: "2026-11-02T08:00:00Z",
          record_counts: { jobs: 1, steps: 0, outcomes: 3, evidence: 0 },
        },
      }),
      canvasCached: true,
    });

    expect(built.provenance.cached).toBe(true);
    const markdown = briefToMarkdown(built);
    expect(markdown).toContain("cached");
    expect(markdown).toContain("stale");
  });

  it("holds nothing when the canvas is empty", () => {
    const built = build({ canvas: null });

    expect(built.provenance.kind).toBe("empty");
    expect(briefToMarkdown(built)).toContain("Not recorded.");
  });
});

describe("briefToMarkdown", () => {
  const built = build({
    canvas: canvas({
      evidence: [
        evidence("E-1", "O-1", { url: "https://gong.example/e-1" }),
        evidence("E-2", "O-1"),
        evidence("E-3", "O-1"),
        evidence("E-4", "O-1"),
        evidence("E-5", "O-3"),
        evidence("E-6", "O-3"),
        evidence("E-7", "O-3"),
        evidence("E-8", "O-2"),
        evidence("E-9", "O-2"),
        evidence("E-10", "O-2"),
        evidence("E-11", "O-2"),
      ],
    }),
    theses: [thesis("O-1", "Because leadership asked for it in October.")],
  });
  const markdown = briefToMarkdown(built);

  it("prints the nine sections in order", () => {
    const headings = markdown
      .split("\n")
      .filter((line) => /^#{1,2} /.test(line))
      .map((line) => line.replace(/^#+ /, ""));

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
  });

  it("dates the document from its own timestamp", () => {
    expect(markdown).toContain("3 November 2026");
  });

  it("names the decision, its score, and the reasoning saved against it", () => {
    expect(markdown).toContain("O-1");
    expect(markdown).toContain("16.0");
    expect(markdown).toContain("Because leadership asked for it in October.");
  });

  it("counts the records each number rests on", () => {
    // O-1 holds four linked records but only three excerpts travel.
    expect(markdown).toContain("1 more linked record not shown");
    // O-3 is the thinnest of the top three at three records.
    expect(markdown).toContain("rests on 3 records");
  });

  it("carries a record url as a footnote, not inside the sentence", () => {
    expect(markdown).toContain("[1]");
    expect(markdown).toContain("1. [Gong](https://gong.example/e-1)");
  });

  it("uses no tables, because the studio's Markdown has no table block", () => {
    expect(markdown).not.toMatch(/^[^\n]*\|[^\n]*$/m);
  });

  it("states the score formula and where the scores come from", () => {
    expect(markdown).toContain("importance + max(importance - satisfaction, 0)");
    expect(markdown).toContain("not from the model");
  });

  it("says out loud when a section has nothing to argue with", () => {
    const oneSided = briefToMarkdown(build({ canvas: canvas() }));
    expect(oneSided).toContain("No dissent recorded. This brief argues one side.");
  });

  it("watermarks a document built from sample data", () => {
    const seeded = briefToMarkdown(build({ canvas: canvas({ source: "seed" }) }));
    expect(seeded).toContain("Demo data. Nothing here comes from your research.");
  });
});

describe("briefFilename", () => {
  it("names the file after the document and its date", () => {
    expect(briefFilename(new Date("2026-11-03T09:00:00Z"))).toBe(
      "agentic-odi-decision-brief-2026-11-03.md",
    );
  });
});
