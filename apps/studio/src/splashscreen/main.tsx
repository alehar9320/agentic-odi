import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import SplashScreen from "./SplashScreen";
import "./styles/theme.css";
import "./vendor/index.css";

const rootElement = document.getElementById("splash-root");
if (!rootElement) {
  throw new Error("Root element #splash-root not found");
}

createRoot(rootElement).render(
  <StrictMode>
    <SplashScreen />
  </StrictMode>,
);