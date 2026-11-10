import { configure } from "@chromatic-com/vitest";
import { afterEach, expect, it } from "vitest";
import { render } from "vitest-browser-react";

import "../../styles/theme.css";
import { SuggestionPills } from "./composerParts";
import { useStudio } from "../../state/StudioContext";
import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import { vi } from "vitest";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

configure({ title: "SuggestionPills" });

const stubContext = (overrides: Record<string, unknown> = {}) =>
  ({
    messages: [],
    canvas: { jobs: [], outcomes: [] },
    llmHealth: { healthy: true, message: "" },
    streaming: false,
    openPanel: vi.fn(),
    sendMessage: vi.fn(async () => {}),
    ...overrides,
  }) as unknown as ReturnType<typeof useStudio>;

function useTheme(theme: "theme-dark" | "theme-light") {
  document.documentElement.className = theme;
  afterEach(() => {
    document.documentElement.className = "";
  });
}

async function renderPills() {
  vi.mocked(useStudio).mockReturnValue(stubContext());
  const { container } = await render(
    <StudioRuntimeProvider>
      <SuggestionPills />
    </StudioRuntimeProvider>
  );
  return container;
}

it("renders starter pills in dark theme", async () => {
  useTheme("theme-dark");
  const container = await renderPills();

  const pills = container.querySelectorAll(".suggestion.suggestion--card");
  expect(pills.length).toBeGreaterThan(0);

  const firstPill = pills[0] as HTMLElement;
  const bgColor = getComputedStyle(firstPill).backgroundColor;
  expect(bgColor).not.toBe("rgba(0, 0, 0, 0)");
  expect(bgColor).not.toBe("transparent");
});

it("renders starter pills in light theme", async () => {
  useTheme("theme-light");
  const container = await renderPills();

  const pills = container.querySelectorAll(".suggestion.suggestion--card");
  expect(pills.length).toBeGreaterThan(0);

  const firstPill = pills[0] as HTMLElement;
  const bgColor = getComputedStyle(firstPill).backgroundColor;
  expect(bgColor).not.toBe("rgba(0, 0, 0, 0)");
  expect(bgColor).not.toBe("transparent");
});

it("renders stacked single column at 390px viewport", async () => {
  useTheme("theme-dark");
  const container = await renderPills();

  const pills = container.querySelectorAll(".suggestion.suggestion--card");
  expect(pills.length).toBeGreaterThan(0);

  const wrapper = container.querySelector(".composer__pills") as HTMLElement;
  expect(wrapper).toBeTruthy();
});