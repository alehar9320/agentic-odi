/**
 * Read-aloud, gated on the shell.
 *
 * The browser and Tauri's WebKit webview do not have identical Web Speech
 * support, so the adapter is exposed only where `speechSynthesis` exists. There
 * is no fallback provider and no autoplay: if the API is absent the control is
 * absent too, rather than a button that throws at click time.
 */

import { WebSpeechSynthesisAdapter, type SpeechSynthesisAdapter } from "@assistant-ui/react";

export function speechSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function createSpeechAdapter(): SpeechSynthesisAdapter | null {
  if (!speechSupported()) {
    return null;
  }
  return new WebSpeechSynthesisAdapter();
}
