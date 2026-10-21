import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ONBOARDING_STORAGE_KEY } from "./storage";

const studio = vi.hoisted(() => ({
  settings: {
    base_url: "http://localhost:8001/v1",
    api_key: "local",
    model_name: "local-tools-model",
    mcp_url: "http://localhost:8000/mcp",
  },
  saveSettings: vi.fn(),
  sidecarReachable: true as boolean | null,
  mcpReachable: true,
  llmHealth: { healthy: true as boolean | null, message: "ok" },
  checkConnections: vi.fn(),
  openPanel: vi.fn(),
  openSetup: vi.fn(),
}));

vi.mock("../state/StudioContext", () => ({
  useStudio: () => studio,
}));

import { FirstRunWizard } from "./FirstRunWizard";
import { OnboardingProvider } from "./OnboardingProvider";
import { useOnboarding } from "./context";

function renderWizard(enabled = true) {
  return render(
    <OnboardingProvider enabled={enabled}>
      <FirstRunWizard />
    </OnboardingProvider>,
  );
}

function seed(record: Record<string, unknown>) {
  window.localStorage.setItem(ONBOARDING_STORAGE_KEY, JSON.stringify(record));
}

function stored() {
  const raw = window.localStorage.getItem(ONBOARDING_STORAGE_KEY);
  return raw ? (JSON.parse(raw) as Record<string, unknown>) : null;
}

function continueButton() {
  return screen.getByRole("button", { name: "Continue" });
}

describe("FirstRunWizard", () => {
  beforeEach(() => {
    window.localStorage.clear();
    studio.sidecarReachable = true;
    studio.mcpReachable = true;
    studio.llmHealth = { healthy: true, message: "ok" };
    studio.saveSettings.mockClear();
    studio.checkConnections.mockReset();
    studio.checkConnections.mockResolvedValue({
      sidecarReachable: true,
      mcpReachable: true,
      llmHealthy: true,
    });
    studio.openPanel.mockClear();
    studio.openSetup.mockClear();
  });

  it("greets a first-time user and focuses the step heading", () => {
    renderWizard();

    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading).toHaveTextContent("People don't buy products.");
    expect(heading).toHaveFocus();
  });

  it("walks from a chosen starting point to the matching surface", async () => {
    renderWizard();

    fireEvent.click(continueButton());
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "Where do you want to begin?",
    );
    expect(continueButton()).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /Read the landscape/ }));
    expect(continueButton()).toBeEnabled();
    fireEvent.click(continueButton());

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "A quick look at your instruments.",
    );
    fireEvent.click(continueButton());

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Your first move.");
    expect(screen.getByText("The opportunity landscape opens full-screen.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Open the landscape" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(studio.openPanel).toHaveBeenCalledWith("landscape");
    expect(studio.openSetup).not.toHaveBeenCalled();
    expect(stored()).toMatchObject({
      status: "done",
      step: 3,
      goal: "landscape",
      version: 1,
    });
  });

  it("hands the job path to the context conversation", () => {
    renderWizard();

    fireEvent.click(continueButton());
    fireEvent.click(screen.getByRole("button", { name: /Name the job/ }));
    fireEvent.click(continueButton());
    fireEvent.click(continueButton());
    fireEvent.click(screen.getByRole("button", { name: "Set up my context" }));

    expect(studio.openSetup).toHaveBeenCalledTimes(1);
    expect(studio.openPanel).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("skips on request and remembers it", () => {
    const { unmount } = renderWizard();

    fireEvent.click(screen.getByRole("button", { name: "Skip the tour" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(stored()).toMatchObject({ status: "skipped" });
    expect(studio.openPanel).not.toHaveBeenCalled();
    expect(studio.openSetup).not.toHaveBeenCalled();

    unmount();
    renderWizard();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("skips with Escape", () => {
    renderWizard();

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(stored()).toMatchObject({ status: "skipped" });
  });

  it("keeps Tab inside the dialog", () => {
    renderWizard();

    const last = continueButton();
    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });

    expect(screen.getByRole("button", { name: "Skip the tour" })).toHaveFocus();
  });

  it("does not let Shift+Tab escape from the step heading", () => {
    renderWizard();

    const heading = screen.getByRole("heading", { level: 2 });
    heading.focus();
    fireEvent.keyDown(heading, { key: "Tab", shiftKey: true });

    expect(continueButton()).toHaveFocus();
  });

  it("resumes an unfinished tour where it stopped", () => {
    seed({ status: "active", step: 2, goal: "name-job", version: 1 });

    renderWizard();

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "A quick look at your instruments.",
    );
  });

  it("does not reappear after completion", () => {
    seed({ status: "done", step: 3, goal: "name-job", version: 1 });

    renderWizard();

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("stays completely inert when the feature flag is off", () => {
    renderWizard(false);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(ONBOARDING_STORAGE_KEY)).toBeNull();
  });

  it("honours the flag when the provider reads it from storage", () => {
    window.localStorage.setItem("studio.flags.firstRunWizard", "off");

    render(
      <OnboardingProvider>
        <FirstRunWizard />
      </OnboardingProvider>,
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("probes the instruments when their state is unknown", async () => {
    studio.sidecarReachable = null;
    studio.llmHealth = { healthy: null, message: "checking" };
    renderWizard();

    fireEvent.click(continueButton());
    fireEvent.click(screen.getByRole("button", { name: /Name the job/ }));
    fireEvent.click(continueButton());

    await waitFor(() => expect(studio.checkConnections).toHaveBeenCalled());
  });

  it("offers inline repair when the model is unreachable", async () => {
    studio.llmHealth = { healthy: false, message: "Connection refused" };
    renderWizard();

    fireEvent.click(continueButton());
    fireEvent.click(screen.getByRole("button", { name: /Name the job/ }));
    fireEvent.click(continueButton());

    expect(screen.getByText("Connection refused")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Base URL"), {
      target: { value: "http://127.0.0.1:11434/v1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save & test" }));

    await waitFor(() => expect(studio.saveSettings).toHaveBeenCalled());
    expect(studio.saveSettings.mock.calls[0][0]).toMatchObject({
      base_url: "http://127.0.0.1:11434/v1",
      model_name: "local-tools-model",
    });
    expect(studio.checkConnections).toHaveBeenCalledWith(
      expect.objectContaining({ base_url: "http://127.0.0.1:11434/v1" }),
    );
    await waitFor(() =>
      expect(screen.getByText("The model answered. You are ready.")).toBeInTheDocument(),
    );
  });

  it("can be replayed from anywhere in the app", async () => {
    seed({ status: "done", step: 3, goal: "name-job", version: 1 });

    function Replay() {
      const { restart } = useOnboarding();
      return (
        <button type="button" onClick={restart}>
          Replay tour
        </button>
      );
    }

    render(
      <OnboardingProvider enabled>
        <FirstRunWizard />
        <Replay />
      </OnboardingProvider>,
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Replay tour" }));

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "People don't buy products.",
    );
    await waitFor(() =>
      expect(stored()).toMatchObject({ status: "active", step: 0, goal: null }),
    );
  });
});
