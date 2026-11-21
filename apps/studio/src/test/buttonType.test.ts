import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Every `<button>` states its `type`.
 *
 * A `<button>` with no `type` defaults to `submit`. Today no button sits inside
 * a `<form>` without the author choosing its type, so nothing misbehaves — but
 * the Studio adds form wrappers over time (the promotion form in
 * `EvidenceStream` is the pattern), and the first button that ends up inside
 * one submits a form the person did not mean to submit.
 *
 * This guard reads the source as text — the same technique
 * `theme.test.ts` uses for `theme.css` — so the rule holds without a parser
 * dependency. Tests and `src/vendor` are exempt: a test's bare `<button>` is a
 * fixture, and vendor code is a copy we do not edit.
 */

/**
 * Where `src/` is, resolved from the package the runner was started in.
 * `process.cwd()` is `apps/studio` under the Studio's vitest, but the root
 * vitest project starts from the repository root, so fall back to the package.
 */
function sourceDirectory(): string {
  const fromPackage = join(process.cwd(), "src");
  return existsSync(fromPackage) ? fromPackage : join(process.cwd(), "apps/studio/src");
}

function tsxFiles(directory: string): string[] {
  return readdirSync(directory, { recursive: true, encoding: "utf8" })
    .filter((entry) => entry.endsWith(".tsx"))
    .filter((entry) => !entry.endsWith(".test.tsx"))
    .filter((entry) => !entry.split("/").includes("vendor"))
    .map((entry) => join(directory, entry))
    .sort();
}

/**
 * The opening tag of every `<button>` in `source`, end of tag included.
 *
 * Brace depth is tracked so a `>` inside `style={{ … }}` or a `ref` arrow
 * function does not close the tag early.
 */
function buttonTags(source: string): string[] {
  const tags: string[] = [];
  const pattern = /<button\b/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(source))) {
    let depth = 0;
    let end = -1;
    for (let index = match.index; index < source.length; index += 1) {
      const char = source[index];
      if (char === "{") depth += 1;
      else if (char === "}") depth -= 1;
      else if (char === ">" && depth === 0) {
        end = index;
        break;
      }
    }
    if (end >= 0) tags.push(source.slice(match.index, end + 1));
  }
  return tags;
}

describe("button types", () => {
  it("gives every button an explicit type", () => {
    const offenders: string[] = [];
    for (const file of tsxFiles(sourceDirectory())) {
      const source = readFileSync(file, "utf8");
      const tags = buttonTags(source);
      const pattern = /<button\b/g;
      let match: RegExpExecArray | null;
      let index = 0;
      while ((match = pattern.exec(source))) {
        const tag = tags[index];
        index += 1;
        if (tag && !/\btype=/.test(tag)) {
          offenders.push(`${file}:${source.slice(0, match.index).split("\n").length}`);
        }
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });
});