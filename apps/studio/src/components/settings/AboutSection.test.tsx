import { render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OnboardingProvider } from "../../onboarding";
import { createUpdateService, UpdateProvider } from "../../updater";
import type { UpdateTransport } from "../../updater/types";
import { AboutSection } from "./sections/AboutSection";

const transport: UpdateTransport = {
  supported: () => true,
  currentVersion: async () => "0.14.0",
  check: async () => null,
  relaunch: async () => undefined,
};

const service = createUpdateService({ transport, storage: null, document: null });

const settings = {
  base_url: "http://localhost:8001/v1",
  api_key: "local",
  model_name: "local-tools-model",
  mcp_url: "http://localhost:8000/mcp",
  theme: "dark" as const,
};

function renderSection({ tourEnabled = false }: { tourEnabled?: boolean } = {}) {
  return render(
    <UpdateProvider service={service}>
      <OnboardingProvider enabled={tourEnabled}>
        <AboutSection settings={settings} capabilities={[]} />
      </OnboardingProvider>
    </UpdateProvider>,
  );
}

describe("AboutSection", () => {
  it("reports the running version, commit, build date, platform, and the essay", async () => {
    renderSection();

    // The transport is supported, so the provider syncs currentVersion from the
    // service; wait for that before asserting on it.
    await waitFor(() => expect(service.getSnapshot().currentVersion).toBe("0.14.0"));

    const about = screen.getByRole("region", { name: "About" });
    expect(within(about).getByText("v0.14.0")).toBeInTheDocument();
    expect(within(about).getByText(__STUDIO_BUILD_COMMIT__)).toBeInTheDocument();
    expect(within(about).getByText(__STUDIO_BUILD_DATE__)).toBeInTheDocument();
    expect(within(about).getByText(/macOS|Windows|Linux|Desktop/)).toBeInTheDocument();
    expect(within(about).getByText(/canvas of human intent/i)).toBeInTheDocument();
    // #533: the updater's state belongs to the Updates row, not About.
    expect(within(about).queryByText(service.statusLine())).not.toBeInTheDocument();
  });

  it("offers the tour as one link when the tour is enabled", () => {
    renderSection({ tourEnabled: true });

    expect(screen.getAllByRole("button", { name: "Take the tour" })).toHaveLength(1);
  });

  it("hides the tour link when the tour is disabled", () => {
    renderSection({ tourEnabled: false });

    expect(screen.queryByRole("button", { name: "Take the tour" })).toBeNull();
  });

  it("offers a diagnostics bundle without uploading anything", () => {
    renderSection();

    expect(screen.getByRole("button", { name: /create diagnostics bundle/i })).toBeInTheDocument();
    expect(screen.getByText(/nothing is uploaded/i)).toBeInTheDocument();
  });
});
