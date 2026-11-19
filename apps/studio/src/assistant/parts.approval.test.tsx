/**
 * The approval card, exercised directly.
 *
 * `ToolPart` reads only the part it is mounted for, so these tests hand it the
 * props the runtime would and assert what a person sees and sends: the
 * arguments, the consequence sentence, and the reason that travels with a
 * refusal.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ToolCallMessagePartProps } from "@assistant-ui/react";

import { ToolPart } from "./parts";

const running = { type: "running" } as const;

function props(overrides: Partial<ToolCallMessagePartProps> = {}): ToolCallMessagePartProps {
  return {
    toolName: "add_job",
    args: {},
    argsText: "{}",
    status: running,
    addResult: vi.fn(),
    resume: vi.fn(),
    respondToApproval: vi.fn(async () => undefined),
    ...overrides,
  } as unknown as ToolCallMessagePartProps;
}

describe("ToolPart approval", () => {
  it("states the consequence and lists the arguments", () => {
    render(
      <ToolPart
        {...props({
          args: { name: "Retention", description: "Keep accounts" },
          approval: { id: "apv_1", prompt: "Allow the assistant to add job?" },
        })}
      />,
    );

    expect(screen.getByText("This creates a job.")).toBeTruthy();
    expect(screen.getByText("name")).toBeTruthy();
    expect(screen.getByText("Retention")).toBeTruthy();
    expect(screen.getByText("description")).toBeTruthy();
    expect(screen.getByText("Keep accounts")).toBeTruthy();
  });

  it("says so honestly when the tool has no known consequence", () => {
    render(
      <ToolPart
        {...props({
          toolName: "make_coffee",
          approval: { id: "apv_1", prompt: "Allow?" },
        })}
      />,
    );

    expect(screen.getByText("This runs make_coffee.")).toBeTruthy();
  });

  it("keeps the raw JSON behind a disclosure", () => {
    render(
      <ToolPart
        {...props({
          args: { name: "Retention" },
          approval: { id: "apv_1", prompt: "Allow?" },
        })}
      />,
    );

    const toggle = screen.getByRole("button", { name: /raw arguments/i });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    const panel = document.getElementById(toggle.getAttribute("aria-controls") as string);
    expect(panel?.hasAttribute("hidden")).toBe(true);

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(panel?.hasAttribute("hidden")).toBe(false);
    expect(panel?.textContent).toContain('"name": "Retention"');
  });

  it("sends a reason with the refusal, and nothing else", async () => {
    const respondToApproval = vi.fn(async () => undefined);
    render(
      <ToolPart {...props({ approval: { id: "apv_1", prompt: "Allow?" }, respondToApproval })} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Don't allow" }));
    fireEvent.change(screen.getByLabelText(/why not/i), {
      target: { value: "Too destructive for a demo" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send refusal" }));

    expect(respondToApproval).toHaveBeenCalledWith({
      approved: false,
      reason: "Too destructive for a demo",
    });
  });

  it("omits the reason when the answer is yes", async () => {
    const respondToApproval = vi.fn(async () => undefined);
    render(
      <ToolPart {...props({ approval: { id: "apv_1", prompt: "Allow?" }, respondToApproval })} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Allow" }));

    expect(respondToApproval).toHaveBeenCalledWith({ approved: true });
  });

  it("stops the reason at 280 characters", () => {
    render(<ToolPart {...props({ approval: { id: "apv_1", prompt: "Allow?" } })} />);

    fireEvent.click(screen.getByRole("button", { name: "Don't allow" }));
    const input = screen.getByLabelText(/why not/i) as HTMLTextAreaElement;
    expect(input.maxLength).toBe(280);
    expect(screen.getByText("0/280")).toBeTruthy();
  });

  it("names a failed call in text, not only in colour", () => {
    render(
      <ToolPart
        {...props({ result: { status: "error" }, isError: true, status: { type: "complete" } })}
      />,
    );

    expect(screen.getByText("· failed")).toBeTruthy();
  });

  it("names a declined call in text", () => {
    render(
      <ToolPart
        {...props({ result: { status: "declined" }, status: { type: "complete" } })}
      />,
    );

    expect(screen.getByText("· declined")).toBeTruthy();
  });

  it("moves focus to the trace after the card is answered", async () => {
    const respondToApproval = vi.fn(async () => undefined);
    render(
      <ToolPart {...props({ approval: { id: "apv_1", prompt: "Allow?" }, respondToApproval })} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Allow" }));

    const trace = await screen.findByText("add job");
    expect(document.activeElement).toBe(trace.closest("p"));
  });

  it("reaches and answers the card with the keyboard alone", () => {
    render(<ToolPart {...props({ approval: { id: "apv_1", prompt: "Allow?" } })} />);

    // Both controls are real buttons, so Tab reaches them and Enter activates
    // them; a focused button's Enter is delivered as a click.
    const allow = screen.getByRole("button", { name: "Allow" });
    const deny = screen.getByRole("button", { name: "Don't allow" });
    expect(allow.tagName).toBe("BUTTON");
    expect(deny.tagName).toBe("BUTTON");

    deny.focus();
    expect(document.activeElement).toBe(deny);
    fireEvent.click(deny);

    expect(screen.getByLabelText(/why not/i)).toBeTruthy();
  });
});
