/// <reference types="node" />
import { readFileSync, readdirSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { FORBIDDEN_SLICES, forbiddenImports } from "./boundary";

/**
 * `src/vendor` is copied presentation. It takes props and renders; it does not
 * read product state, the API client, the assistant bridge, or the BFF.
 *
 * Lint forbids the aliased forms; this test resolves every specifier against
 * the importing file, which a string pattern cannot do — `../assistant/plan`
 * stays inside the vendor tree, while `../../state/StudioContext` leaves it.
 */

// Vitest runs from apps/studio, so the copied tree is one directory in.
const vendorDir = "src/vendor";

const vendorSources = (): { path: string; source: string }[] =>
  readdirSync(vendorDir, { recursive: true })
    .map(String)
    .filter((path) => /\.(ts|tsx)$/.test(path))
    .filter((path) => !path.endsWith(".test.ts") && !path.endsWith(".test.tsx"))
    .map((path) => {
      const file = `${vendorDir}/${path}`;
      return { path: file, source: readFileSync(file, "utf8") };
    });

describe("vendor boundary", () => {
  it("names the four product slices a copied file may not import", () => {
    expect([...FORBIDDEN_SLICES]).toEqual(["state", "api", "assistant", "bff"]);
  });

  it("flags an aliased import of product state", () => {
    const source = `import { useStudio } from "@/state/StudioContext";\n`;

    expect(forbiddenImports(source, "src/vendor/components/ui/card.tsx")).toEqual([
      "@/state/StudioContext",
    ]);
  });

  it("flags a relative import that walks out of the vendor tree", () => {
    const source = `import { runTool } from "../api/client";\n`;

    expect(forbiddenImports(source, "src/vendor/boundary.ts")).toEqual(["../api/client"]);
  });

  it("flags a re-export as well as an import", () => {
    const source = `export * from "@/bff/store/indexedDbStore";\n`;

    expect(forbiddenImports(source, "src/vendor/components/ui/card.tsx")).toEqual([
      "@/bff/store/indexedDbStore",
    ]);
  });

  it("flags a dynamic import", () => {
    const source = `const store = await import("@/assistant/convert");\n`;

    expect(forbiddenImports(source, "src/vendor/components/ui/card.tsx")).toEqual([
      "@/assistant/convert",
    ]);
  });

  it("flags every forbidden slice through either form", () => {
    for (const slice of FORBIDDEN_SLICES) {
      expect(forbiddenImports(`import x from "@/${slice}/thing";\n`, "src/vendor/a.ts")).toEqual([
        `@/${slice}/thing`,
      ]);
      expect(forbiddenImports(`import x from "../${slice}/thing";\n`, "src/vendor/a.ts")).toEqual([
        `../${slice}/thing`,
      ]);
    }
  });

  it("allows a vendor-internal import", () => {
    const source = `import { cn } from "./lib/utils";\n`;

    expect(forbiddenImports(source, "src/vendor/components/ui/card.tsx")).toEqual([]);
  });

  it("allows a sibling copied surface that stays inside the tree", () => {
    const source = `import { Plan } from "../assistant/plan";\n`;

    expect(forbiddenImports(source, "src/vendor/components/ui/card.tsx")).toEqual([]);
  });

  it("allows the vendor alias for a copied component", () => {
    const source = `import { Button } from "@/components/ui/button";\n`;

    expect(forbiddenImports(source, "src/vendor/components/assistant/tool.tsx")).toEqual([]);
  });

  it("allows third-party packages, including the assistant-ui runtime", () => {
    const source =
      `import { Slot } from "@radix-ui/react-slot";\n` +
      `import { useAssistantRuntime } from "@assistant-ui/react";\n`;

    expect(forbiddenImports(source, "src/vendor/components/ui/card.tsx")).toEqual([]);
  });

  it("keeps the copied tree free of forbidden imports", () => {
    const sources = vendorSources();

    expect(sources.length).toBeGreaterThan(0);
    for (const { path, source } of sources) {
      expect(forbiddenImports(source, path), path).toEqual([]);
    }
  });

  it("documents both copied surfaces where they must live", () => {
    for (const surface of ["components/ui", "components/assistant"]) {
      const readme = readFileSync(`${vendorDir}/${surface}/README.md`, "utf8");

      expect(readme).toMatch(/props/);
    }
  });
});
