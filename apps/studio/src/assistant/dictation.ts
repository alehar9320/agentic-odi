/**
 * Dictation, gated on the shell.
 *
 * The browser and Tauri's WebKit webview do not agree on speech recognition, so
 * the adapter exists only where `WebSpeechDictationAdapter.isSupported()` says
 * it does. No audio leaves the browser, nothing is recorded, and the transcript
 * only ever fills the composer — it never sends.
 */

import { WebSpeechDictationAdapter, type DictationAdapter } from "@assistant-ui/react";

export function dictationSupported(): boolean {
  return typeof window !== "undefined" && WebSpeechDictationAdapter.isSupported();
}

/** A session that is already over: a refused start must not crash a turn. */
function endedSession(): DictationAdapter.Session {
  return {
    status: { type: "ended", reason: "error" },
    stop: async () => {},
    cancel: () => {},
    onSpeechStart: () => () => {},
    onSpeechEnd: () => () => {},
    onSpeech: () => () => {},
  };
}

export function createDictationAdapter(): DictationAdapter | null {
  if (!dictationSupported()) {
    return null;
  }
  const inner = new WebSpeechDictationAdapter({
    language: typeof navigator === "undefined" ? undefined : navigator.language,
    continuous: true,
    interimResults: true,
  });
  return {
    // A denied or unavailable microphone can throw before a session exists.
    // Returning an ended session leaves the composer usable and the control
    // idle, instead of failing inside a click handler.
    listen: () => {
      try {
        return inner.listen();
      } catch {
        return endedSession();
      }
    },
    disableInputDuringDictation: false,
  };
}
