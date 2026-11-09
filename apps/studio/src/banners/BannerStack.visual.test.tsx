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

// One Chromatic snapshot per test. Four states prove the critical severity, a
// top strip with actions, both docks, and the overflow affordance without
// spending the free plan's snapshot budget. No catalog kind is a `warning` since
// #507 deleted the last one ("Working by hand"); its styling stays for the next
// real warning rather than being proved by a fixture for a condition that is not
// one.
it("renders a critical top strip with its actions", async () => {
  const screen = await render(
    <Frame>
      <BannerStack banners={[banner("sidecar-down")]} />
    </Frame>,
  );

  await expect.element(screen.getByText(/sidecar isn't running/i)).toBeVisible();
  await expect.element(screen.getByRole("button", { name: "Recheck" })).toBeVisible();
});

it("renders a top strip with its single action", async () => {
  const screen = await render(
    <Frame>
      <BannerStack banners={[banner("update-available")]} />
    </Frame>,
  );

  await expect.element(screen.getByText(/An update is ready to download/i)).toBeVisible();
  await expect.element(screen.getByRole("button", { name: "Install" })).toBeVisible();
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
      <BannerStack banners={[banner("offline")]} overflow={4} />
    </Frame>,
  );

  await expect.element(screen.getByText(/\+4 more notices/i)).toBeVisible();
});
