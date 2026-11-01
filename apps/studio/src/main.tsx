import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { installDiagnosticsConsoleCapture } from "./diagnostics/bundle";
import { SERVICE_WORKER_URL } from "./lib/swRouting";
import "./styles/theme.css";
import "./styles/records.css";
// Vendor utilities last: Tailwind is scoped to src/vendor (issue #385), and
// loading it after the theme keeps the product stylesheet authoritative.
import "./vendor/index.css";

installDiagnosticsConsoleCapture();

/**
 * Register the service worker so an uncached navigation while offline gets the
 * themed `/offline.html` instead of the browser's error page (#546).
 *
 * Production only: in dev the worker would cache Vite's module responses and
 * serve stale code, and a failure to register must never break the app.
 */
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(SERVICE_WORKER_URL).catch(() => {
      // An unregistered worker costs the offline fallback, not the app.
    });
  });
}

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root not found");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
