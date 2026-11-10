/**
 * The bootstrap shell in `index.html` paints the first frame, before the module
 * bundle parses. It lives inside `#root`, so React replaces it on the first
 * commit; removing it here makes that handover explicit and testable rather
 * than a side effect of React's container clearing.
 */
export function removeBootShell(doc: Document = document): void {
  doc.getElementById("boot")?.remove();
}
