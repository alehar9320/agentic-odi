// Choose the site's theme before the first paint.
//
// This runs as a blocking script in <head> so the page never flashes the
// wrong theme: the stored choice wins, otherwise the operating system's
// preference decides. Loaded separately (not inline) so the site keeps its
// `script-src 'self'` policy.
(function () {
  "use strict";

  var KEY = "agentic-odi.theme";
  var root = document.documentElement;
  var stored = null;

  try {
    stored = window.localStorage.getItem(KEY);
  } catch (error) {
    stored = null;
  }

  var prefersLight =
    window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
  var theme = stored === "light" || stored === "dark" ? stored : prefersLight ? "light" : "dark";

  root.setAttribute("data-theme", theme);

  var meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute("content", theme === "light" ? "#f7f8fb" : "#0a0b0e");
  }
})();
