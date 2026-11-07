import type { KnownPair } from "../../src/test/contrast";

/**
 * The pairs the contrast gate already knows about (issue #543, parent #331).
 *
 * These are the failures the browser walker finds today. They are token-level
 * problems — a `--faint` that is a shade too dim, a pill that keeps a
 * dark-theme colour in light mode — and #542 ("Measure every token pair, then
 * fix the tokens that fail AA") is the slice that fixes them. It is not merged
 * yet, and the #543 guardrail says not to gate on a rule the previous slice has
 * not fixed, so the gate records them here instead of blocking every PR on work
 * that is already scheduled.
 *
 * This is a ratchet, not a licence:
 *
 *   - An unlisted pair fails the build immediately, with its selector, both
 *     colours, and its ratio.
 *   - `staleKnownPairs` fails the build when an entry here stops failing — for
 *     example the moment #542 lands — so the list can only shrink.
 *   - Every entry names the issue that owns the fix, so the debt is visible.
 *
 * A pair is keyed by theme, the two colours, and the threshold — not by screen
 * — because one token pair usually appears on several screens.
 */
export const KNOWN_PAIRS: KnownPair[] = [
  // --faint in the dark theme, over the raised and gradient surfaces it lands on.
  {
    theme: "dark",
    foreground: "rgb(125, 130, 140)",
    background: "rgb(29, 28, 28)",
    required: 4.5,
    issue: 542,
    note: "--faint on a raised outcome card (4.39:1)",
  },
  {
    theme: "dark",
    foreground: "rgb(125, 130, 140)",
    background: "rgb(33, 35, 49)",
    required: 4.5,
    issue: 542,
    note: "--faint on the catch-up metric strip (4.03:1)",
  },
  {
    theme: "dark",
    foreground: "rgb(125, 130, 140)",
    background: "rgb(26, 28, 43)",
    required: 4.5,
    issue: 542,
    note: "--faint on the catch-up summary card (4.37:1)",
  },
  {
    theme: "dark",
    foreground: "rgb(125, 130, 140)",
    background: "rgb(25, 27, 39)",
    required: 4.5,
    issue: 542,
    note: "--faint on the settings context label (4.46:1)",
  },
  // --faint in the light theme.
  {
    theme: "light",
    foreground: "rgb(104, 112, 128)",
    background: "rgb(232, 233, 247)",
    required: 4.5,
    issue: 542,
    note: "--faint on the themed shell (4.13:1)",
  },
  {
    theme: "light",
    foreground: "rgb(104, 112, 128)",
    background: "rgb(235, 235, 246)",
    required: 4.5,
    issue: 542,
    note: "--faint on the catch-up metric strip (4.21:1)",
  },
  {
    theme: "light",
    foreground: "rgb(104, 112, 128)",
    background: "rgb(34, 35, 38)",
    required: 4.5,
    issue: 542,
    note: "--faint on the lens footer note (3.14:1)",
  },
  // Other tokens, both themes.
  {
    theme: "light",
    foreground: "rgb(180, 83, 9)",
    background: "rgb(232, 233, 247)",
    required: 4.5,
    issue: 542,
    note: "--amber on the themed shell (4.17:1)",
  },
  {
    theme: "light",
    foreground: "rgb(91, 91, 214)",
    background: "rgb(231, 231, 253)",
    required: 4.5,
    issue: 542,
    note: "--accent on the blue badge (4.41:1)",
  },
  {
    theme: "dark",
    foreground: "rgb(255, 255, 255)",
    background: "rgb(139, 140, 248)",
    required: 4.5,
    issue: 542,
    note: "White on --accent for the primary button (2.91:1)",
  },
  {
    theme: "dark",
    foreground: "rgb(255, 255, 255)",
    background: "rgb(99, 102, 241)",
    required: 4.5,
    issue: 542,
    note: "White on --accent-strong for the bell badge (4.47:1)",
  },
  {
    theme: "light",
    foreground: "rgb(21, 23, 28)",
    background: "rgb(45, 46, 71)",
    required: 4.5,
    issue: 542,
    note: "--text on the lens footer button (1.36:1)",
  },
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
