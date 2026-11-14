import { detectPlatform, type DesktopPlatform } from "../updater/platform";
import { STUDIO_VERSION } from "../lib/version";
import { isInstalled } from "../install";
import { isTauri } from "./desktopBridge";

/** The two shells the Studio runs in: the installed desktop app, or a browser. */
export type HostKind = "desktop" | "browser";

/** Whether the page is a tab or has been installed to its own window. */
export type InstallKind = "installed" | "tab";

/** Whether the page shares the device with the sidecar or is served remotely. */
export type OriginClass = "loopback" | "remote";

/** How the app reaches the sidecar: directly, or through its own origin. */
export type ApiTransport = "sidecar-direct" | "same-origin";

/** Everything `detectRuntime` needs, injected so the matrix is a table. */
export interface RuntimeEnvironment {
  hasTauri: boolean;
  displayStandalone: boolean;
  navigatorStandalone: boolean;
  hostname: string;
  serviceWorkerControlled: boolean;
  platform: DesktopPlatform;
  version: string;
}

/** The answer to "which of the four hosts am I in?", in one shape. */
export interface RuntimeFacts {
  host: HostKind;
  install: InstallKind;
  originClass: OriginClass;
  apiTransport: ApiTransport;
  offlineShell: boolean;
  platform: DesktopPlatform;
  version: string;
  /** One line for a person: `Desktop app`, `Installed web app`, `Browser tab`. */
  label: string;
}

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

/** A hostname is loopback when it is the loopback address or a `*.localhost`. */
function isLoopback(hostname: string): boolean {
  const host = hostname.trim().toLowerCase();
  if (host.length === 0) {
    return false;
  }
  return LOOPBACK_HOSTS.has(host) || host.endsWith(".localhost");
}

/**
 * The one pure answer to "where is this running?".
 *
 * Host decides the API base, not the capability list: nothing here may infer
 * that a model is missing, only where the app is and how it talks home.
 */
export function detectRuntime(env: RuntimeEnvironment): RuntimeFacts {
  const host: HostKind = env.hasTauri ? "desktop" : "browser";
  const installed = env.displayStandalone || env.navigatorStandalone;
  const install: InstallKind = installed ? "installed" : "tab";
  const originClass: OriginClass = isLoopback(env.hostname) ? "loopback" : "remote";

  // Desktop talks to the sidecar's own origin; a browser page always shares the
  // origin it was served from, whether that is the sidecar or a host.
  const apiTransport: ApiTransport = host === "desktop" ? "sidecar-direct" : "same-origin";

  const label = host === "desktop" ? "Desktop app" : installed ? "Installed web app" : "Browser tab";

  return {
    host,
    install,
    originClass,
    apiTransport,
    offlineShell: env.serviceWorkerControlled,
    platform: env.platform,
    version: env.version,
    label,
  };
}

function displayModeStandalone(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return ["standalone", "minimal-ui", "fullscreen"].some(
    (mode) => window.matchMedia(`(display-mode: ${mode})`).matches,
  );
}

/**
 * Read the environment for `detectRuntime`.
 *
 * This is the only impure edge: the decision itself lives in the pure function
 * above, so every host is a test row rather than a branch here.
 */
export function runtimeFacts(): RuntimeFacts {
  const navigatorStandalone =
    typeof navigator !== "undefined" &&
    (navigator as unknown as { standalone?: boolean }).standalone === true;

  return detectRuntime({
    hasTauri: isTauri(),
    displayStandalone: displayModeStandalone() || isInstalled(),
    navigatorStandalone,
    hostname: typeof window === "undefined" ? "" : window.location.hostname,
    serviceWorkerControlled:
      typeof navigator !== "undefined" && Boolean(navigator.serviceWorker?.controller),
    platform: detectPlatform(),
    version: STUDIO_VERSION,
  });
}
