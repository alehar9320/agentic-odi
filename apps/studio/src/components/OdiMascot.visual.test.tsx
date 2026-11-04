import { configure } from "@chromatic-com/vitest";
import { afterEach, expect, it } from "vitest";
import { render } from "vitest-browser-react";

import "../styles/theme.css";
import { OdiMascot } from "./OdiMascot";

// The build table would otherwise name this `OdiMascot.visual` after the test
// file rather than the component it covers.
configure({ title: "OdiMascot" });

/**
 * The mark as it appears in the bar: the tile beside the wordmark on the real
 * `.bar` surface. The theme class mirrors the bootstrap in `index.html`, so the
 * two snapshots capture the mark on both chrome colours.
 */
function Bar({ theme }: { theme: "dark" | "light" }) {
  return (
    <div className={`theme-${theme}`} style={{ background: "var(--bg)", width: 320 }}>
      <header className="bar">
        <div className="bar__left">
          <button type="button" className="brand brand--home">
            <span className="brand__mark" aria-hidden="true">
              <OdiMascot size={32} />
            </span>
            <span className="brand__wordmark">Living Studio</span>
          </button>
        </div>
      </header>
    </div>
  );
}

afterEach(() => {
  document.documentElement.className = "";
});

// One Chromatic snapshot per theme. Chromatic captures at 1x, so this is a
// regression guard on the drawn mark and the single tile, not the DPR proof.
it("draws the home mark on the dark bar", async () => {
  document.documentElement.className = "theme-dark";
  const screen = await render(<Bar theme="dark" />);

  await expect.element(screen.getByText("Living Studio")).toBeVisible();
  expect(document.querySelector(".brand__mark svg ellipse")).not.toBeNull();
});

it("draws the home mark on the light bar", async () => {
  document.documentElement.className = "theme-light";
  const screen = await render(<Bar theme="light" />);

  await expect.element(screen.getByText("Living Studio")).toBeVisible();
  expect(document.querySelector(".brand__mark svg ellipse")).not.toBeNull();
});
