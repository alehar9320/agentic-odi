/* eslint-disable react-refresh/only-export-components -- entry module: the Boot wrapper exists only to time the shell handover, and nothing imports this file */
import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { installDiagnosticsConsoleCapture } from "./diagnostics/bundle";
import { removeBootShell } from "./lib/boot";
import "./styles/theme.css";
import "./styles/records.css";
import "./styles/brief.css";
// Vendor utilities last: Tailwind is scoped to src/vendor (issue #385), and
// loading it after the theme keeps the product stylesheet authoritative.
import "./vendor/index.css";

installDiagnosticsConsoleCapture();

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
