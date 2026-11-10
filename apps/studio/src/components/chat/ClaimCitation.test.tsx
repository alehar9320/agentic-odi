import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Claim, ClaimCitation as ClaimCitationRecord } from "../../types";
import { ClaimCitation } from "./ClaimCitation";

function citation(id: string, name: string, source_name: string): ClaimCitationRecord {
  return { id, name, source_name };
}

function claim(overrides: Partial<Claim> = {}): Claim {
  return {
    index: 0,
    text: "The onboarding quote stalled.",
    status: "cited",
    evidence: [],
    reason: null,
    ...overrides,
  };
}

function renderClaim(c: Claim) {
  return render(<ClaimCitation claim={c} />);
}

function trigger() {
  return screen.getByText("The onboarding quote stalled.");
}

describe("ClaimCitation", () => {
  it("opens the popover when the claim is hovered", () => {
    renderClaim(claim({ evidence: [citation("E-1", "Call with Acme", "Gong")] }));
    fireEvent.mouseEnter(trigger());
    expect(screen.getByText("Gong · Call with Acme")).toBeInTheDocument();
  });

  it("opens the popover when the claim is focused", () => {
    renderClaim(claim({ evidence: [citation("E-1", "Call with Acme", "Gong")] }));
    fireEvent.focus(trigger());
    expect(screen.getByText("Gong · Call with Acme")).toBeInTheDocument();
  });

  it("opens the popover on Enter", () => {
    renderClaim(claim({ evidence: [citation("E-1", "Call with Acme", "Gong")] }));
    fireEvent.keyDown(trigger(), { key: "Enter" });
    expect(screen.getByText("Gong · Call with Acme")).toBeInTheDocument();
  });

  it("closes on Escape and returns focus to the trigger", () => {
    renderClaim(claim({ evidence: [citation("E-1", "Call with Acme", "Gong")] }));
    const tr = trigger();
    fireEvent.focus(tr);
    expect(screen.getByText("Gong · Call with Acme")).toBeInTheDocument();
    fireEvent.keyDown(tr, { key: "Escape" });
    expect(screen.queryByText("Gong · Call with Acme")).not.toBeInTheDocument();
    expect(document.activeElement).toBe(tr);
  });

  it("closes on blur", () => {
    renderClaim(claim({ evidence: [citation("E-1", "Call with Acme", "Gong")] }));
    const tr = trigger();
    fireEvent.focus(tr);
    expect(screen.getByText("Gong · Call with Acme")).toBeInTheDocument();
    fireEvent.blur(tr);
    expect(screen.queryByText("Gong · Call with Acme")).not.toBeInTheDocument();
  });

  it("renders the quote then the sources for a complete claim", () => {
    renderClaim(
      claim({ evidence: [citation("E-1", "Call with Acme", "Gong"), citation("E-2", "Follow-up", "Gong")] }),
    );
    fireEvent.mouseEnter(trigger());
    const panel = document.querySelector(".claim-citation");
    expect(panel).not.toBeNull();
    const texts = Array.from(panel!.querySelectorAll("p, button")).map((el) => el.textContent);
    expect(texts).toEqual(["The onboarding quote stalled.", "Gong · Call with Acme", "Gong · Follow-up"]);
  });

  it("says no source recorded when a claim carries no evidence", () => {
    renderClaim(claim());
    fireEvent.mouseEnter(trigger());
    expect(screen.getByText("No source recorded")).toBeInTheDocument();
  });
});
