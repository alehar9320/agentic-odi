/* eslint-disable react-refresh/only-export-components -- entry module: the Boot wrapper exists only to time the shell handover, and nothing imports this file */
import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { installDiagnosticsConsoleCapture } from "./diagnostics/bundle";
import { removeBootShell } from "./lib/boot";
import { initServiceWorker } from "./lib/swUpdate";
// The cascade order has one home: entry.css layers the product sheets and pulls
// in the vendor utilities last (issue #384), so main.tsx imports nothing else.
import "./styles/entry.css";

installDiagnosticsConsoleCapture();

/**
 * Register the service worker and watch for the next build (#545).
 *
 * The worker precaches the shell, so the installed app opens with no network, and
 * it is what answers an uncached navigation with `/offline.html` (#546). It never
 * swaps code on its own: a new build waits until the person asks, through the
 * `app-update-ready` banner, so an update can never interrupt a streamed turn.
 *
 * Production only: in dev the worker would cache Vite's module responses and
 * serve stale code, and a failure to register must never break the app.
 */
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    initServiceWorker();
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
