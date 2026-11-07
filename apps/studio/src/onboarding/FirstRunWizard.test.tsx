import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ONBOARDING_STORAGE_KEY } from "./storage";
import {
  SAMPLE_COMPARISON_IDS,
  SAMPLE_EVIDENCE_ID,
  SAMPLE_JOB_ID,
  SAMPLE_OUTCOME_ID,
  SAMPLE_OUTCOME_IDS,
  SAMPLE_STEP_ID,
} from "../lib/sampleLoop";

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
  canvasState: { kind: "ready", data: null } as unknown as { kind: string; data: unknown },
  deleteEvidence: vi.fn<(id: string) => Promise<void>>(async () => {}),
  deleteOutcome: vi.fn<(id: string) => Promise<void>>(async () => {}),
  deleteStep: vi.fn<(id: string) => Promise<void>>(async () => {}),
  deleteJob: vi.fn<(id: string) => Promise<void>>(async () => {}),
  refreshCanvas: vi.fn(async () => {}),
}));

vi.mock("../state/StudioContext", () => ({
  useStudio: () => studio,
}));

import { FirstRunWizard } from "./FirstRunWizard";
import { OnboardingProvider } from "./OnboardingProvider";
import { useOnboarding } from "./context";

function TourOpener() {
  const { openTour } = useOnboarding();
  return (
    <button type="button" onClick={openTour}>
      Show me around
    </button>
  );
}

/** Render and let the user ask for the tour, the only way it can open. */
function renderWizard(enabled = true) {
  const utils = render(
    <OnboardingProvider enabled={enabled}>
      <FirstRunWizard />
      <TourOpener />
    </OnboardingProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Show me around" }));
  return utils;
}

/** Render without opening anything. */
function renderClosed(enabled = true) {
  return render(
    <OnboardingProvider enabled={enabled}>
      <FirstRunWizard />
      <TourOpener />
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

/** Walk the whole tour to scene three: choose a goal, clear readiness. */
function walkToLand() {
  fireEvent.click(continueButton());
  fireEvent.click(screen.getByRole("button", { name: /I have one in mind/ }));
  fireEvent.click(continueButton());
  fireEvent.click(continueButton());
  expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Where it lands.");
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
    studio.canvasState = { kind: "ready", data: null };
    studio.deleteEvidence.mockClear();
    studio.deleteOutcome.mockClear();
    studio.deleteStep.mockClear();
    studio.deleteJob.mockClear();
    studio.refreshCanvas.mockClear();
  });

  it("never opens by itself, even on a fresh run", () => {
    renderClosed();

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(stored()).toBeNull();
  });

  it("greets a user who asks for the tour and focuses the step heading", () => {
    renderWizard();

    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading).toHaveTextContent("What do you want to win?");
    expect(heading).toHaveFocus();
  });

  it("lands on the outcome, then starts the chosen surface", async () => {
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

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Where it lands.");
    expect(screen.getByText("Opportunity map")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Start your own job" }));

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

  it("lands on the outcome, then starts the conversation from the chosen door", async () => {
    renderWizard();

    fireEvent.click(continueButton());
    fireEvent.click(screen.getByRole("button", { name: /I have one in mind/ }));
    fireEvent.click(continueButton());
    fireEvent.click(continueButton());
    fireEvent.click(screen.getByRole("button", { name: "Start your own job" }));

    await waitFor(() => expect(studio.closeSetup).toHaveBeenCalledTimes(1));
    expect(studio.sendMessage).toHaveBeenCalledWith(
      expect.stringContaining("I have an opportunity in mind"),
    );
    expect(studio.openSetup).not.toHaveBeenCalled();
    expect(studio.openPanel).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("highlights the scored sample outcome in the plot", () => {
    renderWizard();
    walkToLand();

    expect(screen.getByRole("img", { name: "Opportunity map" })).toBeInTheDocument();
    // The sample outcome is named in the scene and marked as sample data.
    expect(screen.getByText("Sample")).toBeInTheDocument();
    expect(screen.getByText(SAMPLE_OUTCOME_ID)).toBeInTheDocument();

    const highlighted = document.querySelectorAll(".matrix-node--highlighted");
    expect(highlighted).toHaveLength(1);
    expect(highlighted[0]).toHaveAttribute("data-highlighted", "true");
    expect(highlighted[0]).toHaveAccessibleName(new RegExp(`^${SAMPLE_OUTCOME_ID},`));
    // The comparisons are on the plot but not highlighted.
    for (const comparison of SAMPLE_COMPARISON_IDS) {
      const node = document.querySelector(`.matrix-node[aria-label^="${comparison},"]`);
      expect(node).not.toBeNull();
      expect(node).not.toHaveAttribute("data-highlighted");
    }
  });

  it("removes every sample record when she starts her own job", async () => {
    renderWizard();
    walkToLand();

    fireEvent.click(screen.getByRole("button", { name: "Start your own job" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    const removed = [
      ...studio.deleteEvidence.mock.calls.map((call) => call[0]),
      ...studio.deleteOutcome.mock.calls.map((call) => call[0]),
      ...studio.deleteStep.mock.calls.map((call) => call[0]),
      ...studio.deleteJob.mock.calls.map((call) => call[0]),
    ];
    const expected = [
      SAMPLE_EVIDENCE_ID,
      ...SAMPLE_OUTCOME_IDS,
      SAMPLE_STEP_ID,
      SAMPLE_JOB_ID,
    ];
    expect([...removed].sort()).toEqual([...expected].sort());
    // No sample id survives the choice.
    for (const id of expected) {
      expect(removed).toContain(id);
    }
  });

  it("keeps the marked sample when she keeps it", async () => {
    renderWizard();
    walkToLand();

    // The sample is marked before the choice and left marked after it.
    expect(screen.getByText("Sample")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep the sample to poke at" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(studio.deleteOutcome).not.toHaveBeenCalled();
    expect(studio.deleteEvidence).not.toHaveBeenCalled();
    expect(studio.deleteStep).not.toHaveBeenCalled();
    expect(studio.deleteJob).not.toHaveBeenCalled();
    expect(studio.openPanel).toHaveBeenCalledWith("landscape");
    expect(stored()).toMatchObject({ status: "done", step: 3 });
  });

  it("only removes the sample ids the tour made", async () => {
    // A canvas that also holds a job a person made. Cleanup must leave it.
    studio.canvasState = {
      kind: "ready",
      data: {
        jobs: [
          { id: SAMPLE_JOB_ID, name: "Sample brief" },
          { id: "JOB-MINE", name: "A job I made" },
        ],
        steps: [{ id: SAMPLE_STEP_ID, job_id: SAMPLE_JOB_ID, name: "Sample step" }],
        outcomes: [{ id: SAMPLE_OUTCOME_ID, job_id: SAMPLE_JOB_ID, statement: "Sample" }],
        evidence: [{ id: SAMPLE_EVIDENCE_ID, content: "Sample" }],
        source: "local",
      },
    };
    renderWizard();
    walkToLand();

    fireEvent.click(screen.getByRole("button", { name: "Start your own job" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    const jobsRemoved = studio.deleteJob.mock.calls.map((call) => call[0]);
    expect(jobsRemoved).toContain(SAMPLE_JOB_ID);
    expect(jobsRemoved).not.toContain("JOB-MINE");
  });

  it("skips on request and remembers it", () => {
    const { unmount } = renderWizard();

    fireEvent.click(screen.getByRole("button", { name: "Skip the tour" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(stored()).toMatchObject({ status: "skipped" });
    expect(studio.openPanel).not.toHaveBeenCalled();
    expect(studio.openSetup).not.toHaveBeenCalled();

    unmount();
    renderClosed();
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

  it("starts from the top once the tour is finished", () => {
    seed({ status: "done", step: 3, goal: "have-opportunity", version: 1 });

    renderWizard();

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "What do you want to win?",
    );
  });

  it("stays closed after completion until it is asked for", () => {
    seed({ status: "done", step: 3, goal: "have-opportunity", version: 1 });

    renderClosed();

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("stays completely inert when the feature flag is off", () => {
    renderClosed(false);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show me around" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(ONBOARDING_STORAGE_KEY)).toBeNull();
  });

  it("honours the flag when the provider reads it from storage", () => {
    window.localStorage.setItem("studio.flags.firstRunWizard", "off");

    render(
      <OnboardingProvider>
        <FirstRunWizard />
        <TourOpener />
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
