import type {
  CanvasData,
  Observation,
  SearchGroup,
  SearchHit,
  SearchKind,
  SearchResponse,
} from "../types";

/**
 * Search over the records the studio already holds (#539, epic #325).
 *
 * The epic's contract is a pure index, not a route: the canvas is loaded for the
 * rail and panels, memory is fetched once, and both live in the browser. Running
 * the query here is what lets one box reach the ODI store and Studio memory
 * without a server crossing an ownership boundary the two do not share.
 *
 * Only text the person can already see and open is indexed: statements, names,
 * quotes, and observation sentences. Connector payloads (`evidence.raw`) and the
 * observation `data` blob are left out — a hit nobody can explain is worse than
 * a miss.
 */

export interface SearchDoc {
  kind: SearchKind;
  id: string;
  /** The record's own words: a statement, a name, or a quote. */
  title: string;
  /** Secondary text that can also match: a description or a quote body. */
  body: string;
  /** Extra tokens a person might type: the raw id, a source name. */
  keywords: string[];
}

/** Past this many hits in one group the box says so instead of growing. */
export const MAX_HITS_PER_GROUP = 20;

/** A snippet is bounded context around the match, never a whole transcript. */
export const MAX_SNIPPET = 160;

const GROUP_LABELS: Record<SearchKind, string> = {
  outcome: "Desired outcomes",
  evidence: "Evidence",
  observation: "What I've learned",
  job: "Jobs",
  step: "Steps",
};

/** Groups are drawn in this order; within a group, best score first. */
const KIND_ORDER: SearchKind[] = ["outcome", "evidence", "observation", "job", "step"];

/** Lowercase, strip diacritics: "Café" and "cafe" are the same query. */
function normalize(text: string): string {
  return text.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

/** The words of a string, split on anything that is not a letter or a digit. */
function words(text: string): string[] {
  return normalize(text)
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
}

/** A query collapsed to one normalised line, so a phrase can be matched whole. */
function collapse(text: string): string {
  return normalize(text).trim().replace(/\s+/g, " ");
}

/** An id with every separator gone, so `O-31`, `o31`, and `O 31` all agree. */
function compact(text: string): string {
  return normalize(text).replace(/[^a-z0-9]/g, "");
}

/** The tokens an id is reachable by: the id itself and its compact form. */
function idKeywords(id: string): string[] {
  const squashed = compact(id);
  return squashed && squashed !== collapse(id) ? [id, squashed] : [id];
}

/**
 * Build the index once per change of the data it reads. A few thousand short
 * strings rebuild synchronously; there is nothing to page or cache here.
 */
export function buildSearchIndex(
  canvas: CanvasData | null | undefined,
  memory: readonly Observation[] | null | undefined,
): SearchDoc[] {
  const docs: SearchDoc[] = [];
  if (canvas) {
    for (const outcome of canvas.outcomes ?? []) {
      if (!outcome.id) {
        continue;
      }
      docs.push({
        kind: "outcome",
        id: outcome.id,
        title: outcome.statement ?? "",
        body: "",
        keywords: idKeywords(outcome.id),
      });
    }
    for (const item of canvas.evidence ?? []) {
      docs.push({
        kind: "evidence",
        id: item.id,
        title: item.name ?? "",
        body: item.content ?? "",
        keywords: [...idKeywords(item.id), item.source_name ?? ""].filter(Boolean),
      });
    }
    for (const job of canvas.jobs ?? []) {
      docs.push({
        kind: "job",
        id: job.id,
        title: job.name ?? "",
        body: job.description ?? "",
        keywords: idKeywords(job.id),
      });
    }
    for (const step of canvas.steps ?? []) {
      if (!step.id) {
        continue;
      }
      docs.push({
        kind: "step",
        id: step.id,
        title: step.name ?? "",
        body: "",
        keywords: idKeywords(step.id),
      });
    }
  }
  for (const observation of memory ?? []) {
    docs.push({
      kind: "observation",
      id: observation.id,
      title: observation.text ?? "",
      body: "",
      keywords: idKeywords(observation.id),
    });
  }
  return docs;
}

/** A document's searchable surface, normalised once per query. */
interface PreparedDoc {
  doc: SearchDoc;
  title: string;
  body: string;
  titleWords: string[];
  bodyWords: string[];
  haystack: string;
}

function prepare(doc: SearchDoc): PreparedDoc {
  const title = collapse(doc.title);
  const body = collapse(doc.body);
  const keywordText = doc.keywords.join(" ");
  return {
    doc,
    title,
    body,
    titleWords: words(doc.title),
    bodyWords: words(doc.body),
    haystack: collapse([doc.title, doc.body, keywordText].join(" ")),
  };
}

/**
 * The best match class for the whole query, plus five for each extra token that
 * matched, capped at 100. Null when any token is missing: every token must land
 * somewhere, so a partial match never returns a row.
 */
function scoreDoc(prepared: PreparedDoc, tokens: string[], query: string): number | null {
  for (const token of tokens) {
    if (!prepared.haystack.includes(token)) {
      return null;
    }
  }

  const { title, body, titleWords, bodyWords, doc } = prepared;
  let base: number;
  if (collapse(doc.id) === query || title === query) {
    base = 100;
  } else if (title.startsWith(query)) {
    base = 80;
  } else if (titleWords.some((word) => word.startsWith(query))) {
    base = 60;
  } else if (title.includes(query)) {
    base = 40;
  } else if (bodyWords.some((word) => word.startsWith(query))) {
    base = 30;
  } else if (body.includes(query)) {
    base = 20;
  } else {
    base = 10;
  }

  return Math.min(100, base + 5 * (tokens.length - 1));
}

/** Bounded context around the first matched token, with ellipses at the cuts. */
function makeSnippet(title: string, body: string, tokens: string[]): string {
  const text = body ? `${title} — ${body}` : title;
  if (tokens.length === 0) {
    return text.slice(0, MAX_SNIPPET);
  }
  const pattern = new RegExp(
    tokens.map((token) => token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"),
    "i",
  );
  const match = pattern.exec(text);
  if (!match || match.index === undefined) {
    return text.slice(0, MAX_SNIPPET);
  }
  const start = Math.max(0, match.index - 60);
  const end = Math.min(text.length, start + MAX_SNIPPET);
  const lead = start > 0 ? "…" : "";
  const tail = end < text.length ? "…" : "";
  return `${lead}${text.slice(start, end).trim()}${tail}`;
}

function toHit(doc: SearchDoc, score: number, tokens: string[]): SearchHit {
  return {
    kind: doc.kind,
    id: doc.id,
    label: doc.title || doc.id,
    snippet: makeSnippet(doc.title, doc.body, tokens),
    score,
  };
}

/**
 * Run one query against a built index. Hits are grouped per artifact, capped per
 * group, and ordered best-first; `total` counts every match before the cap, so a
 * group header never lies about how much exists. An empty query returns nothing
 * rather than everything.
 */
export function searchAll(docs: readonly SearchDoc[], query: string): SearchResponse {
  const trimmed = query.trim();
  const tokens = words(trimmed);
  if (tokens.length === 0) {
    return { query: trimmed, groups: [], total: 0, truncated: false };
  }
  const collapsed = collapse(trimmed);

  const scored: Array<{ doc: SearchDoc; score: number }> = [];
  for (const doc of docs) {
    const score = scoreDoc(prepare(doc), tokens, collapsed);
    if (score !== null) {
      scored.push({ doc, score });
    }
  }
  // One global ranking: best score first, ties broken by the epic's kind order,
  // then by id so the same query always returns the same order.
  scored.sort(
    (a, b) =>
      b.score - a.score ||
      KIND_ORDER.indexOf(a.doc.kind) - KIND_ORDER.indexOf(b.doc.kind) ||
      a.doc.id.localeCompare(b.doc.id),
  );

  // Groups are the ranking cut by artifact, so they appear in the order their
  // best hit ranked rather than a fixed order that could bury the top result.
  const groups: SearchGroup[] = [];
  const seen = new Set<SearchKind>();
  for (const entry of scored) {
    if (seen.has(entry.doc.kind)) {
      continue;
    }
    seen.add(entry.doc.kind);
    const hits = scored
      .filter((candidate) => candidate.doc.kind === entry.doc.kind)
      .slice(0, MAX_HITS_PER_GROUP);
    groups.push({
      kind: entry.doc.kind,
      label: GROUP_LABELS[entry.doc.kind],
      hits: hits.map((candidate) => toHit(candidate.doc, candidate.score, tokens)),
    });
  }

  const returned = groups.reduce((sum, group) => sum + group.hits.length, 0);

  return {
    query: trimmed,
    groups,
    total: scored.length,
    truncated: scored.length > returned,
  };
}

/** One hit with the group it belongs to, in the order the keyboard walks them. */
export interface OrderedHit {
  hit: SearchHit;
  groupLabel: string;
}

/** Flatten the grouped answer into the single list arrow keys move through. */
export function flattenHits(response: SearchResponse): OrderedHit[] {
  return response.groups.flatMap((group) =>
    group.hits.map((hit) => ({ hit, groupLabel: group.label })),
  );
}
