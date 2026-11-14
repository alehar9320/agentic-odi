/**
 * One shortcut, one composer.
 *
 * The shell owns the keys that reach the composer from anywhere (⌘/Ctrl+K,
 * `/`, and the Escape that has nowhere else to go). It cannot hold a ref to a
 * textarea it does not render, so the composer that is on stage registers how
 * to take the caret here instead. The listener then exists once per page, not
 * once per composer, and a page with two of them still moves the caret into
 * the one the person can see.
 */

export interface ComposerHandle {
  /** Put the caret in the composer's textarea. */
  focus: () => void;
  /** Focus the composer with `/` already typed, so the palette is open. */
  startCommand: () => void;
}

let current: ComposerHandle | null = null;

/**
 * Make `handle` the composer the shortcuts reach. Returns the cleanup that
 * gives the slot back — and only if this handle still holds it, so unmounting
 * an old composer cannot disconnect the one that replaced it.
 */
export function registerComposer(handle: ComposerHandle): () => void {
  current = handle;
  return () => {
    if (current === handle) {
      current = null;
    }
  };
}

export function focusComposer(): boolean {
  if (!current) {
    return false;
  }
  current.focus();
  return true;
}

export function startComposerCommand(): boolean {
  if (!current) {
    return false;
  }
  current.startCommand();
  return true;
}

/**
 * Whether the composer may take the caret when it appears.
 *
 * A composer can mount late — after a boot probe resolves, or when a view
 * swaps in — and by then the person may already be somewhere else: a dialog
 * they just opened, a field they just clicked. Taking the caret then would
 * pull it out from under them, and the dialog that later closes would hand
 * focus back to the composer instead of to the control that opened it (#695).
 */
export function composerMayTakeCaret(): boolean {
  if (typeof document === "undefined") {
    return false;
  }
  if (dialogOpen()) {
    return false;
  }
  const active = document.activeElement;
  return !active || active === document.body || active === document.documentElement;
}

/**
 * Whether a modal is on screen. A dialog owns the keyboard while it is open,
 * so a shell shortcut must not reach behind it to the page it covers.
 */
export function dialogOpen(): boolean {
  return (
    typeof document !== "undefined" &&
    document.querySelector('[aria-modal="true"]') !== null
  );
}
