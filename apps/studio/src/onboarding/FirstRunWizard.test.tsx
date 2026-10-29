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
  closeSetup: vi.fn(),
  sendMessage: vi.fn(),
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
    studio.closeSetup.mockClear();
    studio.sendMessage.mockClear();
  });

  it("greets a first-time user and focuses the step heading", () => {
    renderWizard();

    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading).toHaveTextContent("What do you want to win?");
    expect(heading).toHaveFocus();
  });

  it("walks from a chosen starting point to the matching surface", async () => {
    renderWizard();

    fireEvent.click(continueButton());
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "What's on your mind?",
    );
    expect(continueButton()).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /Help me find the next one/ }));
    expect(continueButton()).toBeEnabled();
    fireEvent.click(continueButton());

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "A quick look at your instruments.",
    );
    fireEvent.click(continueButton());

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Your first move.");
    expect(
      screen.getByText("We start in the conversation. Tell me what you already know."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Find my next opportunity" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(studio.sendMessage).toHaveBeenCalledWith(
      expect.stringContaining("I need to find the next opportunity"),
    );
    expect(studio.openPanel).not.toHaveBeenCalled();
    expect(studio.openSetup).not.toHaveBeenCalled();
    expect(stored()).toMatchObject({
      status: "done",
      step: 3,
      goal: "find-opportunity",
      version: 1,
    });
  });

  it("starts the conversation from the chosen door", () => {
    renderWizard();

    fireEvent.click(continueButton());
    fireEvent.click(screen.getByRole("button", { name: /I have one in mind/ }));
    fireEvent.click(continueButton());
    fireEvent.click(continueButton());
    fireEvent.click(screen.getByRole("button", { name: "Sharpen my opportunity" }));

    expect(studio.closeSetup).toHaveBeenCalledTimes(1);
    expect(studio.sendMessage).toHaveBeenCalledWith(
      expect.stringContaining("I have an opportunity in mind"),
    );
    expect(studio.openSetup).not.toHaveBeenCalled();
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

  it("skips one step without ending the tour", () => {
    renderWizard();

    fireEvent.click(screen.getByRole("button", { name: "Skip this step" }));

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "What's on your mind?",
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(stored()).toMatchObject({ status: "active", step: 1 });
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
    seed({ status: "active", step: 2, goal: "have-opportunity", version: 1 });

    renderWizard();

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "A quick look at your instruments.",
    );
  });

  it("does not reappear after completion", () => {
    seed({ status: "done", step: 3, goal: "have-opportunity", version: 1 });

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
    fireEvent.click(screen.getByRole("button", { name: /I have one in mind/ }));
    fireEvent.click(continueButton());

    await waitFor(() => expect(studio.checkConnections).toHaveBeenCalled());
  });

  it("offers inline repair when the model is unreachable", async () => {
    studio.llmHealth = { healthy: false, message: "Connection refused" };
    renderWizard();

    fireEvent.click(continueButton());
    fireEvent.click(screen.getByRole("button", { name: /I have one in mind/ }));
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
    seed({ status: "done", step: 3, goal: "have-opportunity", version: 1 });

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
      "What do you want to win?",
    );
    await waitFor(() =>
      expect(stored()).toMatchObject({ status: "active", step: 0, goal: null }),
    );
  });
});
