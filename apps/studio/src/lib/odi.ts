import type { ExistingSolution, OutcomeAlternativeLink, OutcomeInterval } from "../types";

export interface PillDescriptor {
  label: string;
  variant: "amber" | "green" | "blue";
}

const UNDERSERVED_THRESHOLD = 10;

export function opportunityScore(importance: number, satisfaction: number): number {
  return importance + Math.max(importance - satisfaction, 0);
}

export function isUnderserved(score: number | null | undefined): boolean {
  return score != null && score > UNDERSERVED_THRESHOLD;
}

export function formatOpportunityScore(score: number | null | undefined): string {
  if (score == null) {
    return "N/A";
  }
  return score.toFixed(1);
}

export function opportunityPill(score: number | null | undefined): PillDescriptor {
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
