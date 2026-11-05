import { configure } from "@chromatic-com/vitest";
import { afterEach, expect, it } from "vitest";
import { render } from "vitest-browser-react";

import "../../styles/theme.css";
import { ToolCallCard } from "./ToolCallCard";

// The build table would otherwise name this `ToolCallCard.visual` after the
// test file rather than the component it covers.
configure({ title: "ToolCallCard" });

const asked = { query: "Retention", limit: 3 };
const answer = { jobs: [{ id: "JOB-1", name: "Retention" }] };

function TwoCalls() {
  return (
    <div style={{ width: 460, padding: 24 }}>
      <ToolCallCard
        callId="call-1"
        name="get_jobs"
        label="get jobs"
        status="ok"
        input={asked}
        preview='[{"id"'
        output={answer}
      />
      <ToolCallCard
        callId="call-2"
        name="get_jobs"
        label="get jobs"
        status="running"
        input={{ query: "Activation" }}
      />
    </div>
  );
}

const rows = () => Array.from(document.querySelectorAll<HTMLElement>("button.tool-trace"));
const bodies = () => Array.from(document.querySelectorAll<HTMLElement>(".tool-call__json"));

afterEach(() => {
  document.documentElement.classList.remove("theme-light");
});

it("keeps the transcript rhythm when a call is closed", async () => {
  await render(<TwoCalls />);

  const [closed, working] = rows();
  await expect.element(closed).toHaveTextContent("get jobs");
  await expect.element(working).toHaveTextContent("working");
  await expect.element(closed).toHaveAttribute("aria-expanded", "false");
  expect(bodies()).toHaveLength(0);
});

// Last, so a light-theme class left on the document cannot tint the dark
// snapshots above it.
it("opens the exchange in the light theme", async () => {
  document.documentElement.classList.add("theme-light");
  await render(<TwoCalls />);

  const [first] = rows();
  first.click();

  await expect.element(first).toHaveAttribute("aria-expanded", "true");
  expect(bodies()).toHaveLength(2);
  await expect.element(bodies()[0]).toHaveTextContent('"query": "Retention"');
  await expect.element(bodies()[1]).toHaveTextContent("JOB-1");
});
