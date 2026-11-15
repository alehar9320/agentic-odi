import { useEffect, type RefObject } from "react";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function focusableWithin(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
}

/**
 * Keep Tab and Shift+Tab inside a dialog for as long as it is open, and give
 * focus back to whatever held it before. A dialog that lets focus escape is a
 * keyboard trap in the wrong direction: the user tabs into the page behind it.
 *
 * When `inertPage` is set, the app shell behind the dialog is also made
 * `inert` — unreachable by Tab and by assistive technology, not merely covered
 * — and restored on close. The dialog must be rendered outside the shell (a
 * portal to `document.body`); `inert` on an ancestor cannot be undone by a
 * descendant. Applying `inert` blurs a control focused inside the shell, so
 * the opener is captured before it is applied and refocused after it is
 * removed.
 *
 * `scopeKey` handles a dialog whose element is replaced while it stays open —
 * a workspace sheet switched from one lens to its sibling. The ref survives the
 * swap, so without a key in the dependencies the trap's listener stays on the
 * detached element and the new dialog never receives focus.
 */
export function useFocusTrap(
  ref: RefObject<HTMLElement | null>,
  active: boolean,
  inertPage = false,
  scopeKey?: unknown,
): void {
  useEffect(() => {
    if (!active) {
      return;
    }
    const container = ref.current;
    if (!container) {
      return;
    }

    const containerEl: HTMLElement = container;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    focusableWithin(containerEl)[0]?.focus();

    const shell = inertPage
      ? document.querySelector<HTMLElement>(".studio-app")
      : null;
    const shellEl = shell && !shell.contains(containerEl) ? shell : null;
    const shellWasInert = shellEl?.hasAttribute("inert") ?? false;
    shellEl?.setAttribute("inert", "");

    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Tab") {
        return;
      }
      const focusable = focusableWithin(containerEl);
      if (focusable.length === 0) {
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const current = document.activeElement as HTMLElement | null;
      const inside = current !== null && containerEl.contains(current);

      if (event.shiftKey) {
        if (!inside || current === first) {
          event.preventDefault();
          last.focus();
        }
      } else if (!inside || current === last) {
        event.preventDefault();
        first.focus();
      }
    }

    containerEl.addEventListener("keydown", onKeyDown);
    return () => {
      containerEl.removeEventListener("keydown", onKeyDown);
      if (shellEl && !shellWasInert) {
        shellEl.removeAttribute("inert");
      }
      previouslyFocused?.focus();
    };
  }, [ref, active, inertPage, scopeKey]);
}
