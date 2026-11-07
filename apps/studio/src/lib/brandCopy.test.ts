/**
 * The name appears once, in the bar. This test is what keeps it that way.
 *
 * It reads every non-test source file under `src`, including comments, so a new
 * surface cannot reintroduce a second variant of the product name. The one
 * module allowed to spell the name is `lib/brand.ts`.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

import { COMPANY_NAME, PRODUCT_NAME, productTitle, updateTitle, versionLabel } from "./brand";

// Vitest runs with the studio package as its working directory.
const STUDIO = process.cwd();
const SRC = join(STUDIO, "src");
const BRAND_MODULE = join(SRC, "lib", "brand.ts");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      return sourceFiles(path);
    }
    if (!/\.tsx?$/.test(entry.name) || /\.(test|visual\.test)\.tsx?$/.test(entry.name)) {
      return [];
    }
    return path === BRAND_MODULE ? [] : [path];
  });
}

describe("brand copy", () => {
  it("keeps the product name out of every surface but the brand module", () => {
    const offenders = sourceFiles(SRC)
      .filter((path) => readFileSync(path, "utf8").includes(PRODUCT_NAME))
      .map((path) => relative(SRC, path));

    expect(offenders).toEqual([]);
  });

  it("names the document, the desktop bundle, and the identifier once each", () => {
    const html = readFileSync(join(STUDIO, "index.html"), "utf8");
    expect(html).toContain(`<title>${productTitle()}</title>`);

    const tauri = JSON.parse(readFileSync(join(STUDIO, "src-tauri", "tauri.conf.json"), "utf8")) as {
      productName: string;
      identifier: string;
      app: { windows: { title: string }[] };
    };
    expect(tauri.productName).toBe(PRODUCT_NAME);
    expect(tauri.app.windows[0].title).toBe(PRODUCT_NAME);
    // Changing the identifier would move the data directory and break updates.
    expect(tauri.identifier).toBe("com.agenticodi.livingstudio");
  });

  it("states the company separately from the product", () => {
    expect(PRODUCT_NAME).toBe("Living Studio");
    expect(COMPANY_NAME).toBe("Agentic ODI");
  });

  it("explains an update without reintroducing the product", () => {
    const copy = [
      versionLabel("0.14.0"),
      updateTitle("0.14.0", "downloading"),
      updateTitle("0.14.0", "installing"),
      updateTitle("0.14.0", "ready"),
    ];

    expect(copy).toEqual([
      "Version 0.14.0",
      "Downloading version 0.14.0",
      "Installing version 0.14.0",
      "Version 0.14.0 is ready. Restart to finish.",
    ]);
    expect(copy.filter((line) => line.includes(PRODUCT_NAME))).toEqual([]);
  });
});
