import { render, screen } from "@testing-library/react";
import ts from "typescript";
import { describe, expect, it, vi } from "vitest";

vi.mock("../banners/BannerBridge", () => ({
  BannerBridge: () => null,
  useBannerActionDispatcher: () => ({ onIntent: vi.fn(), onAction: vi.fn(), onDismiss: vi.fn() }),
}));
vi.mock("../banners/BannerProvider", () => ({
  useBanner: () => ({ view: { visible: [], overflow: 0 } }),
}));
vi.mock("../banners/BannerStack", () => ({ BannerStack: () => null }));
vi.mock("../banners/BannerToasts", () => ({ BannerToasts: () => null }));
vi.mock("../state/StudioContext", () => ({
  useStudio: () => ({
    closePanel: vi.fn(),
    clearChat: vi.fn(),
    closeSetup: vi.fn(),
    customizeOpen: false,
    closeCustomize: vi.fn(),
    streaming: false,
    stopStreaming: vi.fn(),
  }),
}));
// The children keep one control each, so the tab order asserted below is the
// shell's order rather than a fixture that happens to be empty.
vi.mock("../components/layout/StudioBar", () => ({
  StudioBar: () => (
    <header aria-label="Studio bar">
      <button type="button">Notifications</button>
    </header>
  ),
}));
vi.mock("../components/chat/ChatStage", () => ({
  ChatStage: () => (
    <div>
      <p>Conversation stage</p>
      <label htmlFor="mock-composer">Message the studio</label>
      <textarea id="mock-composer" />
    </div>
  ),
}));
vi.mock("../components/workspace/WorkbenchRail", () => ({
  WorkbenchRail: () => (
    <nav aria-label="Your work">
      <button type="button">Open inbox</button>
    </nav>
  ),
}));
vi.mock("../components/workspace/WorkspacePanel", () => ({ WorkspacePanel: () => null }));
vi.mock("../components/customize/CustomizePage", () => ({ CustomizePage: () => null }));
vi.mock("../components/customize/ConnectorSuggestionModal", () => ({
  ConnectorSuggestionModal: () => null,
}));
vi.mock("../components/ChangelogModal", () => ({ ChangelogModal: () => null }));
vi.mock("../updater", () => ({
  UpdateBanner: () => null,
  UpdateProvider: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("../onboarding", () => ({
  FirstRunWizard: () => null,
  OnboardingProvider: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("../assistant/StudioRuntime", () => ({
  StudioRuntimeProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import { StudioShell } from "../App";
import { focusableWithin } from "../lib/useFocusTrap";

/**
 * Source text for every component, loaded through Vite so the scan runs the
 * same way in vitest and in the browser bundle without node typings.
 */
const SOURCES = import.meta.glob("/src/**/*.tsx", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

/** Native controls already handle Enter, Space, and focus. */
const NATIVE_CONTROLS = new Set(["a", "button", "input", "select", "textarea", "summary", "label"]);

/** An onClick is a control contract: native, or role + tab stop + key handler. */
function clickableOffenders(file: string, text: string): string[] {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const offenders: string[] = [];

  function visit(node: ts.Node) {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = node.tagName.getText(source);
      const attributes = node.attributes.properties.map((attribute) =>
        ts.isJsxAttribute(attribute) ? attribute.name.getText(source) : "",
      );
      const clickable = attributes.includes("onClick");
      // Components render their own controls (Radix's Toast.Action is a
      // button); the rule is about intrinsic elements we lay out by hand.
      const intrinsic = /^[a-z]/.test(tag);
      const supported =
        NATIVE_CONTROLS.has(tag) ||
        (attributes.includes("role") &&
          attributes.includes("tabIndex") &&
          attributes.includes("onKeyDown"));
      if (clickable && intrinsic && !supported) {
        const { line } = source.getLineAndCharacterOfPosition(node.getStart(source));
        offenders.push(`${file}:${line + 1} <${tag}>`);
      }
    }
    ts.forEachChild(node, visit);
  }

  visit(source);
  return offenders;
}

describe("studio shell landmarks", () => {
  it("offers a skip link to the conversation and a real header, main, and nav", () => {
    render(<StudioShell />);

    const skip = screen.getByRole("link", { name: /skip to conversation/i });
    expect(skip).toHaveAttribute("href", "#studio-stage");

    const main = screen.getByRole("main");
    expect(main).toHaveAttribute("id", "studio-stage");
    expect(main).toHaveAttribute("tabindex", "-1");
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Your work" })).toBeInTheDocument();
  });

  it("walks the tab path in order: skip link, top bar, rail, transcript", () => {
    render(<StudioShell />);

    const order = focusableWithin(document.body);
    const skip = screen.getByRole("link", { name: /skip to conversation/i });
    const bell = screen.getByRole("button", { name: "Notifications" });
    const rail = screen.getByRole("button", { name: "Open inbox" });
    const composer = screen.getByRole("textbox", { name: "Message the studio" });

    expect(order[0]).toBe(skip);
    expect(order.indexOf(bell)).toBeGreaterThan(0);
    expect(order.indexOf(rail)).toBeGreaterThan(order.indexOf(bell));
    expect(order.indexOf(composer)).toBeGreaterThan(order.indexOf(rail));
  });
});

describe("click handlers", () => {
  it("are only attached to native controls or fully keyboard-operable elements", () => {
    const offenders = Object.entries(SOURCES)
      .filter(([file]) => !file.includes(".test."))
      .flatMap(([file, text]) => clickableOffenders(file, text));
    expect(offenders).toEqual([]);
  });
});
