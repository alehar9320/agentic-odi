import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ONBOARDING_STORAGE_KEY } from "./storage";

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

  it("greets a user who asks for the tour on scene one and focuses its heading", () => {
    renderWizard();

    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    expect(heading()).toHaveTextContent("What is this person trying to get done?");
    expect(heading()).toHaveFocus();
  });

  it("walks forward through all three scenes", () => {
    renderWizard();

    fireEvent.click(continueButton());
    expect(heading()).toHaveTextContent("Two numbers, one opportunity.");

    fireEvent.click(continueButton());
    expect(heading()).toHaveTextContent("Where it lands.");

    // The last scene finishes rather than advancing past the end.
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(stored()).toMatchObject({ status: "done", scene: 2, reason: null });
  });

  it("walks back to a scene it already saw", () => {
    renderWizard();

    fireEvent.click(continueButton());
    fireEvent.click(continueButton());
    expect(heading()).toHaveTextContent("Where it lands.");

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(heading()).toHaveTextContent("Two numbers, one opportunity.");
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(heading()).toHaveTextContent("What is this person trying to get done?");
    // There is no Back on the first scene.
    expect(screen.queryByRole("button", { name: "Back" })).not.toBeInTheDocument();
  });

  it("resumes mid-scene from a stored position", () => {
    seed({ status: "open", scene: 1, reason: null, version: 2 });

    renderWizard();

    expect(heading()).toHaveTextContent("Two numbers, one opportunity.");
    expect(stored()).toMatchObject({ status: "open", scene: 1 });
  });

  it("starts from the top once the tour is finished", () => {
    seed({ status: "done", scene: 2, reason: null, version: 2 });

    renderWizard();

    expect(heading()).toHaveTextContent("What is this person trying to get done?");
  });

  it("skips the tour in one click and records why", () => {
    const { unmount } = renderWizard();

    fireEvent.click(screen.getByRole("button", { name: "Skip the tour" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(stored()).toMatchObject({ status: "skipped", reason: "not-now" });

    // It does not nag again: a fresh mount stays closed.
    unmount();
    renderClosed();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("skips one scene without ending the tour", () => {
    renderWizard();

    fireEvent.click(screen.getByRole("button", { name: "Skip this scene" }));

    expect(heading()).toHaveTextContent("Two numbers, one opportunity.");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(stored()).toMatchObject({ status: "open", scene: 1, reason: null });
  });

  it("hides the scene skip on the last scene", () => {
    seed({ status: "open", scene: 2, reason: null, version: 2 });
    renderWizard();

    expect(screen.queryByRole("button", { name: "Skip this scene" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Skip the tour" })).toBeInTheDocument();
  });

  it("skips with Escape and records that it was dismissed", () => {
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

    heading().focus();
    fireEvent.keyDown(heading(), { key: "Tab", shiftKey: true });

    expect(continueButton()).toHaveFocus();
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

  it("labels the sample in every scene", () => {
    renderWizard();

    expect(screen.getByText("Sample")).toBeInTheDocument();
    fireEvent.click(continueButton());
    expect(screen.getByText("Sample")).toBeInTheDocument();
    fireEvent.click(continueButton());
    expect(screen.getByText("Sample")).toBeInTheDocument();
  });

  it("makes no network call in any scene", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => {
      throw new Error("the tour must not touch the network");
    });

    renderWizard();
    fireEvent.click(continueButton());
    fireEvent.click(continueButton());

    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
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

    expect(heading()).toHaveTextContent("What is this person trying to get done?");
    await waitFor(() =>
      expect(stored()).toMatchObject({ status: "open", scene: 0, reason: null }),
    );
  });
});
