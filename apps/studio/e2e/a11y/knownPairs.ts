import type { KnownPair } from "../../src/test/contrast";

/**
 * The pairs the contrast gate already knows about (issue #543, parent #331).
 *
 * These are the failures the browser walker finds today. They are token-level
 * problems, and every entry names the issue that owns the fix. #542 ("Measure
 * every token pair, then fix the tokens that fail AA") landed the token
 * corrections for the pairs it owned, so those entries are gone; what remains
 * is the opportunity matrix's own canvas fills, which #335 owns.
 *
 * This is a ratchet, not a licence:
 *
 *   - An unlisted pair fails the build immediately, with its selector, both
 *     colours, and its ratio.
 *   - `staleKnownPairs` fails the build when an entry here stops failing — for
 *     example the moment a token is corrected — so the list can only shrink.
 *   - Every entry names the issue that owns the fix, so the debt is visible.
 *
 * A pair is keyed by theme, the two colours, and the threshold — not by screen
 * — because one token pair usually appears on several screens.
 */
export const KNOWN_PAIRS: KnownPair[] = [
  // The opportunity matrix draws its own fills; #335 owns those canvas colours.
  {
    theme: "light",
    foreground: "rgb(21, 23, 28)",
    background: "rgb(109, 110, 113)",
    required: 4.5,
    issue: 335,
    note: "The matrix's SVG axis labels read --text over the chart's own fill",
  },
  {
    theme: "light",
    foreground: "rgb(86, 93, 107)",
    background: "rgb(109, 110, 113)",
    required: 4.5,
    issue: 335,
    note: "The matrix's axis captions read --muted over the chart's own fill",
  },
];
