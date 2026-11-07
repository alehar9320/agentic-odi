import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OnboardingProvider } from "../../../onboarding";
import { AboutSection } from "./AboutSection";

const settings = {
  base_url: "http://localhost:8001/v1",
  api_key: "local",
  model_name: "local-tools-model",
  mcp_url: "http://localhost:8000/mcp",
  theme: "dark" as const,
};

describe("AboutSection", () => {
  it("reports the build facts from the build-info source", () => {
    render(
      <OnboardingProvider enabled={false}>
        <AboutSection settings={settings} capabilities={[]} />
      </OnboardingProvider>,
    );

    const about = screen.getByRole("region", { name: "About" });
    expect(within(about).getByText(`v${__STUDIO_APP_VERSION__}`)).toBeInTheDocument();
    expect(within(about).getByText(__STUDIO_BUILD_COMMIT__)).toBeInTheDocument();
    expect(within(about).getByText(__STUDIO_BUILD_DATE__)).toBeInTheDocument();
    expect(within(about).getByText(/macOS|Windows|Linux|Desktop/)).toBeInTheDocument();
    expect(within(about).getByText(/canvas of human intent/i)).toBeInTheDocument();
  });

  it("offers the tour as one link when the tour is enabled", () => {
    render(
      <OnboardingProvider enabled={true}>
        <AboutSection settings={settings} capabilities={[]} />
      </OnboardingProvider>,
    );

    expect(screen.getAllByRole("button", { name: "Take the tour" })).toHaveLength(1);
  });

  it("hides the tour link when the tour is disabled", () => {
    render(
      <OnboardingProvider enabled={false}>
        <AboutSection settings={settings} capabilities={[]} />
      </OnboardingProvider>,
    );

    expect(screen.queryByRole("button", { name: "Take the tour" })).toBeNull();
  });
});
