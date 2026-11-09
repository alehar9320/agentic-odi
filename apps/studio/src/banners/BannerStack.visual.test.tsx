import { configure } from "@chromatic-com/vitest";
import type { ReactNode } from "react";
import { expect, it } from "vitest";
import { render } from "vitest-browser-react";

import "../styles/theme.css";
import { BannerStack } from "./BannerStack";
import { resolveSpec } from "./catalog";
import type { Banner, BannerKind } from "./types";

// The build table would otherwise name this `BannerStack.visual` after the test
// file rather than the surface it covers.
configure({ title: "Banner" });

function banner(kind: BannerKind, overrides: Partial<Banner> = {}): Banner {
  return {
    ...resolveSpec({ kind }),
    id: kind,
    raisedAt: 0,
    ...overrides,
  };
}

/** The docks are fixed-position; a framed, relative host keeps them in frame. */
function Frame({ children }: { children: ReactNode }) {
  return (
    <div style={{ position: "relative", width: 900, height: 700, background: "#0b0d12" }}>
      {children}
    </div>
  );
}

// One Chromatic snapshot per test. Four states prove every severity, both docks,
// the multi-action layout, and the overflow affordance without spending the free
// plan's snapshot budget.
it("renders a critical top strip", async () => {
  const screen = await render(
    <Frame>
      <BannerStack banners={[banner("write-rejected")]} />
    </Frame>,
  );

  await expect.element(screen.getByText(/write was rejected/i)).toBeVisible();
});

it("renders an informational top strip", async () => {
  const screen = await render(
    <Frame>
      <BannerStack banners={[banner("offline")]} />
    </Frame>,
  );

  await expect.element(screen.getByText(/you're offline/i)).toBeVisible();
});

it("stacks corner toasts for success, info, and error", async () => {
  const screen = await render(
    <Frame>
      <BannerStack
        banners={[
          banner("success", { id: "s1", body: "Step added to Job Map!" }),
          banner("info", { id: "i1", body: "Background activity: sync finished." }),
          banner("error", { id: "e1", body: "The MCP server is unreachable." }),
        ]}
      />
    </Frame>,
  );

  await expect.element(screen.getByText("Step added to Job Map!")).toBeVisible();
  await expect.element(screen.getByText("The MCP server is unreachable.")).toBeVisible();
});

it("collapses the excess into an overflow count", async () => {
  const screen = await render(
    <Frame>
      <BannerStack banners={[banner("write-rejected")]} overflow={4} />
    </Frame>,
  );

  await expect.element(screen.getByText(/\+4 more notices/i)).toBeVisible();
});
