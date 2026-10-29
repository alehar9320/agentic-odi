import { configure } from "@chromatic-com/vitest";
import type { ReactNode } from "react";
import { expect, it } from "vitest";
import { render } from "vitest-browser-react";

import "../styles/theme.css";
import type { StudioError } from "../types";
import { FailurePanel } from "./FailurePanel";

// The build table would otherwise name this `FailurePanel.visual` after the
// test file rather than the component it covers.
configure({ title: "FailurePanel" });

const baseError: StudioError = {
  code: "sidecar_unreachable",
  message: "The Living Studio sidecar is not answering.",
  retryable: true,
};

/** The panel is a block, so give it the width it occupies in the transcript. */
function Frame({ children }: { children: ReactNode }) {
  return <div style={{ width: 420, padding: 24 }}>{children}</div>;
}

// Each test is one Chromatic snapshot per build. Two states is enough to prove
// the pipeline without spending the free plan's snapshot budget.
it("shows a message when nothing else is known", async () => {
  const screen = await render(
    <Frame>
      <FailurePanel error={baseError} />
    </Frame>,
  );

  await expect.element(screen.getByRole("alert")).toBeVisible();
  await expect
    .element(screen.getByRole("alert"))
    .toHaveTextContent("The Living Studio sidecar is not answering.");
});

it("adds the detail, the suggestion, and a retry", async () => {
  const error: StudioError = {
    ...baseError,
    detail: "HTTP 503 from http://127.0.0.1:8100/api/canvas",
    suggestion: "Start the sidecar with `python -m agentic_odi_studio_api.main`.",
    request_id: "req_7f3a",
  };
  const screen = await render(
    <Frame>
      <FailurePanel error={error} onRetry={() => {}} retryText="try again" />
    </Frame>,
  );

  await expect.element(screen.getByText("Details")).toBeVisible();
  await expect
    .element(screen.getByText("Start the sidecar with `python -m agentic_odi_studio_api.main`."))
    .toBeVisible();
  await expect.element(screen.getByRole("button", { name: "Retry" })).toBeVisible();
});
