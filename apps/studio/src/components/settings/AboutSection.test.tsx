import { render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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

function renderSection() {
  return render(
    <UpdateProvider service={service}>
      <AboutSection
        settings={{
          base_url: "http://localhost:8001/v1",
          api_key: "local",
          model_name: "local-tools-model",
          mcp_url: "http://localhost:8000/mcp",
        }}
        capabilities={[]}
      />
    </UpdateProvider>,
  );
}

describe("AboutSection", () => {
  it("reports the running version, build date, platform, and update status", async () => {
    renderSection();

    // The transport is supported, so the provider syncs currentVersion from the
    // service; wait for that before asserting on it.
    await waitFor(() => expect(service.getSnapshot().currentVersion).toBe("0.14.0"));

    const about = screen.getByRole("region", { name: "About" });
    expect(within(about).getByText("v0.14.0")).toBeInTheDocument();
    expect(within(about).getByText(__STUDIO_BUILD_DATE__)).toBeInTheDocument();
    expect(within(about).getByText(/macOS|Windows|Linux|Desktop/)).toBeInTheDocument();
    expect(within(about).getByText(service.statusLine())).toBeInTheDocument();
  });

  it("offers a diagnostics bundle without uploading anything", () => {
    renderSection();

    expect(screen.getByRole("button", { name: /create diagnostics bundle/i })).toBeInTheDocument();
    expect(screen.getByText(/nothing is uploaded/i)).toBeInTheDocument();
  });

  // #800: About answers "which host am I in?" before anything else, from the
  // one runtime module. jsdom is a plain browser tab, so the row reads that.
  it("reports where the app is running", () => {
    renderSection();

    const about = screen.getByRole("region", { name: "About" });
    expect(within(about).getByText("Runtime")).toBeInTheDocument();
    expect(within(about).getByText(/Browser tab/)).toBeInTheDocument();
  });
});
