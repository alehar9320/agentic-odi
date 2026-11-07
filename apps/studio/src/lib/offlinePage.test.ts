import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * #546: the offline shell is a page, not a React route, so the only way to keep
 * its promises is to assert on the file itself. These are the guardrails the
 * issue names: both themes, no network, one action, and a single page.
 *
 * Vitest runs with the studio package as its working directory.
 */
const page = readFileSync(join(process.cwd(), "public", "offline.html"), "utf8");

describe("offline.html", () => {
  it("is themed for both palettes and picks the stored one before paint", () => {
    expect(page).toMatch(/html\[data-theme="light"\]/);
    expect(page).toMatch(/--bg: #0a0b0e/);
    expect(page).toMatch(/--bg: #f5f6f8/);
    // The theme is read from the same key the shell writes, synchronously.
    expect(page).toContain("studio.settings");
    expect(page).toContain("dataset.theme");
  });

  it("makes no network request for fonts, images, or styles", () => {
    // No subresource references of any kind: no script/link/img src, no @import,
    // and no url(...) in the CSS.
    expect(page).not.toMatch(/<link\b[^>]*\brel="(stylesheet|preload|preconnect)"/i);
    expect(page).not.toMatch(/<script\b[^>]*\bsrc=/i);
    expect(page).not.toMatch(/<img\b/i);
    expect(page).not.toMatch(/@import/i);
    expect(page).not.toMatch(/url\(/i);
    // System fonts only.
    expect(page).not.toMatch(/fonts\.(googleapis|gstatic)\.com/i);
    expect(page).toContain("-apple-system");
  });

  it("offers exactly one action that lands on the cached shell", () => {
    const actions = page.match(/class="action"/g) ?? [];
    expect(actions).toHaveLength(1);
    expect(page).toMatch(/class="action" href="\/"/);
    expect(page).toContain("Open the Studio");
  });

  it("says the app is installed and names what still works", () => {
    expect(page).toMatch(/installed/i);
    expect(page).toMatch(/offline/i);
    expect(page).toMatch(/Still yours, on this device/);
  });

  it("does not claim a sync that the outbox does not yet provide", () => {
    // #306 owns writing while offline; until it lands, the page may not promise
    // that anything syncs back.
    expect(page).not.toMatch(/sync/i);
  });
});
