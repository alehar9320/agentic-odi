import { axe } from "vitest-axe";
import { expect } from "vitest";

/**
 * The automated accessibility gate.
 *
 * Runs axe's rules at WCAG 2.1 A + AA (plus its `region` rule, which checks
 * that content sits in landmarks), and fails on any violation. `color-contrast`
 * is scoped out here on purpose: jsdom computes no colors, so axe cannot
 * measure contrast in this environment. Contrast is measured in the Playwright
 * pass instead — see docs/architecture/testing.md#accessibility.
 *
 * Callers render a surface inside `<main>` with a heading so the document-level
 * rules (`landmark-one-main`, `page-has-heading-one`) judge a complete page.
 */
export async function expectAccessible(container: Element): Promise<void> {
  const results = await axe(container, {
    rules: {
      "color-contrast": { enabled: false },
    },
  });
  // vitest-axe 0.1.0's matcher registration is an empty module, so report the
  // violations ourselves: one readable line per rule and offending selector.
  expect(
    results.violations.map((violation) => ({
      rule: violation.id,
      help: violation.help,
      nodes: violation.nodes.map((node) => node.target.join(" ")),
    })),
  ).toEqual([]);
}
