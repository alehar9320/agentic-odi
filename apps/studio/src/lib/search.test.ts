import { describe, expect, it } from "vitest";

import { buildSearchIndex, flattenHits, searchAll, MAX_HITS_PER_GROUP } from "./search";
import type { CanvasData, Observation } from "../types";

const canvas: CanvasData = {
  source: "local",
  jobs: [
    { id: "JOB-1", name: "Propagate secrets", description: "Move a secret through every environment" },
  ],
  steps: [{ id: "STEP-1", job_id: "JOB-1", name: "Rotate the credential", order: 1 }],
  outcomes: [
    {
      id: "O-31",
      job_id: "JOB-1",
      statement: "Minimize the time it takes to propagate secrets",
    },
    { id: "O-32", job_id: "JOB-1", statement: "Reduce deployment drift" },
  ],
  evidence: [
    {
      id: "EV-1",
      name: "Acme call",
      content: "The secrets rotation took an afternoon and nobody knew why.",
      source_name: "Acme",
    },
  ],
};

const observation: Observation = {
  id: "obs-1",
  kind: "constraint",
  text: "We cannot change pricing this quarter.",
  data: {},
  status: "confirmed",
  confidence: 0.9,
  source_turn: 1,
  created_at: "2026-10-22T10:00:00+00:00",
  updated_at: "2026-10-22T10:00:00+00:00",
};

function index() {
  return buildSearchIndex(canvas, [observation]);
}

describe("buildSearchIndex", () => {
  it("indexes the store's records and the studio's memory", () => {
    const docs = index();
    expect(docs.map((doc) => doc.id)).toEqual([
      "O-31",
      "O-32",
      "EV-1",
      "JOB-1",
      "STEP-1",
      "obs-1",
    ]);
  });

  it("never indexes a record without an id", () => {
    const docs = buildSearchIndex(
      { source: "local", jobs: [], steps: [], outcomes: [{ statement: "No id here" }] },
      [],
    );
    expect(docs).toEqual([]);
  });

  it("tolerates a missing canvas and missing memory", () => {
    expect(buildSearchIndex(null, undefined)).toEqual([]);
  });
});

describe("searchAll", () => {
  it("returns nothing for an empty query rather than everything", () => {
    const result = searchAll(index(), "   ");
    expect(result.groups).toEqual([]);
    expect(result.total).toBe(0);
  });

  it("groups a matching outcome, evidence quote, and observation", () => {
    const result = searchAll(index(), "secrets");
    const kinds = result.groups.map((group) => group.kind);
    expect(kinds).toContain("outcome");
    expect(kinds).toContain("evidence");
    expect(result.groups.find((group) => group.kind === "outcome")?.hits[0].id).toBe("O-31");
    expect(result.groups.find((group) => group.kind === "evidence")?.hits[0].id).toBe("EV-1");
  });

  it("matches an observation's words", () => {
    const result = searchAll(index(), "pricing");
    expect(result.groups.map((group) => group.kind)).toEqual(["observation"]);
    expect(result.groups[0].hits[0].id).toBe("obs-1");
  });

  it("requires every token to match somewhere", () => {
    // "secrets" matches, "quarter" only matches the observation — no single
    // record holds both, so nothing is returned.
    expect(searchAll(index(), "secrets quarter").groups).toEqual([]);
  });

  it("is case-insensitive and ignores diacritics", () => {
    const docs = buildSearchIndex(
      { source: "local", jobs: [], steps: [], outcomes: [{ id: "O-1", statement: "Café rollout" }] },
      [],
    );
    expect(searchAll(docs, "CAFE").groups[0]?.hits[0].id).toBe("O-1");
  });

  it("finds an outcome by its id, however it is typed", () => {
    for (const query of ["O-31", "o-31", "o31", "O 31"]) {
      const hits = searchAll(index(), query).groups.flatMap((group) => group.hits);
      expect(hits[0]?.id, `query ${query}`).toBe("O-31");
    }
  });

  it("ranks an exact title above a body-only match", () => {
    const docs = buildSearchIndex(
      {
        source: "local",
        jobs: [{ id: "JOB-1", name: "Secrets", description: "About secrets" }],
        steps: [],
        outcomes: [{ id: "O-1", statement: "A statement that mentions secrets" }],
      },
      [],
    );
    const hits = searchAll(docs, "secrets").groups.flatMap((group) => group.hits);
    expect(hits[0].id).toBe("JOB-1");
  });

  it("bounds each group and reports the true total", () => {
    const outcomes = Array.from({ length: 50 }, (_unused, i) => ({
      id: `O-${i}`,
      statement: "A recurring phrase in every outcome",
    }));
    const docs = buildSearchIndex({ source: "local", jobs: [], steps: [], outcomes }, []);
    const result = searchAll(docs, "recurring");
    expect(result.groups[0].hits).toHaveLength(MAX_HITS_PER_GROUP);
    expect(result.total).toBe(50);
    expect(result.truncated).toBe(true);
  });

  it("keeps a snippet bounded and centred on the match", () => {
    const long = `${"word ".repeat(80)}needle${" word".repeat(80)}`;
    const docs = buildSearchIndex(
      { source: "local", jobs: [], steps: [], outcomes: [{ id: "O-1", statement: long }] },
      [],
    );
    const snippet = searchAll(docs, "needle").groups[0].hits[0].snippet;
    expect(snippet.length).toBeLessThanOrEqual(162);
    expect(snippet).toContain("needle");
    expect(snippet.startsWith("…")).toBe(true);
  });
});

describe("flattenHits", () => {
  it("walks the hits in the order the ranking draws them", () => {
    const flat = flattenHits(searchAll(index(), "secrets"));
    // The outcome and the job both match a title word; the kind order breaks
    // the tie, so the outcome leads. The quote only mentions the word in its
    // body, so it ranks last.
    expect(flat.map((entry) => entry.hit.id)).toEqual(["O-31", "JOB-1", "EV-1"]);
    expect(flat[0].groupLabel).toBe("Desired outcomes");
  });
});
