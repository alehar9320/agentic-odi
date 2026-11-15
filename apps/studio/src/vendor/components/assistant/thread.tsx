// vendored: https://r.assistant-ui.com/thread.json — MIT — retrieved 2026-11-15 from the assistant-ui registry (issue #993) — local edits: only the frame is kept (the thread root, the scrolling viewport, and the viewport footer that carries the composer); the Element's message, composer, attachment, markdown, reasoning, and tool-group sections are dropped because the Studio renders those through Conversation/parts.tsx and ThreadComposer; the frame keeps the Studio's own classes, the viewport keeps auto-scroll, a float slot carries the jump-to-latest control inside the footer, and the empty state arrives as a prop rather than being derived from the runtime, so the Studio store stays the one authority on whether the thread is empty.
// Ledger entry: apps/studio/vendor.lock.json. Refresh with the assistant-ui CLI,
// then restore the dropped sections; src/vendor/ledger.test.ts fails if the two
// drift apart.

import { ThreadPrimitive } from "@assistant-ui/react";
import type { FC, ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The thread layout, copied from assistant-ui's `thread` Element.
 *
 * The Element is a copy-in over `ThreadPrimitive`: it owns the root, the
 * scrolling viewport, and the footer the composer docks into. The Studio keeps
 * its own store, its own `Conversation`, and its own `ThreadComposer`, so this
 * copy keeps the frame and hands the product surfaces in through slots. Nothing
 * here reads the Studio store or the sidecar.
 *
 * Where the Element derives "new chat" from `state.thread.messages` and mounts
 * its own composer, this copy takes `empty` and the slots as props: the Studio
 * already decides emptiness from its store, and a second derivation would be a
 * second authority. The footer pins to the bottom of the viewport only when the
 * thread holds turns; on the empty thread it sits with the welcome so the two
 * are centred together, exactly as the Element centres a new chat.
 */
export type ThreadElementProps = {
  /** The empty thread: the Element centers the welcome slot above the footer. */
  empty?: boolean;
  /** Rendered inside the root, above the scroll frame (the bar and toolbar). */
  header?: ReactNode;
  /** The empty-thread slot, centered while `empty`. */
  welcome?: ReactNode;
  /** The scrolling message list. */
  messages?: ReactNode;
  /**
   * Rendered inside the footer, above the composer, so a control that floats
   * over the transcript is not clipped by the scrolling viewport.
   */
  float?: ReactNode;
  /** The footer contents: the composer and anything that docks with it. */
  composer?: ReactNode;
  className?: string;
  "aria-label"?: string;
};

export const ThreadElement: FC<ThreadElementProps> = ({
  empty = false,
  header,
  welcome,
  messages,
  float,
  composer,
  className,
  "aria-label": ariaLabel,
}) => (
  <ThreadPrimitive.Root
    className={cn("aui-root aui-thread-root chat", className)}
    aria-label={ariaLabel}
  >
    {header}
    <ThreadPrimitive.Viewport
      data-slot="aui_thread-viewport"
      className="aui-thread-viewport chat__scroll"
      autoScroll
    >
      <div
        data-slot="aui_thread-content"
        className={cn(
          "aui-thread-content chat__thread",
          empty && "aui-thread-content--empty",
        )}
      >
        {empty ? (
          <div className="chat__welcome">
            <div className="chat__welcome-inner">{welcome}</div>
          </div>
        ) : (
          <div data-slot="aui_message-group" className="aui-thread-messages">
            {messages}
          </div>
        )}

        {float || composer ? (
          <ThreadPrimitive.ViewportFooter
            data-slot="aui_thread-viewport-footer"
            className={cn(
              "aui-thread-viewport-footer chat__dock",
              !empty && "chat__dock--pinned",
            )}
          >
            {float}
            {composer}
          </ThreadPrimitive.ViewportFooter>
        ) : null}
      </div>
    </ThreadPrimitive.Viewport>
  </ThreadPrimitive.Root>
);
