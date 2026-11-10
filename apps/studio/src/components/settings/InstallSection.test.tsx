import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InstallSection } from "./sections/InstallSection";

vi.mock("../../install", () => ({
  isInstalled: vi.fn(() => false),
  isDismissed: vi.fn(() => false),
  offerInstall: vi.fn(() => false),
  dismissInstall: vi.fn(),
}));

import { dismissInstall, isDismissed, isInstalled, offerInstall } from "../../install";

describe("InstallSection", () => {
  beforeEach(() => {
    vi.mocked(isInstalled).mockReturnValue(false);
    vi.mocked(isDismissed).mockReturnValue(false);
    vi.mocked(offerInstall).mockReturnValue(false);
  });

  it("offers the install control while the app is not installed", () => {
    render(<InstallSection />);

    expect(screen.getByRole("heading", { name: /install/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /install app/i })).toBeInTheDocument();
  });

  it("asks the browser to install, then remembers a refusal", () => {
    vi.mocked(offerInstall).mockReturnValue(false);
    render(<InstallSection />);

    fireEvent.click(screen.getByRole("button", { name: /install app/i }));

    expect(offerInstall).toHaveBeenCalled();
    expect(dismissInstall).toHaveBeenCalled();
  });

  it("stays quiet once the app is installed", () => {
    vi.mocked(isInstalled).mockReturnValue(true);
    render(<InstallSection />);

    expect(screen.queryByRole("button", { name: /install app/i })).toBeNull();
  });
});
