/**
 * Quote-on-select inside the transcript.
 *
 * assistant-ui validates that a selection sits inside one message, positions
 * the toolbar, and clears the selection on choose; rebuilding that would be a
 * second selection system. The primitive portals itself, so it is mounted
 * inside `ThreadPrimitive.Root` and outside the scroll viewport where it cannot
 * be clipped.
 */

import { SelectionToolbarPrimitive } from "@assistant-ui/react";

export function SelectionToolbar() {
  return (
    <SelectionToolbarPrimitive.Root className="quote-toolbar">
      <SelectionToolbarPrimitive.Quote className="quote-toolbar__action">
        Quote
      </SelectionToolbarPrimitive.Quote>
    </SelectionToolbarPrimitive.Root>
  );
}
