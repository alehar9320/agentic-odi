export const SIDECAR_ORIGIN = "http://127.0.0.1:8100";

interface TauriWindow {
  __TAURI_INTERNALS__?: unknown;
}

export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in (window as TauriWindow);
}

export function resolveApiBase(tauri: boolean): string {
  return tauri ? SIDECAR_ORIGIN : "";
}

export function apiUrl(path: string): string {
  return `${resolveApiBase(isTauri())}${path}`;
}
