import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { installDiagnosticsConsoleCapture } from "./diagnostics/bundle";
import "./styles/theme.css";
// Vendor utilities last: Tailwind is scoped to src/vendor (issue #385), and
// loading it after the theme keeps the product stylesheet authoritative.
import "./vendor/index.css";

installDiagnosticsConsoleCapture();

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root not found");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
