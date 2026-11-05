import { configure } from "@chromatic-com/vitest";
import type { ReactNode } from "react";
import { expect, it } from "vitest";
import { render } from "vitest-browser-react";

import "../../styles/theme.css";
import { summarizeRun, type RunCall } from "../../assistant/runSummary";
import { RunRow } from "./RunRow";

configure({ title: "RunRow" });

/** The row is a transcript block, so give it the width it occupies there. */
function Frame({ children }: { children: ReactNode }) {
  return <div style={{ width: 460, padding: 24 }}>{children}</div>;
}

function settled(names: string[]): RunCall[] {
  return names.map((toolName) => ({ toolName, result: { status: "ok" } }));
}

function Cards({ names }: { names: string[] }) {
  return (
    <>
      {names.map((name) => (
        <p className="tool-trace" key={name}>
          <span className="tool-trace__dot" aria-hidden="true" />
          {name.replace(/_/g, " ")}
        </p>
      ))}
    </>
  );
}

it("collapses one call behind the row", async () => {
  const names = ["list_jobs"];
  const screen = await render(
    <Frame>
      <RunRow summary={summarizeRun(settled(names))} running={false} requiresAction={false}>
        <Cards names={names} />
      </RunRow>
    </Frame>,
  );

  const toggle = screen.getByRole("button", { name: /1 call/ });
  await expect.element(toggle).toHaveTextContent("1 call");
  await expect.element(toggle).toHaveAttribute("aria-expanded", "false");
});

it("expands a long run on request", async () => {
  const names = ["list_jobs", "get_outcome", "search_signals", "list_steps", "add_job"];
  const screen = await render(
    <Frame>
      <RunRow summary={summarizeRun(settled(names))} running={false} requiresAction={false}>
        <Cards names={names} />
      </RunRow>
    </Frame>,
  );

  const toggle = screen.getByRole("button", { name: /5 calls/ });
  await expect.element(toggle).toHaveTextContent("5 calls · 1 write");
  await toggle.click();
  await expect.element(toggle).toHaveAttribute("aria-expanded", "true");
  await expect.element(screen.getByText("search signals")).toBeVisible();
});

it("names the call that failed on the row itself", async () => {
  const names = ["list_jobs", "delete_step", "add_outcome"];
  const summary = summarizeRun([
    { toolName: "list_jobs", result: { status: "ok" } },
    { toolName: "delete_step", result: { status: "error" }, isError: true },
    { toolName: "add_outcome", result: { status: "ok" } },
  ]);
  const screen = await render(
    <Frame>
      <RunRow summary={summary} running={false} requiresAction={false}>
        <Cards names={names} />
      </RunRow>
    </Frame>,
  );

  await expect
    .element(screen.getByRole("button", { name: /3 calls/ }))
    .toHaveTextContent("3 calls · 1 write · 1 error: delete step");
});
