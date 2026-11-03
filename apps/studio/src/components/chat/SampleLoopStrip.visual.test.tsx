import { configure } from "@chromatic-com/vitest";
import type { ReactNode } from "react";
import { expect, it } from "vitest";
import { render } from "vitest-browser-react";

import "../../styles/theme.css";
import { SampleLoopStrip } from "./SampleLoopStrip";

// The build table would otherwise name this `SampleLoopStrip.visual` after the
// test file rather than the surface it covers.
configure({ title: "SampleLoopStrip" });

/**
 * One Chromatic snapshot per theme, so a regression in either palette shows up
 * as a diff. The tokens are scoped to `html.theme-*`, so the class is set on
 * the document element the way the app's bootstrap sets it.
 */
function Frame({ children }: { children: ReactNode }) {
  return (
    <div style={{ width: 900, height: 700, padding: 24, background: "var(--bg)" }}>
      <div style={{ maxWidth: 760 }}>{children}</div>
    </div>
  );
}

it("shows the finished sample loop in dark", async () => {
  document.documentElement.className = "theme-dark";
  const screen = await render(
    <Frame>
      <SampleLoopStrip onStartOwn={() => {}} />
    </Frame>,
  );

  await expect.element(screen.getByText("Sample, not your data.")).toBeVisible();
  await expect.element(screen.getByRole("button", { name: "Start with my own" })).toBeVisible();
});

it("shows the finished sample loop in light", async () => {
  document.documentElement.className = "theme-light";
  const screen = await render(
    <Frame>
      <SampleLoopStrip onStartOwn={() => {}} />
    </Frame>,
  );

  await expect.element(screen.getByText("Sample, not your data.")).toBeVisible();
  await expect.element(screen.getByRole("button", { name: "Hide" })).toBeVisible();
});
