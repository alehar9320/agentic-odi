// Visual: the finding card's labelled remedies and customer-words controls (#741).
import { configure } from "@chromatic-com/vitest";
import { afterEach, expect, it } from "vitest";
import { render } from "vitest-browser-react";

import type { Remedy } from "../../domain/Remedies";
import { CustomerWords, WaysToFix } from "./OutcomeCard";
import "../../styles/theme.css";

/**
 * The two illustrative results behind a finding (#741), pinned where a reader
 * meets them: the trigger carries the amber label, not a footnote under it.
 */
configure({ title: "Finding support" });

const previousTheme = document.documentElement.className;

afterEach(() => {
  document.documentElement.className = previousTheme;
});

const fixes: Remedy[] = [
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

function renderFindingSupport(): ReturnType<typeof render> {
  return render(
    <article className="card" aria-label="Outcome O-101">
      <WaysToFix remedies={fixes} />
      <CustomerWords
        evidence={{
          quotes: [
            {
              content:
                "We keep the spreadsheet open beside the tool because we don't trust the numbers in it yet.",
              source_name: "Interview — operations lead",
              source_kind: "interview",
            },
          ],
          count: 142,
          basis: "illustrative",
        }}
      />
    </article>,
  );
}

for (const theme of ["theme-dark", "theme-light"] as const) {
  it(`labels illustrative fixes and quotes beside their controls in ${theme}`, async () => {
    document.documentElement.className = theme;
    const screen = await renderFindingSupport();

    await expect
      .element(screen.getByRole("button", { name: "Ways to fix this (2)" }))
      .toBeVisible();
    await expect
      .element(screen.getByRole("button", { name: "View customer quotes & session data (142)" }))
      .toBeVisible();
    // The amber label sits beside each control, so it is read before the list
    // is opened rather than discovered inside it.
    await expect.element(screen.getByText("Simulated").first()).toBeVisible();
  });
}
