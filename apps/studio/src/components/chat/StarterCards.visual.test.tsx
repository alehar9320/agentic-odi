import { configure } from "@chromatic-com/vitest";
import { expect, it } from "vitest";
import { render } from "vitest-browser-react";

import "../../styles/theme.css";

// One snapshot per theme: the starter cards must read as evidence in both.
configure({ title: "StarterCards" });

const STARTERS = [
  "Turn interview notes into one bet",
  "Summarize last week's support tickets",
  "Draft the Q3 planning doc",
];

function starterCard(label: string) {
  return (
    <button
      type="button"
      className="suggestion suggestion--card"
      aria-label={label}
    >
      <span aria-hidden>{label.charAt(0)}</span>
      {label}
    </button>
  );
}

function frame(theme: "dark" | "light") {
  document.documentElement.className = `theme-${theme}`;
  return (
    <div style={{ width: 390, padding: 16 }}>
      <div className="composer__pills" aria-label="Suggested next steps">
        {STARTERS.map((label) => starterCard(label))}
      </div>
    </div>
  );
}

it("renders visible starter cards in the dark theme", async () => {
  const screen = await render(frame("dark"));

  for (const label of STARTERS) {
    await expect.element(screen.getByRole("button", { name: label })).toBeVisible();
  }
});

it("renders visible starter cards in the light theme", async () => {
  const screen = await render(frame("light"));

  for (const label of STARTERS) {
    await expect.element(screen.getByRole("button", { name: label })).toBeVisible();
  }
});
