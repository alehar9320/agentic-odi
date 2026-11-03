/* eslint-disable react-refresh/only-export-components -- entry module: the Boot wrapper exists only to time the shell handover, and nothing imports this file */
import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { installDiagnosticsConsoleCapture } from "./diagnostics/bundle";
import { removeBootShell } from "./lib/boot";
import { SERVICE_WORKER_URL } from "./lib/swRouting";
import "./styles/entry.css";

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

/**
 * Drop the bootstrap shell from `index.html` once React has committed.
 *
 * The shell paints the first frame; it must not be in the accessibility tree
 * or focusable once the app is up. Removing it here — after the commit that
 * replaces the container — keeps the shell on screen until React has something
 * to show, so the handover is one colour and no blank frame.
 */
function Boot() {
  useEffect(() => {
    removeBootShell();
  }, []);
  return <App />;
}

createRoot(rootElement).render(
  <StrictMode>
    <Boot />
  </StrictMode>,
);
