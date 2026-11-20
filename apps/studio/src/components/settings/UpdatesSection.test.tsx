import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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

function renderSection() {
  return render(
    <UpdateProvider service={service}>
      <UpdatesSection />
    </UpdateProvider>,
  );
}

describe("UpdatesSection", () => {
  it("shows one state line and at most one action", () => {
    renderSection();

    const updates = screen.getByRole("region", { name: "Updates" });
    expect(within(updates).getByText(service.statusLine())).toBeInTheDocument();
    expect(within(updates).queryAllByRole("button").length).toBeLessThanOrEqual(1);
  });

  it("leaves the tour and the product essay to About", () => {
    renderSection();

    expect(screen.queryByRole("button", { name: /replay the tour/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /take the tour/i })).toBeNull();
    expect(screen.queryByText(/how the studio works/i)).toBeNull();
  });
});
