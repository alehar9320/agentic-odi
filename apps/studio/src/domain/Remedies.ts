/**
 * Ways to fix a finding.
 *
 * This is an interface, not a feature. There is no backend that computes
 * remedies today (see the gap analysis in #741), so the module ships a typed
 * shape the agent *can* fill once one exists, plus a mock that says so.
 *
 * The client derives nothing: a remedy arrives whole, with its rationale and
 * its effort, and carries `source` so a surface can label an illustrative
 * entry instead of quoting it onward as analysis.
 */

/** Which finding a remedy addresses. A record kind and id, never a free string. */
export interface FindingSubject {
  kind: string;
  id: string;
}

/** How much work a remedy is. A closed vocabulary, not a sentence. */
export type RemedyEffort = "small" | "medium" | "large";

export interface Remedy {
  id: string;
  title: string;
  rationale: string;
  effort: RemedyEffort;
  /**
   * `"real"` when a backend produced this remedy; `"illustrative"` when it is a
   * labelled mock. A surface must show the label whenever this is not `"real"`.
   */
  source: "real" | "illustrative";
}

const EFFORTS: readonly RemedyEffort[] = ["small", "medium", "large"];

export function isRemedyEffort(value: unknown): value is RemedyEffort {
  return typeof value === "string" && EFFORTS.includes(value as RemedyEffort);
}

/**
 * The two illustrative remedies the mock returns.
 *
 * Placeholder text is not permission to write filler: each entry names an
 * action and the fact it turns on, and each carries `source: "illustrative"`
 * so it cannot be mistaken for a computed recommendation.
 */
const ILLUSTRATIVE_REMEDIES: Remedy[] = [
  {
    id: "remedy-reduce-first-step",
    title: "Remove the first manual step",
    rationale:
      "The finding turns on the effort before any value is seen. Deleting that step is the smallest change that moves the score.",
    effort: "small",
    source: "illustrative",
  },
  {
    id: "remedy-name-the-owner",
    title: "Give the hand-off a named owner",
    rationale:
      "The finding turns on nobody owning the hand-off. Naming one person is cheap and makes the gap measurable.",
    effort: "medium",
    source: "illustrative",
  },
];

/**
 * The remedies for a finding.
 *
 * Until a backend exists this returns the labelled mock for any subject. It
 * takes the subject so a real implementation can key on it without a signature
 * change, and so the call site already threads the finding through.
 */
export function getRemedies(finding: FindingSubject): Remedy[] {
  // Today the mock does not vary by finding; a real backend will. Naming the
  // subject in the body keeps the signature the spec asks for without
  // pretending the result is specific to this record.
  void finding;
  return ILLUSTRATIVE_REMEDIES.map((remedy) => ({ ...remedy }));
}
