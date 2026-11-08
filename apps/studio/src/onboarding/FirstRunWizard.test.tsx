import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ONBOARDING_STORAGE_KEY } from "./storage";

vi.mock("../state/StudioContext", () => ({
  useStudio: () => ({ settings: {}, saveSettings: vi.fn(), checkConnections: vi.fn() }),
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

function heading() {
  return screen.getByRole("heading", { level: 2 });
}

describe("FirstRunWizard", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("never opens by itself, even on a fresh run", () => {
    renderClosed();

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(stored()).toBeNull();
  });

  it("greets a user who asks for the tour on the first scene", () => {
    renderWizard();

    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    expect(heading()).toHaveTextContent("Hear it in a customer's words.");
    expect(heading()).toHaveFocus();
    expect(screen.getByText("Scene 1 of 3")).toBeInTheDocument();
  });

  it("walks forward through the three scenes", () => {
    renderWizard();

    fireEvent.click(continueButton());
    expect(heading()).toHaveTextContent("Turn the quote into a scored outcome.");
    expect(screen.getByText("Scene 2 of 3")).toBeInTheDocument();

    fireEvent.click(continueButton());
    expect(heading()).toHaveTextContent("See where the outcome lands.");
    expect(screen.getByText("Scene 3 of 3")).toBeInTheDocument();
  });

  it("labels the sample on every scene", () => {
    renderWizard();

    expect(screen.getAllByText("Sample").length).toBeGreaterThan(0);
    fireEvent.click(continueButton());
    expect(screen.getAllByText("Sample").length).toBeGreaterThan(0);
    fireEvent.click(continueButton());
    expect(screen.getAllByText("Sample").length).toBeGreaterThan(0);
  });

  it("finishes the tour from the last scene and stays closed", async () => {
    renderWizard();

    fireEvent.click(continueButton());
    fireEvent.click(continueButton());
    fireEvent.click(screen.getByRole("button", { name: "Start with my own" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(stored()).toMatchObject({ status: "done", scene: 2, version: 2 });
  });

  it("skips one scene without ending the tour", () => {
    renderWizard();

    fireEvent.click(screen.getByRole("button", { name: "Skip this scene" }));

    expect(heading()).toHaveTextContent("Turn the quote into a scored outcome.");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(stored()).toMatchObject({ status: "active", scene: 1 });
  });

  it("skips the whole tour in one click and records why", () => {
    const { unmount } = renderWizard();

    fireEvent.click(screen.getByRole("button", { name: "Skip the tour" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(stored()).toMatchObject({ status: "skipped", reason: "not-now" });

    unmount();
    renderClosed();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("skips with Escape, recording a dismissal", () => {
    renderWizard();

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(stored()).toMatchObject({ status: "skipped", reason: "dismissed" });
  });

  it("keeps Tab inside the dialog", () => {
    renderWizard();

    const last = continueButton();
    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });

    expect(screen.getByRole("button", { name: "Skip the tour" })).toHaveFocus();
  });

  it("does not let Shift+Tab escape from the scene heading", () => {
    renderWizard();

    const h = heading();
    h.focus();
    fireEvent.keyDown(h, { key: "Tab", shiftKey: true });

    expect(continueButton()).toHaveFocus();
  });

  it("resumes an unfinished tour at the same scene", () => {
    seed({ status: "active", scene: 2, reason: null, version: 2 });

    renderWizard();

    expect(heading()).toHaveTextContent("See where the outcome lands.");
  });

  it("starts from the top once the tour is finished", () => {
    seed({ status: "done", scene: 2, reason: null, version: 2 });

    renderWizard();

    expect(heading()).toHaveTextContent("Hear it in a customer's words.");
  });

  it("stays closed after completion until it is asked for", () => {
    seed({ status: "done", scene: 2, reason: null, version: 2 });

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

  it("makes no network call in any scene", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    try {
      renderWizard();
      fireEvent.click(continueButton());
      fireEvent.click(continueButton());
      expect(fetchSpy).not.toHaveBeenCalled();
    } finally {
      fetchSpy.mockRestore();
    }
  });

  it("can be replayed from anywhere in the app", async () => {
    seed({ status: "done", scene: 2, reason: null, version: 2 });

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

    expect(heading()).toHaveTextContent("Hear it in a customer's words.");
    await waitFor(() =>
      expect(stored()).toMatchObject({ status: "active", scene: 0, reason: null }),
    );
  });
});
