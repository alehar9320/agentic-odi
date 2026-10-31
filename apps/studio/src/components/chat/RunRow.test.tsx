import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { summarizeRun, type RunSummary } from "../../assistant/runSummary";
import { RunRow } from "./RunRow";

function summary(toolNames: string[]): RunSummary {
  return summarizeRun(toolNames.map((toolName) => ({ toolName, result: { status: "ok" } })));
}

describe("RunRow", () => {
  it("renders nothing for a turn that made no calls", () => {
    const { container } = render(
      <RunRow summary={summarizeRun([])} running={false} requiresAction={false}>
        <p>ignored</p>
      </RunRow>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("collapses a finished turn behind one row that names the calls", () => {
    render(
      <RunRow summary={summary(["list_jobs", "add_job"])} running={false} requiresAction={false}>
        <p className="call-card">list jobs</p>
      </RunRow>,
    );
    const toggle = screen.getByRole("button", { expanded: false });
    expect(toggle).toHaveTextContent("2 calls · 1 write");
    // The cards stay in the document; hiding them is the row's only concession.
    expect(screen.getByText("list jobs")).toBeInTheDocument();
  });

  it("is open while the turn streams", () => {
    render(
      <RunRow summary={summary(["list_jobs"])} running requiresAction={false}>
        <p>list jobs</p>
      </RunRow>,
    );
    expect(screen.getByRole("button", { expanded: true })).toBeInTheDocument();
    expect(document.querySelector(".run-summary__panel")).not.toHaveAttribute("hidden");
  });

  it("opens on click without moving focus off the row", () => {
    render(
      <RunRow summary={summary(["list_jobs", "add_job"])} running={false} requiresAction={false}>
        <p>list jobs</p>
      </RunRow>,
    );
    const toggle = screen.getByRole("button", { expanded: false });
    toggle.focus();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(document.activeElement).toBe(toggle);
  });

  it("cannot be collapsed while a call still needs an answer", () => {
    render(
      <RunRow summary={summary(["add_job"])} running={false} requiresAction>
        <p>allow this write?</p>
      </RunRow>,
    );
    const toggle = screen.getByRole("button", { expanded: true });
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(document.querySelector(".run-summary__panel")).not.toHaveAttribute("hidden");
  });

  it("names the calls that did not land on the row itself", () => {
    const failed = summarizeRun([
      { toolName: "add_job", result: { status: "ok" } },
      { toolName: "delete_job", result: { status: "error" }, isError: true },
    ]);
    render(
      <RunRow summary={failed} running={false} requiresAction={false}>
        <p>cards</p>
      </RunRow>,
    );
    expect(screen.getByRole("button", { expanded: false })).toHaveTextContent(
      "2 calls · 1 write · 1 error: delete job",
    );
  });
});
