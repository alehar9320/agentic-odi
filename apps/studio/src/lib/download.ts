/** Hand a file to the browser's save dialog, with no network involved. */
export function downloadFile(
  contents: string,
  filename: string,
  type = "application/json",
): void {
  const blob = new Blob([contents], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revoking in the same task can cancel the save in Firefox and Safari: the
  // click queues the navigation, the revoke can run first. One macrotask later
  // the navigation has started, and the blob can be released.
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
