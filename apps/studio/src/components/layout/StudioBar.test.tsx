import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { UpdateProvider, createUpdateService } from "../../updater";
import type { UpdateTransport, UpdaterHandle } from "../../updater/types";
import { StudioBar } from "./StudioBar";

const openPanel = vi.fn();

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(() => ({
    llmHealth: { healthy: true, message: "LLM backend is reachable." },
    unreadNotificationCount: 0,
    openPanel,
  })),
}));

function makeTransport(overrides: Partial<UpdateTransport> = {}): UpdateTransport {
  return {
    supported: () => true,
    currentVersion: vi.fn(async () => "0.12.0"),
    check: vi.fn(async () => null),
    relaunch: vi.fn(async () => undefined),
    ...overrides,
  };
}

function makeHandle(): UpdaterHandle {
  return {
    version: "0.13.0",
    currentVersion: "0.12.0",
    date: null,
    notes: null,
    download: vi.fn(async (onProgress) => onProgress({ received: 1, total: 1 })),
    install: vi.fn(async () => undefined),
    close: vi.fn(async () => undefined),
  };
}

function renderBar(transport: UpdateTransport) {
  const service = createUpdateService({
    transport,
    storage: null,
    platform: "linux",
    document: null,
    initialDelayMs: 60_000,
  });

  render(
    <UpdateProvider service={service}>
      <StudioBar onHome={vi.fn()} onNew={vi.fn()} onChangelog={vi.fn()} />
    </UpdateProvider>,
  );

  return service;
}

describe("StudioBar version", () => {
  it("shows the running version and opens update settings", async () => {
    renderBar(makeTransport());

    const version = await screen.findByRole("button", { name: "v0.12.0" });
    fireEvent.click(version);

    expect(openPanel).toHaveBeenCalledWith("settings");
  });

  it("says update ready when a restart will finish the job", async () => {
    const service = renderBar(
      makeTransport({ check: vi.fn(async () => makeHandle()) }),
    );

    await act(async () => {
      await service.check();
    });

    expect(screen.getByRole("button", { name: "Update ready" })).toBeInTheDocument();
  });
});
