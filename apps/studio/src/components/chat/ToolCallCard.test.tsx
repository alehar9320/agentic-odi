import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ToolCallCardProps } from "./ToolCallCard";
import { ToolCallCard } from "./ToolCallCard";

const asked = { query: "Retention", limit: 3 };
const answer = { jobs: [{ id: "JOB-1", name: "Retention" }] };

const writeText = vi.fn<(text: string) => Promise<void>>();

const card = (props: Partial<ToolCallCardProps> = {}) =>
  render(
    <ToolCallCard
      callId="call-1"
      name="get_jobs"
      label="get jobs"
      status="ok"
      input={asked}
      preview='[{"id"'
      output={answer}
      {...props}
    />,
  );

const summary = () => screen.getByRole("button", { name: /get jobs/ });

describe("ToolCallCard", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    writeText.mockReset();
    writeText.mockImplementation(async () => {});
  });

  it("collapses to the one line the transcript already showed", () => {
    const { container } = card();

    expect(summary()).toHaveAttribute("aria-expanded", "false");
    expect(container.querySelector(".tool-trace__preview")?.textContent).toBe('[{"id"');
    // Nothing of the body is mounted until the call is opened.
    expect(container.querySelectorAll(".tool-call__json")).toHaveLength(0);
    expect(screen.queryByText("Input")).toBeNull();
  });

  it("opens to show what was asked and what came back", () => {
    const { container } = card();
    fireEvent.click(summary());

    expect(summary()).toHaveAttribute("aria-expanded", "true");
    const bodies = container.querySelectorAll(".tool-call__json");
    expect(bodies).toHaveLength(2);
    expect(bodies[0]?.textContent).toContain('"query": "Retention"');
    expect(bodies[1]?.textContent).toContain('"JOB-1"');
  });

  it("copies the call as JSON the clipboard can prove", () => {
    card();
    fireEvent.click(summary());
    fireEvent.click(screen.getByRole("button", { name: "Copy JSON" }));

    const [[copied]] = writeText.mock.calls;
    expect(JSON.parse(copied as string)).toEqual({
      name: "get_jobs",
      arguments: asked,
      result: answer,
    });
  });

  it("says it copied and then goes quiet", async () => {
    vi.useFakeTimers();
    card();
    fireEvent.click(summary());
    fireEvent.click(screen.getByRole("button", { name: "Copy JSON" }));
    await act(async () => {});

    expect(screen.getByText("Copied")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(2100);
    });
    expect(screen.queryByText("Copied")).toBeNull();
    vi.useRealTimers();
  });

  it("stays quiet when the clipboard refuses", async () => {
    writeText.mockRejectedValueOnce(new Error("denied"));
    card();
    fireEvent.click(summary());
    fireEvent.click(screen.getByRole("button", { name: "Copy JSON" }));

    await vi.waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(screen.queryByText("Copied")).toBeNull();
  });

  it("shows a plain-text answer as the text it arrived as", () => {
    const { container } = card({ preview: undefined, output: "registered connector Retention" });
    fireEvent.click(summary());

    expect(container.querySelectorAll(".tool-call__json")[1]?.textContent).toBe(
      "registered connector Retention",
    );
  });

  it("shows what a call still waiting was asked", () => {
    const { container } = card({ status: "running", preview: undefined, output: undefined });

    expect(summary().textContent).toContain("working");
    fireEvent.click(summary());
    expect(container.querySelectorAll(".tool-call__json")).toHaveLength(1);
    expect(container.querySelectorAll(".tool-call__json")[0]?.textContent).toContain(
      '"query": "Retention"',
    );
    expect(screen.getByText("Waiting for the tool to answer.")).toBeInTheDocument();
  });

  it("keeps a failed call marked as an error", () => {
    const { container } = card({ status: "error", isError: true });

    expect(container.querySelector(".tool-trace")).toHaveClass("is-error");
  });

  it("expands one call without touching the next", () => {
    render(
      <>
        <ToolCallCard callId="call-1" name="get_jobs" label="get jobs" status="ok" input={asked} />
        <ToolCallCard callId="call-2" name="get_jobs" label="get jobs" status="ok" input={asked} />
      </>,
    );

    const rows = screen.getAllByRole("button", { name: /get jobs/ });
    fireEvent.click(rows[1] as HTMLElement);

    expect(rows[1]).toHaveAttribute("aria-expanded", "true");
    expect(rows[0]).toHaveAttribute("aria-expanded", "false");
  });

  it("collapses every card again when the transcript remounts", () => {
    const first = card();
    fireEvent.click(summary());
    expect(summary()).toHaveAttribute("aria-expanded", "true");
    first.unmount();

    card();
    expect(summary()).toHaveAttribute("aria-expanded", "false");
  });

  it("is a button that hands the keyboard to the body it opens", () => {
    const { container } = card();
    const row = summary();

    expect(row.tagName).toBe("BUTTON");
    row.focus();
    fireEvent.click(row);

    expect(row).toHaveAttribute("aria-expanded", "true");
    const panelId = row.getAttribute("aria-controls");
    expect(container.querySelector(`[id="${panelId}"]`)).not.toBeNull();
  });
});
