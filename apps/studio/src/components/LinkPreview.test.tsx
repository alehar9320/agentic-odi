import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Link } from "../types";
import { LinkPreview } from "./LinkPreview";

const baseLink: Link = {
  id: "L-1",
  source_type: "outcome",
  source_id: "O-1",
  target_type: "outcome",
  target_id: "O-9",
  relationship_type: "evidence_for",
  created_at: "2026-11-01T12:00:00Z",
};

describe("LinkPreview", () => {
  it("renders a plain internal link with no badge", () => {
    const { container } = render(<LinkPreview link={baseLink} />);

    expect(screen.getByText("evidence for")).toBeInTheDocument();
    expect(screen.getByText("outcome")).toBeInTheDocument();
    expect(screen.getByText("O-9")).toBeInTheDocument();
    expect(container.querySelector(".link-preview__badge")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("shows the target title in place of the id when a preview carries one", () => {
    render(
      <LinkPreview
        link={{
          ...baseLink,
          preview: { title: "Login flow", url: "https://jira.example/PROJ-456" },
        }}
      />,
    );

    expect(screen.getByText("Login flow")).toBeInTheDocument();
    expect(screen.queryByText("O-9")).toBeNull();
  });

  it("renders an external badge as plain text when there is no preview url", () => {
    render(
      <LinkPreview
        link={{
          ...baseLink,
          relationship_type: "blocked_by",
          external_system: "jira",
          external_id: "PROJ-456",
        }}
      />,
    );

    expect(screen.getByText("blocked by")).toBeInTheDocument();
    expect(screen.getByText("jira · PROJ-456")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("renders the badge as an anchor when a preview url exists", () => {
    render(
      <LinkPreview
        link={{
          ...baseLink,
          external_system: "jira",
          external_id: "PROJ-456",
          preview: { title: "Login flow", url: "https://jira.example/PROJ-456" },
        }}
      />,
    );

    const badge = screen.getByRole("link", { name: "jira · PROJ-456" });
    expect(badge).toHaveAttribute("href", "https://jira.example/PROJ-456");
    expect(screen.getByText("Login flow")).toBeInTheDocument();
  });

  it("renders an unknown relationship as readable prose, never snake_case", () => {
    render(<LinkPreview link={{ ...baseLink, relationship_type: "some_new_kind" }} />);

    expect(screen.getByText("some new kind")).toBeInTheDocument();
    expect(screen.queryByText("some_new_kind")).toBeNull();
  });
});
