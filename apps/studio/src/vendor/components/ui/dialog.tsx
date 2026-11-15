// Dialog primitive: the Studio's one modal frame. It composes the already-
// declared `radix-ui` Dialog parts — portal, overlay, content, title, close —
// and adds no behaviour of its own. Escape, the focus trap, focus entry and
// focus return all come from the primitive underneath, so a caller gets them
// once instead of re-implementing them per surface.
//
// Authored locally as a first-party presentation primitive for the shared
// Dialog (#1001). No upstream artefact was fetched in this environment, so it
// is tracked as first-party in vendor.lock.json rather than as a copy-in.
"use client";

import * as React from "react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { XIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type DialogProps = {
  /** Whether the dialog is open. Controlled, like the primitive underneath. */
  open: boolean;
  /** Called with the next open state: Escape, the close button, a scrim click. */
  onOpenChange: (open: boolean) => void;
  /** The dialog's accessible name, rendered as its heading. */
  title: string;
  children: React.ReactNode;
  /** Optional actions row, kept outside the scrolling body. */
  footer?: React.ReactNode;
};

/**
 * A presentational modal: props in, markup out. It reads no store, calls no
 * API, and knows nothing about the surface it is shown over.
 */
function Dialog({ open, onOpenChange, title, children, footer }: DialogProps) {
  // Radix returns focus to a `Dialog.Trigger`, and this API is controlled: the
  // element that opened the dialog is whatever held focus a moment before. The
  // primitive hands us that moment through `onOpenAutoFocus` and the close
  // through `onCloseAutoFocus`, so focus entry, trapping and return stay Radix's
  // behaviour — this only tells it where "back" is.
  const returnFocusRef = React.useRef<HTMLElement | null>(null);

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          className={cn(
            "fixed inset-0 z-50 bg-[var(--scrim)] backdrop-blur-[12px]",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0",
          )}
        />
        <DialogPrimitive.Content
          onOpenAutoFocus={() => {
            const active = document.activeElement;
            returnFocusRef.current = active instanceof HTMLElement ? active : null;
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            returnFocusRef.current?.focus();
          }}
          className={cn(
            "fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[calc(100%-2*var(--space-5))]",
            "max-w-[680px] -translate-x-1/2 -translate-y-1/2 flex-col",
            "rounded-[var(--radius-lg)] border border-[var(--line-strong)]",
            "bg-[var(--bg-raised)] p-[var(--space-5)] text-[var(--text)]",
            "shadow-[var(--shadow-dialog)]",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
            "data-[state=closed]:zoom-out-95 data-[state=open]:animate-in",
            "data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          )}
        >
          <div className="flex items-start justify-between gap-[var(--space-4)]">
            <DialogPrimitive.Title className="text-[var(--text-xl)] font-semibold">
              {title}
            </DialogPrimitive.Title>
            <DialogPrimitive.Close
              aria-label="Close dialog"
              className={cn(
                "rounded-[var(--radius-sm)] p-[var(--space-1)] text-[var(--muted)]",
                "transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text)]",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]",
              )}
            >
              <XIcon aria-hidden="true" className="size-4" />
            </DialogPrimitive.Close>
          </div>
          <div className="flex-1 overflow-y-auto text-[var(--text-base)] text-[var(--muted)]">
            {children}
          </div>
          {footer ? (
            <div className="flex items-center justify-end gap-[var(--space-2)] border-t border-[var(--line)] pt-[var(--space-4)]">
              {footer}
            </div>
          ) : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export { Dialog };
export type { DialogProps };