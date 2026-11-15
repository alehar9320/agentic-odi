import { configure } from "@chromatic-com/vitest";
import { afterEach, expect, it } from "vitest";
import { render } from "vitest-browser-react";

import "../../styles/theme.css";

/** The empty-state starter pills, pinned above the composer input. */
configure({ title: "Starter cards" });

const previousTheme = document.documentElement.className;

afterEach(() => {
  document.documentElement.className = previousTheme;
});

function renderStarters(): ReturnType<typeof render> {
  return render(
    <div className="composer__pills" aria-label="Suggested next steps">
      <button type="button" className="suggestion">
        Review opportunity landscape
      </button>
      <button type="button" className="suggestion">
        Capture what you heard
      </button>
      <button type="button" className="suggestion">
        Map the job
      </button>
    </div>,
  );
}

it("shows a visible card surface in dark theme", async () => {
  document.documentElement.className = "theme-dark";
  const screen = await renderStarters();
  await expect
    .element(screen.getByRole("button", { name: /review opportunity landscape/i }))
    .toBeVisible();
  await expect.element(screen.getByRole("button", { name: /capture what you heard/i })).toBeVisible();
});

it("shows a visible card surface in light theme", async () => {
  document.documentElement.className = "theme-light";
  const screen = await renderStarters();
  await expect.element(screen.getByRole("button", { name: /review opportunity landscape/i })).toBeVisible();
  await expect.element(screen.getByRole("button", { name: /map the job/i })).toBeVisible();
});
