/*
 * Pre-React theme resolution (see index.html and bootShell.test.ts). A plain,
 * synchronous same-origin file rather than an inline <script>, because the app
 * is served under `script-src 'self'`; <head> keeps it ahead of the bundle.
 * Reads the key the app does; theme state stays owned by StudioContext.tsx.
 */
(function () {
  var theme = null;
  try {
    var stored = JSON.parse(window.localStorage.getItem("studio.settings") || "null");
    if (stored && (stored.theme === "light" || stored.theme === "dark")) theme = stored.theme;
  } catch {
    // Unreadable or absent settings: fall through to the media query.
  }
  if (!theme) {
    var light =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-color-scheme: light)").matches;
    theme = light ? "light" : "dark";
  }
  var root = document.documentElement;
  root.classList.add(theme === "light" ? "theme-light" : "theme-dark");
  root.style.colorScheme = theme;
})();
