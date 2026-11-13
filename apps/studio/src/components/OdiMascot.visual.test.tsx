import { configure } from "@chromatic-com/vitest";
import { expect, it } from "vitest";
import { render } from "vitest-browser-react";

import "../styles/theme.css";
import { OdiMascot } from "./OdiMascot";

// The build table would otherwise name this `OdiMascot.visual` after the test
// file rather than the component it covers.
configure({ title: "OdiMascot" });

/**
 * The home mark as it appears in the bar: 32 px next to the wordmark. This is
 * a regression guard for the tile edge, the radius, and the face at the size
 * the product actually renders it — Chromatic captures at 1×, so the
 * device-pixel-ratio proof lives in the pull request's screenshots.
 */
function renderOnBar(theme: "dark" | "light") {
  document.documentElement.className = `theme-${theme}`;
  return render(
    <div className="bar" style={{ display: "flex", alignItems: "center", gap: 10, padding: 16 }}>
      <span className="brand__mark" aria-hidden="true">
        <OdiMascot size={32} />
      </span>
      <span className="brand__wordmark">Living Studio</span>
    </div>,
  );
}

it("renders the mark on the dark bar surface", async () => {
  const screen = await renderOnBar("dark");
  await expect.element(screen.getByText("Living Studio")).toBeVisible();
});

it("renders the mark on the light bar surface", async () => {
  const screen = await renderOnBar("light");
  await expect.element(screen.getByText("Living Studio")).toBeVisible();
});
