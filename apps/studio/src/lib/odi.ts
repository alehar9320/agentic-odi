import type { Evidence, ExistingSolution, Outcome, OutcomeAlternativeLink, OutcomeInterval } from "../types";
export interface PillDescriptor {
  label: string;
  variant: "amber" | "green" | "blue";
}

/** The line between "served" and "underserved". `packages/core` keeps its own
 * copy as `UNDERSERVED_SCORE`, and `tests/test_underserved_threshold_parity.py`
 * fails the moment the two disagree. */
export const UNDERSERVED_THRESHOLD = 10;

/** The one phrase for a score the store does not hold. */
export const UNSCORED_LABEL = "Not scored";

export function opportunityScore(importance: number, satisfaction: number): number {
  return importance + Math.max(importance - satisfaction, 0);
}

export function isUnderserved(score: number | null | undefined): boolean {
  return score != null && score > UNDERSERVED_THRESHOLD;
}

/** True only when the store actually holds a numeric score for this outcome.
 * A real score of `0` is scored; `null`, `undefined`, and non-finite values are not. */
export function hasScore(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function formatOpportunityScore(score: number | null | undefined): string {
  if (score == null) {
    return UNSCORED_LABEL;
  }
  return score.toFixed(1);
}

/**
 * True when a stored score no longer matches what its own inputs produce.
 *
 * The store recomputes only when both inputs are present and otherwise keeps
 * whatever it was handed (`packages/core/src/agentic_odi_core/services.py`), so a
 * disagreement is possible. The rule is a tolerance, not equality: a stored
 * `12.34` over inputs `8.6 / 4.9` (which produce `12.3`) is a rounding
 * difference, not a disagreement, so anything within `0.05` is treated as
 * agreeing. An unscored outcome never mismatches — there is nothing stored to
 * disagree with.
 */
export function scoreMismatch(
  stored: number | null | undefined,
  importance: number,
  satisfaction: number,
): boolean {
  if (!hasScore(stored)) {
    return false;
  }
  return Math.abs(stored - opportunityScore(importance, satisfaction)) > 0.05;
}

export function opportunityPill(score: number | null | undefined): PillDescriptor {
  // A missing score is not "served". Saying so would read as a verdict the
  // store never reached, so it gets a neutral descriptor of its own.
  if (!hasScore(score)) {
    return { label: UNSCORED_LABEL, variant: "blue" };
  }
  const formatted = formatOpportunityScore(score);
  if (isUnderserved(score)) {
    return { label: `🔥 Underserved (Opp: ${formatted})`, variant: "amber" };
  }
  return { label: `✓ Served (Opp: ${formatted})`, variant: "green" };
}

export interface SampleMetadata {
  score_method?: "estimate" | "survey" | "import" | null;
  importance_n?: number | null;
  satisfaction_n?: number | null;
}

/**
 * Describe how many people stand behind a score, and how it was obtained.
 *
 * An estimate, or a score with no recorded sample, reads as `est.` — never as a
 * fabricated `n`. A recorded sample shows both counts when they differ, so a
 * thin dimension is visible rather than averaged away. Mirrors the CLI's
 * `_sample_label` so both surfaces say the same thing.
 */
export function formatSample(outcome: SampleMetadata): string {
  const importanceN = outcome.importance_n ?? null;
  const satisfactionN = outcome.satisfaction_n ?? null;
  const method = outcome.score_method ?? "estimate";
  if (method === "estimate" || (importanceN == null && satisfactionN == null)) {
    return "est.";
  }
  if (importanceN === satisfactionN) {
    return `n=${importanceN} (${method})`;
  }
  return `n=${importanceN ?? "?"}/${satisfactionN ?? "?"} (${method})`;
}

export interface BandMetadata {
  score_method?: "estimate" | "survey" | "import" | null;
  opportunity_low?: number | null;
  opportunity_high?: number | null;
}

/**
 * Format a score's band, distinguishing a no-band estimate from a zero-width
 * survey band. An estimate reads as `no band` — never as a tight band — and a
 * survey whose band is zero-width reads `±0` so it is never read as proof of
 * certainty. Mirrors the CLI so both surfaces say the same thing.
 */
export function formatBand(outcome: BandMetadata): string {
  const low = outcome.opportunity_low ?? null;
  const high = outcome.opportunity_high ?? null;
  const method = outcome.score_method ?? "estimate";
  if (low == null || high == null) {
    return "no band";
  }
  if (low === high) {
    return method === "estimate" ? "no band" : `±0 (n=1)`;
  }
  return `${low.toFixed(1)}–${high.toFixed(1)}`;
}

/**
 * Describe a stored band's provenance in one line, or say plainly that there is
 * no band. Mirrors the CLI so both surfaces say the same thing: a no-band score
 * reads "no band", and a stale band says so rather than presenting its bounds
 * as current.
 */
export function formatBandProvenance(interval: OutcomeInterval | null): string {
  const band = interval?.band;
  if (!band) {
    return "no band";
  }
  const confidence = `${(band.confidence_level * 100).toFixed(0)}%`;
  const seed = band.seed == null ? "seed unrecorded" : `seed ${band.seed}`;
  const stale = band.stale ? " · stale" : "";
  return `n=${band.n} · ${confidence} · ${seed}${stale}`;
}

export type ConfidenceClass = "measured" | "thin" | "none";

/**
 * Whether an outcome's only recorded solution is a workaround (M2-07.2).
 *
 * True only when at least one linked alternative is a workaround and no linked
 * alternative is any other non-`nothing` kind. A `nothing` row never makes this
 * true, and an un-inventoried outcome is not "only a workaround" — it is
 * unknown, and the facet must not turn missing inventory into evidence.
 */
export function isOnlyWorkaround(links: OutcomeAlternativeLink[]): boolean {
  if (!links.length) {
    return false;
  }
  const kinds = links.map((entry) => entry.alternative.kind);
  const hasWorkaround = kinds.includes("workaround");
  const hasOtherSolution = kinds.some((kind) => kind !== "workaround" && kind !== "nothing");
  return hasWorkaround && !hasOtherSolution;
}

/**
 * The one sentence every surface renders for a solution state. Mirrors the core's
 * `EXISTING_SOLUTION_LABELS` so the Studio, the CLI and the brief cannot disagree:
 * `no_linked_nothing` and `no_link_at_all` are deliberately different sentences,
 * and only `yes` records a solution.
 */
export function existingSolutionLabel(state: ExistingSolution): string {
  switch (state) {
    case "yes":
      return "Existing solution: yes — a solution is recorded.";
    case "no_linked_nothing":
      return "Existing solution: no — the customer uses nothing today.";
    case "no_link_at_all":
      return "Existing solution: not yet inventoried — we have not asked.";
  }
}

/**
 * Classify how much evidence stands behind a score, matching the core's
 * provisional table: measured at a sample of at least 30 from a survey or
 * import; thin for a smaller survey/import sample; none for an estimate, an
 * unknown count or no score. A method label alone is never sufficient evidence.
 */
export function confidenceClass(outcome: SampleMetadata): ConfidenceClass {
  const method = outcome.score_method ?? "estimate";
  if (method === "estimate") {
    return "none";
  }
  const counts = [outcome.importance_n, outcome.satisfaction_n].filter(
    (value): value is number => value != null,
  );
  if (!counts.length) {
    return "none";
  }
  return Math.min(...counts) >= 30 ? "measured" : "thin";
}

/**
 * The M2-14 advisory threshold. A product warning line, not a claim that a
 * sample below it is worthless or that one above it is reliable. Mirrors the
 * core's `MIN_MEANINGFUL_N` so the landscape chip and the CLI footer agree.
 */
export const MIN_MEANINGFUL_N = 20;

export interface Advisory {
  n: number;
  threshold: number;
  method: string;
  dimension: "importance" | "satisfaction" | "both";
  message: string;
}

/**
 * Warn when a score's recorded sample is below the advisory threshold (M2-14).
 *
 * Returns `null` for an estimate, an unknown count, an unscored outcome or a
 * sample at or above the threshold — an estimate must never be advised at a
 * fabricated `n=0`. The advisory uses the smaller of the two counts and names
 * the dimension that triggered it, mirroring the core's `n_advisory` so both
 * surfaces word the warning identically.
 */
export function nAdvisory(outcome: SampleMetadata & { opportunity_score?: number | null }): Advisory | null {
  const method = outcome.score_method ?? "estimate";
  if (outcome.opportunity_score == null || method === "estimate") {
    return null;
  }
  const known: [Advisory["dimension"], number][] = [];
  if (outcome.importance_n != null) known.push(["importance", outcome.importance_n]);
  if (outcome.satisfaction_n != null) known.push(["satisfaction", outcome.satisfaction_n]);
  if (!known.length) {
    return null;
  }
  const smallest = Math.min(...known.map(([, n]) => n));
  if (smallest >= MIN_MEANINGFUL_N) {
    return null;
  }
  const below = known.filter(([, n]) => n === smallest);
  const dimension: Advisory["dimension"] = below.length === 2 ? "both" : below[0][0];
  return {
    n: smallest,
    threshold: MIN_MEANINGFUL_N,
    method,
    dimension,
    message: `n=${smallest} (${dimension}) is below the advisory threshold of ${MIN_MEANINGFUL_N}; treat this score as a lead to confirm, not a finding.`,
  };
}

/**
 * The importance at which an outcome's opportunity score crosses the threshold
 * for a given satisfaction: the solution of `2·importance − satisfaction =
 * UNDERSERVED_THRESHOLD` for importance. The underserved region sits above this
 * line, so the drawn zone and `isUnderserved(opportunityScore(...))` cannot
 * disagree.
 */
export function underservedBoundaryImportance(satisfaction: number): number {
  return (UNDERSERVED_THRESHOLD + satisfaction) / 2;
}

/**
 * The matrix's region test, in point space rather than score space. It is the
 * same rule as `isUnderserved(opportunityScore(importance, satisfaction))`, kept
 * separate so a plotted point and the shaded polygon share one boundary.
 */
export function isUnderservedPoint(importance: number, satisfaction: number): boolean {
  return importance > underservedBoundaryImportance(satisfaction);
}

/** What a group of member scores supports, with no score invented. */
export interface MemberScoreSummary {
  /** The mean of the members that carry a stored number, or null when none do. */
  mean: number | null;
  /** How many members carry a stored number. */
  scored: number;
  /** How many members carry none. A missing score is not a zero. */
  unscored: number;
}

/**
 * Summarize member scores without treating a missing score as a zero. The mean
 * divides by the scored members only, so one unscored outcome cannot drag the
 * group down, and an all-unscored group reports `null` rather than a fake `0`.
 */
export function summarizeMemberScores(
  scores: ReadonlyArray<number | null | undefined>,
): MemberScoreSummary {
  let total = 0;
  let scored = 0;
  let unscored = 0;
  for (const score of scores) {
    if (typeof score === "number" && Number.isFinite(score)) {
      total += score;
      scored += 1;
    } else {
      unscored += 1;
    }
  }
  return { mean: scored === 0 ? null : total / scored, scored, unscored };
}

/**
 * The landscape's headline average: the mean of the stored scores only. One
 * unscored outcome cannot drag the number down, and an all-unscored board has
 * no mean at all rather than a fake zero. Delegates the counting to
 * `summarizeMemberScores` so there is exactly one place that decides what
 * "scored" means.
 */
export function scoredAverage(outcomes: ReadonlyArray<Outcome>): MemberScoreSummary {
  return summarizeMemberScores(outcomes.map((outcome) => outcome.opportunity_score));
}

/**
 * The one sentence a segment board shows for its member scores. `Not scored`
 * replaces the mean when nothing is scored — never `0`, `NaN`, or a dash that
 * reads as a number.
 */
export function formatMemberMean(summary: MemberScoreSummary): string {
  if (summary.mean == null) {
    return UNSCORED_LABEL;
  }
  const base = `Mean opportunity ${summary.mean.toFixed(1)} across ${summary.scored} scored`;
  return summary.unscored > 0 ? `${base} · ${summary.unscored} not scored` : base;
}

/**
 * The one line a segment shows about where its people came from. An inferred
 * group is a candidate, not a researched market, and the board says so rather
 * than letting the two read alike.
 */
export function segmentBasisLine(peopleInferred: boolean): string {
  return peopleInferred
    ? "Candidate segment — grouped by the job it serves, not by researched people."
    : "People named from your evidence.";
}

/**
 * The one line an outcome card or table row shows for what it advances.
 *
 * The link is recorded at filing time, so the text shown is the objective's
 * text as it read then — a reworded vision leaves the old text behind as
 * drift evidence rather than silently updating the card. An outcome with no
 * link says plainly that it advances nothing yet, and never invents an
 * objective: a guess dressed as a record is the one thing this surface must
 * not do.
 */
export function formatAdvances(outcome: Outcome): string {
  const links = outcome.trace ?? [];
  if (links.length === 0) {
    return "Advances nothing yet";
  }
  const parts = links.map((link) => `${link.text} (${link.field})`);
  return `Advances ${parts.join(" · ")}`;
}

/** How well a stored score is backed, without inventing a number. */
export type ScoreConfidenceLevel = "verified" | "partial" | "hypothesis";

/**
 * What stands behind a score: the interview that produced it and the customer
 * quotes linked to it. Every field is derived from records that already exist —
 * nothing here is a judgement the store cannot justify.
 */
export interface ScoreConfidence {
  level: ScoreConfidenceLevel;
  /** A short phrase for the badge: "Verified", "Partly verified", "Hypothesis". */
  label: string;
  /** One human sentence of the basis, e.g. "3 of 3 answered · 2 quotes from Linear". */
  basis: string;
  /** How many customer quotes are linked to the outcome. */
  quotes: number;
  /** The distinct, non-empty source names those quotes came from. */
  sources: string[];
}

/**
 * Read how strongly an outcome's score is backed.
 *
 * The level is a function of two records only: the `claim_check` behind the
 * score (was the score verified, and was every question answered) and the
 * evidence records linked to the outcome. A score with no check and no linked
 * evidence is a hypothesis and says so — never a fake midpoint. A score whose
 * every asked question was answered is verified; one with answers but gaps is
 * only partly verified.
 */
export function scoreConfidence(
  outcome: Outcome,
  linkedEvidence: ReadonlyArray<Evidence>,
): ScoreConfidence {
  const check = outcome.claim_check ?? null;
  const asked = check?.asked ?? [];
  const answers = check?.answers ?? [];
  const skips = check?.skips ?? [];

  const quotes = linkedEvidence.length;
  const sources: string[] = [];
  for (const item of linkedEvidence) {
    const name = item.source_name?.trim();
    if (name && !sources.includes(name)) {
      sources.push(name);
    }
  }

  let level: ScoreConfidenceLevel;
  if (!check || answers.length === 0) {
    level = "hypothesis";
  } else if (check.verified === true && skips.length === 0 && answers.length >= asked.length) {
    level = "verified";
  } else {
    level = "partial";
  }

  const label =
    level === "verified" ? "Verified" : level === "partial" ? "Partly verified" : "Hypothesis";

  return { level, label, basis: confidenceBasis(level, check, asked.length, answers.length, skips.length, quotes, sources), quotes, sources };
}

function confidenceBasis(
  level: ScoreConfidenceLevel,
  check: Outcome["claim_check"],
  askedCount: number,
  answeredCount: number,
  skippedCount: number,
  quotes: number,
  sources: string[],
): string {
  // Nothing was asked and nothing is linked: the one sentence that says so.
  if (level === "hypothesis" && !check && quotes === 0) {
    return "nothing backs this yet";
  }

  const answered = check ? `${answeredCount} of ${askedCount} answered` : "no questions recorded";
  const skipped = skippedCount > 0 ? ` · ${skippedCount} skipped` : "";

  let evidence: string;
  if (quotes === 0) {
    evidence = "no quotes linked";
  } else if (sources.length === 0) {
    evidence = `${quotes} ${quotes === 1 ? "quote" : "quotes"} captured by hand`;
  } else {
    evidence = `${quotes} ${quotes === 1 ? "quote" : "quotes"} from ${sources.join(", ")}`;
  }

  return `${answered}${skipped} · ${evidence}`;
}

/**
 * The badge for a confidence level. A verified score reads settled (green), a
 * partly verified one is amber, and a hypothesis borrows the neutral blue that
 * "Not scored" uses — it is the one level that must never read as settled.
 */
export function confidencePill(confidence: ScoreConfidence): PillDescriptor {
  if (confidence.level === "verified") {
    return { label: confidence.label, variant: "green" };
  }
  if (confidence.level === "partial") {
    return { label: confidence.label, variant: "amber" };
  }
  return { label: confidence.label, variant: "blue" };
}

