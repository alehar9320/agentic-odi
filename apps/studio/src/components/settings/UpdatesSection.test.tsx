import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { createUpdateService, UpdateProvider } from "../../updater";
import type { UpdateTransport } from "../../updater/types";
import { UpdatesSection } from "./sections/UpdatesSection";

const transport: UpdateTransport = {
  supported: () => false,
  currentVersion: async () => "0.14.0",
  check: async () => null,
  relaunch: async () => undefined,
};

const service = createUpdateService({ transport, storage: null, document: null });

function renderSection(overrides: Partial<Parameters<typeof UpdatesSection>[0]> = {}) {
  const props = {
    tourEnabled: false,
    restartTour: vi.fn(),
    ...overrides,
  };
  return {
    ...render(
      <UpdateProvider service={service}>
        <UpdatesSection {...props} />
      </UpdateProvider>,
    ),
    props,
  };
}

describe("UpdatesSection", () => {
  it("renders the software update block", () => {
    renderSection();

    expect(screen.getByRole("region", { name: /software update/i })).toBeInTheDocument();
    expect(screen.getByText(/how the studio works/i)).toBeInTheDocument();
  });

  it("hides the tour when it is not enabled", () => {
    renderSection({ tourEnabled: false });
    expect(screen.queryByRole("button", { name: /replay the tour/i })).toBeNull();
  });

  it("replays the tour when it is enabled", () => {
    const { props } = renderSection({ tourEnabled: true });
    fireEvent.click(screen.getByRole("button", { name: /replay the tour/i }));
    expect(props.restartTour).toHaveBeenCalled();
  });
});
