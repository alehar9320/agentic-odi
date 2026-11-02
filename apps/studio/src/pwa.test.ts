/**
 * The web app manifest and the document's install metadata are the contract the
 * browser's installability check reads. This test pins them so a future change
 * cannot quietly drop the manifest link, the theme colour, or the maskable icon.
 *
 * The 192 px and 512 px icons, and the maskable variant, are generated from the
 * Odi mascot by `brand/tools/render.py`; `brand/tests/test_generated_sources.py`
 * proves the PNGs match a fresh render.
 */
import { readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const STUDIO = dirname(dirname(fileURLToPath(import.meta.url)));
const PUBLIC = join(STUDIO, "public");
const INDEX = readFileSync(join(STUDIO, "index.html"), "utf8");

interface ManifestIcon {
  src: string;
  sizes: string;
  type: string;
  purpose: string;
}

interface Manifest {
  name: string;
  short_name: string;
  id: string;
  start_url: string;
  scope: string;
  display: string;
  background_color: string;
  theme_color: string;
  icons: ManifestIcon[];
}

const MANIFEST = JSON.parse(
  readFileSync(join(PUBLIC, "manifest.webmanifest"), "utf8"),
) as Manifest;

describe("web app manifest", () => {
  it("is linked from the document with a theme colour", () => {
    expect(INDEX).toContain('<link rel="manifest" href="/manifest.webmanifest" />');
    expect(INDEX).toContain('<meta name="theme-color" content="#0a0b0e" />');
  });

  it("opens as its own window rather than a browser tab", () => {
    expect(MANIFEST.display).toBe("standalone");
    expect(MANIFEST.start_url).toBe("/");
    expect(MANIFEST.scope).toBe("/");
    expect(MANIFEST.id).toBe("/");
  });

  it("names the app for the window and the short label", () => {
    expect(MANIFEST.name).toBe("Living Studio");
    expect(MANIFEST.short_name).toBe("Studio");
    // short_name is what fits under an icon; keep it short.
    expect(MANIFEST.short_name.length).toBeLessThanOrEqual(12);
  });

  it("brands the installed window with the studio's own background", () => {
    // Colours match --bg in apps/studio/src/styles/theme.css.
    expect(MANIFEST.theme_color).toBe("#0a0b0e");
    expect(MANIFEST.background_color).toBe("#0a0b0e");
  });

  it("ships the 192 px, 512 px, and maskable icons the install check wants", () => {
    const bySrc = new Map(MANIFEST.icons.map((icon) => [icon.src, icon]));

    expect(bySrc.get("/icons/icon-192.png")).toMatchObject({
      sizes: "192x192",
      type: "image/png",
      purpose: "any",
    });
    expect(bySrc.get("/icons/icon-512.png")).toMatchObject({
      sizes: "512x512",
      type: "image/png",
      purpose: "any",
    });

    const maskable = MANIFEST.icons.filter((icon) => icon.purpose === "maskable");
    expect(maskable).toHaveLength(1);
    expect(maskable[0]).toMatchObject({
      src: "/icons/maskable-512.png",
      sizes: "512x512",
      type: "image/png",
    });
  });

  it("every declared icon exists on disk and is a PNG", () => {
    for (const icon of MANIFEST.icons) {
      const path = join(PUBLIC, icon.src.replace(/^\//, ""));
      expect(statSync(path).isFile(), `${icon.src} is missing`).toBe(true);
      const header = readFileSync(path).subarray(0, 8);
      expect(header.equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))).toBe(
        true,
      );
    }
  });
});
