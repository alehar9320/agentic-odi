import { describe, expect, it } from "vitest";

import { detectRuntime, type RuntimeEnvironment } from "./runtime";

/**
 * The four hosts the Studio can run in, as a table.
 *
 * The point of this file is that one pure function answers "where am I?", so
 * every combination is a row here rather than a branch buried in a component.
 */
const baseEnv: RuntimeEnvironment = {
  hasTauri: false,
  displayStandalone: false,
  navigatorStandalone: false,
  hostname: "studio.example.com",
  serviceWorkerControlled: false,
  platform: "unknown",
  version: "0.14.0",
};

describe("detectRuntime", () => {
  it.each([
    {
      name: "desktop app",
      env: { hasTauri: true, hostname: "tauri.localhost" },
      expected: { host: "desktop", apiTransport: "sidecar-direct", label: "Desktop app" },
    },
    {
      name: "installed web app",
      env: { displayStandalone: true, hostname: "studio.example.com" },
      expected: { host: "browser", install: "installed", apiTransport: "same-origin", label: "Installed web app" },
    },
    {
      name: "tab on loopback",
      env: { hostname: "127.0.0.1" },
      expected: { host: "browser", install: "tab", originClass: "loopback", label: "Browser tab" },
    },
    {
      name: "hosted tab",
      env: { hostname: "app.all-hands.dev" },
      expected: { host: "browser", install: "tab", originClass: "remote", label: "Browser tab" },
    },
    {
      name: "iOS standalone",
      env: { navigatorStandalone: true, hostname: "studio.example.com" },
      expected: { install: "installed", label: "Installed web app" },
    },
    {
      name: "service-worker controlled",
      env: { serviceWorkerControlled: true },
      expected: { offlineShell: true },
    },
  ])("reads the $name", ({ env, expected }) => {
    expect(detectRuntime({ ...baseEnv, ...env })).toMatchObject(expected);
  });

  it.each(["127.0.0.1", "::1", "localhost", "studio.localhost", "app.localhost"])(
    "treats %s as loopback",
    (hostname) => {
      expect(detectRuntime({ ...baseEnv, hostname }).originClass).toBe("loopback");
    },
  );

  it.each(["", "file", "studio.example.com", "app.all-hands.dev"])(
    "treats %s as remote",
    (hostname) => {
      expect(detectRuntime({ ...baseEnv, hostname }).originClass).toBe("remote");
    },
  );

  it("reports the offline shell only when a service worker controls the page", () => {
    expect(detectRuntime(baseEnv).offlineShell).toBe(false);
    expect(detectRuntime({ ...baseEnv, serviceWorkerControlled: true }).offlineShell).toBe(true);
  });

  it("carries the platform and version through unchanged", () => {
    const facts = detectRuntime({ ...baseEnv, platform: "macos", version: "1.2.3" });

    expect(facts.platform).toBe("macos");
    expect(facts.version).toBe("1.2.3");
  });

  it("does not infer the host from the origin class", () => {
    // A desktop webview is loopback, but so is a browser tab on 127.0.0.1.
    const desktop = detectRuntime({ ...baseEnv, hasTauri: true, hostname: "127.0.0.1" });
    const tab = detectRuntime({ ...baseEnv, hostname: "127.0.0.1" });

    expect(desktop.host).toBe("desktop");
    expect(tab.host).toBe("browser");
    expect(desktop.originClass).toBe(tab.originClass);
  });
});
