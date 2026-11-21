import * as React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Dialog } from "./dialog";

function Harness({ onOpenChange }: { onOpenChange: (open: boolean) => void }) {
  const [open, setOpen] = React.useState(false);

  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open
      </button>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          onOpenChange(next);
        }}
        title="Harness title"
        footer={
          <button type="button" onClick={() => setOpen(false)}>
            Done
          </button>
        }
      >
        <p>Harness body</p>
      </Dialog>
    </>
  );
}

describe("Dialog", () => {
  it("renders the dialog and its title when open", async () => {
    render(
      <Dialog open onOpenChange={vi.fn()} title="Ship it">
        <p>Body</p>
      </Dialog>,
    );

    expect(screen.getByRole("dialog", { name: "Ship it" })).toBeInTheDocument();
    expect(screen.getByText("Body")).toBeInTheDocument();
    // Focus enters the dialog, so Tab and Escape have somewhere to start.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Close dialog" })).toHaveFocus(),
    );
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <Dialog open={false} onOpenChange={vi.fn()} title="Ship it">
        <p>Body</p>
      </Dialog>,
    );

    expect(container.firstChild).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("takes its accessible name from the title", () => {
    render(
      <Dialog open onOpenChange={vi.fn()} title="Review diagnostics">
        <p>Body</p>
      </Dialog>,
    );

    expect(screen.getByRole("dialog", { name: "Review diagnostics" })).toBeInTheDocument();
  });

  it("calls onOpenChange(false) on Escape", () => {
    const onOpenChange = vi.fn();

    render(
      <Dialog open onOpenChange={onOpenChange} title="Ship it">
        <p>Body</p>
      </Dialog>,
    );

    fireEvent.keyDown(document, { key: "Escape" });

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("returns focus to the trigger after close", async () => {
    render(<Harness onOpenChange={vi.fn()} />);

    const trigger = screen.getByRole("button", { name: "Open" });
    trigger.focus();
    fireEvent.click(trigger);

    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});