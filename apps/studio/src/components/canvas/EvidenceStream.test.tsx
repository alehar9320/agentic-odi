import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { StudioContextValue } from "../../state/StudioContext";
import type { Evidence } from "../../types";
import { EvidenceStream } from "./EvidenceStream";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";

const evidence: Evidence[] = [
  {
    id: "e1",
    name: "Call with Ada",
    content: "Deploys break whenever a secret rotates.",
    source_name: "Gong",
    item_type: "resource",
    job_id: "j1",
  },
  {
    id: "e2",
    name: "Slack thread",
    content: "Third time this week staging broke.",
    source_name: "Slack",
    item_type: "resource",
    job_id: "j2",
  },
  {
    id: "e3",
    name: "Support ticket",
    content: "We copy secrets by hand.",
    source_name: "Intercom",
    item_type: "note",
    job_id: null,
  },
];

const openPanel = vi.fn();

function renderWith(items: Evidence[] = evidence) {
  vi.mocked(useStudio).mockReturnValue({
    openPanel,
    canvasState: {
      kind: "ready",
      data: {
        jobs: [
          { id: "j1", name: "Ship safely" },
          { id: "j2", name: "Recover fast" },
        ],
        steps: [],
        outcomes: [],
        evidence: items,
        source: "local",
      },
    },
  } as unknown as StudioContextValue);
  return render(<EvidenceStream />);
}

const labels = () =>
  screen.getAllByRole("listitem").map((item) => item.querySelector("figcaption")?.textContent);

beforeEach(() => {
  localStorage.clear();
  vi.mocked(useStudio).mockReset();
  openPanel.mockReset();
});

describe("EvidenceStream", () => {
  it("renders each captured record with its source and linked job", () => {
    renderWith([evidence[0]]);

    expect(screen.getByText("Call with Ada")).toBeInTheDocument();
    expect(screen.getByText(/Deploys break whenever a secret rotates/)).toBeInTheDocument();
    expect(screen.getByText(/Linked to Ship safely · Gong · resource/)).toBeInTheDocument();
  });

  it("says plainly when nothing has been captured", () => {
    renderWith([]);

    expect(screen.getByText(/No evidence captured yet/)).toBeInTheDocument();
    expect(screen.queryByRole("listitem")).toBeNull();
    expect(screen.queryByText(/Gong call/i)).toBeNull();
  });

  it("opens Settings from the empty-state call to action", () => {
    renderWith([]);

    fireEvent.click(screen.getByRole("button", { name: /connect a source/i }));

    expect(openPanel).toHaveBeenCalledWith("settings");
  });

  it("reorders with the keyboard and remembers the order", () => {
    renderWith();

    fireEvent.keyDown(screen.getByRole("listitem", { name: /Call with Ada/ }), {
      key: "ArrowDown",
    });

    expect(labels()).toEqual(["Slack thread", "Call with Ada", "Support ticket"]);
    expect(JSON.parse(localStorage.getItem("agentic-odi.evidence-order") ?? "[]")).toEqual([
      "e2",
      "e1",
      "e3",
    ]);
  });

  it("reorders by dragging one record onto another", () => {
    renderWith();

    const first = screen.getByRole("listitem", { name: /Call with Ada/ });
    const last = screen.getByRole("listitem", { name: /Support ticket/ });
    fireEvent.dragStart(first);
    fireEvent.dragOver(last);
    fireEvent.drop(last);

    expect(labels()).toEqual(["Slack thread", "Support ticket", "Call with Ada"]);
    expect(JSON.parse(localStorage.getItem("agentic-odi.evidence-order") ?? "[]")).toEqual([
      "e2",
      "e3",
      "e1",
    ]);
  });

  it("restores a stored order on mount", () => {
    localStorage.setItem("agentic-odi.evidence-order", JSON.stringify(["e3", "e2", "e1"]));

    renderWith();

    expect(labels()).toEqual(["Support ticket", "Slack thread", "Call with Ada"]);
  });

  it("links a record back to the tool that owns it", () => {
    renderWith([{ ...evidence[0], url: "https://app.gong.io/calls/104" }]);

    const link = screen.getByRole("link", { name: /open in gong/i });
    expect(link).toHaveAttribute("href", "https://app.gong.io/calls/104");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("does not invent a link for a record captured by hand", () => {
    renderWith([evidence[2]]);

    expect(screen.queryByRole("link")).toBeNull();
  });
});
